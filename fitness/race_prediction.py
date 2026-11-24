"""Race-time estimates from recorded performances, separate from plan adherence.

Running: Riegel power law, optionally fitted to the athlete's race results.
Other disciplines: observed sustained speeds, explicitly labelled scenarios.
The scenario span and goal position are NOT calibrated probabilities.
See docs/race-prediction.md for sources, assumptions and selection limits.
"""
from datetime import date, timezone
from math import isfinite, log
import re
from statistics import median, quantiles

from fitness.plan_analysis import sport_family, workout_date

MODEL_VERSION = "race-time-v1"
SOURCES = [
    {"title": "Riegel (1981): Athletic Records and Human Endurance", "url": "https://www.rrtc.net/Articles/ARHE.pdf"},
    {"title": "Vickers & Vertosick (2016): Prüfung bei Freizeitläufern", "url": "https://doi.org/10.1186/s13102-016-0052-y"},
    {"title": "Modelling human endurance (2023)", "url": "https://doi.org/10.1007/s00421-023-05274-5"},
    {"title": "Triathlon: Einfluss der Radbelastung auf den Lauf", "url": "https://pubmed.ncbi.nlm.nih.gov/23347994/"},
    {"title": "Minetti et al. (2002): Einfluss von Steigungen", "url": "https://pubmed.ncbi.nlm.nih.gov/12183501/"},
]
NAMES = {"Swim": "Schwimmen", "Ride": "Radfahren", "Run": "Laufen"}


def race_distances(race: dict) -> tuple[dict, list[str]]:
    distances = dict(race.get("distances_km", {}))
    notes = []
    # Only an explicit branded distance designation; never infer from a target time.
    if "tri" in race.get("sport", "").casefold() and re.search(r"\b70[.,]3\b", race.get("name", "")):
        defaults = {"Swim": 1.9, "Ride": 90.0, "Run": 21.1}
        if any(s not in distances for s in defaults):
            distances = {**defaults, **distances}
            notes.append("Für die Bezeichnung 70.3 werden 1,9 km Schwimmen, 90 km Rad und 21,1 km Lauf angenommen. Abweichende Strecken kannst du beim Wettkampf eintragen.")
    return distances, notes


def goal_position(target: float, faster: float, slower: float) -> int:
    """Position of the target in the time span, NOT a success probability."""
    if slower <= faster:
        return 100 if target >= slower else 0
    return round(max(0, min(100, 100 * (target - faster) / (slower - faster))))


def _span(values: list[float]) -> tuple[float, float, float]:
    """Keep a lone extreme observation from determining the scenario endpoints."""
    if len(values) >= 4:
        q1, _, q3 = quantiles(values, n=4, method="inclusive")
        spread = q3 - q1
        values = [v for v in values if q1 - 1.5 * spread <= v <= q3 + 1.5 * spread]
    if len(values) < 3:
        return min(values), median(values), max(values)
    q1, _, q3 = quantiles(values, n=4, method="inclusive")
    return q1, median(values), q3


def _running_exponent(workouts: list) -> tuple[float, str]:
    races = [w for w in workouts if w.is_race and w.distance_km >= 3]
    slopes = []
    for i, a in enumerate(races):
        for b in races[i + 1:]:
            if max(a.distance_km, b.distance_km) / min(a.distance_km, b.distance_km) < 1.4:
                continue
            k = log(_duration(a) / _duration(b)) / log(a.distance_km / b.distance_km)
            if 1 <= k <= 1.3:
                slopes.append(k)
    if slopes:
        return median(slopes), "Persönlicher Distanz-Zeit-Verlauf aus unterschiedlich langen Wettkämpfen."
    return 1.07, "Riegel-Potenzmodell mit Standardexponent 1,07; nicht individuell kalibriert."


def _duration(workout) -> float:
    # Race results include stops; swim sessions retain rests rather than claiming interval speed.
    return max(workout.duration_sec, workout.elapsed_sec or 0)


def _timestamp(workout) -> float:
    value = workout.start_time
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).timestamp()


def _is_brick(run, workouts: list) -> bool:
    return any(sport_family(w.sport) == "Ride" and w.duration_sec >= 3600
               and 0 <= _timestamp(run) - _timestamp(w) - _duration(w) <= 2700 for w in workouts)


def _fatigue_scenarios(workouts: list, today: date) -> tuple[tuple, str]:
    """Personal brick/standalone observations where available; no causal claim."""
    current = [w for w in workouts if 0 <= (today - workout_date(w)).days <= 90]

    runs = [w for w in current if w.sport == "Run" and w.distance_km > 0 and w.duration_sec >= 600]
    bricks = [w for w in runs if _is_brick(w, current)]
    standalone = [w for w in runs if w not in bricks]
    used, changes = set(), []
    for w in sorted(bricks, key=lambda w: (workout_date(w), w.id)):
        matches = [p for p in standalone if p.id not in used and w.avg_hr and p.avg_hr
                   and abs(w.avg_hr - p.avg_hr) <= 5 and .8 <= w.duration_sec / p.duration_sec <= 1.2
                   and w.elevation_gain is not None and p.elevation_gain is not None
                   and abs(w.elevation_gain / w.distance_km - p.elevation_gain / p.distance_km) <= 5]
        if matches:
            p = min(matches, key=lambda p: (abs((workout_date(w) - workout_date(p)).days), p.id))
            change = (_duration(w) / w.distance_km) / (_duration(p) / p.distance_km)
            if .8 <= change <= 1.5:
                used.add(p.id)
                changes.append(max(0, change - 1))
    if len(changes) >= 3:
        return _span(changes), f"Zusätzliche Laufzeit nach dem Rad aus {len(changes)} persönlichen Koppel-/Einzellaufvergleichen bei ähnlichem Puls, Dauer und Höhenmetern. Ein Beobachtungsvergleich, kein Beleg für einen ursächlichen Ermüdungseffekt."
    return (0, .075, .15), "Laufen nach dem Rad: Szenarien mit 0–15 % zusätzlicher Laufzeit, Mitte 7,5 %. Drei passende persönliche Koppel-/Einzellaufvergleiche fehlen. Das ist eine Modellannahme, kein wissenschaftlich bestätigter persönlicher Ermüdungsfaktor."


def _leg(sport: str, distance: float, workouts: list, today: date, race: dict) -> dict:
    trail = "trail" in race.get("sport", "").casefold() or "mountain" in race.get("sport", "").casefold()
    candidates, excluded = [], {}

    def exclude(reason):
        excluded[reason] = excluded.get(reason, 0) + 1

    for w in sorted(workouts, key=lambda w: (workout_date(w), w.id)):
        if sport_family(w.sport) != sport:
            continue
        if not 0 <= (today - workout_date(w)).days <= 180:
            exclude("Älter als 180 Tage oder in der Zukunft")
            continue
        if not isfinite(w.distance_km) or w.distance_km <= 0 or _duration(w) < 600:
            exclude("Keine nutzbare Distanz oder weniger als zehn Minuten")
            continue
        speed = w.distance_km / _duration(w) * 3600
        upper_speed = {"Swim": 10, "Ride": 70, "Run": 30}[sport]
        if speed > upper_speed:
            exclude("Unplausibel hohe Durchschnittsgeschwindigkeit")
            continue
        if "virtual" in w.sport.casefold() or w.is_indoor:
            exclude("Virtuelle oder Indoor-Geschwindigkeit ist nicht auf die Strecke übertragbar")
            continue
        if sport == "Run" and "tri" in race.get("sport", "").casefold() and _is_brick(w, workouts):
            exclude("Koppellauf wird für den Rad-Lauf-Vergleich genutzt, nicht doppelt als frischer Lauf")
            continue
        if sport == "Ride" and w.sport != "Ride":
            exclude("Andere Radart: keine Übertragung von Gravel-/Mountainbike-Geschwindigkeit")
            continue
        minimum = .25 if sport == "Run" and w.is_race else .5
        if not minimum <= w.distance_km / distance <= 2:
            exclude("Distanz zu weit von der Wettkampfdisziplin entfernt")
            continue
        if sport in {"Run", "Ride"}:
            if w.elevation_gain is None:
                exclude("Höhenmeter für den Streckenvergleich fehlen")
                continue
            density = w.elevation_gain / w.distance_km
            if trail:
                target_gain = race.get("elevation_gain_m")
                if target_gain is None:
                    exclude("Beim Berglauf fehlen die Wettkampf-Höhenmeter")
                    continue
                target_density = target_gain / distance
                if abs(density - target_density) > max(5, .25 * target_density):
                    exclude("Höhenmeter pro Kilometer passen nicht zur Berglaufstrecke")
                    continue
            elif density > 15:
                exclude("Deutlich hügelige Einheit: keine Übertragung auf eine flache Strecke")
                continue
        if sport == "Ride" and w.elapsed_sec and w.elapsed_sec > 1.2 * w.duration_sec:
            exclude("Zu viele Pausen für einen durchgehenden Radvergleich")
            continue
        candidates.append(w)

    races = [w for w in candidates if w.is_race]
    # Recent race evidence is preferred. Otherwise use the recent usable training cohort.
    selected = races or candidates
    if selected:
        newest = max(workout_date(w) for w in selected)
        selected = [w for w in selected if (newest - workout_date(w)).days <= 56]
    result = dict(sport=sport, label=NAMES[sport], distance_km=distance,
                  count=len(selected), excluded=excluded, evidence=[], available=False)
    if not selected:
        result["reason"] = f"Für {NAMES[sport]} gibt es noch keinen passenden Strecken-/Distanzvergleich. Die ausgeschlossenen Einheiten stehen in den Details."
        return result
    exponent, method = _running_exponent(selected) if sport == "Run" else (1.0, "Hochrechnung mit tatsächlich aufgezeichnetem Dauertempo; kein wissenschaftlich validiertes Wettkampfmodell.")
    projected = [_duration(w) * (distance / w.distance_km) ** exponent for w in selected]
    low, center, high = _span(projected)
    # Model-sensitivity scenarios for running, not an invented confidence interval.
    if sport == "Run":
        sensitivity = [_duration(w) * (distance / w.distance_km) ** k for w in selected for k in (1.06, 1.10, exponent)]
        sensitivity_low, _, sensitivity_high = _span(sensitivity)
        low, high = min(low, sensitivity_low), max(high, sensitivity_high)
    age = (today - max(workout_date(w) for w in selected)).days
    result.update(available=True, faster_seconds=round(low), estimate_seconds=round(center), slower_seconds=round(high),
                  seconds_per_km=round(center / distance, 1), method=method, exponent=exponent,
                  basis="race" if races else "training", age_days=age,
                  evidence=[dict(id=w.id, date=workout_date(w).isoformat(), distance_km=w.distance_km,
                                 duration_sec=round(_duration(w)), rpe=w.rpe, avg_hr=w.avg_hr,
                                 time_basis="Gesamtzeit" if w.elapsed_sec else "Bewegungszeit",
                                 projected_seconds=round(t)) for w, t in zip(selected, projected)])
    notes = []
    if not races:
        notes.append("Trainingsleistungen sind keine maximalen Wettkampfleistungen. Die Rechnung zeigt Szenarien aus deinem Dauertempo, nicht dein ausgeschöpftes Potenzial.")
    if age > 42:
        notes.append(f"Die jüngste passende Einheit ist {age} Tage alt. Deine heutige Form kann abweichen.")
    if len(selected) < 3:
        notes.append("Weniger als drei passende Einheiten: Eine einzelne Leistung prägt die Schätzung stark.")
    if any(not w.elapsed_sec for w in selected):
        notes.append("Bei einigen Nachweisen ist nur die Bewegungszeit verfügbar. Nicht erfasste Pausen können die Hochrechnung zu schnell erscheinen lassen.")
    if sport == "Run" and distance > 21.1 and exponent == 1.07:
        notes.append("Bei Marathon und längeren Strecken kann die Standardformel deutlich zu optimistisch sein. Der Bereich ist kein verlässlicher Fehlerkorridor.")
    if sport == "Swim" and any(w.sport != "OpenWaterSwim" for w in selected):
        notes.append("Beckentraining enthält Wenden und gegebenenfalls Pausen. Freiwasser, Neopren und Orientierung können anders ausfallen.")
    if sport == "Ride":
        notes.append("Radtempo hängt von Wind, Rad, Sitzposition und Strecke ab. FTP allein ergibt keine Straßengeschwindigkeit.")
    if trail:
        notes.append("Ähnliche Höhenmeter pro Kilometer bedeuten noch kein gleiches Gelände. Technische Wege, Gefälle und Gehanteile bleiben unsicher.")
    result["notes"] = notes
    return result


def predict_race(race: dict, workouts: list, today: date, errors=()) -> dict:
    distances, assumptions = race_distances(race)
    triathlon = "tri" in race.get("sport", "").casefold()
    sports = ["Swim", "Ride", "Run"] if triathlon else [sport_family(race.get("sport", ""))]
    days = (date.fromisoformat(race["date"]) - today).days
    result = dict(model_version=MODEL_VERSION, as_of=today.isoformat(), status="partial", score=None,
                  gauge_title="Dein Ziel im Zeitvergleich", verdict="Zeitvergleich noch offen", distances_km=distances,
                  target_seconds=race.get("target_seconds"), parts=[], assumptions=assumptions,
                  notes=["Geschätzt wird deine Leistung aus den vorhandenen Aufzeichnungen. Verbesserungen bis zum Rennen werden nicht vorweggenommen."],
                  sources=SOURCES, notice="Die Uhr zeigt deine geschätzte Zeit und die Lage deiner Wunschzeit auf der Zeitspanne. Sie zeigt keine Prozentchance und garantiert kein Rennergebnis.")
    if days < 0 or race.get("status") != "planned":
        result.update(status="not_applicable", verdict="Kein bevorstehender Wettkampf")
        return result
    if "activities" in errors:
        result["notes"].append("Deine Aktivitäten konnten gerade nicht geladen werden. Deshalb wird keine neue Zeit geschätzt.")
        return result
    for sport in sports:
        if sport not in NAMES:
            result["notes"].append("Für diese Sportart gibt es noch kein Zeitmodell.")
            continue
        if not distances.get(sport):
            result["notes"].append(f"Die Wettkampfdistanz für {NAMES[sport]} fehlt. Trage die Strecke ein; Einzelzielzeiten sind nicht nötig.")
            continue
        result["parts"].append(_leg(sport, distances[sport], workouts, today, race))
    if len(result["parts"]) != len(sports) or not all(p["available"] for p in result["parts"]):
        result["notes"].append("Vorhandene Teilschätzungen bleiben sichtbar. Eine fehlende Disziplin wird nicht durch eine erfundene Zeit ersetzt.")
        return result

    parts = result["parts"]
    low = sum(p["faster_seconds"] for p in parts)
    center = sum(p["estimate_seconds"] for p in parts)
    high = sum(p["slower_seconds"] for p in parts)
    if triathlon:
        # Prefer personal brick observations; disclose fallback sensitivity assumptions.
        run = next(p for p in parts if p["sport"] == "Run")
        fatigue, fatigue_note = _fatigue_scenarios(workouts, today)
        low += run["faster_seconds"] * fatigue[0]
        center += run["estimate_seconds"] * fatigue[1]
        high += run["slower_seconds"] * fatigue[2]
        transition = race.get("transition_seconds")
        if transition is None:
            low += 300
            center += 450
            high += 600
            assumptions.append("Wechsel insgesamt: angenommen 5–10 Minuten. Du kannst deine eigene Gesamtwechselzeit eintragen.")
        else:
            low += transition
            center += transition
            high += transition
        assumptions.append(fatigue_note)
    low, center, high = round(low), round(center), round(high)
    quality = "Wettkampfbasierte Schätzung" if all(p["basis"] == "race" for p in parts) else "Grobe Schätzung aus Training"
    if any(p["basis"] != "race" for p in parts):
        result["notes"].append("Training ist oft langsamer als ein Rennen. Diese Schätzung zeigt deshalb nicht deine Leistungsgrenze. Eine Wunschzeit außerhalb der Spanne ist damit noch nicht als unerreichbar bewiesen.")
    result.update(status="estimated", faster_seconds=low, estimate_seconds=center, slower_seconds=high,
                  data_quality=quality, label=f"{center} Sekunden", phase_note=f"Noch {days} Tage bis zum Rennen. Die Rechnung bewertet den heutigen Stand.")
    for part in parts:
        if part["age_days"] > 42:
            result["notes"].append(f"{part['label']}: Der jüngste passende Nachweis ist {part['age_days']} Tage alt. Dieser Teil der Schätzung ist deshalb besonders unsicher.")
    target = race.get("target_seconds")
    if target:
        score = goal_position(target, low, high)
        if target < low:
            verdict = "Deine Wunschzeit ist schneller als die bisherigen Schätzungen"
        elif target < center:
            verdict = "Deine Wunschzeit liegt im schnelleren Teil der Schätzung"
        elif target < high:
            verdict = "Deine Wunschzeit passt in die geschätzte Zeitspanne"
        else:
            verdict = "Die geschätzte Zeitspanne liegt innerhalb deiner Wunschzeit"
        result.update(score=score, verdict=verdict, target_gap_seconds=round(target - center),
                      score_explanation="0: Wunschzeit am schnellen Rand oder schneller. 100: Wunschzeit am langsamen Rand oder langsamer. Dazwischen liegt die Position auf der Zeitspanne. Keine Aussage über Sicherheit oder Anstrengung.")
    else:
        result["verdict"] = "Geschätzte Zeit ohne Zeitvorgabe"
    return result
