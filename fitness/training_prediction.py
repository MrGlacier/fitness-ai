"""Disclosed fallback heuristics and cautious, target-independent development."""
from statistics import median
import re

from fitness.performance_evidence import positive, classify
from fitness.plan_analysis import sport_family, workout_date


def running_intervals(workouts: list, distance: float) -> dict | None:
    """Long work repetitions support an estimate; short VO2 repeats do not set race pace."""
    selected, estimates = [], []
    for workout in workouts:
        if workout.is_indoor or 'virtual' in workout.sport.casefold():
            continue
        if workout.elevation_gain is not None and workout.elevation_gain / workout.distance_km > 15:
            continue
        sections = [s for s in workout.splits
                    if (s.split_type or '').casefold() == 'work'
                    and s.active_time_available and positive(s.distance_km)
                    and positive(s.duration_sec) and s.duration_sec >= 600
                    and .5 <= s.distance_km * 1000 / s.duration_sec <= 8
                    and not re.search(r'warm|cool|einlauf|auslauf|recover|pause', s.label or '', re.I)]
        if sum(s.duration_sec for s in sections) < 1800:
            continue
        effort_known = workout.rpe is not None and 5 <= workout.rpe <= 8
        hr_supported = positive(workout.lthr) and all(positive(s.avg_hr) and .85 <= s.avg_hr / workout.lthr <= 1.03 for s in sections)
        if not effort_known and not hr_supported:
            continue
        active = sum(s.duration_sec for s in sections)
        measured_distance = sum(s.distance_km for s in sections)
        # Treat repeated work as a supported scenario, with an explicit rest/durability allowance.
        estimates.append(active * (distance / measured_distance) ** 1.07 * 1.04)
        selected.append(workout)
    if not estimates:
        return None
    center = median(estimates)
    return dict(times=(center*.88, center, center*1.16), selected=selected,
                basis='interval_scenario', assumptions=[
                    'Längere Laufintervalle: mindestens 30 aktive Minuten in Abschnitten ab 10 Minuten, '
                    'mit passendem RPE oder Schwellenpuls. Riegel-Übertragung plus 4 % für Pausen und Ausdauer ist eine Heuristik.'])


def training_scenario(sport: str, distance: float, workouts: list, today, context=None,
                      preloaded_ids: set[str] | None = None) -> dict | None:
    rows = [w for w in workouts if sport_family(w.sport) == sport
            and workout_date(w) <= today and positive(w.distance_km) and positive(w.duration_sec)
            and w.distance_km / w.duration_sec * 3600 <= {'Swim': 10, 'Ride': 70, 'Run': 30}[sport]]
    current = [w for w in rows if (today - workout_date(w)).days <= 120]
    values, selected, assumptions = [], [], []
    basis = 'training_scenario'
    if sport == 'Run':
        settings = sorted([w for w in current if positive(w.threshold_speed_mps) and .5 <= w.threshold_speed_mps <= 8],
                          key=lambda w: (workout_date(w), w.id))
        if settings:
            # Threshold setting represents approximately one-hour effort; extrapolation is heuristic.
            latest_day = workout_date(settings[-1])
            selected = [w for w in settings if (latest_day - workout_date(w)).days <= 28]
            speed = median(w.threshold_speed_mps for w in selected)
            center = 3600 * (distance * 1000 / (speed * 3600)) ** 1.07
            assumptions.append('Schwellenpace als angenäherte Stundenleistung; Riegel-Übertragung ist eine Trainingsheuristik.')
            return dict(times=(center * .92, center, center * 1.12), selected=selected,
                        basis='threshold_scenario', assumptions=assumptions)
        standalone = [w for w in current if w.id not in (preloaded_ids or set())]
        interval_estimate = running_intervals(standalone, distance)
        if interval_estimate:
            return interval_estimate
        for w in standalone:
            text = f'{w.name} {w.comment or ""}'.casefold()
            if w.distance_km < min(5., distance * .4) or w.duration_sec < 1200 or re.search(r'intervall|\bvo2\b|\bhit\b', text):
                continue
            if w.elevation_gain is not None and w.elevation_gain / w.distance_km > 15:
                continue
            if w.is_indoor or 'virtual' in w.sport.casefold():
                continue
            # Never call easy pace a maximum test: estimate an explicit conservative scenario.
            factor = .95 if w.rpe is not None and w.rpe <= 4 else 1.
            values.append(w.duration_sec * (distance / w.distance_km) ** 1.07 * factor)
            selected.append(w)
        basis = 'supporting_scenario'
        assumptions.append('Dauerläufe als grobe Orientierung, kein maximaler Test; bei lockerem RPE bis 5 % schnelleres Tempo angenommen.')
    elif sport == 'Swim':
        for w in current:
            sections = []
            for position, s in enumerate(w.splits):
                text = (s.label or '').casefold()
                if (s.split_type or '').casefold() in {'recovery', 'rest'}:
                    continue
                if re.search(r'pause|rest|recover|technik|drill|beine|kick|pull|paddle|flosse|fin\b|buoy|einschw|ausschw|warm|cool|brust|rücken', text):
                    continue
                if not s.active_time_available or not positive(s.distance_km) or not positive(s.duration_sec):
                    continue
                if not text and (s.distance_km < .2 or (len(w.splits) >= 4 and position in {0, len(w.splits)-1})):
                    continue  # Unlabelled short drills and likely warm-up/cool-down do not set race pace.
                if s.distance_km < .05 or not 600 <= s.duration_sec / s.distance_km <= 2400:
                    continue
                sections.append(s)
            if sections and sum(s.distance_km for s in sections) >= min(.4, distance * .3):
                active = sum(s.duration_sec for s in sections)
                metres = sum(s.distance_km for s in sections)
                # Repeated short efforts get a small durability allowance, never a speed bonus.
                allowance = 1.04 if max(s.distance_km for s in sections) < distance * .5 else 1.
                values.append(active / metres * distance * allowance)
                selected.append(w)
        assumptions.append('Aktive Serien ohne erkannte Technik/Hilfsmittel; unbenannte Abschnitte als wahrscheinliches Dauerschwimmen eingeordnet. Stil und Material bleiben unsicher.')
        if not values:
            # A dated swim threshold is preferable to total session time containing rests.
            settings = sorted([w for w in current if positive(w.threshold_speed_mps) and .2 <= w.threshold_speed_mps <= 2.5],
                              key=lambda w: (workout_date(w), w.id))
            if settings:
                selected = settings[-6:]
                speed = median(w.threshold_speed_mps for w in selected)
                values = [distance * 1000 / speed * 1.03]
                assumptions.append('Schwellen-Einstellung als Ersatzmodell mit 3 % Ausdaueraufschlag; aktive Serien fehlen.')
                basis = 'threshold_scenario'
            else:
                # Only genuinely active open-water duration, never pool session totals.
                selected = [w for w in current if 'openwater' in w.sport.casefold() and w.distance_km >= distance * .4]
                values = [w.duration_sec / w.distance_km * distance for w in selected]
                basis = 'supporting_scenario'
    if not values:
        # Old probable/confirmed performances remain useful, explicitly stale.
        selected = [w for w in rows if classify(w, today)['race_recognition']
                    and .5 <= w.distance_km / distance <= 2]
        values = [max(w.duration_sec, w.elapsed_sec or 0) * (distance / w.distance_km) ** (1.07 if sport == 'Run' else 1.)
                  for w in selected]
        basis = 'historical_scenario'
        assumptions.append('Historische Wettkampfleistung als Orientierung; heutige Übertragbarkeit ungewiss.')
    if not values:
        return None
    # AI can modestly weight a cited observation; it cannot invent a time or change a sensor value.
    weights = (context or {}).get('weights', {})
    if len(values) == len(selected):
        weighted = sorted((v, 2 ** (-min(730, (today-workout_date(w)).days) / 42)
                           * weights.get(w.id, 1.)) for v, w in zip(values, selected))
        cumulative, center = 0., median(values)
        for value, weight in weighted:
            cumulative += weight
            if cumulative >= sum(x[1] for x in weighted) / 2:
                center = value
                break
    else:
        center = median(values)
    disagreement = min(.15, (max(values)-min(values)) / center / 2)
    margin = (.20 if basis in {'supporting_scenario', 'historical_scenario'} else .12) + disagreement
    return dict(times=(center * (1-margin), center, center * (1+margin)), selected=selected,
                basis=basis, assumptions=assumptions)


def development_forecast(workouts: list, today, days: int, estimate: float,
                         faster: float, slower: float, context=None, parts=None) -> dict:
    """Observed matched submaximal efficiency or dated settings; no plan-only gain."""
    trends = []
    for sport in ('Swim', 'Ride', 'Run'):
        rows = [w for w in workouts if sport_family(w.sport) == sport
                and 0 <= (today-workout_date(w)).days <= 84]
        recent = [w for w in rows if (today-workout_date(w)).days <= 28]
        older = [w for w in rows if 28 < (today-workout_date(w)).days <= 84]
        pairs, used = [], set()
        for a in sorted(recent, key=lambda w: (workout_date(w), w.id)):
            if a.rpe is None or a.rpe > 6 or not positive(a.avg_hr) or a.duration_sec < 1800:
                continue
            candidates = [b for b in older if b.id not in used and b.rpe is not None
                          and abs(b.rpe-a.rpe) <= 1 and positive(b.avg_hr) and abs(b.avg_hr-a.avg_hr) <= 5
                          and .75 <= b.duration_sec/a.duration_sec <= 1.25
                          and bool(b.is_indoor or 'virtual' in b.sport.casefold()) == bool(a.is_indoor or 'virtual' in a.sport.casefold())
                          and positive(b.distance_km) and positive(a.distance_km)
                          and b.elevation_gain is not None and a.elevation_gain is not None
                          and abs(b.elevation_gain/b.distance_km-a.elevation_gain/a.distance_km) <= 5]
            if not candidates:
                continue
            b = min(candidates, key=lambda w: (abs(w.duration_sec-a.duration_sec), w.id))
            if sport == 'Ride':
                if not positive(a.avg_watts) or not positive(b.avg_watts):
                    continue
                ratio = (a.avg_watts/a.avg_hr)/(b.avg_watts/b.avg_hr)
            elif sport == 'Run':
                ratio = (a.distance_km/a.duration_sec/a.avg_hr)/(b.distance_km/b.duration_sec/b.avg_hr)
            else:
                continue  # Whole-session pool speeds contain rests and drills.
            span = (workout_date(a)-workout_date(b)).days
            if span >= 14 and .8 <= ratio <= 1.2:
                pairs.append(dict(recent_id=a.id, older_id=b.id, change_28d=(ratio-1)*28/span))
                used.add(b.id)
        metric = 'ftp' if sport == 'Ride' else 'threshold_speed_mps'
        old_settings = [getattr(w, metric) for w in older if positive(getattr(w, metric))]
        new_settings = [getattr(w, metric) for w in recent if positive(getattr(w, metric))]
        rates = [median(p['change_28d'] for p in pairs)] if len(pairs) >= 3 else []
        if len(old_settings) >= 3 and len(new_settings) >= 3:
            rates.append((median(new_settings)/median(old_settings)-1) * 28/42)
        if rates:
            trends.append(dict(sport=sport, change_28d=round(median(rates), 5),
                               pairs=pairs, metric=metric, source='matched_efficiency_and_dated_settings'))
    # Dampen extrapolation and saturate at 12 weeks: no unlimited linear improvement.
    projected = []
    for part in (parts or []):
        trend = next((t for t in trends if t['sport'] == part['sport']), None)
        rate = trend['change_28d'] if trend else 0.
        # Bike speed responds sublinearly to power in the aerodynamic model.
        response = 1/3 if part['sport'] == 'Ride' else 1.
        gain = max(-.05, min(.05, rate * min(max(0, days), 84)/28 * .5 * response))
        projected.append(dict(sport=part['sport'], change_fraction=round(gain, 5),
                              estimate_seconds=round(part['estimate_seconds']/(1+gain))))
    if projected:
        seconds = estimate-sum(p['estimate_seconds'] for p in parts)+sum(p['estimate_seconds'] for p in projected)
        factor = seconds/estimate
        change = 1/factor-1
    else:
        rate = median(t['change_28d'] for t in trends) if trends else 0.
        change = max(-.05, min(.05, rate * min(max(0, days), 84)/28 * .5))
        factor = 1/(1+change)
    uncertainty = min(.05, max(0, days)/365 * .1)
    return dict(status='estimated', estimate_seconds=round(estimate*factor),
                faster_seconds=round(faster*factor*(1-uncertainty)),
                slower_seconds=round(slower*factor*(1+uncertainty)),
                change_fraction=round(change, 5), trends=trends, parts=projected,
                reason=('Vorsichtige Fortschreibung vergleichbarer Leistungen; keine garantierte Verbesserung.' if change
                        else 'Heutiger Leistungsstand vorsichtig fortgeschrieben; keine zusätzliche Verbesserung unterstellt.'))
