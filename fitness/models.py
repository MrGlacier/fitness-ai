from datetime import datetime
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
    