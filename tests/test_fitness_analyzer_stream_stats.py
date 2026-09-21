import unittest

from fitness.fitness_analyzer import FitnessAnalyzer


class StreamStatsAnalyzerTests(unittest.TestCase):
    """Tests für FitnessAnalyzer.get_activity_detail und _compute_trend."""

    def test_compute_trend_stable(self):
        self.assertEqual(
            FitnessAnalyzer._compute_trend(150, 152, 148),
            "stabil",
        )

    def test_compute_trend_increasing(self):
        result = FitnessAnalyzer._compute_trend(140, 148, 155)
        self.assertIn("zunehmend", result)

    def test_compute_trend_decreasing(self):
        result = FitnessAnalyzer._compute_trend(160, 150, 140)
        self.assertIn("abnehmend", result)

    def test_compute_trend_insufficient_values(self):
        self.assertIsNone(FitnessAnalyzer._compute_trend(None, None, None))
        self.assertIsNone(FitnessAnalyzer._compute_trend(150, None, None))

    def test_compute_trend_zero_start(self):
        self.assertIsNone(FitnessAnalyzer._compute_trend(0, 10, 20))

    def test_get_activity_detail_with_mock_client(self):
        class MockClient:
            def get_activity_detail(self, activity_id):
                return {
                    "id": "act-1",
                    "name": "Test Lauf",
                    "start_date": "2026-08-15T08:00:00",
                    "sport": "Run",
                    "distance_km": 10.0,
                    "duration_sec": 3600,
                    "avg_hr": 150,
                    "max_hr": 170,
                    "avg_watts": 200,
                    "tss": 75,
                    "intensity": 80,
                    "rpe": 7,
                    "stream_stats": {
                        "heartrate": {
                            "min": 130,
                            "max": 170,
                            "avg": 150,
                            "start_avg": 140,
                            "mid_avg": 155,
                            "end_avg": 160,
                        },
                        "watts": {
                            "min": 150,
                            "max": 250,
                            "avg": 200,
                            "start_avg": 210,
                            "mid_avg": 200,
                            "end_avg": 190,
                        },
                    },
                    "splits": [],
                }

        analyzer = FitnessAnalyzer(MockClient())
        result = analyzer.get_activity_detail("act-1")

        self.assertEqual(result["id"], "act-1")
        self.assertEqual(result["name"], "Test Lauf")
        self.assertEqual(result["sport"], "Run")
        self.assertEqual(result["distance_km"], 10.0)
        self.assertEqual(result["avg_hr"], 150)
        self.assertEqual(result["max_hr"], 170)
        self.assertIn("stream_stats", result)

        hr_stats = result["stream_stats"]["heartrate"]
        self.assertEqual(hr_stats["min"], 130)
        self.assertEqual(hr_stats["max"], 170)
        self.assertEqual(hr_stats["avg"], 150)
        self.assertIn("zunehmend", hr_stats["trend"])

        watts_stats = result["stream_stats"]["watts"]
        self.assertIn("abnehmend", watts_stats["trend"])

    def test_get_activity_detail_missing_activity(self):
        class MockClient:
            def get_activity_detail(self, activity_id):
                return None

        analyzer = FitnessAnalyzer(MockClient())
        result = analyzer.get_activity_detail("missing")

        self.assertEqual(result["error"], "activity_not_found")
        self.assertEqual(result["activity_id"], "missing")

    def test_get_activity_detail_compact_stats(self):
        class MockClient:
            def get_activity_detail(self, activity_id):
                return {
                    "id": "act-2",
                    "name": "Test",
                    "start_date": "2026-08-15T08:00:00",
                    "sport": "Ride",
                    "distance_km": 30.0,
                    "duration_sec": 5400,
                    "stream_stats": {
                        "heartrate": {
                            "min": 130,
                            "max": 165,
                            "avg": 148,
                            "start_avg": 140,
                            "mid_avg": 149,
                            "end_avg": 145,
                        },
                    },
                    "splits": [],
                }

        analyzer = FitnessAnalyzer(MockClient())
        result = analyzer.get_activity_detail("act-2")

        # Nur min/max/avg/trend — kein start_avg/mid_avg/end_avg im Ergebnis
        hr = result["stream_stats"]["heartrate"]
        self.assertIn("min", hr)
        self.assertIn("max", hr)
        self.assertIn("avg", hr)
        self.assertIn("trend", hr)
        self.assertNotIn("start_avg", hr)
        self.assertNotIn("mid_avg", hr)
        self.assertNotIn("end_avg", hr)


if __name__ == "__main__":
    unittest.main()
