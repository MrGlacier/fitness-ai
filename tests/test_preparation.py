"""Synthetic evidence for preparation rubric; no Garmin accuracy claims or live data."""
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from fitness.analyst import TrainingAnalyst
from fitness.analyst_models import Race, TrainingPlan
from fitness.archive import AnalystStore
from fitness.models import Workout
from fitness.preparation import MODEL_VERSION, endurance, preparation_index

TODAY = date(2026, 11, 23)  # Monday: three complete reference weeks.


def evidence(target=None):
    workouts = [Workout(id=str(day), name="Example Run", start_time=datetime.combine(TODAY-timedelta(days=day), datetime.min.time()),
                        sport="Run", duration_sec=1000, distance_km=5, avg_hr=140, tss=50,
                        intensity=80, rpe=5, is_race=True)
                for day in [7, 14, 20, 28, 31, 35]]
    rows = [dict(event=dict(id=w.id, date=w.start_time.date().isoformat(), duration_sec=1000,
                            tss=50, intensity_percent=80), status="completed", activity_id=w.id)
            for w in workouts[:3]]
    plan = TrainingPlan(id="example", name="Example", sport="Run",
                        sessions=[dict(week=i, day=1, title="Example Run", sport="Run", phase="Build",
                                       duration_sec=1000, distance_km=5) for i in range(1, 5)])
    active = dict(plan_id="example", week=4, phases=["Build"])
    wellness = [dict(date=(TODAY-timedelta(days=i)).isoformat(), hrv=50, resting_hr=50, sleep_secs=28800) for i in range(28)]
    race = Race(id="race", name="Example Race", date=TODAY+timedelta(days=70), sport="Run",
                distances_km={"Run": 5}, target_seconds=target).model_dump(mode="json")
    return dict(race=race, workouts=workouts, comparison=dict(sessions=rows), wellness=wellness,
                plan=plan, active=active, today=TODAY)


def test_complete_evidence_score_is_reproducible_and_bounded():
    data = evidence()
    a = preparation_index(**data)
    assert a == preparation_index(**data)
    assert a["score"] == 100 and a["status"] == "available"
    assert a["components"]["goal"]["status"] == "not_applicable"
    assert a["model_version"] == MODEL_VERSION
    assert "keine Zielerreichungswahrscheinlichkeit" in a["notice"]
    assert "total_seconds" not in a


def test_plan_compliance_alone_never_produces_score():
    data = evidence()
    data["workouts"] = data["workouts"][:3]
    index = preparation_index(**data)
    assert index["components"]["plan"]["score"] == 100
    assert index["components"]["performance"]["score"] is None
    assert index["score"] is None and index["label"] == "Datenlage unzureichend"


def test_weak_performance_caps_high_compliance():
    data = evidence()
    for w in data["workouts"][3:]:
        w.distance_km = 10
    index = preparation_index(**data)
    assert index["components"]["plan"]["score"] == 100
    assert index["components"]["performance"]["score"] == 50
    assert index["score"] == 50
    assert index["negative_factors"][0]["score"] == 50


def test_missing_data_is_neither_zero_nor_good():
    data = evidence()
    data["wellness"] = []
    index = preparation_index(**data)
    assert index["components"]["tolerance"]["score"] is None
    assert index["score"] is None
    assert index["data_quality"] == "unvollständig"
    assert index["missing"]


def test_single_extreme_outlier_does_not_dominate():
    data = evidence()
    data["workouts"][0].distance_km = 5000
    data["workouts"][0].rpe = 10
    assert preparation_index(**data)["score"] == 100


def test_moved_sessions_get_same_credit():
    data = evidence()
    before = preparation_index(**data)
    data["comparison"]["sessions"][0]["status"] = "moved"
    after = preparation_index(**data)
    assert after["score"] == before["score"]
    assert after["components"]["plan"]["moved_sessions"] == 1


def test_unmatched_and_intensity_gaps_remain_open():
    data = evidence()
    data["comparison"]["sessions"][0]["activity_id"] = None
    assert preparation_index(**data)["components"]["plan"]["score"] is None
    data = evidence()
    for row in data["comparison"]["sessions"]:
        row["event"]["intensity_percent"] = None
    assert preparation_index(**data)["score"] is None


def test_excess_load_or_intensity_is_not_a_bonus():
    data = evidence()
    for w in data["workouts"][:3]:
        w.intensity = 160
    index = preparation_index(**data)
    assert index["components"]["plan"]["score"] == 50
    assert index["score"] == 50


def test_phase_and_race_distance_change_reference_window():
    data = evidence()
    plan = data["plan"].model_copy(update={"sessions": [*data["plan"].sessions,
        data["plan"].sessions[0].model_copy(update={"week": 5, "duration_sec": 5000})]})
    early = endurance(["Run"], data["workouts"], plan, data["active"], 70, TODAY)
    assert early["reference_weeks"] == [2, 3, 4]
    assert early["score"] == 100  # Future peak demand is not imposed on Build.
    near = endurance(["Run"], data["workouts"], plan, data["active"], 10, TODAY)
    taper = endurance(["Run"], data["workouts"], plan, dict(data["active"], phases=["Taper"]), 70, TODAY)
    assert near["reference_weeks"] == taper["reference_weeks"] == [1, 2, 3, 4]


def test_goal_uses_demonstrated_speed_not_predicted_time():
    data = evidence(target=800)
    index = preparation_index(**data)
    assert index["components"]["goal"]["score"] == 80
    assert index["score"] == 80
    assert index["components"]["goal"]["checks"][0]["reference"] == 22.5
    data["workouts"][0].is_race = False
    data["workouts"][1].is_race = False
    data["workouts"][2].is_race = False
    # Prior races still qualify; once no race evidence remains, don't invent it.
    for w in data["workouts"]:
        w.is_race = False
    assert preparation_index(**data)["components"]["goal"]["score"] is None


def test_triathlon_requires_evidence_in_every_discipline_and_goal_splits():
    data = evidence(target=10000)
    data["race"].update(sport="Triathlon", distances_km={"Swim": 1.9, "Ride": 90, "Run": 21.1})
    index = preparation_index(**data)
    assert index["score"] is None
    assert any("Swim" in m for m in index["components"]["performance"]["missing"])
    assert index["components"]["goal"]["score"] is None


def test_ctl_alone_has_no_effect():
    data = evidence()
    before = preparation_index(**data)
    for row in data["wellness"]:
        row.update(ctl=10000, atl=1, tsb=9999)
    assert preparation_index(**data) == before


def test_failed_source_suppresses_number_and_finished_race_is_not_preparation():
    assert preparation_index(**evidence(), errors=["calendar"])["score"] is None
    data = evidence()
    data["race"]["status"] = "completed"
    assert preparation_index(**data)["score"] is None


def test_goal_split_validation():
    with pytest.raises(ValidationError):
        Race(name="Test", date=TODAY, goal_splits_seconds={"Run": -1})


def test_history_is_separate_and_survives_source_outage(tmp_path):
    data = evidence()
    store = AnalystStore(tmp_path)
    store.save_plan(data["plan"])
    store.save_race(Race.model_validate(data["race"]))
    with store.connect() as db:
        db.execute("CREATE TABLE predictions(race_id TEXT, day TEXT, body TEXT)")
        db.execute("INSERT INTO predictions VALUES(?,?,?)", ("race", TODAY.isoformat(), '{"total_seconds":4000}'))
    client = Mock()
    client.get_calendar.return_value = []
    client.get_workouts.return_value = data["workouts"]
    client.get_wellness_history.return_value = data["wellness"]
    service = TrainingAnalyst(client, store)
    summary = service.summary(TODAY)
    assert "race_predictions" not in summary
    assert summary["race_preparation"]["race"]["score"] is None
    saved = store.preparation_history("race")
    assert len(saved) == 1 and "total_seconds" not in saved[0]
    client.get_workouts.side_effect = RuntimeError("offline")
    service.summary(TODAY)
    assert store.preparation_history("race") == saved
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM predictions").fetchone()[0] == 1




def test_complete_triathlon_and_goal_budget():
    data = evidence()
    base = list(data["workouts"])
    for sport, distance in [("Swim", 1.9), ("Ride", 90)]:
        additions = [w.model_copy(update={"id": f"{sport}-{w.id}", "sport": sport,
                      "distance_km": distance, "weighted_avg_watts": 200}) for w in base]
        data["workouts"] += additions
        data["comparison"]["sessions"] += [
            dict(event=dict(id=w.id, date=w.start_time.date().isoformat(), duration_sec=1000,
                            tss=50, intensity_percent=80), status="completed", activity_id=w.id)
            for w in additions[:3]]
        data["plan"].sessions += [s.model_copy(update={"sport": sport, "distance_km": distance})
                                  for s in data["plan"].sessions if s.sport == "Run"]
    data["race"].update(sport="Triathlon", distances_km={"Swim": 1.9, "Ride": 90, "Run": 5},
                        target_seconds=3100, goal_splits_seconds={"Swim": 1000, "Ride": 1000, "Run": 1000},
                        transition_seconds=100)
    index = preparation_index(**data)
    assert index["score"] == 100
    data["race"]["target_seconds"] = 3000
    index = preparation_index(**data)
    assert index["score"] is None and index["components"]["goal"]["score"] is None


def test_negative_values_cannot_escape_index_bounds():
    from fitness.preparation import ratio
    assert ratio(-1, 1) == 0
    assert ratio(10, 1) == 100


def test_zero_wellness_observations_are_missing_not_recovery_evidence():
    data = evidence()
    for row in data["wellness"]:
        row.update(hrv=0, resting_hr=None, sleep_secs=0)
    assert preparation_index(**data)["components"]["tolerance"]["score"] is None


def test_missing_distances_do_not_count_as_bad_endurance():
    data = evidence()
    for w in data["workouts"]:
        w.distance_km = 0  # Existing activity mapping uses 0 when distance is unavailable.
    part = endurance(["Run"], data["workouts"], data["plan"], data["active"], 70, TODAY)
    assert part["score"] is None
    assert any("Ist-Distanzen" in reason for reason in part["missing"])
