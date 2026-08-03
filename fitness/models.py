from datetime import date, datetime
from pydantic import BaseModel, Field


class WorkoutSplit(BaseModel):
    index: int
    label: str | None = None
    split_type: str | None = None
    distance_km: float | None = None
    duration_sec: int | None = None
    pace_sec_per_km: float | None = None
    avg_speed_kmh: float | None = None
    avg_hr: int | None = None
    max_hr: int | None = None
    avg_watts: float | None = None
    avg_cadence: float | None = None
    elevation_gain: float | None = None


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
    comparison_summary: str | None = None
    similar_avg_hr: float | None = None
    similar_avg_rpe: float | None = None
    similar_avg_intensity: float | None = None
    similar_workouts_count: int = 0
    splits: list[WorkoutSplit] = Field(default_factory=list)
    detail_summary: str | None = None
    recovery_summary: str | None = None
    days_since_previous_same_sport: int | None = None


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
    sleep_quality: int | None = None
    sleep_score: float | None = None
    readiness: float | None = None
