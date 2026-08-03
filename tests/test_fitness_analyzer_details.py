import unittest
from datetime import date, datetime

from fitness.fitness_analyzer import FitnessAnalyzer
from fitness.models import TrainingStatus, Workout, WorkoutSplit


def build_workout(
    workout_id: str,
    day: int,
    sport: str = "Run",
    rpe: int | None = 6,
    comment: str | None = None,
) -> Workout:
    return Workout(
        id=workout_id,
        name="Test workout",
        start_time=datetime(2026, 8, day, 8, 0),
        sport=sport,
        distance_km=10,
        duration_sec=3600,
        avg_hr=150,
        intensity=75,
        decoupling=3,
        variability_index=1.02,
        rpe=rpe,
        comment=comment,
    )


def build_training_status(
    day: int,
    hrv: float | None = 55,
    sleep_secs: int | None = 27000,
) -> TrainingStatus:
    return TrainingStatus(
        date=date(2026, 8, day),
        ctl=50,
        atl=65,
        resting_hr=48,
        hrv=hrv,
        sleep_secs=sleep_secs,
    )


class FakeIntervalsClient:
    def __init__(
        self,
        last_workout: Workout,
        history: list[Workout] | None = None,
        splits: list[WorkoutSplit] | None = None,
        training_status: TrainingStatus | None = None,
    ):
        self.last_workout = last_workout
        self.history = history or []
        self.splits = splits or []
        self.training_status = training_status
        self.detail_calls = []

    def get_last_workout(self, sport_type: str | None = None) -> Workout:
        return self.last_workout

    def get_workouts(self, **kwargs) -> list[Workout]:
        return self.history

    def get_workout_details(self, activity_id: str) -> list[WorkoutSplit]:
        self.detail_calls.append(activity_id)
        return self.splits

    def get_current_training_status(
        self,
        for_date: date,
    ) -> TrainingStatus | None:
        return self.training_status


class FitnessAnalyzerDetailTests(unittest.TestCase):
    def test_last_run_with_splits(self):
        workout = build_workout("run-current", 7)
        splits = [
            WorkoutSplit(index=1, pace_sec_per_km=300, avg_hr=145),
            WorkoutSplit(index=2, pace_sec_per_km=302, avg_hr=147),
            WorkoutSplit(index=3, pace_sec_per_km=330, avg_hr=153),
            WorkoutSplit(index=4, pace_sec_per_km=335, avg_hr=156),
        ]
        client = FakeIntervalsClient(
            last_workout=workout,
            splits=splits,
            training_status=build_training_status(7),
        )

        result = FitnessAnalyzer(client).get_last_workout("Run")

        self.assertEqual(result.splits, splits)
        self.assertIn("zweite Hälfte", result.detail_summary)
        self.assertIn("Puls", result.detail_summary)

    def test_last_ride_with_power_data(self):
        workout = build_workout("ride-current", 7, sport="Ride")
        splits = [
            WorkoutSplit(index=1, avg_watts=250, avg_hr=140, avg_cadence=90),
            WorkoutSplit(index=2, avg_watts=245, avg_hr=143, avg_cadence=89),
            WorkoutSplit(index=3, avg_watts=210, avg_hr=148, avg_cadence=84),
            WorkoutSplit(index=4, avg_watts=200, avg_hr=151, avg_cadence=82),
        ]
        client = FakeIntervalsClient(
            last_workout=workout,
            splits=splits,
            training_status=build_training_status(7),
        )

        result = FitnessAnalyzer(client).get_last_workout("Ride")

        self.assertIn("Leistung", result.detail_summary)
        self.assertIn("zweiten Hälfte", result.detail_summary)

    def test_workout_without_hrv_or_sleep(self):
        workout = build_workout("run-current", 7)
        client = FakeIntervalsClient(
            last_workout=workout,
            training_status=build_training_status(7, hrv=None, sleep_secs=None),
        )

        result = FitnessAnalyzer(client).get_last_workout("Run")

        self.assertIn("HRV und Schlafdauer", result.recovery_summary)

    def test_workout_without_rpe_or_comment(self):
        workout = build_workout(
            "run-current",
            7,
            rpe=None,
            comment=None,
        )
        client = FakeIntervalsClient(
            last_workout=workout,
            training_status=build_training_status(7),
        )

        result = FitnessAnalyzer(client).get_last_workout("Run")

        self.assertIsInstance(result.workout_summary, str)
        self.assertNotIn("subjektiv", result.workout_summary)

    def test_workout_without_detail_data(self):
        workout = build_workout("run-current", 7)
        client = FakeIntervalsClient(
            last_workout=workout,
            splits=[],
            training_status=build_training_status(7),
        )

        result = FitnessAnalyzer(client).get_last_workout("Run")

        self.assertEqual(result.splits, [])
        self.assertIn("keine verwertbaren Abschnittsdaten", result.detail_summary)

    def test_workout_with_one_comparison(self):
        workout = build_workout("run-current", 7)
        previous = build_workout("run-previous", 2)
        client = FakeIntervalsClient(
            last_workout=workout,
            history=[previous],
            training_status=build_training_status(7),
        )

        result = FitnessAnalyzer(client).get_last_workout("Run")

        self.assertEqual(result.similar_workouts_count, 1)
        self.assertIn("nur eine vergleichbare", result.comparison_summary)
        self.assertEqual(result.days_since_previous_same_sport, 5)

    def test_existing_get_last_workout_supports_other_sports(self):
        workout = build_workout(
            "swim-current",
            7,
            sport="Swim",
            rpe=None,
            comment="Techniktraining",
        )
        client = FakeIntervalsClient(
            last_workout=workout,
            training_status=None,
        )

        result = FitnessAnalyzer(client).get_last_workout("Swim")

        self.assertEqual(result.sport, "Swim")
        self.assertEqual(result.workout_summary, "Trainingseinheit abgeschlossen.")
        self.assertEqual(result.splits, [])
        self.assertEqual(client.detail_calls, [])
        self.assertIn("keine Erholungsdaten", result.recovery_summary)


if __name__ == "__main__":
    unittest.main()
