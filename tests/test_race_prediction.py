"""Synthetic race and training performances; no external services or local LLM."""
from datetime import date, datetime, timedelta
from math import isclose
from unittest.mock import Mock, patch

import pytest

from fitness.analyst import TrainingAnalyst
from fitness.analyst_models import Race
from fitness.archive import AnalystStore
from fitness.models import Workout
from fitness.race_prediction import _fatigue_scenarios, goal_position, predict_race

TODAY = date(2026, 11, 24)


def race(**changes):
    values = dict(id="example", name="Example 70.3", date=TODAY + timedelta(days=100),
                  sport="Triathlon", target_seconds=21000)
    values.update(changes)
    return Race(**values).model_dump(mode="json")


def workout(sport="Run", day=7, distance=15, seconds=5400, **changes):
    values = dict(id=f"{sport}-{day}", name="Example", sport=sport, distance_km=distance,
                  duration_sec=seconds, start_time=datetime.combine(TODAY - timedelta(days=day), datetime.min.time()),
                  elevation_gain=20, avg_hr=140)
    values.update(changes)
    return Workout(**values)


def training():
    return [workout(sport, day, distance, seconds + day * 10)
            for day in (5, 12, 19, 26)
            for sport, distance, seconds in [("Swim", 2, 2400), ("Ride", 75, 9000), ("Run", 15, 4500)]]


def test_total_goal_uses_actual_times_and_reacts_to_target_without_splits():
    data = training()
    a = predict_race(race(target_seconds=17000), data, TODAY)
    b = predict_race(race(target_seconds=25000), data, TODAY)
    assert a["status"] == b["status"] == "estimated"
    assert a["estimate_seconds"] == b["estimate_seconds"]
    assert a["score"] < b["score"]
    assert a["distances_km"] == {"Swim": 1.9, "Ride": 90, "Run": 21.1}
    assert len(a["parts"]) == 3 and all(p["basis"] == "training" for p in a["parts"])
    assert "Grobe" in a["data_quality"]
    assert any("nicht deine Leistungsgrenze" in note for note in a["notes"])
    assert a == predict_race(race(target_seconds=17000), list(reversed(data)), TODAY)


def test_faster_recorded_performances_change_time_estimate():
    original = training()
    faster = [w.model_copy(update={"duration_sec": int(w.duration_sec * .9)}) for w in original]
    assert predict_race(race(), faster, TODAY)["estimate_seconds"] < predict_race(race(), original, TODAY)["estimate_seconds"]


def test_run_race_uses_published_power_law_and_elapsed_time():
    r = race(sport="Run", name="Example half", distances_km={"Run": 21.1}, target_seconds=7200)
    p = predict_race(r, [workout(distance=10, seconds=2900, elapsed_sec=3000, is_race=True)], TODAY)
    assert p["estimate_seconds"] == round(3000 * (21.1 / 10) ** 1.07)
    assert p["parts"][0]["basis"] == "race"
    assert p["parts"][0]["count"] == 1
    assert any("Weniger als drei" in n for n in p["parts"][0]["notes"])


def test_personal_exponent_is_estimated_only_from_actual_races():
    r = race(sport="Run", name="Example", distances_km={"Run": 21.1})
    observations = [workout(day=10, distance=10, seconds=3000, is_race=True),
                    workout(day=20, distance=20, seconds=6600, is_race=True)]
    p = predict_race(r, observations, TODAY)
    assert isclose(p["parts"][0]["exponent"], 1.13750352375)
    assert "Persönlicher" in p["parts"][0]["method"]
    for w in observations:
        w.is_race = False
    assert predict_race(r, observations, TODAY)["parts"][0]["exponent"] == 1.07


def test_missing_discipline_does_not_invent_a_total_or_erase_other_estimates():
    p = predict_race(race(), [w for w in training() if w.sport != "Swim"], TODAY)
    assert p["status"] == "partial" and p["score"] is None
    assert "estimate_seconds" not in p
    assert sum(part["available"] for part in p["parts"]) == 2


def test_virtual_cycling_speed_and_indoor_flag_are_not_road_speed():
    w = [x for x in training() if x.sport != "Ride"]
    w += [workout(sport="VirtualRide", distance=90, seconds=9000),
          workout(sport="Ride", distance=90, seconds=9000, id="indoor", is_indoor=True)]
    p = predict_race(race(), w, TODAY)
    ride = next(x for x in p["parts"] if x["sport"] == "Ride")
    assert ride["count"] == 0 and not ride["available"]
    assert sum(ride["excluded"].values()) == 2
    assert p["score"] is None


def test_no_automatic_distance_guess_from_a_target_or_unknown_name():
    p = predict_race(race(name="Example triathlon"), training(), TODAY)
    assert p["status"] == "partial" and p["distances_km"] == {}
    assert any("Wettkampfdistanz" in note for note in p["notes"])
    custom = race(distances_km={"Ride": 87})
    assert predict_race(custom, training(), TODAY)["distances_km"]["Ride"] == 87


def test_transition_budget_is_used_and_default_is_disclosed():
    a = predict_race(race(), training(), TODAY)
    b = predict_race(race(transition_seconds=900), training(), TODAY)
    assert b["estimate_seconds"] - a["estimate_seconds"] == 450
    assert any("Wechsel insgesamt: angenommen" in n for n in a["assumptions"])
    assert not any("Wechsel insgesamt: angenommen" in n for n in b["assumptions"])


def test_plan_fulfillment_does_not_enter_goal_prediction():
    # The predictor accepts measured workouts and race requirements, no plan/CTL score.
    p = predict_race(race(), training(), TODAY)
    assert "plan" not in p and p["estimate_seconds"] > 0
    assert all(p["evidence"] for p in p["parts"])


def test_single_extreme_training_outlier_does_not_determine_prediction():
    r = race(sport="Run", name="Example", distances_km={"Run": 15})
    observations = [workout(day=d, distance=15, seconds=4500) for d in (5, 10, 15, 20, 25, 30)]
    before = predict_race(r, observations, TODAY)
    observations.append(workout(day=6, distance=15, seconds=15000))
    after = predict_race(r, observations, TODAY)
    assert before["estimate_seconds"] == after["estimate_seconds"]
    assert before["slower_seconds"] == after["slower_seconds"]


def test_trail_requires_course_elevation_and_comparable_terrain_evidence():
    r = race(sport="TrailRun", name="Example trail", distances_km={"Run": 30}, target_seconds=None)
    runs = [workout(distance=20, seconds=9000, elevation_gain=1000)]
    assert predict_race(r, runs, TODAY)["status"] == "partial"
    r["elevation_gain_m"] = 1500
    p = predict_race(r, runs, TODAY)
    assert p["status"] == "estimated" and p["score"] is None
    assert any("Technische Wege" in n for n in p["parts"][0]["notes"])
    assert predict_race(r, [workout(distance=20, seconds=9000, elevation_gain=10)], TODAY)["status"] == "partial"


def test_marathon_warns_about_known_standard_formula_optimism():
    p = predict_race(race(sport="Run", name="Marathon", distances_km={"Run": 42.195}),
                     [workout(distance=21.1, seconds=6600, is_race=True)], TODAY)
    assert p["status"] == "estimated"
    assert any("zu optimistisch" in n for n in p["parts"][0]["notes"])


@pytest.mark.parametrize("target, expected", [(2500, 0), (3000, 0), (3500, 50), (4000, 100), (4500, 100)])
def test_goal_position_is_a_time_comparison_not_a_probability(target, expected):
    assert goal_position(target, 3000, 4000) == expected


def test_outage_and_past_race_never_return_a_fresh_prediction():
    assert predict_race(race(), training(), TODAY, ["activities"])["status"] == "partial"
    assert predict_race(race(date=TODAY - timedelta(days=1)), training(), TODAY)["status"] == "not_applicable"
    assert predict_race(race(status="cancelled"), training(), TODAY)["score"] is None


def test_stale_evidence_and_fallback_fatigue_are_disclosed():
    runs = [workout(day=90, distance=15, seconds=4500)]
    p = predict_race(race(sport="Run", name="Example", distances_km={"Run": 21.1}), runs, TODAY)
    assert p["parts"][0]["age_days"] == 90
    assert any("90 Tage" in n for n in p["parts"][0]["notes"])
    assert _fatigue_scenarios(runs, TODAY)[0] == (0, .075, .15)


def test_personal_brick_pairs_replace_the_generic_fatigue_assumption():
    observations = []
    for i, day in enumerate((5, 15, 25)):
        run = workout(day=day, seconds=3600, distance=10, id=f"brick-{i}")
        bike = workout(sport="Ride", day=day, seconds=3600, distance=30, id=f"bike-{i}",
                       start_time=run.start_time-timedelta(seconds=3900))
        standalone = workout(day=day+2, seconds=3300, distance=10, id=f"standalone-{i}")
        observations.extend([run, bike, standalone])
    factors, note = _fatigue_scenarios(observations, TODAY)
    assert all(isclose(v, 3600/3300-1) for v in factors)
    assert "3 persönlichen" in note


def test_summary_exposes_prediction_separately_from_preparation(tmp_path):
    store = AnalystStore(tmp_path)
    store.save_race(Race.model_validate(race()))
    client = Mock()
    client.get_workouts.return_value = training()
    client.get_calendar.return_value = []
    client.get_wellness_history.return_value = []
    summary = TrainingAnalyst(client, store).summary(TODAY)
    assert summary["goal_predictions"]["example"]["estimate_seconds"] > 0
    assert "race_preparation" in summary


def test_dashboard_renders_real_target_comparison_and_local_ai_button():
    from dashboard import routes
    from tests.test_dashboard import DashboardRouteTests
    r = race()
    p = predict_race(r, training(), TODAY)
    summary = dict(races=[r], next_race=r, days_to_race=100, goal_predictions={r["id"]: p})
    with patch.object(routes, "_safe_summary", return_value={}), patch.object(routes, "_safe_analyst", return_value=summary):
        html = routes.dashboard_index(DashboardRouteTests._request()).body.decode()
    assert "Geschätzte Zeitspanne" in html and "Dein Ziel im Zeitvergleich" in html
    assert 'aria-label="Zeitvergleich: Wunschzeit' in html
    assert 'geschätzte Mitte' in html
    assert "Grobe Schätzung aus Training" in html
    assert "Von meiner lokalen KI erklären lassen" in html
    assert "goal_predictions" in html and "keine Prozentchance" in html
    assert "70.3" in html


def test_activity_mapping_retains_elapsed_time_and_indoor_flag():
    from intervals.intervals_client import IntervalsClient
    client = IntervalsClient.__new__(IntervalsClient)
    w = client._map_activity_to_workout(dict(id="synthetic", name="Example", type="Ride",
        start_date="2026-11-10T10:00:00Z", moving_time=3000, elapsed_time=3600, distance=20000, trainer=True))
    assert w.duration_sec == 3000 and w.elapsed_sec == 3600 and w.is_indoor is True


def test_local_ai_tool_receives_calculated_predictions_with_bounded_evidence():
    from connectors import mcp_server
    data = training() + [workout(sport=s, day=d, distance=dist, seconds=seconds)
                         for d in (33, 40, 47) for s, dist, seconds in
                         [("Swim", 2, 2400), ("Ride", 75, 9000), ("Run", 15, 4500)]]
    p = predict_race(race(), data, TODAY)
    summary = dict(races=[race()], race_preparation={"example": {"history": []}},
                   goal_predictions={"example": p}, errors=[])
    with patch.object(mcp_server, "TrainingAnalyst") as service:
        service.return_value.summary.return_value = summary
        result = mcp_server.get_training_analysis("predictions")
    assert "race_preparation" not in result
    output = result["goal_predictions"]["example"]
    assert output["estimate_seconds"] == p["estimate_seconds"]
    assert all(len(part["evidence"]) <= 5 for part in output["parts"])
    assert output["assumptions"] and output["sources"]
