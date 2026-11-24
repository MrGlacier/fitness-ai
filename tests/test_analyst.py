"""Synthetic deterministic analyst fixtures, no live API or model."""
from datetime import date, datetime, timedelta
import json
from math import exp
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from fitness.analyst import TrainingAnalyst
from fitness.analyst_models import PlanAssignment, Race, TrainingPlan
from fitness.archive import AnalystStore
from fitness.models import Workout
from fitness.plan_analysis import compare_sessions, recognize_plan
from fitness.projections import forecast_fitness
from intervals.intervals_client import IntervalsClient

TODAY = date(2026, 11, 18)


def plan(**changes):
    return TrainingPlan.model_validate(dict(id="test", name="Example Plan", sport="Triathlon",
        sessions=[dict(week=1, day=1, title="Build Week 1 Easy Run", sport="Run", phase="Build", duration_sec=3600)], **changes))


def event(key="1", **changes):
    return dict(id=key, date="2026-11-16", name="Build Week 1 Easy Run", sport="Run",
                category="WORKOUT", duration_sec=3600, tss=50, **changes)


def workout(key="a", day="2026-11-17", sport="Run", **changes):
    values = dict(id=key, name="Build Week 1 Easy Run", start_time=datetime.fromisoformat(day),
                  sport=sport, duration_sec=3500, distance_km=10, tss=48)
    values.update(changes)
    return Workout(**values)


def test_import_preserves_original_and_validates(tmp_path):
    store = AnalystStore(tmp_path / "store")
    source = tmp_path / "plan.json"
    source.write_text(plan().model_dump_json())
    original = source.read_bytes()
    imported = store.import_plan(source)
    assert imported.id == "test"
    assert next(store.originals.iterdir()).read_bytes() == original
    assert store.plans()[0] == imported
    with pytest.raises(ValidationError):
        TrainingPlan.model_validate({"id": "../bad", "name": "Bad", "sport": "Run", "sessions": []})


@pytest.mark.parametrize("suffix,content", [
    ("csv", "week,day,title,sport,tss\n1,2,Test Run,Run,0\n"),
    ("md", "| week | day | title | sport | tss |\n|---|---|---|---|---|\n|1|2|Test Run|Run|0|\n")])
def test_table_import(tmp_path, suffix, content):
    source = tmp_path / f"table.{suffix}"
    source.write_text(content)
    result = AnalystStore(tmp_path / "store").import_plan(source, {"id": "table", "name": "Table", "sport": "Run"})
    assert result.sessions[0].tss == 0


def test_pdf_preserved_requires_review(tmp_path):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"synthetic document")
    store = AnalystStore(tmp_path / "store")
    with pytest.raises(ValueError, match="reviewed"):
        store.import_plan(source)
    assert next(store.originals.iterdir()).read_bytes() == source.read_bytes()
    assert not store.plans()


def test_recognition_and_ambiguous_plan():
    p = plan()
    assert recognize_plan([p], [event()], TODAY)["active"]["week"] == 1
    other = p.model_copy(update={"id": "other"})
    result = recognize_plan([p, other], [event()], TODAY)
    assert result["status"] == "uncertain" and result["active"] is None
    assert recognize_plan([], [event()], TODAY)["status"] == "unavailable"


def test_manual_plan_assignment(tmp_path):
    store = AnalystStore(tmp_path)
    p = plan()
    store.save_plan(p)
    store.save_assignment(PlanAssignment(plan_id=p.id, start_date="2026-11-16", end_date="2026-11-22"))
    assert recognize_plan([p], [], TODAY, store.records("assignment"))["active"]["plan_id"] == p.id
    with pytest.raises(ValueError):
        store.save_assignment(PlanAssignment(plan_id="absent", start_date=TODAY, end_date=TODAY))


def test_moved_and_multiple_same_day():
    rows = compare_sessions([event(), dict(event("2"), sport="Ride")],
                            [workout(), workout("b", sport="Ride")], TODAY)["sessions"]
    assert [r["status"] for r in rows] == ["moved", "moved"]
    assert rows[0]["duration_delta_sec"] == -100
    assert rows[0]["tss_delta"] == -2


def test_pairing_and_ambiguity():
    w = workout(paired_event_id="2")
    rows = compare_sessions([event(), event("2")], [w], TODAY)["sessions"]
    assert rows[1]["activity_id"] == w.id
    assert rows[0]["status"] == "unmatched"
    rows = compare_sessions([event(), event("2")], [workout()], TODAY)["sessions"]
    assert all(r["status"] == "uncertain" for r in rows)


def test_forecast_math_and_missing_load():
    seed = dict(date="2026-11-15", ctl=40, atl=50)
    first = forecast_fitness(seed, [event()], date(2026, 11, 16))["points"][0]
    assert first["ctl"] == round(40 + 10 * (1-exp(-1/42)), 2)
    assert first["atl"] == 50
    assert first["tsb"] == round(40 + 10*(1-exp(-1/42)) - 50, 2)
    missing = dict(event(), tss=None)
    assert forecast_fitness(seed, [missing], TODAY)["points"][-1]["ctl"] is None
    estimated = dict(missing, intensity_percent=80)
    first = forecast_fitness(seed, [estimated], TODAY)["points"][0]
    assert first["tss"] == 64 and first["estimated_sessions"] == 1
    assert forecast_fitness(None, [], TODAY)["status"] == "unavailable"


def test_zero_load_is_known():
    seed = dict(date="2026-11-15", ctl=40, atl=50)
    assert forecast_fitness(seed, [dict(event(), tss=0)], TODAY)["status"] == "scenario"


def test_race_sync_preserves_goals(tmp_path):
    store = AnalystStore(tmp_path)
    original = store.save_race(Race(name="Test Race", date="2026-11-20", target_seconds=4000,
                                   performance_goal="Finish", transition_seconds=120))
    service = TrainingAnalyst(None, store)
    imported = dict(event(), name="Test Race", date="2026-11-20", category="RACE_A", distance_km=10)
    result = service.sync_races([imported, imported])
    assert len(result) == 1 and result[0]["id"] == original.id
    assert result[0]["source_id"] == "1" and result[0]["target_seconds"] == 4000
    result = service.sync_races([dict(imported, date="2026-11-21")])
    assert result[0]["date"] == "2026-11-21" and result[0]["performance_goal"] == "Finish"



def test_summary_without_llm_and_source_failure(tmp_path):
    client = Mock()
    client.get_calendar.side_effect = RuntimeError("offline")
    client.get_workouts.return_value = []
    client.get_wellness_history.return_value = []
    service = TrainingAnalyst(client, AnalystStore(tmp_path))
    service.store.save_race(Race(name="Local", date="2026-11-20"))
    summary = service.summary(TODAY)
    assert summary["next_race"]["name"] == "Local"
    assert "calendar" in summary["errors"]
    assert summary["fitness_forecast"]["status"] == "unavailable"


def test_calendar_contract():
    client = IntervalsClient.__new__(IntervalsClient)
    client.athlete_id = "synthetic"
    client._get = Mock(return_value=[dict(id=1, start_date_local="2026-11-18T10:00:00", category="WORKOUT",
                                        name="Test", type="Run", moving_time=3600, distance=10000, icu_training_load=0)])
    rows = client.get_calendar(TODAY, TODAY)
    assert rows[0]["distance_km"] == 10 and rows[0]["tss"] == 0
    assert client._get.call_args.args[1] == {"oldest": TODAY.isoformat(), "newest": TODAY.isoformat()}


def test_nonfinite_values_rejected():
    with pytest.raises(ValidationError):
        Race(name="Test", date=TODAY, target_seconds=float("nan"))
    with pytest.raises(ValidationError):
        Race(name="Test", date=TODAY, distances_km={"Run": -1})


def test_xlsx_import_scalar_table(tmp_path):
    from zipfile import ZipFile
    source = tmp_path / "plan.xlsx"
    headers = ["week", "day", "title", "sport"]
    rows = [headers, ["1", "2", "Test Run", "Run"]]
    xml = '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
    for index, row in enumerate(rows, 1):
        xml += '<row>' + ''.join(f'<c r="{chr(65+i)}{index}" t="inlineStr"><is><t>{v}</t></is></c>' for i, v in enumerate(row)) + '</row>'
    xml += '</sheetData></worksheet>'
    with ZipFile(source, "w") as book:
        book.writestr("xl/worksheets/sheet1.xml", xml)
    result = AnalystStore(tmp_path / "store").import_plan(source, {"id": "excel", "name": "Example", "sport": "Run"})
    assert result.sessions[0].day == 2


def test_stale_seed_uses_actual_not_planned(tmp_path):
    client = Mock()
    client.get_calendar.return_value = [dict(event(), tss=1000)]
    client.get_workouts.return_value = [workout(day="2026-11-16", tss=0)]
    client.get_wellness_history.return_value = [dict(date="2026-11-15", ctl=40, atl=50, tsb=-10)]
    result = TrainingAnalyst(client, AnalystStore(tmp_path)).summary(TODAY)
    point = result["fitness_forecast"]["points"][0]
    assert point["date"] == "2026-11-19"
    assert point["ctl"] == round(40 * exp(-4/42), 2)


def test_manual_assignment_wins_calendar_titles(tmp_path):
    p = plan()
    other = p.model_copy(update={"id": "other", "name": "Other"})
    assignment = dict(plan_id="test", start_date="2026-11-16", end_date="2026-11-22")
    result = recognize_plan([p, other], [dict(event(str(i)), name="Other Build Week 1") for i in range(10)], TODAY, [assignment])
    assert result["active"]["plan_id"] == "test"






def test_successful_api_gets_are_cached():
    from threading import RLock
    import httpx
    calls = []
    def respond(request):
        calls.append(request)
        return httpx.Response(200, json=[{"id": "synthetic"}])
    client = IntervalsClient.__new__(IntervalsClient)
    client.client = httpx.Client(base_url="https://example.test", transport=httpx.MockTransport(respond))
    client._cache, client._cache_lock = {}, RLock()
    result = client._get("/events", {"oldest": TODAY})
    result[0]["id"] = "changed"
    assert client._get("/events", {"oldest": TODAY})[0]["id"] == "synthetic"
    assert len(calls) == 1
    client.client.close()


def test_explicit_pairing_conflicts_remain_uncertain():
    activity = workout(paired_event_id="1")
    events = [event(), dict(event("2"), activity_id=activity.id)]
    for ordered in [events, list(reversed(events))]:
        rows = compare_sessions(ordered, [activity], TODAY)["sessions"]
        assert all(row["status"] == "uncertain" and row["activity_id"] is None for row in rows)
    # An explicit link outside the fetched calendar may not be stolen by a title match.
    result = compare_sessions([event()], [workout(paired_event_id="outside")], TODAY)
    assert result["sessions"][0]["status"] == "unmatched"


def test_local_calendar_date_overrides_utc_day():
    activity = workout(day="2026-11-15T23:30:00+00:00", local_date=date(2026, 11, 16))
    row = compare_sessions([event()], [activity], TODAY)["sessions"][0]
    assert row["status"] == "completed" and row["actual_date"] == "2026-11-16"


def test_wellness_and_calendar_reject_invalid_optional_values():
    client = IntervalsClient.__new__(IntervalsClient)
    client.athlete_id = "synthetic"
    client._get = Mock(return_value=[dict(id=TODAY.isoformat(), ctl="40", atl=50,
                                        hrv=-1, restingHR="invalid", sleepSecs=float("nan")),
                                    dict(id="not-a-date", ctl=1, atl=1)])
    history = client.get_wellness_history(TODAY, TODAY)
    assert len(history) == 1 and history[0]["tsb"] == -10
    assert all(history[0][key] is None for key in ["hrv", "resting_hr", "sleep_secs"])
    client._get.return_value = [dict(id=1, start_date_local=TODAY.isoformat(), moving_time="3600",
                                    icu_training_load=float("inf"), distance=-1)]
    row = client.get_calendar(TODAY, TODAY)[0]
    assert row["duration_sec"] == 3600 and row["tss"] is None and row["distance_km"] is None


def test_csv_multiline_description_is_preserved(tmp_path):
    source = tmp_path / "plan.csv"
    source.write_text('week,day,title,sport,description\n1,1,Test,Run,"first line\nsecond line"\n')
    imported = AnalystStore(tmp_path / "store").import_plan(source, {"id": "csv", "name": "Example", "sport": "Run"})
    assert imported.sessions[0].description == "first line\nsecond line"


def test_store_connection_is_closed_after_context(tmp_path):
    import sqlite3
    store = AnalystStore(tmp_path)
    with store.connect() as db:
        assert db.execute("SELECT 1").fetchone()[0] == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        db.execute("SELECT 1")


def test_forecast_is_bounded_by_fetched_calendar(tmp_path):
    client = Mock()
    client.get_calendar.return_value = []
    client.get_workouts.return_value = []
    client.get_wellness_history.return_value = [dict(date=TODAY.isoformat(), ctl=40, atl=50, tsb=-10)]
    service = TrainingAnalyst(client, AnalystStore(tmp_path))
    service.store.save_race(Race(name="Distant", date="2029-11-20"))
    forecast = service.summary(TODAY)["fitness_forecast"]
    assert len(forecast["points"]) == 365
    assert forecast["coverage_note"]
    assert forecast["points"][-1]["date"] == forecast["calendar_end"]


def test_latest_saved_assignment_wins_and_context_contains_week(tmp_path):
    store = AnalystStore(tmp_path)
    first = plan()
    second = first.model_copy(update={"id": "second", "name": "Second Plan"})
    store.save_plan(first)
    store.save_plan(second)
    store.save_assignment(PlanAssignment(plan_id=first.id, start_date="2026-11-09", end_date="2026-11-30"))
    store.save_assignment(PlanAssignment(plan_id=second.id, start_date="2026-11-16", end_date="2026-11-30"))
    context = TrainingAnalyst(None, store).local_plan_context(TODAY)
    assert context["plan_id"] == "second" and context["week"] == 1
    assert context["sessions"][0]["title"] == second.sessions[0].title
    assert "source_details" not in context["sessions"][0]
    assert context["recognition"]["selected_assignment"]["plan_id"] == "second"
    assert len(store.records("assignment")) == 2  # Ältere Zuordnungen bleiben erhalten.


def test_assignment_reasons_are_actionable():
    p = plan()
    future = dict(plan_id=p.id, start_date="2026-11-23", end_date="2026-12-30")
    result = recognize_plan([p], [], TODAY, [future])
    assert "Zukunft" in result["message"] and result["selected_assignment"] == future
    old = dict(future, start_date="2026-11-02", end_date="2026-11-08")
    assert "abgelaufen" in recognize_plan([p], [], TODAY, [old])["message"]
    invalid = dict(future, start_date="2026-11-02")
    assert "außerhalb" in recognize_plan([p], [], TODAY, [invalid])["message"]


def test_assignment_requires_monday(tmp_path):
    store = AnalystStore(tmp_path)
    store.save_plan(plan())
    with pytest.raises(ValueError, match="Montag"):
        store.save_assignment(PlanAssignment(plan_id="test", start_date="2026-11-17", end_date="2026-11-30"))


def test_local_chat_context_keeps_total_goal_and_goal_free_race(tmp_path):
    store = AnalystStore(tmp_path)
    store.save_race(Race(name="Example Triathlon", date="2027-04-10", target_seconds=18000))
    store.save_race(Race(name="Example Trail", date="2027-05-10", sport="TrailRun"))
    context = TrainingAnalyst(None, store).local_plan_context(TODAY)
    targets = {race["name"]: race["target_seconds"] for race in context["race_goals"]}
    assert targets == {"Example Triathlon": 18000, "Example Trail": None}
