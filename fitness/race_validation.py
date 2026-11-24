"""Expanding-window evaluation. No current settings or held-out results in fitting."""
from datetime import date, timedelta
from statistics import mean

from fitness.plan_analysis import sport_family, workout_date
from fitness.race_prediction import predict_race
from fitness.performance_evidence import classify


def backtest(workouts: list, horizons=(90, 60, 30, 7), predictor=predict_race,
             baseline=None, as_of: date | None = None) -> dict:
    """Use recorded race flags only; never treat a target as an observed result.

    Callers must supply as-recorded snapshots for strict historical reproducibility:
    an activity's occurrence date cannot establish when a later edit was available.
    No calibration on held-out races is performed. Baseline is an optional callable.
    """
    as_of = as_of or date.today()
    workouts = [w for w in workouts if workout_date(w) <= as_of]
    rows = []
    for event in sorted(workouts, key=lambda w: (workout_date(w), w.id)):
        sport = sport_family(event.sport)
        recognition = classify(event, as_of)['race_recognition']
        if not recognition or sport not in {'Swim', 'Ride', 'Run'} or event.distance_km <= 0 or event.duration_sec <= 0:
            continue
        actual = max(event.duration_sec, event.elapsed_sec or 0)
        for horizon in horizons:
            if horizon < 1:
                raise ValueError('Backtest horizons must precede the race')
            cutoff = workout_date(event) - timedelta(days=horizon)
            history = [w for w in workouts if workout_date(w) <= cutoff and w.id != event.id]
            race = dict(id=event.id, name='Held-out race', date=workout_date(event).isoformat(),
                        sport=sport, distances_km={sport: event.distance_km}, status='planned')
            prediction = predictor(race, history, cutoff)
            row = dict(race_id=event.id, sport=sport, horizon_days=horizon, cutoff=cutoff.isoformat(),
                       actual_seconds=actual, race_recognition=recognition,
                       available=prediction.get('status') == 'estimated')
            if row['available']:
                row.update(estimate_seconds=prediction['estimate_seconds'],
                           error_seconds=prediction['estimate_seconds'] - actual,
                           covered=prediction['faster_seconds'] <= actual <= prediction['slower_seconds'])
            if baseline:
                old = baseline(race, history, cutoff)
                row['baseline_error_seconds'] = old['estimate_seconds'] - actual if old.get('status') == 'estimated' else None
            rows.append(row)
    metrics = {}
    for sport in ('Swim', 'Ride', 'Run'):
        valid = [r for r in rows if r['sport'] == sport and r['available']]
        paired = [r for r in valid if r.get('baseline_error_seconds') is not None]
        metrics[sport] = dict(count=len(valid), unique_races=len({r['race_id'] for r in valid}),
                             mae_seconds=mean(abs(r['error_seconds']) for r in valid) if valid else None,
                             bias_seconds=mean(r['error_seconds'] for r in valid) if valid else None,
                             scenario_coverage=mean(r['covered'] for r in valid) if valid else None,
                             paired_comparisons=len(paired),
                             paired_new_mae=mean(abs(r['error_seconds']) for r in paired) if paired else None,
                             paired_baseline_mae=mean(abs(r['baseline_error_seconds']) for r in paired) if paired else None)
    return dict(status='provisional', rows=rows, metrics=metrics,
                note='Retrospektives Backtesting; Änderungen historischer Einstellungen sind ohne archivierte Snapshots nicht zeitlich nachweisbar. Mehrere Horizonte desselben Rennens sind keine unabhängigen Wettkämpfe.')
