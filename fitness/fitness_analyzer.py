from datetime import date, timedelta
from statistics import mean, median, pstdev

from fitness.models import TrainingStatus, Workout, WorkoutSplit

SIMILAR_WORKOUT_DAYS = 90
PREVIOUS_WORKOUT_DAYS = 365


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

        from_date = date.today() - timedelta(days=PREVIOUS_WORKOUT_DAYS)
        to_date = date.today()
        last_workouts = self.intervals_client_instance.get_workouts(
            from_date=from_date,
            to_date=to_date,
            sport_type=sport_type
        )

        min_duration = last_workout.duration_sec * 0.8
        max_duration = last_workout.duration_sec * 1.2
        similar_workouts = []
        previous_same_sport_workouts = []

        for workout in last_workouts:
            if workout.id == last_workout.id:
                continue

            if workout.sport != last_workout.sport:
                continue

            if workout.start_time >= last_workout.start_time:
                continue

            previous_same_sport_workouts.append(workout)

            if (
                last_workout.start_time.date() - workout.start_time.date()
            ).days > SIMILAR_WORKOUT_DAYS:
                continue

            if workout.duration_sec < min_duration:
                continue

            if workout.duration_sec > max_duration:
                continue

            similar_workouts.append(workout)

        if previous_same_sport_workouts:
            previous_same_sport = max(
                previous_same_sport_workouts,
                key=lambda workout: workout.start_time,
            )
            last_workout.days_since_previous_same_sport = (
                last_workout.start_time.date()
                - previous_same_sport.start_time.date()
            ).days

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

        if last_workout.sport in {"Run", "Ride"}:
            last_workout.splits = (
                self.intervals_client_instance.get_workout_details(last_workout.id)
            )
            last_workout.detail_summary = self._build_detail_summary(last_workout)

        training_status_at_workout = (
            self.intervals_client_instance.get_current_training_status(
                last_workout.start_time.date(),
            )
        )
        last_workout.recovery_summary = self._build_recovery_summary(
            workout=last_workout,
            training_status=training_status_at_workout,
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

        subjective_summary = self._build_subjective_summary(last_workout)
        if subjective_summary:
            last_workout.workout_summary += f" {subjective_summary}"

        if last_workout.days_since_previous_same_sport is not None:
            days = last_workout.days_since_previous_same_sport
            if days == 1:
                last_workout.workout_summary += (
                    " Die vorherige Einheit derselben Sportart lag einen Tag zurück."
                )
            else:
                last_workout.workout_summary += (
                    f" Die vorherige Einheit derselben Sportart lag {days} Tage zurück."
                )

        return last_workout

    def _build_subjective_summary(self, workout: Workout) -> str | None:
        if workout.rpe is None:
            return None

        if workout.similar_avg_rpe is not None:
            rpe_difference = workout.rpe - workout.similar_avg_rpe

            if rpe_difference >= 2:
                objective_values_below_comparison = (
                    workout.intensity is not None
                    and workout.similar_avg_intensity is not None
                    and workout.intensity <= workout.similar_avg_intensity - 5
                ) or (
                    workout.avg_hr is not None
                    and workout.similar_avg_hr is not None
                    and workout.avg_hr <= workout.similar_avg_hr - 5
                )

                if objective_values_below_comparison:
                    return (
                        "Die Einheit wurde subjektiv deutlich schwerer erlebt, "
                        "obwohl Intensität oder Puls unter dem Niveau der "
                        "Vergleichseinheiten lagen."
                    )

                return (
                    "Die Einheit wurde subjektiv deutlich anstrengender erlebt "
                    "als vergleichbare frühere Einheiten."
                )

            if rpe_difference >= 1:
                return (
                    "Die subjektive Belastung lag leicht über dem Niveau "
                    "vergleichbarer Einheiten."
                )

            if rpe_difference <= -2:
                return (
                    "Die Einheit wurde leichter wahrgenommen als vergleichbare "
                    "frühere Einheiten."
                )

            if rpe_difference <= -1:
                return (
                    "Die subjektive Belastung lag leicht unter dem Niveau "
                    "vergleichbarer Einheiten."
                )

            return (
                "Die subjektive Belastung entsprach ungefähr dem Niveau "
                "vergleichbarer Einheiten."
            )

        if workout.rpe >= 8:
            return "Die Einheit wurde subjektiv als sehr anstrengend erlebt."

        return None

    def _build_detail_summary(self, workout: Workout) -> str:
        if not workout.splits:
            return (
                "Für diese Einheit sind keine verwertbaren Abschnittsdaten "
                "verfügbar."
            )

        if workout.sport == "Run":
            return self._build_run_detail_summary(workout.splits)

        if workout.sport == "Ride":
            return self._build_ride_detail_summary(workout.splits)

        return "Für diese Sportart ist noch keine Detailanalyse verfügbar."

    def _build_run_detail_summary(self, splits: list[WorkoutSplit]) -> str:
        summary_parts = []
        pace_values = self._split_values(splits, "pace_sec_per_km")
        first_pace, second_pace = self._half_averages(
            splits,
            "pace_sec_per_km",
        )

        if first_pace is not None and second_pace is not None:
            pace_change = (second_pace - first_pace) / first_pace
            if pace_change >= 0.05:
                summary_parts.append(
                    "Die zweite Hälfte war rund "
                    f"{round(pace_change * 100)} Prozent langsamer als die erste."
                )
            elif pace_change <= -0.05:
                summary_parts.append(
                    "Die zweite Hälfte war rund "
                    f"{abs(round(pace_change * 100))} Prozent schneller als die erste."
                )
            elif len(pace_values) >= 2:
                summary_parts.append(
                    "Die Pace blieb zwischen erster und zweiter Hälfte stabil."
                )

        if len(pace_values) >= 3:
            pace_variation = pstdev(pace_values) / mean(pace_values)
            if pace_variation >= 0.08:
                summary_parts.append(
                    "Das Pacing schwankte zwischen den Abschnitten deutlich."
                )
            elif not summary_parts:
                summary_parts.append(
                    "Das Pacing war über die Abschnitte gleichmäßig."
                )

            slowest_split = max(
                (split for split in splits if split.pace_sec_per_km is not None),
                key=lambda split: split.pace_sec_per_km,
            )
            if slowest_split.pace_sec_per_km >= median(pace_values) * 1.15:
                if slowest_split.elevation_gain is not None:
                    elevation_values = self._split_values(
                        splits,
                        "elevation_gain",
                    )
                    if (
                        elevation_values
                        and slowest_split.elevation_gain > median(elevation_values)
                    ):
                        summary_parts.append(
                            "Der deutlich langsamste Abschnitt fiel mit "
                            "überdurchschnittlichem Höhengewinn zusammen."
                        )
                    else:
                        summary_parts.append(
                            "Mindestens ein Abschnitt zeigte einen deutlichen "
                            "Pace-Verlust."
                        )
                else:
                    summary_parts.append(
                        "Mindestens ein Abschnitt zeigte einen deutlichen Pace-Verlust."
                    )

        first_hr, second_hr = self._half_averages(splits, "avg_hr")
        if first_hr is not None and second_hr is not None:
            hr_change = second_hr - first_hr
            pace_was_similar = (
                first_pace is not None
                and second_pace is not None
                and abs(second_pace - first_pace) / first_pace <= 0.03
            )
            if hr_change >= 5 and pace_was_similar:
                summary_parts.append(
                    "Bei vergleichbarer Pace lag der Puls in der zweiten Hälfte höher."
                )
            elif hr_change >= 5:
                summary_parts.append(
                    "Der durchschnittliche Puls stieg in der zweiten Hälfte an."
                )
            elif hr_change <= -5:
                summary_parts.append(
                    "Der durchschnittliche Puls lag in der zweiten Hälfte niedriger."
                )
            else:
                summary_parts.append(
                    "Der durchschnittliche Puls blieb über beide Hälften stabil."
                )

        if not summary_parts:
            return (
                "Die vorhandenen Abschnitte reichen für eine belastbare Pace- "
                "oder Herzfrequenzanalyse nicht aus."
            )

        return " ".join(summary_parts[:3])

    def _build_ride_detail_summary(self, splits: list[WorkoutSplit]) -> str:
        summary_parts = []
        power_values = self._split_values(splits, "avg_watts")
        first_power, second_power = self._half_averages(splits, "avg_watts")

        if first_power is not None and second_power is not None:
            power_change = (second_power - first_power) / first_power
            if power_change <= -0.08:
                summary_parts.append(
                    "Die durchschnittliche Leistung lag in der zweiten Hälfte rund "
                    f"{abs(round(power_change * 100))} Prozent niedriger."
                )
            elif power_change >= 0.08:
                summary_parts.append(
                    "Die durchschnittliche Leistung lag in der zweiten Hälfte rund "
                    f"{round(power_change * 100)} Prozent höher."
                )
            else:
                summary_parts.append(
                    "Die Leistung blieb zwischen erster und zweiter Hälfte stabil."
                )

        if len(power_values) >= 3:
            power_variation = pstdev(power_values) / mean(power_values)
            if power_variation >= 0.20:
                summary_parts.append(
                    "Die Leistung schwankte zwischen den erkannten Abschnitten deutlich."
                )
            elif power_variation <= 0.10 and not summary_parts:
                summary_parts.append(
                    "Die erkannten Abschnitte wurden mit gleichmäßiger Leistung gefahren."
                )

            elevation_power_pairs = [
                (split.elevation_gain, split.avg_watts)
                for split in splits
                if split.elevation_gain is not None
                and split.avg_watts is not None
            ]
            if len(elevation_power_pairs) >= 3:
                elevation_midpoint = median(
                    elevation for elevation, _ in elevation_power_pairs
                )
                climb_power = [
                    power
                    for elevation, power in elevation_power_pairs
                    if elevation > elevation_midpoint
                ]
                flatter_power = [
                    power
                    for elevation, power in elevation_power_pairs
                    if elevation <= elevation_midpoint
                ]
                if climb_power and flatter_power:
                    climb_power_change = (
                        mean(climb_power) - mean(flatter_power)
                    ) / mean(flatter_power)
                    if abs(climb_power_change) <= 0.08:
                        summary_parts.append(
                            "In den anstiegsreicheren Abschnitten blieb die Leistung "
                            "auf einem ähnlichen Niveau."
                        )
                    elif climb_power_change > 0.08:
                        summary_parts.append(
                            "In den anstiegsreicheren Abschnitten lag die Leistung höher."
                        )
                    else:
                        summary_parts.append(
                            "In den anstiegsreicheren Abschnitten lag die Leistung "
                            "niedriger."
                        )

        first_hr, second_hr = self._half_averages(splits, "avg_hr")
        if first_hr is not None and second_hr is not None:
            hr_change = second_hr - first_hr
            power_was_similar = (
                first_power is not None
                and second_power is not None
                and abs(second_power - first_power) / first_power <= 0.05
            )
            if hr_change >= 5 and power_was_similar:
                summary_parts.append(
                    "Bei vergleichbarer Leistung lag der Puls in der zweiten Hälfte höher."
                )
            elif hr_change >= 5:
                summary_parts.append(
                    "Der durchschnittliche Puls stieg in der zweiten Hälfte an."
                )
            elif hr_change <= -5:
                summary_parts.append(
                    "Der durchschnittliche Puls lag in der zweiten Hälfte niedriger."
                )

        first_cadence, second_cadence = self._half_averages(
            splits,
            "avg_cadence",
        )
        if first_cadence is not None and second_cadence is not None:
            cadence_change = (second_cadence - first_cadence) / first_cadence
            if cadence_change <= -0.08:
                summary_parts.append(
                    "Die durchschnittliche Kadenz fiel in der zweiten Hälfte ab."
                )
            elif cadence_change >= 0.08:
                summary_parts.append(
                    "Die durchschnittliche Kadenz stieg in der zweiten Hälfte an."
                )

        if not summary_parts:
            return (
                "Die vorhandenen Abschnitte reichen für eine belastbare Leistungs-, "
                "Herzfrequenz- oder Kadenzanalyse nicht aus."
            )

        return " ".join(summary_parts[:3])

    def _build_recovery_summary(
        self,
        workout: Workout,
        training_status: TrainingStatus | None,
    ) -> str:
        if training_status is None:
            return (
                "Für den Tag der Einheit sind keine Erholungsdaten verfügbar."
            )

        summary_parts = []
        form = None
        if training_status.ctl is not None and training_status.atl is not None:
            form = training_status.ctl - training_status.atl
            if form <= -10:
                summary_parts.append(
                    "Die Einheit wurde bei einer erhöhten kurzfristigen "
                    "Trainingsbelastung absolviert."
                )
            elif form >= 5:
                summary_parts.append(
                    "Die kurzfristige Trainingsbelastung lag am Tag der Einheit "
                    "unter der langfristigen Belastung."
                )
            else:
                summary_parts.append(
                    "Kurzfristige und langfristige Trainingsbelastung lagen am Tag "
                    "der Einheit nah beieinander."
                )

        if workout.rpe is not None and workout.rpe >= 7 and form is not None:
            if form <= -10:
                summary_parts.append(
                    "Die subjektiv hohe Belastung könnte zur damaligen erhöhten "
                    "kurzfristigen Trainingsbelastung passen."
                )

        missing_recovery_values = []
        if training_status.hrv is None:
            missing_recovery_values.append("HRV")
        if training_status.sleep_secs is None:
            missing_recovery_values.append("Schlafdauer")

        if missing_recovery_values:
            summary_parts.append(
                "Für eine belastbarere Erholungsbewertung fehlen "
                f"{' und '.join(missing_recovery_values)}."
            )
        elif not summary_parts:
            summary_parts.append(
                "HRV und Schlafdauer sind dokumentiert, lassen sich als Einzelwerte "
                "aber nicht belastbar einordnen."
            )

        return " ".join(summary_parts)

    def _split_values(
        self,
        splits: list[WorkoutSplit],
        attribute: str,
    ) -> list[float]:
        return [
            value
            for split in splits
            if (value := getattr(split, attribute)) is not None and value > 0
        ]

    def _half_averages(
        self,
        splits: list[WorkoutSplit],
        attribute: str,
    ) -> tuple[float | None, float | None]:
        entries = [
            (value, split.duration_sec)
            for split in splits
            if (value := getattr(split, attribute)) is not None and value > 0
        ]
        if len(entries) < 2:
            return None, None

        if all(duration is not None and duration > 0 for _, duration in entries):
            total_duration = sum(duration for _, duration in entries)
            half_duration = total_duration / 2
            elapsed_duration = 0
            first_weighted_sum = 0.0
            first_weight = 0.0
            second_weighted_sum = 0.0
            second_weight = 0.0

            for value, duration in entries:
                section_end = elapsed_duration + duration
                first_part = max(
                    0,
                    min(section_end, half_duration) - elapsed_duration,
                )
                second_part = duration - first_part
                first_weighted_sum += value * first_part
                first_weight += first_part
                second_weighted_sum += value * second_part
                second_weight += second_part
                elapsed_duration = section_end

            if first_weight > 0 and second_weight > 0:
                return (
                    first_weighted_sum / first_weight,
                    second_weighted_sum / second_weight,
                )

        values = [value for value, _ in entries]
        half_index = (len(values) + 1) // 2

        return mean(values[:half_index]), mean(values[half_index:])
