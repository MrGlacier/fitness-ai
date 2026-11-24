"""Validated archive and local race inputs. All durations are seconds."""
from datetime import date
from math import isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AnalystModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class PlanSession(AnalystModel):
    week: int = Field(ge=1)
    day: int = Field(ge=1, le=7)
    title: str = Field(min_length=1)
    sport: str
    phase: str | None = None
    duration_sec: float | None = Field(default=None, ge=0)
    distance_km: float | None = Field(default=None, ge=0)
    intensity: str | None = None
    description: str = ""
    tss: float | None = Field(default=None, ge=0)
    notes: str = ""
    uncertainty: str | None = None
    source_details: dict = Field(default_factory=dict)


class TrainingPlan(AnalystModel):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    name: str = Field(min_length=1)
    sport: str
    start_date: date | None = None
    aliases: list[str] = Field(default_factory=list)
    description: str = ""
    source_format: str | None = None
    source_plan_id: str | None = None
    sessions: list[PlanSession] = Field(min_length=1)


class PlanAssignment(AnalystModel):
    plan_id: str
    start_date: date
    end_date: date


class Race(AnalystModel):
    id: str | None = None
    source_id: str | None = None
    name: str = Field(min_length=1, max_length=200)
    date: date
    sport: str = "Triathlon"
    distances_km: dict[str, float] = Field(default_factory=dict)
    target_seconds: float | None = Field(default=None, gt=0)
    goal_splits_seconds: dict[str, float] = Field(default_factory=dict)
    performance_goal: str | None = None
    priority: Literal["A", "B", "C"] | None = None
    status: Literal["planned", "completed", "cancelled"] = "planned"
    transition_seconds: float | None = Field(default=None, ge=0)
    elevation_gain_m: float | None = Field(default=None, ge=0)

    def model_post_init(self, context):
        if any(v <= 0 or not isfinite(v) for v in self.goal_splits_seconds.values()):
            raise ValueError("Goal splits must be finite and positive")
        if any(v <= 0 or not isfinite(v) for v in self.distances_km.values()):
            raise ValueError("Distances must be finite and positive")
