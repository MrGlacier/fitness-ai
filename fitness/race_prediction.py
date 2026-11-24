"""Race-time estimates from recorded performances, separate from plan adherence.

Running: Riegel power law, optionally fitted to the athlete's race results.
Other disciplines: verified swim sections and conditional cycling power scenarios.
Scenario spans and heuristic goal indices are NOT calibrated probabilities.
See docs/race-prediction.md for sources, assumptions and selection limits.
"""
from datetime import date, timezone
from math import log, sqrt
import re
from statistics import median, quantiles

from fitness.plan_analysis import sport_family, workout_date
from fitness.performance_evidence import classify, positive, swim_sections, fitness_development, goal_attainment, endurance_assessment
from fitness.cycling_prediction import cycling_scenario
from fitness.training_prediction import training_scenario, development_forecast

MODEL_VERSION = "race-time-v3.1"
SOURCES = [
    {"title": "Riegel (1981): Athletic Records and Human Endurance", "url": "https://www.rrtc.net/Articles/ARHE.pdf"},
    {"title": "Vickers & Vertosick (2016): Prüfung bei Freizeitläufern", "url": "https://doi.org/10.1186/s13102-016-0052-y"},
    {"title": "Triathlon: Einfluss der Radbelastung auf den Lauf", "url": "https://pubmed.ncbi.nlm.nih.gov/23347994/"},
    {"title": "Martin et al. (1998): Rad-Leistungsbilanz", "url": "https://doi.org/10.1123/jab.14.3.276"},
    {"title": "Jones & Vanhatalo (2017): Critical Power", "url": "https://doi.org/10.1007/s40279-017-0688-0"},
    {"title": "Wakayoshi et al. (1992): Critical Swim Velocity", "url": "https://doi.org/10.2114/ahs1983.11.301"},
    {"title": "Maunder et al. (2021): Durability", "url": "https://doi.org/10.1007/s40279-021-01459-0"},
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


def _fatigue_scenarios(workouts: list, today: date, bike_duration: float | None = None) -> tuple[tuple, str]:
    """Personal brick/standalone observations where available; no causal claim."""
    current = [w for w in workouts if 0 <= (today - workout_date(w)).days <= 90]

    runs = [w for w in current if w.sport == "Run" and w.distance_km > 0 and w.duration_sec >= 600]
    bricks = [w for w in runs if _is_brick(w, current)]
    # Compare similar preload cohorts; a one-hour brick cannot calibrate a
    # three-hour race bike leg merely because the subsequent runs have equal HR.
    preloads = {}
    for run in bricks:
        rides = [b for b in current if sport_family(b.sport) == "Ride"
                 and positive(b.avg_watts) and positive(b.ftp) and b.rpe is not None
                 and b.avg_hr is not None and b.duration_sec >= 3600
                 and 0 <= _timestamp(run) - _timestamp(b) - _duration(b) <= 2700]
        if rides:
            preloads[run.id] = max(rides, key=_timestamp)
    qualified = []
    if preloads:
        relative_power = median(b.avg_watts / b.ftp for b in preloads.values())
        duration = bike_duration or median(b.duration_sec for b in preloads.values())
        effort = median(b.rpe for b in preloads.values())
        hr = median(b.avg_hr for b in preloads.values())
        qualified = [w for w in bricks if w.id in preloads
                     and abs(preloads[w.id].avg_watts / preloads[w.id].ftp - relative_power) <= .1
                     and .8 <= preloads[w.id].duration_sec / duration <= 1.2
                     and abs(preloads[w.id].rpe - effort) <= 1
                     and abs(preloads[w.id].avg_hr - hr) <= 5]
    standalone = [w for w in runs if w not in bricks]
    used, changes = set(), []
    for w in sorted(qualified, key=lambda w: (workout_date(w), w.id)):
        matches = [p for p in standalone if p.id not in used and w.avg_hr and p.avg_hr
                   and w.rpe is not None and p.rpe is not None and abs(w.rpe - p.rpe) <= 1
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
        return _span(changes), f"Zusätzliche Laufzeit nach dem Rad aus {len(changes)} persönlichen Koppel-/Einzellaufvergleichen bei ähnlichem Puls, RPE, Dauer, Höhenmetern und vergleichbarer Radvorbelastung. Ein Beobachtungsvergleich, kein Beleg für einen ursächlichen Ermüdungseffekt."
    return (0, .075, .15), "Laufen nach dem Rad: Szenarien mit 0–15 % zusätzlicher Laufzeit, Mitte 7,5 %. Drei passende persönliche Koppel-/Einzellaufvergleiche fehlen. Das ist eine Modellannahme, kein wissenschaftlich bestätigter persönlicher Ermüdungsfaktor."


def _leg(sport: str, distance: float, workouts: list, today: date, race: dict, planned=None, context=None) -> dict:
    audit, selected, times = [], [], []
    excluded = {}
    tri = 'tri' in race.get('sport', '').casefold()
    trail = any(t in race.get('sport', '').casefold() for t in ('trail', 'mountain'))
    for w in sorted(workouts, key=lambda w: (workout_date(w), w.id)):
        if sport_family(w.sport) != sport or workout_date(w) > today:
            continue
        row = classify(w, today, (planned or {}).get(w.id))
        reason = None
        duration, measured_distance = _duration(w), w.distance_km
        if not positive(w.distance_km) or not positive(duration) or not positive(w.duration_sec):
            reason = 'Fehlerhafte oder unvollständige Zeit/Distanz'
        elif w.distance_km / duration * 3600 > {'Swim': 10, 'Ride': 70, 'Run': 30}[sport]:
            reason = 'Unplausible Geschwindigkeit'
        elif row['age_days'] > 365:
            reason = 'Historischer Kontext; kein aktueller Leistungsnachweis'
        elif row['indoor'] and sport != 'Swim':
            reason = 'Indoor-Tempo nicht übertragbar; Leistungsdaten bleiben Fitnessindikatoren'
        elif sport == 'Run' and tri and _is_brick(w, workouts):
            row['role'] = 'durability'
            reason = 'Koppellauf: Vorbelastung separat, keine doppelte Ermüdung'
        elif sport == 'Ride' and w.sport != 'Ride':
            reason = 'Radart nicht vergleichbar'
        elif sport in {'Run', 'Ride'} and w.elevation_gain is None:
            reason = 'Streckenvergleich ohne Höhenprofil nicht belastbar'
        elif sport in {'Run', 'Ride'}:
            density = w.elevation_gain / w.distance_km
            target_gain = race.get('elevation_gain_m')
            if trail and (target_gain is None or abs(density - target_gain / distance) > max(5, .25 * target_gain / distance)):
                reason = 'Höhenprofil nicht vergleichbar oder Wettkampf-Höhenmeter fehlen'
            elif not trail and density > 15:
                reason = 'Hügelige Strecke nicht auf Flachstrecke übertragbar'
        if not reason and sport == 'Swim' and not w.is_race:
            sections, rejected = swim_sections(w, distance)
            row['sections'], row['excluded_sections'] = sections, rejected
            if not sections:
                reason = 'Keine ausreichend langen, eindeutig geeigneten Kraulabschnitte; Gesamtschwimmzeit ungeeignet'
            elif row['role'] != 'direct':
                reason = 'Aktive Schwimmserien werden im Trainingsmodell bewertet'
            else:
                # One session is one observation; do not cherry-pick its fastest repeat.
                duration = sum(s['duration_sec'] for s in sections)
                measured_distance = sum(s['distance_km'] for s in sections)
        if not reason and row['role'] != 'direct':
            reason = 'Bewertung über Trainingsmodell, Schwellenwerte oder Ausdauerkontext'
        if not reason and not (.25 if sport == 'Run' and w.is_race else .5) <= measured_distance / distance <= 2:
            reason = 'Zu kurze/lange Leistung für die Zieldauer; keine direkte Extrapolation'
        if reason:
            row.update(used=False, reason=reason)
            excluded[reason] = excluded.get(reason, 0) + 1
        else:
            row.update(used=True, duration_sec=duration, distance_km=measured_distance,
                       time_basis='Aktive Abschnitte' if row['sections'] else 'Gesamtzeit',
                       data_quality='medium', reason='Distanznaher Wettkampf oder bestätigter maximaler Test')
            selected.append(w)
        audit.append(row)
    result = dict(sport=sport, label=NAMES[sport], distance_km=distance, count=len(selected),
                  excluded=excluded, activity_audit=audit, evidence=[], available=False,
                  reason=f'Für {NAMES[sport]} fehlen geeignete Leistungsnachweise. Unterstützende Daten bleiben sichtbar.')
    exponent, method = _running_exponent(selected) if sport == 'Run' else (1., 'Distanznahes Dauertempo aus Wettkampf oder maximalem Test; lineare Übertragung ist heuristisch.')
    evidence = [r for r in audit if r['used']]
    for row in evidence:
        row['projected_seconds'] = row['duration_sec'] * (distance / row['distance_km']) ** exponent
        times.append(row['projected_seconds'])
    notes = []
    preloaded_ids = {row['id'] for row in audit if row['role'] == 'durability'}
    basis = ('race' if selected and all(w.is_race for w in selected) else 'probable_race'
             if any(classify(w, today)['race_recognition'] == 'probable' for w in selected) else 'test')
    scenario = cycling_scenario(distance, workouts, today, race) if sport == 'Ride' else None
    use_power = scenario and (not selected or max(workout_date(w) for w in scenario['selected']) > max(workout_date(w) for w in selected))
    if use_power:
        low, center, high = scenario['times']
        selected = scenario['selected']
        ids = {w.id for w in selected}
        evidence = [r for r in audit if r['id'] in ids]
        for row in audit:
            if row['used'] and row['id'] not in ids:
                row.update(used=False, role='supporting', reason='Historischer Rennvergleich; aktuellere Leistungsdaten tragen das Radszenario')
        for row in evidence:
            row.update(used=True, role='indirect', time_basis='Leistungsdaten',
                       reason='Lange gemessene Radleistung im bedingten physikalischen Szenario')
        excluded = {}
        for row in audit:
            if not row['used']:
                excluded[row['reason']] = excluded.get(row['reason'], 0) + 1
        result.update(power_watts=scenario['power_watts'], calibration=scenario['calibration'],
                      ftp_activity_id=scenario['ftp_activity_id'], excluded=excluded)
        notes.extend(scenario['assumptions'])
        method = 'Stationäre physikalische Leistungsbilanz nach Martin; vereinfachtes Flachstreckenszenario.'
        basis = 'power_scenario'
    elif times:
        low, _, high = _span(times)
        # Continuous recency weighting, independent of workout order and target.
        weighted = sorted((r['projected_seconds'], r['weight']) for r in evidence)
        total = sum(weight for _, weight in weighted)
        cumulative = 0
        center = weighted[-1][0]
        for value, weight in weighted:
            cumulative += weight
            if cumulative >= total / 2:
                center = value
                break
        # Evidence count/age/missing effort affect scenarios, never athletic ability.
        age = min(r['age_days'] for r in evidence)
        disagreement = (max(times) - min(times)) / center
        margin = .04 + .08 / len(evidence) ** .5 + min(.20, age / 900) + min(.20, disagreement / 2)
        if disagreement > .20:
            notes.append("Widersprüchliche Leistungsnachweise: robuste Mitte, zusätzliche Szenariounsicherheit; keine automatische Auswahl des Bestwerts.")
        if any(r['rpe'] is None for r in evidence):
            margin += .02
        low, high = min(low, center * (1 - margin)), max(high, center * (1 + margin))
        alternative = training_scenario(sport, distance, workouts, today, context, preloaded_ids) if sport in {'Run', 'Swim'} and not trail else None
        if alternative and alternative['basis'] in {'threshold_scenario', 'interval_scenario', 'training_scenario'}:
            threshold_center = alternative['times'][1]
            result['alternative_models'] = [dict(model='direct_distance_time', estimate_seconds=round(center),
                                                 activity_ids=[w.id for w in selected]),
                                            dict(model=alternative['basis'], estimate_seconds=round(threshold_center),
                                                 activity_ids=[w.id for w in alternative['selected']])]
            direct_weight = 2 ** (-age / 84)
            center = (center * direct_weight + threshold_center * .5) / (direct_weight + .5)
            low = min(low, alternative['times'][0], center)
            high = max(high, alternative['times'][2], center)
            notes.append('Direkte Leistung und trainingsbasiertes Modell gemeinsam gewichtet; jüngere Nachweise erhalten mehr Gewicht.')
            if abs(threshold_center / times[0] - 1) > .15:
                notes.append('Widersprüchliches Trainingsmodell und direkte Leistung: breitere Spanne statt Auswahl des schnellsten Modells.')
            training_ids = {w.id for w in alternative['selected']}
            for row in audit:
                if row['id'] in training_ids and not row['used']:
                    row.update(used=True, role='indirect', time_basis='Trainingsmodell',
                               reason='Aktuelle Trainingsleistung im Modellvergleich berücksichtigt')
            selected = list({w.id: w for w in [*selected, *alternative['selected']]}.values())
            evidence = [row for row in audit if row['used']]
            basis = 'combined_scenario'
    else:
        if trail:
            return result  # Flat training cannot establish a technical trail time.
        fallback = training_scenario(sport, distance, workouts, today, context, preloaded_ids)
        if not fallback:
            return result
        low, center, high = fallback['times']
        selected = fallback['selected']
        ids = {w.id for w in selected}
        evidence = [r for r in audit if r['id'] in ids]
        for row in evidence:
            row.update(used=True, role='indirect' if fallback['basis'] != 'supporting_scenario' else 'supporting',
                       time_basis='Aktive Serien / Schwelle / bedingtes Trainingstempo',
                       reason='Abgestuftes Trainingsmodell; Unsicherheit separat ausgewiesen')
        notes.extend(fallback['assumptions'])
        basis = fallback['basis']
        method = 'Trainingsbasierte Orientierung aus aktiven Serien, Schwelle oder geeigneten Dauerleistungen.'
    age = (today - max(workout_date(w) for w in selected)).days
    # Evidence strength comes from repeated, recent and consistent observations, not a race flag.
    relative_span = (high - low) / center
    quality = 'medium' if len(selected) >= 3 and age <= 42 and relative_span <= .4 and basis not in {'supporting_scenario', 'historical_scenario'} else 'low'
    excluded = {}
    for row in audit:
        if not row['used']:
            excluded[row['reason']] = excluded.get(row['reason'], 0) + 1
    result['excluded'] = excluded
    notes.append('Modellbasierte Szenariospanne; kein statistisches Konfidenz- oder Prognoseintervall.')
    if len(selected) < 3:
        notes.append('Weniger als drei passende Nachweise: geringe individuelle Aussagekraft.')
    if age > 42:
        notes.append(f'Der jüngste Leistungsnachweis ist {age} Tage alt; erhöhte Unsicherheit.')
    if sport == 'Swim':
        notes.append('Beckenlänge, Wenden, Hilfsmittel, Neopren und Freiwasserbedingungen nicht individuell kalibriert; keine pauschalen Zeitboni.')
    if sport == 'Run' and distance > 21.1:
        notes.append('Marathonübertragung kann zu optimistisch sein; keine individuelle Validierung.')
    if trail:
        notes.append('Technische Wege, Gefälle und Gehanteile bleiben unbekannt.')
    result.update(available=True, count=len(selected), faster_seconds=round(low), estimate_seconds=round(center),
                  slower_seconds=round(high), seconds_per_km=round(center / distance, 1), method=method,
                  exponent=exponent, basis=basis, age_days=age, evidence=evidence, notes=notes,
                  data_quality=quality)
    # Keep the API and saved snapshots compact while preserving selected historical evidence.
    recent_ids = {r['id'] for r in audit[-120:]}
    used_ids = {r['id'] for r in evidence}
    result['activity_audit'] = [r for r in audit if r['id'] in recent_ids | used_ids]
    result['audit_omitted'] = len(audit)-len(result['activity_audit'])
    return result


def predict_race(race: dict, workouts: list, today: date, errors=(), planned=None, context=None, wellness=None) -> dict:
    # Filter before *all* fitting and brick matching, including historical calls.
    workouts = [w for w in workouts if workout_date(w) <= today]
    distances, assumptions = race_distances(race)
    triathlon = "tri" in race.get("sport", "").casefold()
    sports = ["Swim", "Ride", "Run"] if triathlon else [sport_family(race.get("sport", ""))]
    days = (date.fromisoformat(race["date"]) - today).days
    result = dict(model_version=MODEL_VERSION, as_of=today.isoformat(), status="partial", score=None,
                  gauge_title="Zielerreichungsindex", verdict="Zeitvergleich noch offen", distances_km=distances,
                  target_seconds=race.get("target_seconds"), parts=[], assumptions=assumptions,
                  notes=["Geschätzt wird deine Leistung aus den vorhandenen Aufzeichnungen. Verbesserungen bis zum Rennen werden nicht vorweggenommen."],
                  sources=SOURCES, notice="Persönlicher Zielerreichungsindex, keine Prozentchance. Modellbasierte Zeitspanne, keine Garantie.")
    result.update(fitness_development=fitness_development(workouts, today),
                  race_day_forecast=dict(status="unavailable", reason="Für die Fortschreibung fehlt noch eine vollständige aktuelle Zeitschätzung."),
                  goal_index=dict(value=None, status="unavailable", reason="Für den Zielvergleich fehlen noch eine vollständige Zeitschätzung oder eine persönliche Zielzeit."),
                  uncertainty_kind="model_scenario", validation_status="provisional",
                  data_quality="Unvollständige Aussagekraft")
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
        result["parts"].append(_leg(sport, distances[sport], workouts, today, race, planned, context))
    if len(result["parts"]) != len(sports) or not all(p["available"] for p in result["parts"]):
        result["uncertainty_factors"] = [p.get("reason") for p in result["parts"] if not p["available"]]
        result["notes"].append("Vorhandene Teilschätzungen bleiben sichtbar. Eine fehlende Disziplin wird nicht durch eine erfundene Zeit ersetzt.")
        return result

    parts = result["parts"]
    center = sum(p["estimate_seconds"] for p in parts)
    # Independent model uncertainties are not simultaneous all-best/all-worst conditions.
    low = center - sqrt(sum((p['estimate_seconds']-p['faster_seconds'])**2 for p in parts))
    high = center + sqrt(sum((p['slower_seconds']-p['estimate_seconds'])**2 for p in parts))
    if triathlon:
        # Prefer personal brick observations; disclose fallback sensitivity assumptions.
        run = next(p for p in parts if p["sport"] == "Run")
        run["fresh_estimate_seconds"] = run["estimate_seconds"]
        bike = next(p for p in parts if p["sport"] == "Ride")
        fatigue, fatigue_note = _fatigue_scenarios(workouts, today, bike["estimate_seconds"])
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
        run["triathlon_estimate_seconds"] = round(run["estimate_seconds"] * (1 + fatigue[1]))
        result['transition_seconds'] = transition if transition is not None else 450
        run['estimate_seconds'] = run['triathlon_estimate_seconds']
    low, center, high = round(low), round(center), round(high)
    quality = "Mittlere Aussagekraft" if all(p["data_quality"] == "medium" for p in parts) else "Niedrige Aussagekraft"
    if any(p["basis"] != "race" for p in parts):
        result["notes"].append("Bedingte Trainings-/Leistungsszenarien belegen keine maximal mögliche Wettkampfleistung und keine Unerreichbarkeit deiner Wunschzeit.")
    result.update(status="estimated", faster_seconds=low, estimate_seconds=center, slower_seconds=high,
                  data_quality=quality, label=f"{center} Sekunden", phase_note=f"Noch {days} Tage bis zum Rennen. Die Rechnung bewertet den heutigen Stand.")
    for part in parts:
        if part["age_days"] > 42:
            result["notes"].append(f"{part['label']}: Der jüngste passende Nachweis ist {part['age_days']} Tage alt. Dieser Teil der Schätzung ist deshalb besonders unsicher.")
    target = race.get("target_seconds")
    forecast = development_forecast(workouts, today, days, center, low, high, context, parts)
    result['race_day_forecast'] = forecast
    endurance = endurance_assessment(parts, workouts, today)
    result['endurance'] = endurance
    for part in parts:
        coverage = next(c['coverage'] for c in endurance['disciplines'] if c['sport'] == part['sport'])
        part['assessment'] = ('Deine Ausdauer für diese Distanz ist gut gestützt.' if coverage is not None and coverage >= .85
                              else 'Die Ausdauer für die volle Distanz bleibt noch eine Herausforderung.' if coverage is not None
                              else 'Die Zeit ist schätzbar; aktuelle längere Ausdauernachweise fehlen.')
        if part['sport'] == 'Ride' and part['basis'] == 'power_scenario':
            part['assessment'] += ' Die Zeit beruht auf gemessener Leistung und angenommenen Rennbedingungen.'
        elif part['sport'] == 'Swim' and part['basis'] == 'training_scenario':
            part['assessment'] += ' Aktive Schwimmserien tragen die Schätzung; unklare Abschnittsarten bleiben unsicher.'
    result['context_analysis'] = context or dict(status='unavailable', reason='Lokale Kontextanalyse nicht verfügbar.')
    # Recovery contextualizes readiness; a single night never changes time or finish ability.
    recent_health = [r for r in (wellness or []) if 0 <= (today-date.fromisoformat(r['date'])).days <= 28]
    result['recovery_context'] = dict(days=len(recent_health),
        available_metrics=[k for k in ('weight', 'hrv', 'resting_hr', 'sleep_secs', 'sleep_quality', 'sleep_score', 'readiness', 'vo2max', 'ctl', 'atl')
                           if any(r.get(k) is not None for r in recent_health)],
        note='Regeneration ordnet Tagesform ein; einzelne schlechte Nächte oder hohe Belastung sind kein belegter Fitnessverlust.')
    comparisons = []
    for metric in ('hrv', 'resting_hr', 'sleep_secs', 'weight'):
        recent_values = [r[metric] for r in recent_health if positive(r.get(metric))
                         and (today-date.fromisoformat(r['date'])).days <= 7]
        baseline_values = [r[metric] for r in recent_health if positive(r.get(metric))
                           and (today-date.fromisoformat(r['date'])).days > 7]
        if len(recent_values) >= 3 and len(baseline_values) >= 7:
            comparisons.append(dict(metric=metric, recent_median=median(recent_values),
                                    baseline_median=median(baseline_values),
                                    change_fraction=round(median(recent_values)/median(baseline_values)-1, 3)))
    result['recovery_context']['comparisons'] = comparisons
    result["goal_index"] = goal_attainment(parts, target, forecast['estimate_seconds'], workouts, today, days,
        race.get("goal_splits_seconds"), endurance=endurance, conservative=forecast['slower_seconds'],
        cutoff_seconds=race.get('cutoff_seconds'))
    if target:
        score = result["goal_index"]["value"]
        if target < low:
            verdict = "Deine Wunschzeit ist schneller als die bisherigen Schätzungen"
        elif target < center:
            verdict = "Deine Wunschzeit liegt im schnelleren Teil der Schätzung"
        elif target < high:
            verdict = "Deine Wunschzeit passt in die geschätzte Zeitspanne"
        else:
            verdict = "Die geschätzte Zeitspanne liegt innerhalb deiner Wunschzeit"
        verdict = result['goal_index'].get('label', verdict)
        result.update(score=score, verdict=verdict, target_gap_seconds=round(target - center),
                      score_explanation=result["goal_index"]["reason"])
        messages = ['Die vollständige Distanz ist derzeit eine große Herausforderung.',
                    'Ein Finish erscheint möglich; die Zielzeit liegt noch deutlich entfernt.',
                    'Ein Finish ist realistisch; für die Zielzeit fehlen noch Fortschritte.',
                    'Deine Zielzeit liegt in Reichweite und erfordert weitere Fortschritte oder einen sehr guten Tag.',
                    'Deine Zielzeit ist realistisch erreichbar; der Wettkampf bleibt anspruchsvoll.',
                    'Deine Zielzeit erscheint sehr gut erreichbar und lässt Leistungsreserven.',
                    'Deine Zielzeit ist gut abgesichert; eine schnellere Zeit erscheint realistisch.']
        band = next(i for i, bound in enumerate((25, 49, 64, 74, 89, 99, 100)) if score <= bound)
        result['assessment'] = messages[band]
        if endurance['value'] is not None and endurance['value'] >= .85:
            result['assessment'] += ' Deine längeren Einheiten stützen die Ausdauer für die Wettkampfdistanz.'
    else:
        result["verdict"] = "Geschätzte Zeit ohne Zeitvorgabe"
    return result
