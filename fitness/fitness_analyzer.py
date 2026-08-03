from datetime import date, timedelta

from fitness.models import TrainingStatus, Workout


class FitnessAnalyzer:
    def __init__(self, intervals_client):
        self.intervals_client_instance = intervals_client

    def get_current_ftp(self, sport_type: str | None = None) -> dict:
        training_zones = self.intervals_client_instance.get_training_zones(sport_type)

        if not training_zones:
            return {"sport_type": sport_type, "ftp": None}

        training_zone = training_zones[0]
        resolved_sport_type = (
            training_zone.types[0] if training_zone.types else sport_type
        )
        return {
            "sport_type": resolved_sport_type,
            "ftp": training_zone.ftp,
        }

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

    def get_last_workout(self, sport_type: str | None = None) -> Workout | None:
        last_workout = self.intervals_client_instance.get_last_workout(sport_type)

        if last_workout is None:
            return None

        from_date = date.today() - timedelta(days=90)
        to_date = date.today()
        last_workouts = self.intervals_client_instance.get_workouts(
            from_date=from_date,
            to_date=to_date,
            sport_type=sport_type
        )

        min_duration = last_workout.duration_sec * 0.8
        max_duration = last_workout.duration_sec * 1.2
        similar_workouts = []

        for workout in last_workouts:
            if workout.id == last_workout.id:
                continue

            if workout.sport != last_workout.sport:
                continue

            if workout.start_time >= last_workout.start_time:
                continue

            if workout.duration_sec < min_duration:
                continue

            if workout.duration_sec > max_duration:
                continue

            similar_workouts.append(workout)

        similar_workouts.sort(key=lambda workout: workout.start_time, reverse=True)
        similar_workouts = similar_workouts[:5]
        last_workout.similar_workouts_count = len(similar_workouts)

        if last_workout.similar_workouts_count == 0:
            last_workout.comparison_summary = (
                "Es wurden keine vergleichbaren früheren Einheiten gefunden."
            )
        elif last_workout.similar_workouts_count == 1:
            last_workout.comparison_summary = (
                "Es wurde nur eine vergleichbare frühere Einheit gefunden. "
                "Der persönliche Vergleich ist deshalb noch wenig belastbar."
            )
        else:
            last_workout.comparison_summary = (
                f"Die Einheit wurde mit {last_workout.similar_workouts_count} "
                "ähnlichen früheren Einheiten verglichen."
            )

        if similar_workouts:
            total_hr = 0
            count_hr = 0

            total_rpe = 0
            count_rpe = 0

            total_intensity = 0
            count_intensity = 0

            for workout in similar_workouts:
                if workout.avg_hr is not None:
                    total_hr += workout.avg_hr
                    count_hr += 1

                if workout.rpe is not None:
                    total_rpe += workout.rpe
                    count_rpe += 1

                if workout.intensity is not None:
                    total_intensity += workout.intensity
                    count_intensity += 1

            if count_hr > 0:
                last_workout.similar_avg_hr = round(total_hr / count_hr, 1)

            if count_rpe > 0:
                last_workout.similar_avg_rpe = round(total_rpe / count_rpe, 1)

            if count_intensity > 0:
                last_workout.similar_avg_intensity = round(
                    total_intensity / count_intensity,
                    2,
                )

        if (
            last_workout.avg_hr is not None
            and last_workout.similar_avg_hr is not None
        ):
            hr_difference = last_workout.avg_hr - last_workout.similar_avg_hr

            if hr_difference <= -10:
                last_workout.comparison_summary += (
                    " Der durchschnittliche Puls lag rund "
                    f"{abs(round(hr_difference))} Schläge unter dem Durchschnitt "
                    "der Vergleichseinheiten."
                )
            elif hr_difference >= 10:
                last_workout.comparison_summary += (
                    " Der durchschnittliche Puls lag rund "
                    f"{round(hr_difference)} Schläge über dem Durchschnitt "
                    "der Vergleichseinheiten."
                )
            else:
                last_workout.comparison_summary += (
                    " Der durchschnittliche Puls lag ungefähr auf dem Niveau "
                    "der Vergleichseinheiten."
                )

        last_workout.workout_summary = "Trainingseinheit abgeschlossen."

        if last_workout.sport == "Run":
            if (
                last_workout.duration_sec >= 5300
                and last_workout.intensity is not None
                and last_workout.intensity < 80
                and last_workout.decoupling is not None
                and last_workout.decoupling < 5
            ):
                last_workout.workout_summary = (
                    "Langer und sehr gleichmäßig absolvierter Lauf mit moderater Intensität. "
                    "Die geringe aerobe Entkopplung spricht für eine stabile "
                    "Belastungsverträglichkeit über die Dauer der Einheit."
                )

            elif last_workout.intensity is not None and last_workout.intensity >= 85:
                last_workout.workout_summary = (
                    "Intensiver Lauf mit hoher relativer Belastung."
                )

            elif (
                last_workout.variability_index is not None
                and last_workout.variability_index <= 1.05
            ):
                last_workout.workout_summary = (
                    "Gleichmäßig absolvierter Lauf mit moderater relativer Belastung."
                )

            else:
                last_workout.workout_summary = (
                    "Laufeinheit mit moderater relativer Belastung."
                )

        elif last_workout.sport == "Ride":
            if (
                last_workout.duration_sec >= 7200
                and last_workout.intensity is not None
                and last_workout.intensity < 75
                and last_workout.decoupling is not None
                and last_workout.decoupling < 5
            ):
                last_workout.workout_summary = (
                    "Lange und kontrolliert absolvierte Radeinheit mit moderater Intensität. "
                    "Die geringe aerobe Entkopplung spricht für eine stabile "
                    "Belastungsverträglichkeit über die Dauer der Einheit."
                )

            elif last_workout.intensity is not None and last_workout.intensity >= 85:
                last_workout.workout_summary = (
                    "Intensive Radeinheit mit hoher relativer Belastung."
                )

            elif (
                last_workout.variability_index is not None
                and last_workout.variability_index <= 1.05
            ):
                last_workout.workout_summary = (
                    "Sehr gleichmäßig absolvierte Radeinheit mit moderater relativer Belastung."
                )

            elif (
                last_workout.variability_index is not None
                and last_workout.variability_index >= 1.15
            ):
                last_workout.workout_summary = (
                    "Unruhig gefahrene Radeinheit mit vielen Belastungsschwankungen."
                )

            else:
                last_workout.workout_summary = (
                    "Radeinheit mit moderater relativer Belastung."
                )

        if last_workout.similar_avg_rpe is not None and last_workout.rpe is not None:
            rpe_difference = last_workout.rpe - last_workout.similar_avg_rpe

            if rpe_difference >= 2:
                last_workout.workout_summary += (
                    f" Die Einheit fühlte sich subjektiv deutlich anstrengender an "
                    f"als vergleichbare Einheiten (RPE {last_workout.rpe} statt "
                    f"durchschnittlich {last_workout.similar_avg_rpe:.1f})."
                )

            elif rpe_difference >= 1:
                last_workout.workout_summary += (
                    f" Die subjektive Belastung lag leicht über dem Durchschnitt "
                    f"vergleichbarer Einheiten."
                )

            elif rpe_difference <= -2:
                last_workout.workout_summary += (
                    f" Die Einheit fühlte sich deutlich leichter an als vergleichbare "
                    f"Einheiten."
                )

            elif rpe_difference <= -1:
                last_workout.workout_summary += (
                    f" Die subjektive Belastung lag leicht unter dem Durchschnitt "
                    f"vergleichbarer Einheiten."
                )

            else:
                last_workout.workout_summary += (
                    f" Die subjektive Belastung entsprach ungefähr dem Niveau "
                    f"vergleichbarer Einheiten."
                )

        normalized_comment = (last_workout.comment or "").strip()
        if normalized_comment:
            last_workout.workout_summary += (
                f' Der Athlet beschreibt die Einheit so: "{normalized_comment}"'
            )

        return last_workout
