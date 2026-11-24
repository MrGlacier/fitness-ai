"""Application orchestration, independent of the LLM and MCP transport."""
from datetime import date, timedelta
import json

from core.logger import logger
from fitness.archive import AnalystStore
from fitness.analyst_models import Race
from fitness.plan_analysis import compare_sessions, normalized, recognize_plan, workout_date, build_plan_context
from fitness.projections import forecast_fitness
from fitness.preparation import preparation_index


class TrainingAnalyst:
    def __init__(self, client, store: AnalystStore | None = None):
        self.client = client
        self.store = store or AnalystStore()

    def sync_races(self, events: list[dict]) -> list[dict]:
        races = self.store.records("race")
        for event in events:
            if event.get("category") not in {"RACE_A", "RACE_B", "RACE_C"}:
                continue
            source_id = event["id"]
            matches = [r for r in races if r.get("source_id") == source_id]
            if not matches:
                matches = [r for r in races if not r.get("source_id") and r["date"] == event["date"]
                           and normalized(r["name"]) == normalized(event["name"])]
            if len(matches) > 1:
                continue  # Ambiguous local records require explicit source_id assignment.
            if matches:
                race = matches[0]
                race.update(source_id=source_id, name=event["name"], date=event["date"])
            else:
                distances = {event["sport"]: event["distance_km"]} if event.get("distance_km") and "tri" not in event["sport"].casefold() else {}
                race = Race(id=f"intervals-{source_id}", source_id=source_id, name=event["name"],
                            date=event["date"], sport=event["sport"] or "Unknown",
                            distances_km=distances, priority=event["category"][-1]).model_dump(mode="json")
                races.append(race)
            self.store.save_race(Race.model_validate(race))
        return sorted(races, key=lambda r: (r["date"], r["id"]))

    def local_plan_context(self, today: date | None = None) -> dict:
        """Liest manuelle Planzuordnungen ohne Intervals- oder LLM-Abfrage."""
        today = today or date.today()
        plans = self.store.plans()
        assignments = self.store.records("assignment")
        recognition = recognize_plan(plans, [], today, assignments)
        result = build_plan_context(plans, recognition)
        result["recognition"] = recognition
        result["race_goals"] = [
            {key: race.get(key) for key in ("name", "date", "sport", "target_seconds", "performance_goal")}
            for race in self.store.records("race") if race.get("status") == "planned"
        ]
        return result

    def summary(self, today: date | None = None) -> dict:
        today = today or date.today()
        errors = []

        def load(label, function, fallback):
            try:
                return function()
            except Exception:
                # Isolate source failures without logging private response bodies.
                logger.warning("Analyst source unavailable: %s", label)
                errors.append(label)
                return fallback

        start = today - timedelta(days=56)
        events = load("calendar", lambda: self.client.get_calendar(start, today + timedelta(days=365)), [])
        workouts = load("activities", lambda: self.client.get_workouts(today - timedelta(days=180), today), [])
        history = load("wellness", lambda: self.client.get_wellness_history(start, today), [])
        history = sorted([r for r in history if r["date"] <= today.isoformat()], key=lambda r: r["date"])
        local_races = load("local races", lambda: self.store.records("race"), [])
        races = load("races", lambda: self.sync_races(events), local_races)
        upcoming = [r for r in races if r["date"] >= today.isoformat() and r["status"] == "planned"]
        next_race = upcoming[0] if upcoming else None
        horizon = max(today + timedelta(days=42), date.fromisoformat(next_race["date"])) if next_race else today + timedelta(days=42)
        plans = load("plan archive", self.store.plans, [])
        training = [e for e in events if e["category"] in {"WORKOUT", "RACE_A", "RACE_B", "RACE_C"}]
        monday = today - timedelta(days=today.weekday())
        week_end = monday + timedelta(days=6)
        comparison = compare_sessions(training, workouts, today)
        week_rows = [r for r in comparison["sessions"] if monday.isoformat() <= r["event"]["date"] <= week_end.isoformat()]
        week_workouts = [w for w in workouts if monday <= workout_date(w) <= week_end]
        week_events = [r["event"] for r in week_rows]
        seed = next((r for r in reversed(history) if r.get("ctl") is not None and r.get("atl") is not None), None)
        if seed and seed["date"] < today.isoformat():
            if "activities" in errors:
                seed = None
            else:
                # A dated seed represents end-of-day load, so start on the following day.
                observed = [dict(date=workout_date(w).isoformat(), tss=w.tss)
                            for w in workouts if seed["date"] < workout_date(w).isoformat() <= today.isoformat()]
                bridge = forecast_fitness(seed, observed, today)
                last = bridge.get("final_state")
                seed = last if last and last["ctl"] is not None else None
        calendar_end = today + timedelta(days=365)
        projection = forecast_fitness(seed, training, min(horizon, calendar_end)) if "calendar" not in errors else {"points": [], "status": "unavailable", "reason": "Calendar unavailable"}
        projection["requested_end"] = horizon.isoformat()
        projection["calendar_end"] = calendar_end.isoformat()
        if horizon > calendar_end:
            projection["coverage_note"] = "Prognose endet am abgerufenen Kalenderhorizont; bis zum Wettkampf fehlen Planwerte."
        assignments = load("plan assignments", lambda: self.store.records("assignment"), [])
        recognition = recognize_plan(plans, training, today, assignments)
        active = recognition["active"]
        active_plan = next((p for p in plans if active and p.id == active["plan_id"]), None)
        preparation = {}
        for race in races:
            index = preparation_index(race, workouts, comparison, history, active_plan, active, today, errors)
            if not errors:
                with self.store.connect() as db:
                    db.execute("INSERT OR REPLACE INTO preparation_history VALUES(?,?,?)",
                               (race["id"], today.isoformat(), json.dumps(index)))
            # Old race-time predictions remain private and are never mixed into the new series.
            history_points = [
                {key: point.get(key) for key in ("day", "score", "label", "model_version", "data_quality", "target_seconds")}
                for point in self.store.preparation_history(race["id"])[-90:]
            ]
            preparation[race["id"]] = dict(index, history=history_points)
        weekly = []
        for offset in range(7, -1, -1):
            begin = monday - timedelta(weeks=offset)
            finish = begin + timedelta(days=6)
            planned = [e for e in training if begin.isoformat() <= e["date"] <= finish.isoformat()]
            actual = [w for w in workouts if begin <= workout_date(w) <= min(finish, today)]
            weekly.append(dict(start=begin.isoformat(), planned_sessions=len(planned), actual_sessions=len(actual),
                               planned_duration_sec=sum(e.get("duration_sec") or 0 for e in planned),
                               actual_duration_sec=sum(w.duration_sec for w in actual),
                               planned_tss=sum(e["tss"] for e in planned) if all(e.get("tss") is not None for e in planned) else None,
                               actual_tss=sum(w.tss for w in actual) if all(w.tss is not None for w in actual) else None))
        intensity = {"below_80_percent": 0, "80_to_100_percent": 0, "above_100_percent": 0, "unknown": 0}
        for w in week_workouts:
            key = "unknown" if w.intensity is None else "below_80_percent" if w.intensity < 80 else "80_to_100_percent" if w.intensity <= 100 else "above_100_percent"
            intensity[key] += w.duration_sec
        valid = [r for r in history if r.get("ctl") is not None and r.get("atl") is not None]
        trend = {"ctl_delta": round(valid[-1]["ctl"] - valid[0]["ctl"], 2),
                 "atl_delta": round(valid[-1]["atl"] - valid[0]["atl"], 2),
                 "from": valid[0]["date"], "to": valid[-1]["date"]} if len(valid) >= 2 else None
        return dict(date=today.isoformat(), errors=errors, races=races, next_race=next_race,
                    days_to_race=(date.fromisoformat(next_race["date"]) - today).days if next_race else None,
                    plan=recognition, plan_context=build_plan_context(plans, recognition),
                    available_plans=[dict(id=p.id, name=p.name, total_weeks=max(s.week for s in p.sessions)) for p in plans],
                    week=dict(start=monday.isoformat(), sessions=week_rows, actual_sessions=len(week_workouts),
                              planned_sessions=len(week_events), planned_duration_sec=sum(e.get("duration_sec") or 0 for e in week_events),
                              missing_duration=sum(e.get("duration_sec") is None for e in week_events),
                              actual_duration_sec=sum(w.duration_sec for w in week_workouts),
                              planned_tss=sum(e["tss"] for e in week_events) if all(e.get("tss") is not None for e in week_events) else None,
                              actual_tss=sum(w.tss for w in week_workouts) if all(w.tss is not None for w in week_workouts) else None,
                              intensity_duration_sec=intensity),
                    comparison=comparison, weekly_comparison=weekly, fitness_history=history,
                    fitness_trend=trend, fitness_forecast=projection, race_preparation=preparation)
