from datetime import datetime
from pydantic import BaseModel

class Workout(BaseModel):
    id: str
    name: str
    start_time: datetime
    sport: str
    distance_km: float
    duration_sec: int
    avg_hr: int | None = None
    tss: float | None = None

class Athlete(BaseModel):
    id: str
    name: str
    city: str
    email: str
    timezone: str
    icu_ftp: int | None = None
    threshold_hr: int | None = None

class TrainingZones(BaseModel):
    sport: str
    ftp: int | None = None
    threshold_hr: int | None = None
    threshold_pace: float | None = None