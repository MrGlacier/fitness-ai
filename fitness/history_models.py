"""Validated input for historical comparisons; dates are athlete-local calendar days."""
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, model_validator


class HistoryPeriod(BaseModel):
    start: date
    end: date
    race_date: date | None = None

    @model_validator(mode="after")
    def validate_range(self):
        if self.end < self.start or (self.end - self.start).days > 365:
            raise ValueError("Zeitraum muss 1 bis 366 Tage umfassen.")
        return self


class HistoryComparison(BaseModel):
    a: HistoryPeriod
    b: HistoryPeriod
    sport: Literal["all", "Ride", "Run", "Swim"] = "all"


class HistoricalPreparation(BaseModel):
    id: str = Field(pattern=r"^[\w-]{1,80}$")
    name: str = Field(min_length=1, max_length=120)
    start: date
    end: date
    race_date: date | None = None

    @model_validator(mode="after")
    def validate_range(self):
        if self.end < self.start:
            raise ValueError("Ende liegt vor dem Start.")
        return self


class HistoricalAssignment(BaseModel):
    reference: str = Field(min_length=1, max_length=150)
    preparation_id: str | None = Field(default=None, max_length=80)
    phase: str | None = Field(default=None, max_length=80)
    week: int | None = Field(default=None, ge=1, le=80)
