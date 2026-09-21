from datetime import date, datetime
from enum import Enum
import re

from pydantic import BaseModel, Field, field_validator, model_validator


# ------------------------------------------------------------------ #
# Training Today — strukturierte Empfehlung                        #
# ------------------------------------------------------------------ #


class SportType(str, Enum):
    """Mögliche Sportarten für die Empfehlung."""
    RUN = "Run"
    RIDE = "Ride"
    SWIM = "Swim"


class WorkoutType(str, Enum):
    """Maschinell lesbarer Workourttyp."""
    EASY = "easy"
    TEMPO = "tempo"
    THRESHOLD = "threshold"
    VO2 = "vo2"
    Z2 = "z2"
    TECHNIQUE = "technique"
    # Fallback, wenn kein Typ passt
    OTHER = "other"


class AlternativeCategory(str, Enum):
    """Kategorie einer Alternative — steuert auch UI-Färbung."""
    SWIM = "swim"
    HARD = "hard"
    EASY = "easy"


class Alternative(BaseModel):
    """Eine Alternative zur Hauptempfehlung."""
    category: AlternativeCategory
    sport: SportType
    title: str = Field(..., min_length=1, max_length=120)
    duration_min: int = Field(..., ge=1, le=480)
    details: str = Field(..., min_length=1, max_length=500)
    available: bool = True
    unavailable_reason: str | None = None

    @field_validator("unavailable_reason")
    @classmethod
    def validate_unavailable_reason(cls, v: str | None, info) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("unavailable_reason darf nicht leer sein, wenn available=False")
        if v is not None and info.data.get("available", True):
            raise ValueError("unavailable_reason sollte nur bei available=False gesetzt sein")
        return v

    @model_validator(mode="after")
    def validate_availability(self):
        if not self.available and self.unavailable_reason is None:
            raise ValueError("unavailable_reason ist bei available=False erforderlich")
        return self


class PrimaryRecommendation(BaseModel):
    """Die Hauptempfehlung für heute."""
    sport: SportType
    type: WorkoutType
    title: str = Field(..., min_length=1, max_length=120)
    duration_min: int = Field(..., ge=1, le=480)
    details: str = Field(..., min_length=1, max_length=800)


class TrainingTodayRecommendation(BaseModel):
    """Strukturierte Training-Heute-Empfehlung."""
    primary: PrimaryRecommendation
    alternatives: list[Alternative] = Field(..., min_length=3, max_length=6)
    reason: str = Field(..., min_length=10, max_length=500)
    warning: str | None = None

    @field_validator("alternatives")
    @classmethod
    def validate_alternatives(cls, v: list[Alternative]) -> list[Alternative]:
        categories = [alt.category for alt in v]
        # Mindestens eine Schwimmen-Alternative
        if AlternativeCategory.SWIM not in categories:
            raise ValueError("Mindestens eine Alternative muss die Kategorie 'swim' haben")
        # Mindestens eine harte Alternative
        if AlternativeCategory.HARD not in categories:
            raise ValueError("Mindestens eine Alternative muss die Kategorie 'hard' haben")
        # Mindestens eine lockere Alternative
        if AlternativeCategory.EASY not in categories:
            raise ValueError("Mindestens eine Alternative muss die Kategorie 'easy' haben")
        return v

    @model_validator(mode="after")
    def validate_evidence_based_language(self):
        texts = [
            self.primary.title,
            self.primary.details,
            self.reason,
            self.warning or "",
        ]
        for alternative in self.alternatives:
            texts.extend([
                alternative.title,
                alternative.details,
                alternative.unavailable_reason or "",
            ])

        combined = " ".join(texts).casefold()
        unsupported_claims = (
            "verletzungsrisiko",
            "nervensystem",
            "erholung verzögern",
            "erholung verzögert",
        )
        if any(claim in combined for claim in unsupported_claims):
            raise ValueError("medizinische oder kausale Risikoaussage ist nicht ausreichend belegt")

        isolated_atl_patterns = (
            r"\batl(?:-wert)?\s+(?:von\s+|mit\s+)?\d+(?:[.,]\d+)?\s+ist\s+(?:zu\s+|sehr\s+)?hoch\b",
            r"\batl\s+ist\s+(?:mit\s+|bei\s+)?\d+(?:[.,]\d+)?\s+(?:zu\s+|sehr\s+)?hoch\b",
            r"\batl\s+ist\s+(?:zu\s+|sehr\s+)?hoch\b",
            r"\b(?:zu\s+|sehr\s+)?hohe[rn]?\s+atl\b",
        )
        if any(re.search(pattern, combined) for pattern in isolated_atl_patterns):
            raise ValueError("ATL darf nicht isoliert als hoch oder zu hoch bewertet werden")

        return self


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
