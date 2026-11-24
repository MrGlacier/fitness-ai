"""Synthetische Lorang-Exporte für Direktimport, Erhaltung und CLI-Abläufe."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

from fitness.archive import AnalystStore, read_plan
from fitness.import_plan import main
from fitness.lorang_import import import_lorang


def source_plan():
    return dict(id="example-plan", title="Example Build", sportType="TRIATHLON", summary="Planabsicht",
                weeks=[dict(weekNumber=1, phase=None, description="Wochenabsicht",
                            notes=[dict(dayNumber=1, title="Hinweis", note="Originalhinweis")],
                            days=[dict(dayNumber=1, orderOfDay=2, gapAfterWorkout=0,
                                       workout=dict(workoutTypeId="RUN", name="Original Run", description="Originalbeschreibung",
                                                    duration=dict(time=3600), metricTypeId="thresholdPace",
                                                    segments=[dict(type="active", values=[dict(rangeMin=80, rangeMax=90)])],
                                                    nutrition={"workout": {"carb": 40}},
                                                    nutritionUnits={"workout": {"carbUnit": "g/h"}})),
                                  dict(dayNumber=1, orderOfDay=1, gapAfterWorkout=120,
                                       workout=dict(workoutTypeId="BIKE", name="Original Ride", duration=dict(time=7200))),
                                  dict(dayNumber=2, orderOfDay=1,
                                       workout=dict(workoutTypeId="SWIM", name="Original Swim", duration=dict(distance=2.5, distanceType="km"))),
                                  dict(dayNumber=3, orderOfDay=1,
                                       workout=dict(workoutTypeId="STRENGTH", name="Original Strength", sets=[{"repetitions": 10}]))])])


def write_source(path: Path, data: dict | None = None):
    path.write_text(json.dumps(data or source_plan(), ensure_ascii=False))
    return path


def test_direct_and_wrapped_exports_have_identical_identity_and_preserve_source():
    source = source_plan()
    original = deepcopy(source)
    plan = import_lorang(source)
    assert plan == import_lorang(dict(sampleWeeks=[9], userTrainingPlan=source))
    assert source == original
    assert plan.source_plan_id == "example-plan" and plan.source_format == "lorang"
    assert plan.description == "Planabsicht"
    assert [s.sport for s in plan.sessions] == ["Ride", "Run", "Swim", "Strength"]
    assert [s.phase for s in plan.sessions] == ["Build"]*4
    assert plan.sessions[0].duration_sec == 7200
    run, swim, strength = plan.sessions[1:]
    assert run.title == "Original Run" and run.description == "Originalbeschreibung"
    assert run.source_details["workout"]["segments"] == source["weeks"][0]["days"][0]["workout"]["segments"]
    assert "Originalhinweis" in run.notes and "g/h" in run.notes
    assert "120" in plan.sessions[0].notes
    assert swim.distance_km == 2.5 and swim.duration_sec is None
    assert strength.duration_sec is None and strength.source_details["workout"]["sets"] == [{"repetitions": 10}]
    assert all(s.tss is None for s in plan.sessions)


def test_content_revisions_are_not_overwritten_and_private_author_does_not_change_identity(tmp_path):
    source = source_plan()
    first = write_source(tmp_path / "first.json", source)
    store = AnalystStore(tmp_path / "archive")
    a = store.import_plan(first)
    source["author"] = {"name": "Synthetic Author"}
    assert import_lorang(source).id == a.id
    source["weeks"][0]["days"][0]["workout"]["duration"]["time"] = 4200
    second = write_source(tmp_path / "second.json", source)
    b = store.import_plan(second)
    assert a.id != b.id
    assert len(store.plans()) == 2
    assert store.import_plan(first).id == a.id and len(store.plans()) == 2
    assert first.read_bytes() in [p.read_bytes() for p in store.originals.iterdir()]


def test_explicit_phase_wins_and_unknown_phase_is_marked():
    data = source_plan()
    data["weeks"][0]["phase"] = "Recovery"
    assert import_lorang(data).sessions[0].phase == "Recovery"
    data["title"] = "Example"
    data["weeks"][0]["phase"] = None
    result = import_lorang(data)
    assert result.sessions[0].phase is None
    assert "Trainingsphase" in result.sessions[0].uncertainty


def test_unknown_distance_units_are_not_guessed():
    data = source_plan()
    swim = data["weeks"][0]["days"][2]["workout"]
    swim["duration"]["distanceType"] = "yards"
    result = import_lorang(data).sessions[2]
    assert result.distance_km is None and result.uncertainty
    assert result.source_details["workout"]["duration"]["distance"] == 2.5
    swim["duration"] = dict(distance=2500, distanceType="m")
    assert import_lorang(data).sessions[2].distance_km == 2.5


@pytest.mark.parametrize("change", ["day", "week", "duration", "empty", "duplicates"])
def test_invalid_plan_rejected_without_guessed_assignments(change):
    data = source_plan()
    if change == "day":
        data["weeks"][0]["days"][0]["dayNumber"] = 8
    elif change == "week":
        data["weeks"][0]["weekNumber"] = 0
    elif change == "duration":
        data["weeks"][0]["days"][0]["workout"]["duration"]["time"] = -1
    elif change == "duplicates":
        data["weeks"].append(deepcopy(data["weeks"][0]))
    else:
        data["weeks"] = []
    with pytest.raises(ValueError):
        import_lorang(data)


def test_invalid_source_does_not_replace_valid_plan(tmp_path):
    path = write_source(tmp_path / "original.json")
    store = AnalystStore(tmp_path / "archive")
    good = store.import_plan(path)
    path.write_text(json.dumps({"userTrainingPlan": None}))
    with pytest.raises(ValueError):
        store.import_plan(path)
    assert store.plans() == [good]


def test_converted_intervals_export_has_actionable_error(tmp_path):
    path = write_source(tmp_path / "converted.json", {"name": "Example", "weeks": []})
    with pytest.raises(ValueError, match="ursprüngliche Lorang"):
        read_plan(path)


def test_cli_folder_dry_run_and_import(tmp_path, monkeypatch, capsys):
    folder = tmp_path / "input"
    folder.mkdir()
    path = write_source(folder / "TC Example.json")
    write_source(folder / "converted.json", {"name": "Example", "weeks": []})
    archive = tmp_path / "archive"
    monkeypatch.setenv("FITNESS_DATA_DIR", str(archive))
    monkeypatch.setattr(sys, "argv", ["import", str(folder), "--pattern", "TC*.json", "--dry-run"])
    assert main() == 0 and not archive.exists()
    assert "1 erfolgreich" in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["import", str(folder), "--pattern", "TC*.json"])
    assert main() == 0
    store = AnalystStore(archive)
    assert len(store.plans()) == 1
    assert next(store.originals.iterdir()).read_bytes() == path.read_bytes()
    assert main() == 0 and len(store.plans()) == 1


def test_cli_continues_after_invalid_file_and_returns_failure(tmp_path, monkeypatch, capsys):
    write_source(tmp_path / "good.json")
    (tmp_path / "bad.json").write_text("invalid-json")
    monkeypatch.setenv("FITNESS_DATA_DIR", str(tmp_path / "archive"))
    monkeypatch.setattr(sys, "argv", ["import", str(tmp_path), "--dry-run"])
    assert main() == 1
    output = capsys.readouterr()
    assert "1 erfolgreich, 1 fehlgeschlagen" in output.out
    assert "bad.json" in output.err
    assert not (tmp_path / "archive").exists()


def test_cli_empty_directory_returns_nonzero(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["import", str(tmp_path), "--dry-run"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code != 0
