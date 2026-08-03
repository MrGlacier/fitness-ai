from datetime import date

from fitness.models import Workout, TrainingStatus

from core.logger import logger

class FitnessAnalyzer:
    def __init__(self, intervals_client):
        self.intervals_client_instance = intervals_client

    def get_current_ftp(self, sport_type: str | None = None) -> dict:
        #logger.info("getcurrent_ftp: %s", sport_type)
        training_zones = self.intervals_client_instance.get_training_zones(sport_type)
        return dict(
            sport_type = training_zones[0].types[0],
            ftp = training_zones[0].ftp or None
        )

    def get_current_training_status(self, for_date: date) -> TrainingStatus | None:
        training_status = self.intervals_client_instance.get_current_training_status(for_date)

        if training_status is None:
            return None

        if training_status.ctl is None or training_status.atl is None:
            return training_status

        training_status.form = round(training_status.ctl - training_status.atl, 2)

        if training_status.form >= 15:
            training_status.form_status = "sehr frisch"
            training_status.summary = "Du bist aktuell sehr frisch und gut erholt. Deine kurzfristige Trainingsbelastung liegt deutlich unter deiner langfristigen Belastung."

        elif training_status.form >= 5:
            training_status.form_status = "frisch"
            training_status.summary = "Du bist aktuell gut erholt. Deine kurzfristige Trainingsbelastung liegt etwas unter deiner langfristigen Belastung."

        elif training_status.form >= -5:
            training_status.form_status = "ausgeglichen"
            training_status.summary = "Deine kurzfristige und langfristige Trainingsbelastung sind aktuell nahezu ausgeglichen."

        elif training_status.form >= -10:
            training_status.form_status = "leicht ermüdet"
            training_status.summary = "Deine kurzfristige Trainingsbelastung liegt leicht über deiner langfristigen Belastung. Eine lockere Einheit könnte sinnvoll sein."

        elif training_status.form >= -20:
            training_status.form_status = "ermüdet"
            training_status.summary = "Deine kurzfristige Trainingsbelastung liegt deutlich über deiner langfristigen Belastung. Zusätzliche intensive Einheiten solltest du gut abwägen."

        elif training_status.form >= -30:
            training_status.form_status = "stark ermüdet"
            training_status.summary = "Deine kurzfristige Trainingsbelastung ist sehr hoch. Erholung sollte momentan Priorität haben."

        else:
            training_status.form_status = "extrem ermüdet"
            training_status.summary = "Du befindest dich aktuell in einer sehr hohen Belastungsphase. Erholung ist dringend zu empfehlen."

        return training_status

    def get_last_workout(self, sport_type: str) -> Workout | None:
        workout = self.intervals_client_instance.get_last_workout(sport_type)

        if workout is None:
            return None

        if workout.sport == "Run":
            if (
                workout.duration_sec >= 5300
                and workout.intensity is not None
                and workout.intensity < 80
                and workout.decoupling is not None
                and workout.decoupling < 5
            ):
                workout.workout_summary = (
                    "Langer und sehr gleichmäßig absolvierter Lauf mit moderater Intensität. "
                    "Die geringe aerobe Entkopplung spricht für eine stabile "
                    "Belastungsverträglichkeit über die Dauer der Einheit."
                )

            elif workout.intensity is not None and workout.intensity >= 85:
                workout.workout_summary = (
                    "Intensiver Lauf mit hoher relativer Belastung."
                )

            elif (
                workout.variability_index is not None
                and workout.variability_index <= 1.05
            ):
                workout.workout_summary = (
                    "Gleichmäßig absolvierter Lauf mit moderater relativer Belastung."
                )

            else:
                workout.workout_summary = (
                    "Laufeinheit mit moderater relativer Belastung."
                )

        elif workout.sport == "Ride":
            if (
                workout.duration_sec >= 7200
                and workout.intensity is not None
                and workout.intensity < 75
                and workout.decoupling is not None
                and workout.decoupling < 5
            ):
                workout.workout_summary = (
                    "Lange und kontrolliert absolvierte Radeinheit mit moderater Intensität. "
                    "Die geringe aerobe Entkopplung spricht für eine stabile "
                    "Belastungsverträglichkeit über die Dauer der Einheit."
                )

            elif workout.intensity is not None and workout.intensity >= 85:
                workout.workout_summary = (
                    "Intensive Radeinheit mit hoher relativer Belastung."
                )

            elif (
                workout.variability_index is not None
                and workout.variability_index <= 1.05
            ):
                workout.workout_summary = (
                    "Sehr gleichmäßig absolvierte Radeinheit mit moderater relativer Belastung."
                )

            elif (
                workout.variability_index is not None
                and workout.variability_index >= 1.15
            ):
                workout.workout_summary = (
                    "Unruhig gefahrene Radeinheit mit vielen Belastungsschwankungen."
                )

            else:
                workout.workout_summary = (
                    "Radeinheit mit moderater relativer Belastung."
                )

        if workout.rpe is not None:
            if (
                workout.intensity is not None
                and workout.intensity < 80
                and workout.rpe >= 7
            ):
                workout.workout_summary += (
                    f" Trotz der moderaten objektiven Intensität wurde die Einheit "
                    f"subjektiv mit RPE {workout.rpe} als deutlich anstrengend erlebt. "
                    "Die subjektive Belastung war damit höher, als die Messwerte allein vermuten lassen."
                )

            elif (
                workout.intensity is not None
                and workout.intensity >= 85
                and workout.rpe <= 4
            ):
                workout.workout_summary += (
                    f" Trotz der hohen objektiven Intensität wurde die Einheit "
                    f"subjektiv mit RPE {workout.rpe} als vergleichsweise leicht erlebt. "
                    "Die Belastung wurde offenbar gut vertragen."
                )

            elif workout.rpe >= 8:
                workout.workout_summary += (
                    f" Subjektiv wurde die Einheit mit RPE {workout.rpe} "
                    "als sehr anstrengend bewertet."
                )

            elif workout.rpe >= 6:
                workout.workout_summary += (
                    f" Subjektiv wurde die Einheit mit RPE {workout.rpe} "
                    "als anstrengend bewertet."
                )

            elif workout.rpe <= 3:
                workout.workout_summary += (
                    f" Subjektiv wurde die Einheit mit RPE {workout.rpe} "
                    "als leicht bewertet."
                )

        if workout.comment:
            workout.workout_summary += (
                f' Der Athlet beschreibt die Einheit so: "{workout.comment.strip()}"'
            )

        return workout

