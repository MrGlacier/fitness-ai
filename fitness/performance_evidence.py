"""Deterministic evidence classification; labels are hints, never measured intensity."""
from math import isfinite
import re
from datetime import date

from fitness.plan_analysis import sport_family, workout_date


def positive(value: float | None) -> bool:
    return value is not None and isfinite(value) and value > 0


def classify(workout, today, planned: dict | None = None) -> dict:
    """Keep intention, measured effort, and model role separate."""
    text = ' '.join(filter(None, [workout.name, workout.workout_summary, workout.comment])).casefold()
    name = workout.name.casefold()
    probable_race = bool(re.search(r'\b(wettkampf|race|halbmarathon|half marathon|marathon|triathlon|ironman|volkslauf|stadtlauf)\b', name)) and not bool(re.search(r'\b(training|vorbereitung|pace|tempo|plan|woche|nach)\b|race pace|marathonpace', name))
    test = bool(re.search(r'\b(time trial|leistungstest|all.out|maximaltest)\b', text))
    interval = bool(re.search(r'\b(interval|intervalle|hit|vo2)\b', text))
    easy = workout.rpe is not None and workout.rpe <= 4
    maximal = workout.is_race or probable_race or (test and workout.rpe is not None and workout.rpe >= 9)
    kind = 'race' if workout.is_race else 'test' if maximal else 'interval' if interval else 'LIT' if easy else 'unknown'
    role = 'direct' if maximal and not interval else 'endurance' if workout.duration_sec >= 3600 else 'supporting'
    age = (today - workout_date(workout)).days
    return dict(id=workout.id, name=workout.name, date=workout_date(workout).isoformat(),
                training_type=kind, role=role, race_recognition='confirmed' if workout.is_race else 'probable' if probable_race else None,
                planned_intensity=(planned or {}).get('intensity_percent'),
                planned_name=(planned or {}).get('name'),
                actual_intensity=workout.intensity, rpe=workout.rpe, avg_hr=workout.avg_hr,
                avg_watts=workout.avg_watts, ftp=workout.ftp, ftp_source='activity setting; measurement method unknown',
                threshold_speed_mps=workout.threshold_speed_mps, lthr=workout.lthr,
                normalized_power=workout.weighted_avg_watts, variability_index=workout.variability_index,
                decoupling=workout.decoupling, indoor=bool(workout.is_indoor or 'virtual' in workout.sport.casefold()),
                duration_sec=workout.duration_sec, distance_km=workout.distance_km,
                age_days=age, weight=round(2 ** (-max(0, age) / 42), 4),
                data_quality='medium' if maximal else 'low', sections=[],
                reason='Direkter Leistungsnachweis' if role == 'direct' else 'Unterstützender Indikator; kein maximaler Leistungsnachweis')


def swim_sections(workout, distance: float) -> tuple[list[dict], list[dict]]:
    """Only explicit unassisted freestyle sections; never infer stroke from speed."""
    accepted, rejected = [], []
    for split in workout.splits:
        text = (split.label or '').casefold()
        reason = None
        if re.search(r'pause|rest|recover|technik|drill|beine|kick|pull|paddle|flosse|fin\b|band|buoy|einschw|ausschw|warm|cool', text):
            reason = 'Pause, Technik, Hilfsmittel oder Ein-/Ausschwimmen'
        elif not re.search(r'\b(kraul|freestyle|front crawl)\b', text):
            reason = 'Schwimmstil und Hilfsmittelfreiheit nicht belegt'
        elif not split.active_time_available or not positive(split.distance_km) or not positive(split.duration_sec):
            reason = 'Aktive Zeit oder Distanz fehlt'
        elif split.distance_km < distance / 2:
            reason = 'Kurzer Abschnitt: nur ergänzender Leistungsindikator'
        row = dict(index=split.index, label=split.label, distance_km=split.distance_km,
                   duration_sec=split.duration_sec, reason=reason)
        (rejected if reason else accepted).append(row)
    return accepted, rejected


def fitness_development(workouts: list, today) -> dict:
    """Dated settings and contextual measurements, never guaranteed future gains."""
    points = []
    for w in sorted(workouts, key=lambda w: (workout_date(w), w.id)):
        if workout_date(w) > today:
            continue
        sport = sport_family(w.sport)
        if sport == 'Ride' and positive(w.ftp):
            points.append(dict(id=w.id, date=workout_date(w).isoformat(), sport=sport,
                               metric='configured_ftp_watts', value=w.ftp))
        elif sport == 'Run' and positive(w.threshold_speed_mps):
            points.append(dict(id=w.id, date=workout_date(w).isoformat(), sport=sport,
                               metric='configured_threshold_speed_mps', value=w.threshold_speed_mps))
        if w.is_race and positive(w.distance_km) and positive(w.duration_sec):
            points.append(dict(id=w.id, date=workout_date(w).isoformat(), sport=sport,
                               metric='race_speed_mps', value=round(w.distance_km * 1000 / max(w.duration_sec, w.elapsed_sec or 0), 3),
                               distance_km=w.distance_km))
        if w.rpe is not None and w.rpe <= 4 and positive(w.avg_hr) and positive(w.duration_sec):
            value = None
            if sport == 'Ride' and positive(w.avg_watts):
                value = w.avg_watts / w.avg_hr
            elif sport == 'Run' and positive(w.distance_km):
                value = w.distance_km * 1000 / (w.duration_sec / 60 * w.avg_hr)
            if value is not None:
                points.append(dict(id=w.id, date=workout_date(w).isoformat(), sport=sport,
                                   metric='watts_per_bpm' if sport == 'Ride' else 'metres_per_heartbeat',
                                   value=round(value, 3), rpe=w.rpe, avg_hr=w.avg_hr,
                                   indoor=bool(w.is_indoor or 'virtual' in w.sport.casefold()),
                                   duration_sec=w.duration_sec, elevation_gain=w.elevation_gain))
    return dict(status='indicators' if points else 'unavailable', points=points,
                note='Datierte Einstellungen, Rennleistungen und submaximale Effizienzindikatoren; nur bei gleicher Distanz, Intensität und Bedingungen vergleichbar. Ermüdung und Wetter nicht kontrolliert; keine garantierte Fitnessentwicklung oder Fortschreibung.')


INDEX_BANDS = (
    (25, "Finish gefährdet", "#fa7182"),
    (49, "Finish möglich", "#ffa45c"),
    (64, "Zielzeit ambitioniert", "#e5ca58"),
    (74, "Zielzeit in Reichweite", "#bedb62"),
    (89, "Zielzeit realistisch erreichbar", "#68d98b"),
    (99, "Zielzeit sehr gut erreichbar", "#68d98b"),
    (100, "Leistungsreserven vorhanden", "#68d98b"),
)


def endurance_assessment(parts: list[dict], workouts: list, today) -> dict:
    """Distance/duration coverage is a disclosed heuristic, not a finish probability."""
    from statistics import median
    components = []
    for part in parts:
        sport = part['sport']
        rows = [w for w in workouts if sport_family(w.sport) == sport
                and 0 <= (today - workout_date(w)).days <= 120
                and positive(w.duration_sec) and positive(w.distance_km)]
        coverage = []
        for w in rows:
            if sport == 'Ride':
                # Indoor kilometres never establish outdoor endurance.
                ratio = w.duration_sec / (part['estimate_seconds'] * .65)
            else:
                ratio = w.distance_km / (part['distance_km'] * (.8 if sport == 'Swim' else .7))
            if positive(ratio):
                coverage.append(min(1.2, ratio))
        if coverage:
            value = min(1., median(sorted(coverage, reverse=True)[:3]))
            state = 'belegt'
        else:
            # Historical completion is supporting evidence, with explicit recency limits.
            historical = [w for w in workouts if sport_family(w.sport) == sport
                          and classify(w, today)['race_recognition']
                          and w.distance_km >= part['distance_km'] * .8
                          and 0 <= (today - workout_date(w)).days <= 730]
            value = .7 if historical else None
            state = 'historischer Vergleich' if historical else 'nicht ausreichend beobachtet'
        components.append(dict(sport=sport, coverage=value, status=state, count=len(coverage)))
    known = [c['coverage'] for c in components if c['coverage'] is not None]
    weakest = min(components, key=lambda c: c['coverage'] if c['coverage'] is not None else 1.) if known else None
    return dict(value=min(known) if known else None, disciplines=components,
                limiting_sport=weakest['sport'] if weakest else None,
                note='Ausdauer aus den drei längsten Einheiten in 120 Tagen; fehlende Beobachtungen sind kein Leistungsdefizit.')


def goal_attainment(parts: list[dict], target: float | None, estimate: float,
                    workouts: list, today, days: int, goal_splits: dict | None = None,
                    endurance: dict | None = None, conservative: float | None = None,
                    cutoff_seconds: float | None = None) -> dict:
    """Product scale: finish first, then goal demands and sustainable reserves."""
    if not positive(target) or not parts:
        return dict(value=None, status='unavailable', reason='Eine persönliche Zielzeit fehlt.')
    endurance = endurance or endurance_assessment(parts, workouts, today)
    ability = endurance['value']
    reserve = target / estimate - 1
    # Piecewise sporting anchors: matching centre is 75, 8% reserve is 90,
    # 15% reserve is 100, subject to demonstrated endurance and uncertainty.
    anchors = [(-1., 26), (-.30, 35), (-.15, 50), (-.06, 65), (0., 75), (.08, 90), (.15, 100)]
    value = 100.
    for (a, x), (b, y) in zip(anchors, anchors[1:]):
        if reserve <= b:
            value = x + (y-x) * max(0., min(1., (reserve-a)/(b-a)))
            break
    if ability is not None:
        if ability < .35:
            value = min(value, 25 * ability / .35)
        elif ability < .65:
            value = min(value, 26 + 23 * (ability - .35) / .30)
        elif ability < .85:
            value = min(value, 50 + 24 * (ability - .65) / .20)
    if positive(cutoff_seconds) and estimate > cutoff_seconds:
        value = min(value, 25 * cutoff_seconds / estimate)
    # Unknown endurance never means a dangerous finish, but cannot support reserves.
    if ability is None or any(c['coverage'] is None for c in endurance['disciplines']):
        value = min(value, 74)
    if value >= 90:
        if ability is not None and ability < .95:
            value = min(value, 89)
        if conservative and target < conservative:
            value = min(value, 89)
        if any(p.get('basis') in {'supporting_scenario', 'historical_scenario'} for p in parts):
            value = min(value, 89)
    value = round(max(0, min(100, value)))
    _, label, color = next(b for b in INDEX_BANDS if value <= b[0])
    return dict(value=value, status='heuristic', label=label, color=color,
                reason='Persönlicher Zielerreichungsindex für den Wettkampftag; keine Erfolgswahrscheinlichkeit.',
                components=dict(finish=endurance, reserve_fraction=round(reserve, 4),
                                forecast_seconds=estimate, conservative_seconds=conservative,
                                days_remaining=days),
                scale=[dict(upper=b[0], label=b[1], color=b[2]) for b in INDEX_BANDS])
