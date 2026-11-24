"""Deterministic plan recognition and conservative one-to-one activity matching."""
from datetime import date, timedelta
from difflib import SequenceMatcher
import re

from fitness.analyst_models import TrainingPlan


def normalized(value: str) -> str:
    return " ".join(re.findall(r"[^\W_]+", value.casefold()))


def sport_family(value: str) -> str:
    value = value.casefold()
    for key, aliases in {"Run": ("run", "lauf"), "Ride": ("ride", "bike", "rad"),
                         "Swim": ("swim", "schwimm")}.items():
        if any(alias in value for alias in aliases):
            return key
    return value


def workout_date(workout) -> date:
    """Intervals calendar dates are local, while start_time can be UTC."""
    return getattr(workout, "local_date", None) or workout.start_time.date()


def recognize_plan(plans: list[TrainingPlan], events: list[dict], today: date,
                   assignments: list[dict] = ()) -> dict:
    monday = today - timedelta(days=today.weekday())
    current = [e for e in events if monday.isoformat() <= e["date"] <= (monday + timedelta(days=6)).isoformat()]
    manual = [a for a in assignments if a["start_date"] <= today.isoformat() <= a["end_date"]]
    selected = max(manual or assignments, key=lambda a: a.get("updated_at", a["start_date"]), default=None)
    context = dict(assignments=list(assignments), selected_assignment=selected)
    if manual:
        manual = [selected]
    candidates = []
    for plan in plans:
        if manual and plan.id not in {a["plan_id"] for a in manual}:
            continue
        votes: dict[int, float] = {}
        reasons = []
        start = plan.start_date
        matching_manual = [a for a in manual if a["plan_id"] == plan.id]
        if matching_manual:
            start = date.fromisoformat(matching_manual[-1]["start_date"])
            reasons.append("manual")
        if start:
            week = (monday - (start - timedelta(days=start.weekday()))).days // 7 + 1
            if 1 <= week <= max(s.week for s in plan.sessions):
                votes[week] = 10 if matching_manual else 1
                reasons.append("calendar")
        for event in ([] if matching_manual else current):
            title = normalized(event["name"])
            week_match = re.search(r"\b(?:week|woche|wk|w)\s*(\d+)\b", title)
            explicit_week = int(week_match[1]) if week_match else None
            name_match = any(normalized(n) in title for n in [plan.name, *plan.aliases] if n.strip())
            for week in sorted({s.week for s in plan.sessions}):
                sessions = [s for s in plan.sessions if s.week == week]
                phase_match = any(s.phase and normalized(s.phase) in title for s in sessions)
                title_match = any(
                    sport_family(s.sport) == sport_family(event.get("sport", ""))
                    and SequenceMatcher(None, normalized(s.title), title).ratio() >= .72
                    for s in sessions if not s.uncertainty
                )
                if explicit_week and explicit_week != week:
                    continue
                score = 3 * name_match + 2 * phase_match + 2 * title_match
                if score:
                    votes[week] = votes.get(week, 0) + score
                    reasons.append("calendar title / archive")
        for week, score in votes.items():
            phases = list(dict.fromkeys(s.phase for s in plan.sessions if s.week == week and s.phase))
            later = [s.phase for s in plan.sessions if s.week > week and s.phase and s.phase not in phases]
            candidates.append(dict(plan_id=plan.id, name=plan.name, week=week, phases=phases,
                                   total_weeks=max(s.week for s in plan.sessions),
                                   elapsed_weeks=week - 1, next_phase=later[0] if later else None,
                                   score=score, evidence=sorted(set(reasons))))
    candidates.sort(key=lambda c: (-c["score"], c["plan_id"], c["week"]))
    if not candidates:
        reason = "Noch keine Planzuordnung gespeichert. Plan und Start der Planwoche 1 festlegen."
        if selected:
            if selected["start_date"] > today.isoformat():
                reason = "Die gespeicherte Zuordnung beginnt erst in der Zukunft."
            elif selected["end_date"] < today.isoformat():
                reason = "Die gespeicherte Zuordnung ist abgelaufen."
            elif selected["plan_id"] not in {p.id for p in plans}:
                reason = "Der zugeordnete Plan fehlt im lokalen Archiv."
            else:
                reason = "Das Startdatum liegt außerhalb der vorhandenen Planwochen. Bitte Start der Planwoche 1 prüfen."
        return dict(status="unavailable", active=None, candidates=[], message=reason,
                    observed_titles=[e["name"] for e in current[:10]], **context)
    ambiguous = len(candidates) > 1 and candidates[0]["score"] - candidates[1]["score"] < 2
    uncertain = candidates[0]["score"] < 3 or ambiguous
    message = "Mehrere Planvarianten passen zum Kalender. Eine manuelle Zuordnung schafft Klarheit." if uncertain else "Plan aus dem Kalender erkannt."
    if manual and not uncertain:
        message = "Manuelle Zuordnung gespeichert und aktuell aktiv."
    return dict(status="uncertain" if uncertain else "matched", active=None if uncertain else candidates[0],
                candidates=candidates[:8], message=message, **context)


def compare_sessions(events: list[dict], workouts: list, today: date) -> dict:
    """Explicit pairing wins; fallback requires sport, name and a unique candidate."""
    matches = {}
    used = set()
    explicit_proposals = {}
    for event in events:
        explicit_proposals[event["id"]] = [
            w for w in workouts if str(getattr(w, "paired_event_id", "")) == event["id"]
            or w.id == event.get("activity_id")]
    explicit_ids = {w.id for values in explicit_proposals.values() for w in values}
    for event_id, possible in explicit_proposals.items():
        if len(possible) == 1 and sum(any(w.id == possible[0].id for w in values)
                                     for values in explicit_proposals.values()) == 1:
            matches[event_id] = (possible[0], "paired")
            used.add(possible[0].id)
    proposals = {}
    for event in events:
        if event["id"] in matches:
            continue
        if explicit_proposals[event["id"]]:
            proposals[event["id"]] = explicit_proposals[event["id"]]
            continue
        possible = []
        for w in workouts:
            if w.id in explicit_ids or getattr(w, "paired_event_id", None) is not None:
                continue
            if sport_family(w.sport) != sport_family(event.get("sport", "")):
                continue
            delta = abs((workout_date(w) - date.fromisoformat(event["date"])).days)
            similarity = SequenceMatcher(None, normalized(event["name"]), normalized(w.name)).ratio()
            if delta <= 3 and similarity >= .72:
                possible.append(w)
        proposals[event["id"]] = possible
    for key, possible in proposals.items():
        if explicit_proposals[key]:
            continue
        if len(possible) == 1 and sum(any(w.id == possible[0].id for w in values)
                                     for values in proposals.values()) == 1:
            matches[key] = (possible[0], "name/sport/date")
            used.add(possible[0].id)
    rows = []
    for event in events:
        match = matches.get(event["id"])
        w = match[0] if match else None
        if w:
            status = "moved" if workout_date(w).isoformat() != event["date"] else "completed"
        elif proposals.get(event["id"]):
            status = "uncertain"
        else:
            status = "unmatched" if event["date"] < today.isoformat() else "planned"
        rows.append(dict(event=event, status=status, activity_id=w.id if w else None,
                         actual_date=workout_date(w).isoformat() if w else None,
                         actual_duration_sec=w.duration_sec if w else None,
                         actual_tss=w.tss if w else None,
                         duration_delta_sec=w.duration_sec - event["duration_sec"]
                         if w and event.get("duration_sec") is not None else None,
                         tss_delta=w.tss - event["tss"] if w and w.tss is not None and event.get("tss") is not None else None,
                         evidence=match[1] if match else None))
    return {"sessions": rows, "unplanned_activity_ids": [w.id for w in workouts if w.id not in used],
            "note": "Unmatched means no reliable match; it does not prove a missed workout."}


def build_plan_context(plans: list[TrainingPlan], recognition: dict) -> dict:
    """Kompakte archivierte Wocheninhalte samt expliziter Herkunft für Dashboard und Chat."""
    active = recognition.get("active")
    plan = next((p for p in plans if active and p.id == active["plan_id"]), None)
    if not plan:
        return dict(status="unavailable", message=recognition.get("message"), sessions=[])
    sessions = [s.model_dump(mode="json", exclude={"source_details"})
                for s in plan.sessions if s.week == active["week"]]
    for session in sessions:
        session["description"] = session["description"][:600]
        session["notes"] = session["notes"][:400]
    return dict(status="available", source="local_plan_archive", plan_id=plan.id, name=plan.name,
                week=active["week"], phases=active["phases"], description=plan.description[:600],
                sessions=sessions, note="Archivvorgaben sind Trainingsabsichten. Der Intervals-Kalender bleibt führend für Termine und Soll/Ist.")
