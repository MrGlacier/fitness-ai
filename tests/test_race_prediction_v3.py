"""Product scale and graded evidence: synthetic data, no real LLM or network."""
from datetime import timedelta
import json
from unittest.mock import Mock

import pytest

from fitness.archive import AnalystStore
from fitness.models import WorkoutSplit
from fitness.performance_evidence import classify, goal_attainment
from fitness.prediction_context import analyze_context
from fitness.race_prediction import predict_race
from fitness.training_prediction import development_forecast
from tests.test_race_prediction import TODAY, race, workout, training
from tests.test_race_prediction_v2 import single


@pytest.mark.parametrize('reserve,expected', [(-.3, 35), (-.15, 50), (-.06, 65), (0, 75), (.08, 90), (.2, 100)])
def test_scale_anchors_with_demonstrated_endurance(reserve, expected):
    part = dict(sport='Run', available=True, distance_km=21.1, estimate_seconds=7000,
                basis='race', count=3)
    endurance = dict(value=1., disciplines=[dict(sport='Run', coverage=1.)])
    index = goal_attainment([part], 7000*(1+reserve), 7000, [], TODAY, 60,
                           endurance=endurance, conservative=7500)
    assert index['value'] == expected


@pytest.mark.parametrize('coverage,lower,upper', [(.0, 0, 25), (.2, 0, 25), (.5, 26, 49), (.75, 50, 74), (1., 75, 100)])
def test_generous_goal_cannot_compensate_for_missing_endurance(coverage, lower, upper):
    part = dict(sport='Run', available=True, distance_km=21.1, estimate_seconds=7000, basis='race')
    index = goal_attainment([part], 10000, 7000, [], TODAY, 90,
        endurance=dict(value=coverage, disciplines=[dict(coverage=coverage)]), conservative=7500)
    assert lower <= index['value'] <= upper


def test_unrealistic_goal_does_not_mean_endangered_finish():
    data = training()
    p = predict_race(race(target_seconds=10000), data, TODAY)
    assert p['endurance']['value'] >= .85
    assert 26 <= p['score'] <= 49
    assert p['verdict'] == 'Finish möglich'


def test_official_cutoff_caps_finish_assessment():
    p = predict_race(race(cutoff_seconds=10000), training(), TODAY)
    assert p['score'] <= 25


def test_index_and_independent_forecasts_react_consistently():
    a = predict_race(race(), training(), TODAY)
    b = predict_race(race(target_seconds=25000), training(), TODAY)
    assert a['estimate_seconds'] == b['estimate_seconds']
    assert a['race_day_forecast'] == b['race_day_forecast']
    assert a['score'] < b['score']
    faster = [w.model_copy(update={'duration_sec': round(w.duration_sec*.95)}) for w in training()]
    c = predict_race(race(), faster, TODAY)
    assert c['estimate_seconds'] < a['estimate_seconds'] and c['score'] >= a['score']


def test_historical_race_without_flag_is_probable_not_confirmed():
    data = [workout(name='Stadtlauf Halbmarathon', distance=21.1, seconds=7000)]
    p = predict_race(single(), data, TODAY)
    assert p['status'] == 'estimated'
    assert p['parts'][0]['basis'] == 'probable_race'
    assert p['parts'][0]['evidence'][0]['race_recognition'] == 'probable'
    assert not classify(workout(name='Halbmarathon Tempo Training'), TODAY)['race_recognition']


def test_indoor_ftp_without_long_ride_supplies_conditional_physics():
    w = workout(sport='VirtualRide', distance=200, seconds=2400, ftp=230, weight_kg=72, avg_watts=170)
    a = predict_race(single('Ride', 90), [w], TODAY)
    w.distance_km = 1000
    b = predict_race(single('Ride', 90), [w], TODAY)
    assert a['status'] == 'estimated' and a['estimate_seconds'] == b['estimate_seconds']
    assert a['endurance']['value'] < .65
    assert any('aus FTP' in n for n in a['parts'][0]['notes'])


def test_unlabelled_active_swim_series_exclude_pauses_drills_and_aids():
    splits = [WorkoutSplit(index=1, label='Einschwimmen', distance_km=.2, duration_sec=400, active_time_available=True),
              WorkoutSplit(index=2, distance_km=.8, duration_sec=1000, active_time_available=True),
              WorkoutSplit(index=3, label='Pause', duration_sec=900),
              WorkoutSplit(index=4, label='Kraul Paddles', distance_km=.4, duration_sec=300, active_time_available=True),
              WorkoutSplit(index=5, label='Technik Beine', distance_km=.2, duration_sec=900, active_time_available=True)]
    w = workout(sport='Swim', distance=1.6, seconds=3600, splits=splits)
    p = predict_race(single('Swim', 1.9), [w], TODAY)
    assert p['status'] == 'estimated'
    assert p['estimate_seconds'] == round(1000/.8*1.9*1.04)
    w.elapsed_sec = 10000
    assert predict_race(single('Swim', 1.9), [w], TODAY)['estimate_seconds'] == p['estimate_seconds']


def test_current_threshold_updates_old_race_and_records_both_models():
    old = workout(day=250, distance=10, seconds=3600, is_race=True)
    recent = workout(day=3, threshold_speed_mps=3.8, rpe=3)
    a = predict_race(single(), [old], TODAY)
    b = predict_race(single(), [old, recent], TODAY)
    assert b['estimate_seconds'] < a['estimate_seconds']
    assert len(b['parts'][0]['alternative_models']) == 2


def progressing_training():
    return [workout(day=d, distance=10, seconds=3600, rpe=3, avg_hr=140,
                    threshold_speed_mps=3.2 if d > 28 else 3.4)
            for d in (5, 12, 19, 40, 47, 54)]


def test_progress_without_maximal_tests_and_less_remaining_time():
    data = progressing_training()
    far = predict_race(single(), data, TODAY)
    close = predict_race(single() | {'date': (TODAY+timedelta(days=1)).isoformat()}, data, TODAY)
    assert far['race_day_forecast']['estimate_seconds'] < far['estimate_seconds']
    assert close['race_day_forecast']['estimate_seconds'] > far['race_day_forecast']['estimate_seconds']
    assert close['score'] <= far['score']


def test_deload_and_single_bad_night_do_not_create_fitness_loss():
    data = progressing_training()
    a = predict_race(single(), data, TODAY)
    b = predict_race(single(), data, TODAY, context={'phase': 'recovery'},
                     wellness=[dict(date=TODAY.isoformat(), sleep_secs=9000, hrv=15)])
    assert a['estimate_seconds'] == b['estimate_seconds']
    assert a['score'] == b['score']
    assert a['race_day_forecast'] == b['race_day_forecast']


def test_single_bad_day_does_not_override_repeated_threshold_evidence():
    data = progressing_training()
    before = predict_race(single(), data, TODAY)
    after = predict_race(single(), data+[workout(day=1, seconds=8000, distance=10, rpe=8)], TODAY)
    assert before['estimate_seconds'] == after['estimate_seconds']


def test_same_input_order_and_goal_do_not_change_context_cache(tmp_path):
    store = AnalystStore(tmp_path)
    w = workout(comment='Kontrolliert und locker gelaufen.')
    llm = Mock()
    llm.ask.return_value = {'answer': json.dumps(dict(phase='build', interpretations=[dict(
        activity_id=w.id, quote='Kontrolliert und locker', kind='controlled', explanation='Die Einheit war kontrolliert.')]))}
    a = analyze_context([w], TODAY, {}, [], store, llm)
    b = analyze_context([w], TODAY, {}, [], store, llm)
    assert a['status'] == b['status'] == 'analyzed' and b['cached']
    assert llm.ask.call_count == 1 and a['weights'][w.id] == 1.05
    assert 'target_seconds' not in llm.ask.call_args.args[0]


def test_fabricated_ai_evidence_is_discarded(tmp_path):
    llm = Mock()
    llm.ask.return_value = {'answer': json.dumps(dict(phase='build', interpretations=[dict(
        activity_id='invented', quote='Ich bin sehr schnell', kind='controlled', explanation='Unbelegt.')]))}
    result = analyze_context([workout()], TODAY, {}, [], AnalystStore(tmp_path), llm)
    assert result['status'] == 'unavailable'
    assert 'weights' not in result


def test_archived_deload_takes_precedence_over_ai_phase(tmp_path):
    llm = Mock()
    w = workout(comment='Eine lockere Einheit.')
    llm.ask.return_value = {'answer': json.dumps(dict(phase='build', interpretations=[dict(
        activity_id=w.id, quote='lockere Einheit', kind='controlled', explanation='Locker absolviert.')]))}
    plan = dict(sessions=[dict(title='Training', notes='x'*200+' ENTLASTUNGSWOCHE')])
    result = analyze_context([w], TODAY, plan, [], AnalystStore(tmp_path), llm)
    assert result['phase'] == 'recovery'
    assert llm.ask.call_args.kwargs['response_schema']['type'] == 'object'


def test_llm_forwards_schema_only_when_explicitly_requested():
    from llm.llm_client import LlmClient
    client = LlmClient.__new__(LlmClient)
    client._post = Mock(return_value={'choices': [dict(message={'content': '{}'})]})
    schema = {'type': 'object', 'properties': {}}
    client.ask('Synthetic example', response_schema=schema)
    assert client._post.call_args.args[1]['response_format'] == {'type': 'json_object', 'schema': schema}
    client.ask('Synthetic example')
    assert 'response_format' not in client._post.call_args.args[1]


def test_invalid_optional_swim_details_do_not_break_summary(tmp_path):
    from fitness.analyst import TrainingAnalyst
    client = Mock()
    client.get_calendar.return_value = []
    client.get_workouts.return_value = [workout(sport='Swim', threshold_speed_mps=.8)]
    client.get_wellness_history.return_value = []
    client.get_historical_session_details.return_value = {'intervals': [{'index': 'invalid'}]}
    store = AnalystStore(tmp_path)
    from fitness.analyst_models import Race
    store.save_race(Race.model_validate(single('Swim', 1.9)))
    result = TrainingAnalyst(client, store).summary(TODAY)
    assert 'swim details' in result['errors']
    assert result['goal_predictions']['example']['status'] == 'estimated'


@pytest.mark.parametrize('value,color', [(0, '#fa7182'), (25, '#fa7182'), (26, '#ffa45c'), (49, '#ffa45c'),
    (50, '#e5ca58'), (64, '#e5ca58'), (65, '#bedb62'), (74, '#bedb62'), (75, '#68d98b'), (100, '#68d98b')])
def test_dial_colors_match_product_scale(value, color):
    from dashboard.routes import _gauge_geometry
    assert _gauge_geometry(value)['color'] == color


def test_dial_is_present_even_without_a_score():
    from dashboard.routes import templates
    r = single()
    p = predict_race(r, [], TODAY)
    html = str(templates.env.get_template('goal_prediction.html').module.goal_prediction(p, r))
    assert 'confidence-dial' in html
    assert 'Noch kein Wert berechnet' in html


def test_older_than_180_days_can_calibrate_outdoor_resistance():
    old = workout(sport='Ride', day=600, distance=60, seconds=7200, avg_watts=150,
                  ftp=200, weight_kg=70, elevation_gain=50)
    current = workout(sport='VirtualRide', day=2, distance=80, seconds=7200,
                      avg_watts=160, ftp=220, weight_kg=70)
    p = predict_race(single('Ride', 90), [old, current], TODAY)
    assert p['parts'][0]['calibration'][0]['id'] == old.id


def normal_training_only():
    return [w for day in (3, 10, 17) for w in (
        workout(sport='Swim', day=day, distance=2.4, seconds=3500, rpe=5,
                splits=[WorkoutSplit(index=1, label='Kraul', distance_km=1.2,
                                     duration_sec=1500, active_time_available=True)]),
        workout(sport='VirtualRide', day=day+1, distance=60, seconds=7200,
                avg_watts=160, ftp=220, weight_kg=70, rpe=5),
        workout(day=day+2, distance=16, seconds=5500, threshold_speed_mps=3.5, rpe=4))]


def test_normal_training_alone_supports_complete_forecasts_index_and_dial():
    from dashboard.routes import templates
    data = normal_training_only()
    assert all(not w.is_race and classify(w, TODAY)['role'] != 'direct' for w in data)
    p = predict_race(race(), data, TODAY)
    assert p['status'] == 'estimated'
    assert p['race_day_forecast']['estimate_seconds'] > 0
    assert 0 <= p['score'] <= 100
    assert all(part['available'] and part['data_quality'] == 'medium' for part in p['parts'])
    assert p['transition_seconds'] > 0
    assert 'confidence-dial' in str(templates.env.get_template('goal_prediction.html').module.goal_prediction(p, race()))
    assert all(sum(part['excluded'].values()) == sum(not row['used'] for row in part['activity_audit']) for part in p['parts'])


def test_missing_race_flags_alone_do_not_lower_training_model_quality():
    data = normal_training_only()
    a = predict_race(race(), data, TODAY)
    # Indoor power retains the same measurement context, irrespective of its race flag.
    b = predict_race(race(), [w.model_copy(update={'is_race': True}) if w.sport == 'VirtualRide' else w for w in data], TODAY)
    ride_a = next(p for p in a['parts'] if p['sport'] == 'Ride')
    ride_b = next(p for p in b['parts'] if p['sport'] == 'Ride')
    assert ride_a['estimate_seconds'] == ride_b['estimate_seconds']
    assert ride_a['data_quality'] == ride_b['data_quality'] == 'medium'


def test_long_measured_intervals_without_threshold_or_race_produce_estimate():
    data = [workout(day=d, name='3x10 Minuten kontrolliert', rpe=7, distance=12, seconds=4500,
                    splits=[WorkoutSplit(index=i, split_type='WORK', distance_km=2.2,
                                         duration_sec=600, active_time_available=True) for i in (1, 2, 3)]
                    + [WorkoutSplit(index=4, split_type='RECOVERY', distance_km=.5,
                                    duration_sec=900, active_time_available=True)]) for d in (3, 10, 17)]
    p = predict_race(single(), data, TODAY)
    assert p['status'] == 'estimated'
    assert p['parts'][0]['basis'] == 'interval_scenario'
    assert p['parts'][0]['data_quality'] == 'medium'
    for w in data:
        w.splits[-1].duration_sec = 3000
    assert predict_race(single(), data, TODAY)['estimate_seconds'] == p['estimate_seconds']


def test_brick_training_pace_is_not_used_twice_as_fresh_running_performance():
    run = workout(day=2, rpe=4, distance=10, seconds=4000)
    ride = workout(sport='Ride', day=2, distance=60, seconds=7200, avg_watts=160,
                   ftp=220, weight_kg=70, start_time=run.start_time-timedelta(seconds=7500))
    p = predict_race(race(), [run, ride], TODAY)
    part = next(part for part in p['parts'] if part['sport'] == 'Run')
    assert not part['available']
    run.threshold_speed_mps = 3.5
    p = predict_race(race(), [run, ride], TODAY)
    part = next(part for part in p['parts'] if part['sport'] == 'Run')
    assert part['available'] and part['basis'] == 'threshold_scenario'


def test_current_swim_training_updates_old_calibration_and_remains_visible():
    old = workout(sport='Swim', day=150, distance=1.9, seconds=3000, is_race=True)
    current = [workout(sport='Swim', day=d, distance=2.4, seconds=3300, rpe=5,
                       splits=[WorkoutSplit(index=1, label='Kraul', distance_km=1.2,
                                            duration_sec=1400, active_time_available=True)]) for d in (3, 10, 17)]
    a = predict_race(single('Swim', 1.9), [old], TODAY)
    b = predict_race(single('Swim', 1.9), [old, *current], TODAY)
    assert b['estimate_seconds'] < a['estimate_seconds']
    part = b['parts'][0]
    assert part['basis'] == 'combined_scenario'
    assert {w.id for w in current} <= {row['id'] for row in part['evidence']}
    assert part['age_days'] == 3
