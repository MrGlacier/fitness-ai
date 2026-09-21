import unittest

from intervals.intervals_client import IntervalsClient
from fitness.models import Workout


class ActivitySearchTests(unittest.TestCase):
    """Tests für get_activities_by_name."""

    def setUp(self):
        self.client = IntervalsClient.__new__(IntervalsClient)
        self.client.athlete_id = "test-athlete"

    def _fake_activities(self):
        return [
            {
                "id": "1",
                "name": "Einstein Marathon Ulm - Halbmarathon",
                "type": "Run",
                "start_date": "2025-03-15T08:00:00",
                "distance": 21097,
                "moving_time": 7200,
                "average_heartrate": 155,
                "max_heartrate": 175,
                "icu_training_load": 85,
                "icu_intensity": 75,
                "icu_weighted_avg_watts": None,
                "average_cadence": 88,
                "total_elevation_gain": 120,
                "decoupling": None,
                "icu_variability_index": None,
                "icu_rpe": 7,
                "description": None,
            },
            {
                "id": "2",
                "name": "Einstein Marathon - 10 km Spaßlauf",
                "type": "Run",
                "start_date": "2024-03-10T09:00:00",
                "distance": 10000,
                "moving_time": 3600,
                "average_heartrate": 160,
                "max_heartrate": 170,
                "icu_training_load": 60,
                "icu_intensity": 70,
                "icu_weighted_avg_watts": None,
                "average_cadence": 90,
                "total_elevation_gain": 50,
                "decoupling": None,
                "icu_variability_index": None,
                "icu_rpe": 6,
                "description": None,
            },
            {
                "id": "3",
                "name": "Lockeres Training im Grünen",
                "type": "Ride",
                "start_date": "2025-05-01T07:00:00",
                "distance": 30000,
                "moving_time": 5400,
                "average_heartrate": 140,
                "max_heartrate": 155,
                "icu_training_load": 65,
                "icu_intensity": 60,
                "icu_weighted_avg_watts": 150,
                "average_cadence": 85,
                "total_elevation_gain": 300,
                "decoupling": None,
                "icu_variability_index": None,
                "icu_rpe": 5,
                "description": None,
            },
            {
                "id": "4",
                "name": "Kaiserkrone - Berglauf",
                "type": "Run",
                "start_date": "2025-06-20T06:00:00",
                "distance": 12000,
                "moving_time": 5400,
                "average_heartrate": 165,
                "max_heartrate": 180,
                "icu_training_load": 70,
                "icu_intensity": 80,
                "icu_weighted_avg_watts": None,
                "average_cadence": 82,
                "total_elevation_gain": 800,
                "decoupling": None,
                "icu_variability_index": None,
                "icu_rpe": 8,
                "description": None,
            },
            {
                "id": "5",
                "name": "Einstein Marathon - Team Staffel",
                "type": "Run",
                "start_date": "2023-03-12T08:30:00",
                "distance": 10500,
                "moving_time": 3900,
                "average_heartrate": 162,
                "max_heartrate": 178,
                "icu_training_load": 68,
                "icu_intensity": 72,
                "icu_weighted_avg_watts": None,
                "average_cadence": 87,
                "total_elevation_gain": 90,
                "decoupling": None,
                "icu_variability_index": None,
                "icu_rpe": 7,
                "description": None,
            },
        ]

    def test_exact_match(self):
        self.client._get = lambda endpoint, query_string=None: self._fake_activities()
        results = self.client.get_activities_by_name("Einstein Marathon Ulm - Halbmarathon")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "1")

    def test_case_insensitive_partial_match(self):
        self.client._get = lambda endpoint, query_string=None: self._fake_activities()
        results = self.client.get_activities_by_name("einstein")
        self.assertEqual(len(results), 3)
        ids = {r.id for r in results}
        self.assertEqual(ids, {"1", "2", "5"})

    def test_partial_match_other_activity(self):
        self.client._get = lambda endpoint, query_string=None: self._fake_activities()
        results = self.client.get_activities_by_name("Kaiserkrone")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "4")

    def test_no_match(self):
        self.client._get = lambda endpoint, query_string=None: self._fake_activities()
        results = self.client.get_activities_by_name("Nirvana")
        self.assertEqual(results, [])

    def test_empty_search_term(self):
        self.client._get = lambda endpoint, query_string=None: self._fake_activities()
        results = self.client.get_activities_by_name("")
        self.assertEqual(results, [])

    def test_whitespace_only_search_term(self):
        self.client._get = lambda endpoint, query_string=None: self._fake_activities()
        results = self.client.get_activities_by_name("   ")
        self.assertEqual(results, [])

    def test_sport_type_filter_no_match(self):
        self.client._get = lambda endpoint, query_string=None: self._fake_activities()
        results = self.client.get_activities_by_name("Einstein", sport_type="Ride")
        self.assertEqual(results, [])

    def test_sport_type_filter_matches(self):
        self.client._get = lambda endpoint, query_string=None: self._fake_activities()
        results = self.client.get_activities_by_name("Kaiserkrone", sport_type="Run")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "4")

    def test_limit(self):
        self.client._get = lambda endpoint, query_string=None: self._fake_activities()
        results = self.client.get_activities_by_name("Einstein", limit=2)
        self.assertEqual(len(results), 2)

    def test_returns_workout_objects(self):
        self.client._get = lambda endpoint, query_string=None: self._fake_activities()
        results = self.client.get_activities_by_name("Einstein")
        self.assertIsInstance(results, list)
        for r in results:
            self.assertIsInstance(r, Workout)

    def test_activity_without_name(self):
        activities = self._fake_activities()
        activities.append({"id": "99", "name": None, "type": "Run", "start_date": "2025-01-01T00:00:00", "distance": 10000, "moving_time": 3600, "average_heartrate": 140, "max_heartrate": 150, "icu_training_load": 50, "icu_intensity": 50, "icu_weighted_avg_watts": None, "average_cadence": 80, "total_elevation_gain": 0, "decoupling": None, "icu_variability_index": None, "icu_rpe": 5, "description": None})
        activities.append({"id": "100", "name": "", "type": "Run", "start_date": "2025-01-02T00:00:00", "distance": 10000, "moving_time": 3600, "average_heartrate": 140, "max_heartrate": 150, "icu_training_load": 50, "icu_intensity": 50, "icu_weighted_avg_watts": None, "average_cadence": 80, "total_elevation_gain": 0, "decoupling": None, "icu_variability_index": None, "icu_rpe": 5, "description": None})
        self.client._get = lambda endpoint, query_string=None: activities
        results = self.client.get_activities_by_name("Einstein")
        self.assertEqual(len(results), 3)


if __name__ == "__main__":
    unittest.main()
