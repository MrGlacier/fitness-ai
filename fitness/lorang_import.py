"""Überträgt Lorang-Originalexporte ohne Kalender- oder LLM-Zugriff ins Archiv.

Feldnamen, Sportzuordnung und Einheiten folgen dem Parser und Mapper des
benachbarten Projekts lorang-intervals-converter. Das Archiv benötigt dessen
Intervals-Schritterzeugung nicht und bleibt ohne Laufzeitabhängigkeit nutzbar.
"""
from hashlib import sha256
import json
import re

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from fitness.analyst_models import PlanSession, TrainingPlan

SPORTS = {"RUN": "Run", "BIKE": "Ride", "SWIM": "Swim", "STRENGTH": "Strength"}


class SourceModel(BaseModel):
    """Validiert die für eine verlustfreie Zuordnung erforderlichen Quellfelder."""
    model_config = ConfigDict(allow_inf_nan=False)


class SourceDuration(SourceModel):
    time: float | None = Field(default=None, ge=0)
    distance: float | None = Field(default=None, ge=0)
    distanceType: str | None = None


class SourceWorkout(SourceModel):
    workoutTypeId: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str | None = None
    duration: SourceDuration | None = None


class SourceDay(SourceModel):
    dayNumber: int = Field(ge=1, le=7)
    orderOfDay: int | None = None
    workout: SourceWorkout


class SourceWeek(SourceModel):
    weekNumber: int = Field(ge=1)
    phase: str | None = None
    description: str | None = None
    days: list[SourceDay]
    notes: list = Field(default_factory=list)


class SourcePlan(SourceModel):
    id: str
    title: str = Field(min_length=1)
    sportType: str
    summary: str | None = None
    weeks: list[SourceWeek] = Field(min_length=1)


def phase_from_title(title: str) -> str | None:
    """Übernimmt nur einen ausdrücklich benannten, eindeutigen Phasenbegriff."""
    phases = {p.casefold() for p in re.findall(r"\b(Base|Build|Peak|Taper|Recovery)\b", title, re.I)}
    return next(iter(phases)).capitalize() if len(phases) == 1 else None


def import_lorang(data: dict) -> TrainingPlan:
    """Unterstützt direkte Pläne sowie die Hülle userTrainingPlan, keine Sample-Wochen."""
    raw = data.get("userTrainingPlan", data)
    try:
        plan = SourcePlan.model_validate(raw)
    except ValidationError as exc:
        locations = ", ".join(".".join(str(p) for p in e["loc"]) for e in exc.errors(include_input=False))
        raise ValueError(f"Ungültiger Lorang-Plan; erforderliche Angaben prüfen: {locations}") from exc
    week_numbers = [week.weekNumber for week in plan.weeks]
    if len(set(week_numbers)) != len(week_numbers):
        raise ValueError("Lorang-Plan enthält doppelte Wochennummern; Zuordnung muss geprüft werden.")

    # Dieselbe Plan-ID kann mehrere Revisionen besitzen. Identische Inhalte bleiben idempotent.
    identity = {key: raw.get(key) for key in ("id", "title", "sportType", "summary", "weeks")}
    digest = sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]
    title_phase = phase_from_title(plan.title)
    sessions = []
    for week, raw_week in sorted(zip(plan.weeks, raw["weeks"]), key=lambda pair: pair[0].weekNumber):
        ordered = sorted(enumerate(zip(week.days, raw_week["days"])),
                         key=lambda item: (item[1][0].dayNumber,
                                           item[1][0].orderOfDay if item[1][0].orderOfDay is not None else item[0]))
        for _, (day, raw_day) in ordered:
            workout = day.workout
            raw_workout = raw_day["workout"]
            duration = workout.duration
            warnings = []
            sport = SPORTS.get(workout.workoutTypeId, workout.workoutTypeId)
            if workout.workoutTypeId not in SPORTS:
                warnings.append("Sportart wurde unverändert übernommen; Zuordnung prüfen.")
            distance = None
            if duration and duration.distance is not None:
                if duration.distanceType == "km":
                    distance = duration.distance
                elif duration.distanceType == "m":
                    distance = duration.distance / 1000
                else:
                    warnings.append("Distanz ohne bekannte Einheit; Originalangabe in source_details erhalten.")
            notes = []
            if week.description:
                notes.append(f"Wochenbeschreibung: {week.description}")
            for note in week.notes:
                if isinstance(note, str):
                    notes.append(note)
                elif isinstance(note, dict) and note.get("dayNumber") in (None, day.dayNumber):
                    notes.append(json.dumps(note, ensure_ascii=False, sort_keys=True))
            # Details sind lesbar durchsuchbar; Rohstrukturen bleiben für spätere Auswertung erhalten.
            for key, label in [("nutrition", "Ernährung"), ("nutritionUnits", "Ernährungseinheiten")]:
                if raw_workout.get(key):
                    notes.append(f"{label}: " + json.dumps(raw_workout[key], ensure_ascii=False, sort_keys=True))
            if raw_day.get("gapAfterWorkout") is not None:
                notes.append(f"gapAfterWorkout laut Original (Minuten): {raw_day['gapAfterWorkout']}")
            if not week.phase and not title_phase:
                warnings.append("Trainingsphase nicht eindeutig angegeben.")
            intensity = {key: raw_workout[key] for key in ("metricTypeId", "metricValue", "hashtags") if raw_workout.get(key)}
            sessions.append(PlanSession(
                week=week.weekNumber, day=day.dayNumber, title=workout.name, sport=sport,
                phase=week.phase or title_phase,
                duration_sec=duration.time if duration else None, distance_km=distance,
                description=workout.description or "", notes="\n".join(notes),
                intensity=json.dumps(intensity, ensure_ascii=False, sort_keys=True) if intensity else None,
                source_details={"workout": raw_workout, "orderOfDay": day.orderOfDay,
                                "gapAfterWorkout": raw_day.get("gapAfterWorkout")},
                uncertainty=" ".join(warnings) if warnings else None,
            ))
    return TrainingPlan(id=f"lorang-{digest}", name=plan.title,
                        sport="Triathlon" if plan.sportType == "TRIATHLON" else plan.sportType,
                        description=plan.summary or "", source_format="lorang", source_plan_id=plan.id,
                        sessions=sessions)
