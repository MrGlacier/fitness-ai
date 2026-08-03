from datetime import date, datetime
from pydantic import BaseModel, Field

class Workout(BaseModel):
    id: str
    name: str
    start_time: datetime
    sport: str
    distance_km: float
    duration_sec: int
    avg_hr: int | None = None
    tss: float | None = None
    intensity: float | None = None
    max_hr: int | None = None
    average_cadence: float | None = None
    elevation_gain: float | None = None
    decoupling: float | None = None
    weighted_avg_watts: float | None = None
    variability_index: float | None = None
    rpe: int | None = None
    comment: str | None = None
    workout_summary: str | None = None

class TrainingZones(BaseModel):
    types: list[str] = Field(default_factory=list)
    ftp: int | None = None
    indoor_ftp: int | None = None
    lthr: int | None = None
    max_hr: int | None = None
    threshold_pace: float | None = None
    pace_units: str | None = None
    power_zones: list[int] | None = None
    power_zone_names: list[str] | None = None
    hr_zones: list[int] | None = None
    hr_zone_names: list[str] | None = None
    pace_zones: list[float] | None = None
    pace_zone_names: list[str] | None = None

class Athlete(BaseModel):
    id: str
    name: str
    city: str | None = None
    email: str
    timezone: str

class TrainingStatus(BaseModel):
    date: date
    ctl: float | None = None
    atl: float | None = None
    form: float | None = None
    form_status: str | None = None
    summary: str | None = None
    resting_hr: int | None = None
    hrv: float | None = None
    sleep_secs: int | None = None
