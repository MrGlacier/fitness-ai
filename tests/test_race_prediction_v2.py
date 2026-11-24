"""Behavioral regression tests using exclusively synthetic performances."""
from datetime import timedelta
from math import nan

import pytest

from fitness.models import WorkoutSplit
from fitness.performance_evidence import goal_attainment
from fitness.race_prediction import predict_race, _fatigue_scenarios
from fitness.cycling_prediction import road_speed
from fitness.race_validation import backtest
from tests.test_race_prediction import TODAY, race, workout, training


def single(sport='Run', distance=21.1):
    return race(sport=sport, name='Synthetic event', distances_km={sport: distance})


def span(prediction):
    return prediction['slower_seconds'] - prediction['faster_seconds']


def test_easy_runs_cannot_lower_estimated_maximal_performance():
    r = single()
    measured = workout(distance=10, seconds=3000, is_race=True)
    before = predict_race(r, [measured], TODAY)
    easy = [workout(day=d, distance=15, seconds=7200, rpe=3) for d in range(1, 7)]
    after = predict_race(r, [measured, *easy], TODAY)
    assert before['estimate_seconds'] == after['estimate_seconds']
    assert all(not row['used'] for row in after['parts'][0]['activity_audit'] if row['rpe'] == 3)


@pytest.mark.parametrize('label', ['Technik Kraul', 'Kraul Pull-Buoy', 'Kraul Paddles', 'Kraul Flossen', 'Kraul Beine', 'Pause'])
def test_swim_drills_aids_and_unknown_stroke_do_not_supply_race_pace(label):
    w = workout(sport='Swim', name='Maximaltest', rpe=10, distance=2, seconds=4000,
                splits=[WorkoutSplit(index=1, label=label, distance_km=1, duration_sec=1000, active_time_available=True)])
    p = predict_race(single('Swim', 1.9), [w], TODAY)
    assert not p['parts'][0]['available']
    assert p['parts'][0]['activity_audit'][0]['excluded_sections']


def test_swim_uses_active_sections_and_ignores_long_rests():
    w = workout(sport='Swim', name='Maximaltest', rpe=10, distance=2, seconds=2000, elapsed_sec=5000,
                splits=[WorkoutSplit(index=1, label='Kraul', distance_km=1, duration_sec=1000, active_time_available=True),
                        WorkoutSplit(index=2, label='Pause', distance_km=0, duration_sec=3000)])
    p = predict_race(single('Swim', 1.9), [w], TODAY)
    assert p['estimate_seconds'] == 1900
    w.elapsed_sec = 9000
    assert predict_race(single('Swim', 1.9), [w], TODAY)['estimate_seconds'] == 1900
    w.splits[0].active_time_available = False
    assert predict_race(single('Swim', 1.9), [w], TODAY)['status'] == 'partial'


def test_missing_swim_laps_abstains_instead_of_averaging_total_time():
    p = predict_race(single('Swim', 1.9), [workout(sport='Swim', distance=2, seconds=4000)], TODAY)
    assert p['status'] == 'partial'
    assert 'Gesamtschwimmzeit' in p['parts'][0]['activity_audit'][0]['reason']


@pytest.mark.parametrize('distance,seconds,name,rpe', [(1, 180, 'Maximaltest', 10), (5, 1400, 'VO2 Intervalle', 10), (20, 8000, 'Langer Grundlagenlauf', 3)])
def test_short_intervals_and_easy_endurance_runs_remain_supporting(distance, seconds, name, rpe):
    p = predict_race(single(), [workout(distance=distance, seconds=seconds, name=name, rpe=rpe)], TODAY)
    assert p['status'] == ('estimated' if distance == 20 else 'partial')
    if distance == 20:
        assert p['parts'][0]['basis'] == 'supporting_scenario'


def test_maximal_test_changes_prediction_but_target_does_not():
    r = single()
    test = workout(name='Leistungstest', rpe=10, distance=15, seconds=4500)
    a = predict_race(r, [test], TODAY)
    test.duration_sec = 4200
    b = predict_race(r, [test], TODAY)
    assert b['estimate_seconds'] < a['estimate_seconds']
    r['target_seconds'] = 10000
    assert predict_race(r, [test], TODAY)['estimate_seconds'] == b['estimate_seconds']


def indoor_data():
    return [workout(sport='Ride', day=100, distance=75, seconds=9000, avg_watts=140, ftp=200, weight_kg=70),
            workout(sport='VirtualRide', day=2, distance=200, seconds=7200, avg_watts=160, ftp=220, weight_kg=70, rpe=5)]


def test_recent_indoor_power_updates_old_outdoor_scenario_without_using_virtual_speed():
    r = single('Ride', 90)
    data = indoor_data()
    a = predict_race(r, data, TODAY)
    assert a['parts'][0]['age_days'] == 2
    assert a['parts'][0]['power_watts'] == 160
    data[-1].distance_km = 999
    assert predict_race(r, data, TODAY)['estimate_seconds'] == a['estimate_seconds']
    data[-1].avg_watts = 180
    assert predict_race(r, data, TODAY)['estimate_seconds'] < a['estimate_seconds']


def test_ftp_progress_changes_dated_power_transfer_without_modifying_old_speed():
    r = single('Ride', 90)
    data = indoor_data()
    data[-1].duration_sec = 1800  # indicator, too short to supply sustained race power
    a = predict_race(r, data, TODAY)
    data[-1].ftp = 250
    b = predict_race(r, data, TODAY)
    assert b['estimate_seconds'] < a['estimate_seconds']
    assert b['parts'][0]['age_days'] == 100  # do not relabel old endurance evidence as recent


def test_missing_ftp_or_rpe_increases_scenario_uncertainty():
    r = single('Ride', 90)
    data = indoor_data()
    a = predict_race(r, data, TODAY)
    for w in data:
        w.ftp = None
        w.rpe = None
    b = predict_race(r, data, TODAY)
    assert b['status'] == 'estimated'
    assert span(b) > span(a)


def test_stale_and_missing_effort_widen_uncertainty_without_changing_ability():
    r = single()
    recent = workout(distance=10, seconds=3000, is_race=True, rpe=10)
    a = predict_race(r, [recent], TODAY)
    stale = recent.model_copy(update={'start_time': recent.start_time - timedelta(days=100), 'rpe': None})
    b = predict_race(r, [stale], TODAY)
    assert a['estimate_seconds'] == b['estimate_seconds']
    assert span(b) > span(a)


@pytest.mark.parametrize('changes', [{'distance_km': nan}, {'distance_km': 0}, {'duration_sec': 0}, {'distance_km': -2}])
def test_invalid_activity_does_not_supply_performance(changes):
    p = predict_race(single(), [workout(is_race=True).model_copy(update=changes)], TODAY)
    assert p['status'] == 'partial'


def test_conflicting_results_widen_scenarios_without_selecting_best_result():
    r = single()
    data = [workout(day=d, distance=10, seconds=3000, is_race=True) for d in (3, 10, 20)]
    a = predict_race(r, data, TODAY)
    b = predict_race(r, data + [workout(day=15, distance=10, seconds=4500, is_race=True)], TODAY)
    assert a['estimate_seconds'] == b['estimate_seconds']
    assert span(b) > span(a)
    assert any('Widersprüchliche' in n for n in b['parts'][0]['notes'])


def test_future_workouts_cannot_affect_exponent_or_brick_detection():
    r = single()
    data = [workout(day=20, distance=10, seconds=3000, is_race=True)]
    a = predict_race(r, data, TODAY)
    b = predict_race(r, data + [workout(day=-1, distance=20, seconds=5500, is_race=True)], TODAY)
    assert a == b


def test_backtest_is_chronological_and_compares_same_available_rows():
    past = workout(day=150, distance=10, seconds=3000, is_race=True)
    heldout = workout(day=1, distance=21.1, seconds=7000, is_race=True)
    observed = []
    def spy(race, history, cutoff):
        assert all(w.start_time.date() <= cutoff for w in history)
        assert all(w.id != race['id'] for w in history)
        observed.append(cutoff)
        return predict_race(race, history, cutoff)
    report = backtest([past, heldout, workout(day=-1, is_race=True)], predictor=spy, baseline=predict_race, as_of=TODAY)
    assert len(observed) == 8
    assert report['metrics']['Run']['count'] > 0
    assert report['metrics']['Run']['paired_new_mae'] == report['metrics']['Run']['paired_baseline_mae']
    assert report['metrics']['Run']['mae_seconds'] is not None


def test_no_historical_races_produces_no_invented_error_metrics():
    report = backtest([workout()])
    assert report['rows'] == []
    assert report['metrics']['Run']['mae_seconds'] is None


def test_physics_power_balance_and_monotonic_response():
    v = road_speed(180, 80, .3, .004)
    assert .5 * 1.225 * .3 * v**3 + 80 * 9.80665 * .004 * v == pytest.approx(180 * .97)
    assert road_speed(200, 80, .3, .004) > v
    assert road_speed(180, 80, .4, .004) < v
    assert road_speed(180, 80, .3, .004, headwind=2) < v


def test_index_requires_repeated_comparable_results_and_cannot_be_high_from_continuity():
    w = [workout(day=d, distance=10, seconds=3000, is_race=True) for d in (5, 30, 55)]
    p = predict_race(single(), w, TODAY)
    assert p['goal_index']['status'] == 'heuristic'
    p_bad = predict_race(single(), w, TODAY)
    part = p_bad['parts'][0]
    index = goal_attainment([part], 3600, p_bad['estimate_seconds'], w, TODAY, 100)
    assert 26 <= index['value'] <= 49


def test_different_bike_preloads_do_not_produce_a_personal_fatigue_factor():
    data = []
    for i, duration in enumerate((3600, 7200, 10800)):
        run = workout(day=5+i*10, seconds=3600, distance=10, id=f'brick{i}', rpe=5)
        ride = workout(sport='Ride', day=5+i*10, seconds=duration, distance=60, id=f'bike{i}',
                       start_time=run.start_time-timedelta(seconds=duration+300), avg_watts=150, ftp=220, rpe=5)
        solo = workout(day=7+i*10, seconds=3300, distance=10, id=f'solo{i}', rpe=5)
        data.extend([run, ride, solo])
    assert _fatigue_scenarios(data, TODAY)[0] == (0, .075, .15)


def test_short_bricks_cannot_calibrate_a_long_race_bike_leg():
    data = []
    for i in range(3):
        run = workout(day=5+i*10, seconds=3600, distance=10, id=f'brick{i}', rpe=5)
        ride = workout(sport='Ride', day=5+i*10, seconds=3600, distance=30, id=f'bike{i}',
                       start_time=run.start_time-timedelta(seconds=3900), avg_watts=150, ftp=220, rpe=5)
        solo = workout(day=7+i*10, seconds=3300, distance=10, id=f'solo{i}', rpe=5)
        data.extend([run, ride, solo])
    assert _fatigue_scenarios(data, TODAY, bike_duration=10800)[0] == (0, .075, .15)


def test_recent_power_is_not_masked_by_an_old_outdoor_race():
    data = indoor_data()
    data[0].is_race = True
    prediction = predict_race(single('Ride', 90), data, TODAY)
    assert prediction['parts'][0]['basis'] == 'power_scenario'
    assert prediction['parts'][0]['age_days'] == 2


def test_easy_training_supplies_efficiency_and_explicit_supporting_scenario():
    easy = workout(distance=12, seconds=3600, avg_hr=120, rpe=3)
    p = predict_race(single(), [easy], TODAY)
    assert p['status'] == 'estimated'
    assert p['parts'][0]['basis'] == 'supporting_scenario'
    point = next(r for r in p['fitness_development']['points'] if r['metric'] == 'metres_per_heartbeat')
    assert point['value'] == pytest.approx(1.667)
    assert point['rpe'] == 3 and point['avg_hr'] == 120
