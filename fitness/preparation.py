"""Versioned evidence index, not a probability or a validated physiological score."""
from datetime import date, timedelta
from statistics import median

from fitness.plan_analysis import sport_family, workout_date

MODEL_VERSION = "preparation-v1.2"
NOTICE = "Vorbereitungsindex, keine Zielerreichungswahrscheinlichkeit. Nicht wissenschaftlich validiert."


def ratio(actual: float, reference: float) -> float:
    return min(100.0, max(0.0, 100 * actual / reference))


def component(label: str, checks: list[dict], missing: list[str]) -> dict:
    return dict(label=label, score=round(min(c["score"] for c in checks)) if checks and not missing else None,
                checks=checks, missing=missing,
                reason="Schwächster belegter Vergleich begrenzt die Teilbewertung; offene Kriterien werden nicht als 0 gewertet.")


def check(label: str, actual: float, reference: float, unit: str) -> dict:
    return dict(label=label, actual=round(actual, 3), reference=round(reference, 3), unit=unit,
                score=ratio(actual, reference))


def plan_fulfillment(rows: list[dict], workouts: list, today: date) -> dict:
    # Leave the three-day matching window open; do not mark recent moves as failures.
    eligible = [r for r in rows if today - timedelta(days=31) <= date.fromisoformat(r["event"]["date"]) < today - timedelta(days=3)]
    lookup = {w.id: w for w in workouts}
    checks, missing = [], []
    matched = [r for r in eligible if r["activity_id"] in lookup]
    if len(matched) < 3:
        missing.append("Mindestens drei zugeordnete Einheiten im abgeschlossenen Vergleichsfenster erforderlich.")
    if len(matched) != len(eligible):
        missing.append("Nicht zugeordnete Soll-Einheiten bleiben ungeklärt; sie zählen nicht automatisch als ausgefallen.")
    for field, actual_field, label in [("duration_sec", "duration_sec", "Dauer"),
                                        ("tss", "tss", "Belastung"),
                                        ("intensity_percent", "intensity", "Intensität")]:
        comparisons = []
        for row in matched:
            expected = row["event"].get(field)
            actual = getattr(lookup[row["activity_id"]], actual_field, None)
            if expected is None or actual is None or expected <= 0 or actual < 0:
                continue
            # Excess load/intensity is a deviation, not bonus credit.
            comparisons.append(100 * min(expected, actual) / max(expected, actual))
        if len(comparisons) < 3:
            missing.append(f"{label}: mindestens drei vollständige Vergleiche erforderlich.")
        else:
            checks.append(dict(label=label, score=median(comparisons), pairs=len(comparisons)))
    result = component("Trainingsplanerfüllung", checks, missing)
    result.update(matched_sessions=len(matched), eligible_sessions=len(eligible),
                  moved_sessions=sum(r["status"] == "moved" for r in matched))
    return result


def performance_trend(sports: list[str], workouts: list, today: date) -> dict:
    checks, missing = [], []
    for sport in sports:
        recent = [w for w in workouts if sport_family(w.sport) == sport and 0 <= (today-workout_date(w)).days < 21]
        prior = [w for w in workouts if sport_family(w.sport) == sport and 21 <= (today-workout_date(w)).days < 42]
        comparisons = []
        used = set()
        for w in sorted(recent, key=lambda w: (workout_date(w), w.id)):
            # Pair nearest comparable duration/HR; every observation used at most once.
            candidates = [p for p in prior if p.id not in used and p.duration_sec > 0
                          and .8 <= w.duration_sec / p.duration_sec <= 1.2
                          and ((w.avg_hr and p.avg_hr and abs(w.avg_hr-p.avg_hr) <= 5)
                               or (w.is_race and p.is_race and p.distance_km > 0
                                   and .9 <= w.distance_km/p.distance_km <= 1.1))]
            if not candidates or w.duration_sec <= 0:
                continue
            p = min(candidates, key=lambda p: (abs(p.duration_sec-w.duration_sec), p.id))
            if sport == "Ride":
                current, previous = w.weighted_avg_watts, p.weighted_avg_watts
                metric = "Leistung bei vergleichbarem Puls/Dauer"
            else:
                current = w.distance_km / w.duration_sec
                previous = p.distance_km / p.duration_sec
                metric = "Geschwindigkeit bei vergleichbarem Puls/Dauer oder Wettkampf"
            if current and previous and current > 0 and previous > 0:
                comparisons.append(current / previous)
                used.add(p.id)
        if len(comparisons) < 3:
            missing.append(f"{sport}: drei unabhängige Vergleichspaare aus zwei 21-Tage-Fenstern fehlen.")
        else:
            item = check(f"{sport}: {metric}", median(comparisons), 1, "Verhältnis aktuell/früher")
            item.update(pairs=len(comparisons), change_percent=round((median(comparisons)-1)*100, 1))
            checks.append(item)
    result = component("Nachgewiesene Leistungsentwicklung", checks, missing)
    result["limitation"] = "Persönlicher Beobachtungsvergleich, kein kontrollierter Leistungstest. Strecke, Wetter, Technik und Messgeräte können abweichen; keine historische FTP-Reihe verfügbar."
    return result


def endurance(sports: list[str], workouts: list, plan, active: dict | None, days: int, today: date) -> dict:
    checks, missing = [], []
    if not plan or not active:
        return component("Wettkampfspezifische Ausdauer", [], ["Eindeutiger Plan und aktuelle Planwoche fehlen."])
    # Early phases reference only their current demands. Taper retains previous peak evidence.
    taper = any("taper" in p.casefold() or "peak" in p.casefold() for p in active["phases"])
    weeks_back = 7 if taper or days <= 21 else 2
    sessions = [s for s in plan.sessions if max(1, active["week"]-weeks_back) <= s.week <= active["week"]]
    for sport in sports:
        swim_references = [s for s in sessions if sport_family(s.sport) == sport] if sport == "Swim" else []
        # Distanzvorgaben benötigen keine erfundene Schwimmdauer. Zeitpläne bleiben unterstützt.
        if swim_references and any(s.distance_km and s.duration_sec is None for s in swim_references):
            prescribed = [s for s in swim_references if s.distance_km and s.distance_km > 0 and not s.uncertainty]
            actual = [w for w in workouts if sport_family(w.sport) == sport and 0 <= (today-workout_date(w)).days < 28]
            if len(prescribed) != len(swim_references):
                missing.append("Swim: unvollständige oder unsichere Distanzreferenzen im Plan.")
            known = [w for w in actual if w.distance_km > 0]
            if len(prescribed) < 3 or len(known) < 3:
                missing.append("Swim: mindestens drei Plan- und Ist-Distanzen für den Ausdauervergleich fehlen.")
                continue
            if len(known) != len(actual):
                missing.append("Swim: bei absolvierten Einheiten fehlt die Distanz; der Wochenumfang bleibt unvollständig.")
            checks.append(check("Swim: wiederholte lange Distanzen",
                                median(sorted((w.distance_km for w in known), reverse=True)[:3]),
                                median(sorted((s.distance_km for s in prescribed), reverse=True)[:3]), "km"))
            monday = today-timedelta(days=today.weekday())
            totals = [sum(w.distance_km for w in known if monday-timedelta(weeks=i) <= workout_date(w) < monday-timedelta(weeks=i-1))
                      for i in range(1, 4)]
            reference_totals = [sum(s.distance_km for s in prescribed if s.week == week)
                                for week in sorted({s.week for s in prescribed})]
            checks.append(check("Swim: typischer Wochenumfang", median(totals), median(reference_totals), "km/Woche"))
            continue
        if any(sport_family(s.sport) == sport and (s.duration_sec is None or s.uncertainty) for s in sessions):
            missing.append(f"{sport}: unvollständige oder unsichere Ausdauerreferenzen im Plan.")
        prescribed = [s for s in sessions if sport_family(s.sport) == sport and s.duration_sec and not s.uncertainty]
        actual = [w for w in workouts if sport_family(w.sport) == sport and 0 <= (today-workout_date(w)).days < 28]
        if len(prescribed) < 3 or len(actual) < 3:
            missing.append(f"{sport}: mindestens drei Plan- und Ist-Einheiten für Ausdauervergleich fehlen.")
            continue
        target = median(sorted((s.duration_sec for s in prescribed), reverse=True)[:3])
        observed = median(sorted((w.duration_sec for w in actual), reverse=True)[:3])
        checks.append(check(f"{sport}: wiederholte lange Einheiten", observed, target, "Sekunden"))
        distances = [s.distance_km for s in prescribed if s.distance_km and s.distance_km > 0]
        if len(distances) >= 3:
            observed_distances = [w.distance_km for w in actual if w.distance_km > 0]
            if len(observed_distances) < 3:
                missing.append(f"{sport}: drei bekannte Ist-Distanzen für den Distanzvergleich fehlen.")
            else:
                checks.append(check(f"{sport}: lange Distanzen", median(sorted(observed_distances, reverse=True)[:3]),
                                    median(sorted(distances, reverse=True)[:3]), "km"))
        # Complete weeks only; no penalty for a week still in progress.
        monday = today-timedelta(days=today.weekday())
        totals = [sum(w.duration_sec for w in actual if monday-timedelta(weeks=i) <= workout_date(w) < monday-timedelta(weeks=i-1))
                  for i in range(1, 4)]
        by_week = [sum(s.duration_sec or 0 for s in prescribed if s.week == week) for week in sorted({s.week for s in prescribed})]
        checks.append(check(f"{sport}: typischer Wochenumfang", median(totals), median(by_week), "Sekunden/Woche"))
    result = component("Wettkampfspezifische Ausdauer", checks, missing)
    result.update(reference_weeks=sorted({s.week for s in sessions}),
                  phase=active["phases"], days_to_race=days,
                  limitation="Planrelative Anforderungen, keine Bestätigung der Eignung des externen Plans für die Renndistanz.")
    return result


def load_tolerance(workouts: list, wellness: list[dict], today: date) -> dict:
    checks, missing = [], []
    current = [w for w in workouts if 0 <= (today-workout_date(w)).days < 21 and w.rpe and w.tss and w.tss > 0]
    prior = [w for w in workouts if 21 <= (today-workout_date(w)).days < 42 and w.rpe and w.tss and w.tss > 0]
    pairs, used = [], set()
    for w in sorted(current, key=lambda w: (workout_date(w), w.id)):
        candidates = [p for p in prior if p.id not in used and sport_family(p.sport) == sport_family(w.sport) and .8 <= w.tss/p.tss <= 1.2]
        if candidates:
            p = min(candidates, key=lambda p: (abs(p.tss-w.tss), p.id))
            pairs.append(p.rpe / w.rpe)
            used.add(p.id)
    if len(pairs) >= 3:
        checks.append(check("Subjektiver Aufwand bei vergleichbarer Belastung", median(pairs), 1, "RPE früher/aktuell"))
    else:
        missing.append("Drei unabhängige RPE-Vergleiche bei ähnlicher sportartspezifischer Last fehlen.")
    for field, inverse, label in [("hrv", False, "HRV"), ("resting_hr", True, "Ruhepuls"), ("sleep_secs", False, "Schlafdauer")]:
        recent = [r[field] for r in wellness if r.get(field) and 0 <= (today-date.fromisoformat(r["date"])).days < 14]
        baseline = [r[field] for r in wellness if r.get(field) and 14 <= (today-date.fromisoformat(r["date"])).days < 42]
        if len(recent) >= 7 and len(baseline) >= 7:
            a, b = median(recent), median(baseline)
            checks.append(check(label, b if inverse else a, a if inverse else b, "persönlicher Medianvergleich"))
    if len(checks) < 2:
        missing.append("Mindestens ein Erholungsindikator mit je sieben Messungen in zwei Zeitfenstern fehlt.")
    result = component("Belastungsverträglichkeit (Beobachtungsindikatoren)", checks, missing)
    result["limitation"] = "RPE und Erholungsdaten sind unspezifisch. Keine medizinische Aussage; CTL/TSS/TSB allein werden nicht bewertet."
    return result


def goal_alignment(race: dict, sports: list[str], workouts: list, today: date) -> dict:
    if not race.get("target_seconds"):
        return dict(label="Bezug zum Wettkampfziel", score=None, status="not_applicable", checks=[], missing=[],
                    reason="Kein Zeitziel hinterlegt. Bewertet wird die Vorbereitung auf den Wettkampf, ohne Zeitvorgabe.")
    splits = race.get("goal_splits_seconds", {})
    triathlon = "tri" in race.get("sport", "").casefold()
    if not triathlon and len(sports) == 1:
        splits = {sports[0]: race["target_seconds"]}
    checks, missing = [], []
    if triathlon and not splits:
        return dict(label="Bezug zum Wettkampfziel", score=None, status="target_recorded", checks=[], missing=[],
                    target_seconds=race["target_seconds"],
                    reason="Gesamtziel hinterlegt. Einzelzeiten und Wechselziele sind freiwillig und werden nicht verlangt.",
                    limitation="Für eine belastbare Bewertung der Gesamtzielzeit fehlen derzeit geeignete Gesamtrennnachweise. Das blockiert den allgemeinen Vorbereitungsindex nicht.")
    if triathlon and (set(splits) != set(sports) or race.get("transition_seconds") is None
                     or sum(splits.values()) + race["transition_seconds"] > race["target_seconds"]):
        missing.append("Zum Gesamtziel passende Disziplin-Zielzeiten und explizite Wechselzeit fehlen.")
    for sport in sports:
        distance = race.get("distances_km", {}).get(sport)
        target = splits.get(sport)
        if not distance or not target:
            missing.append(f"{sport}: Renndistanz oder Disziplin-Ziel fehlt.")
            continue
        evidence = [w for w in workouts if sport_family(w.sport) == sport and w.is_race and w.duration_sec > 0
                    and .9*distance <= w.distance_km <= 1.1*distance and 0 <= (today-workout_date(w)).days < 90]
        if len(evidence) < 2:
            missing.append(f"{sport}: zwei aktuelle Rennen mit vergleichbarer Distanz fehlen.")
            continue
        checks.append(check(f"{sport}: belegte Geschwindigkeit / Zielanforderung",
                            median(w.distance_km/w.duration_sec*3600 for w in evidence), distance/target*3600, "km/h"))
    result = component("Bezug zum Wettkampfziel", checks, missing)
    result["limitation"] = "Kurs, Wetter und Vorermüdung können abweichen; Disziplin-Nachweise garantieren keine Triathlon-Gesamtleistung. Keine Zeitprognose."
    return result


def preparation_index(race: dict, workouts: list, comparison: dict, wellness: list[dict],
                      plan, active: dict | None, today: date, errors: list[str] = ()) -> dict:
    days = (date.fromisoformat(race["date"])-today).days
    sports = ["Swim", "Ride", "Run"] if "tri" in race.get("sport", "").casefold() else [sport_family(race.get("sport", ""))]
    components = dict(plan=plan_fulfillment(comparison["sessions"], workouts, today),
                      performance=performance_trend(sports, workouts, today),
                      endurance=endurance(sports, workouts, plan, active, days, today),
                      tolerance=load_tolerance(workouts, wellness, today),
                      goal=goal_alignment(race, sports, workouts, today))
    # Unbekannter Zielbezug ist weder schlechte Vorbereitung noch eine Pflicht zur Eingabe von Einzelzielen.
    required = [c for key, c in components.items() if key != "goal" or c["score"] is not None]
    missing = [f"{c['label']}: {reason}" for c in required for reason in c["missing"]]
    missing.extend(f"Datenquelle nicht verfügbar: {error}" for error in errors)
    if days < 0 or race.get("status") != "planned":
        missing.append("Keine aktuelle Vorbereitung für einen geplanten zukünftigen Wettkampf.")
    score = min(c["score"] for c in required) if not missing and all(c["score"] is not None for c in required) else None
    return dict(model_version=MODEL_VERSION, score=score, as_of=today.isoformat(),
                target_seconds=race.get("target_seconds"), goal_splits_seconds=race.get("goal_splits_seconds", {}),
                status="available" if score is not None else "insufficient_data",
                label=f"{score} %" if score is not None else "Datenlage unzureichend",
                notice=NOTICE, components=components, missing=missing,
                data_quality=("Vorbereitung belegt; Zielvergleich offen" if race.get("target_seconds") and components["goal"]["score"] is None else "belegt, methodisch begrenzt") if score is not None else "unvollständig",
                positive_factors=[c["label"] for c in required if c["score"] is not None and c["score"] == 100],
                negative_factors=[dict(label=c["label"], score=c["score"]) for c in sorted(required, key=lambda c: c["score"] if c["score"] is not None else 101) if c["score"] is not None and c["score"] < 100],
                phase=active["phases"] if active else [], days_to_race=days,
                method="Engpassmodell: Minimum der vier Kernbereiche und eines belegbaren optionalen Zielvergleichs, keine Prozentgewichtungen. Verhältniswerte auf 0–100 begrenzt, Anzeige ganzzahlig. 100 heißt Kriterien erfüllt, nicht sieg- oder zielzeitsicher.")
