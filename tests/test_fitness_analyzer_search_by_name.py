import unittest
from datetime import datetime

from fitness.fitness_analyzer import FitnessAnalyzer
from fitness.models import Workout


def _make_workout(workout_id: str, name: str, sport: str = "Run",
                  distance_km: float = 10.0, duration_sec: int = 3600,
                  avg_hr: int = 150) -> Workout:
    return Workout(
        id=workout_id,
        name=name,
        start_time=datetime(2025, 3, 15, 8, 0),
        sport=sport,
        distance_km=distance_km,
        duration_sec=duration_sec,
        avg_hr=avg_hr,
        weighted_avg_watts=150.0,
        tss=85.0,
    )


class FakeIntervalsClient:
    def __init__(self, workouts: list[Workout]):
        self.workouts = workouts

    def get_activities_by_name(
        self, search_term: str, sport_type=None, limit=50
    ) -> list[Workout]:
        search_lower = search_term.strip().lower()
        if not search_lower:
            return []
        filtered = [
            w for w in self.workouts
            if search_lower in w.name.lower()
        ]
        if sport_type:
            filtered = [
                w for w in filtered
                if w.sport.lower() == sport_type.lower()
            ]
        return filtered[:limit]


class FitnessAnalyzerSearchTests(unittest.TestCase):
    """Tests für FitnessAnalyzer.search_activities_by_name."""

    def setUp(self):
        workouts = [
            _make_workout("1", "Einstein Marathon Ulm"),
            _make_workout("2", "Einstein Marathon 10km"),
            _make_workout("3", "Kaiserkrone Berglauf"),
            _make_workout("4", "Lockeres Training", sport="Ride"),
        ]
        self.analyzer = FitnessAnalyzer(FakeIntervalsClient(workouts))

    def test_returns_compact_dicts(self):
        results = self.analyzer.search_activities_by_name("Einstein")
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertIsInstance(r, dict)
            self.assertIn("id", r)
            self.assertIn("name", r)
            self.assertIn("sport", r)
            self.assertIn("start_time", r)
            self.assertIn("distance_km", r)
            self.assertIn("duration_sec", r)
            self.assertIn("avg_hr", r)
            self.assertIn("avg_watts", r)
            self.assertIn("tss", r)

    def test_search_fields_correct(self):
        results = self.analyzer.search_activities_by_name("Einstein")
        self.assertEqual(results[0]["id"], "1")
        self.assertEqual(results[0]["name"], "Einstein Marathon Ulm")
        self.assertEqual(results[0]["sport"], "Run")

    def test_case_insensitive(self):
        results_lower = self.analyzer.search_activities_by_name("einstein")
        results_upper = self.analyzer.search_activities_by_name("EINSTEIN")
        self.assertEqual(len(results_lower), 2)
        self.assertEqual(len(results_upper), 2)

    def test_no_match_returns_empty(self):
        results = self.analyzer.search_activities_by_name("Nirvana")
        self.assertEqual(results, [])

    def test_sport_filter(self):
        results = self.analyzer.search_activities_by_name("Einstein", sport_type="Ride")
        self.assertEqual(results, [])

    def test_empty_search_term(self):
        results = self.analyzer.search_activities_by_name("")
        self.assertEqual(results, [])

    def test_limit(self):
        results = self.analyzer.search_activities_by_name("Einstein", limit=1)
        self.assertEqual(len(results), 1)

    def test_compact_data_no_workout_attributes(self):
        results = self.analyzer.search_activities_by_name("Einstein")
        # Nur die kompakten Felder sollten enthalten sein, nicht alle Workout-Felder
        for r in results:
            self.assertNotIn("splits", r)
            self.assertNotIn("detail_summary", r)
            self.assertNotIn("recovery_summary", r)
            self.assertNotIn("similar_workouts_count", r)


if __name__ == "__main__":
    unittest.main()
