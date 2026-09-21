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
        self.assertEqual(hr_stats["start"], 140)
        self.assertEqual(hr_stats["mid"], 155)
        self.assertEqual(hr_stats["end"], 160)
        self.assertIn("zunehmend", hr_stats["trend"])

        watts_stats = result["stream_stats"]["watts"]
        self.assertEqual(watts_stats["start"], 210)
        self.assertEqual(watts_stats["mid"], 200)
        self.assertEqual(watts_stats["end"], 190)
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
        self.assertIn("start", hr)
        self.assertIn("mid", hr)
        self.assertIn("end", hr)
        self.assertIn("trend", hr)
        self.assertNotIn("start_avg", hr)
        self.assertNotIn("mid_avg", hr)
        self.assertNotIn("end_avg", hr)
        self.assertEqual(hr["start"], 140)
        self.assertEqual(hr["mid"], 149)
        self.assertEqual(hr["end"], 145)

    def test_stream_stats_includes_relevant_types(self):
        """Relevante Stream-Typen werden im Ergebnis ausgegeben."""
        class MockClient:
            def get_activity_detail(self, activity_id):
                return {
                    "id": "act-3",
                    "name": "Trail",
                    "start_date": "2026-09-01T06:00:00",
                    "sport": "Run",
                    "distance_km": 15.0,
                    "duration_sec": 5400,
                    "stream_stats": {
                        "heartrate": {
                            "min": 140, "max": 175, "avg": 158,
                            "start_avg": 145, "mid_avg": 160, "end_avg": 165,
                        },
                        "watts": {
                            "min": 180, "max": 280, "avg": 220,
                            "start_avg": 230, "mid_avg": 220, "end_avg": 210,
                        },
                        "cadence": {
                            "min": 75, "max": 95, "avg": 85,
                            "start_avg": 88, "mid_avg": 84, "end_avg": 82,
                        },
                        "velocity_smooth": {
                            "min": 4.0, "max": 6.5, "avg": 5.2,
                            "start_avg": 5.5, "mid_avg": 5.2, "end_avg": 5.0,
                        },
                        "temp": {
                            "min": 12, "max": 22, "avg": 17,
                            "start_avg": 13, "mid_avg": 18, "end_avg": 21,
                        },
                    },
                    "splits": [],
                }

        analyzer = FitnessAnalyzer(MockClient())
        result = analyzer.get_activity_detail("act-3")

        stats = result["stream_stats"]
        self.assertIn("heartrate", stats)
        self.assertIn("watts", stats)
        self.assertIn("cadence", stats)
        self.assertIn("velocity_smooth", stats)
        self.assertIn("temp", stats)
        for metric in stats.values():
            self.assertIn("trend", metric)
            self.assertIn("start", metric)
            self.assertIn("mid", metric)
            self.assertIn("end", metric)

    def test_stream_stats_start_end_differ_from_min_max(self):
        """Start und End entsprechen den zeitlichen Dritteln, nicht min/max."""
        class MockClient:
            def get_activity_detail(self, activity_id):
                return {
                    "id": "act-6",
                    "name": "Temp-Test",
                    "start_date": "2026-09-01T06:00:00",
                    "sport": "Run",
                    "distance_km": 15.0,
                    "duration_sec": 5400,
                    "stream_stats": {
                        "temp": {
                            "min": 22,
                            "max": 36,
                            "avg": 28.3,
                            "start_avg": 25,
                            "mid_avg": 28,
                            "end_avg": 32,
                        },
                    },
                    "splits": [],
                }

        analyzer = FitnessAnalyzer(MockClient())
        result = analyzer.get_activity_detail("act-6")

        temp = result["stream_stats"]["temp"]
        # min/max sind statistische Extremwerte
        self.assertEqual(temp["min"], 22)
        self.assertEqual(temp["max"], 36)
        self.assertEqual(temp["avg"], 28.3)
        # start/mid/end sind zeitliche Drittel — nicht gleich min/max
        self.assertEqual(temp["start"], 25)
        self.assertEqual(temp["mid"], 28)
        self.assertEqual(temp["end"], 32)
        self.assertNotEqual(temp["start"], temp["min"])
        self.assertNotEqual(temp["end"], temp["max"])
        self.assertNotEqual(temp["start"], temp["max"])
        self.assertNotEqual(temp["end"], temp["min"])

    def test_stream_stats_excludes_irrelevant_types(self):
        """Irrelevante Stream-Typen werden nicht an das LLM weitergegeben."""
        class MockClient:
            def get_activity_detail(self, activity_id):
                return {
                    "id": "act-4",
                    "name": "Trail",
                    "start_date": "2026-09-01T06:00:00",
                    "sport": "Run",
                    "distance_km": 15.0,
                    "duration_sec": 5400,
                    "stream_stats": {
                        "time": {
                            "min": 0, "max": 5400, "avg": 2700,
                            "start_avg": 100, "mid_avg": 2700, "end_avg": 5300,
                        },
                        "distance": {
                            "min": 0, "max": 15000, "avg": 7500,
                            "start_avg": 2000, "mid_avg": 7500, "end_avg": 14800,
                        },
                        "latlng": {
                            "min": 0, "max": 100, "avg": 50,
                            "start_avg": 10, "mid_avg": 50, "end_avg": 90,
                        },
                        "altitude": {
                            "min": 200, "max": 1200, "avg": 600,
                            "start_avg": 300, "mid_avg": 700, "end_avg": 1100,
                        },
                        "fixed_altitude": {
                            "min": 195, "max": 1190, "avg": 590,
                            "start_avg": 290, "mid_avg": 690, "end_avg": 1090,
                        },
                        "torque": {
                            "min": 10, "max": 50, "avg": 25,
                            "start_avg": 20, "mid_avg": 25, "end_avg": 30,
                        },
                        "heartrate": {
                            "min": 140, "max": 175, "avg": 158,
                            "start_avg": 145, "mid_avg": 160, "end_avg": 165,
                        },
                    },
                    "splits": [],
                }

        analyzer = FitnessAnalyzer(MockClient())
        result = analyzer.get_activity_detail("act-4")

        stats = result["stream_stats"]
        self.assertIn("heartrate", stats)
        self.assertNotIn("time", stats)
        self.assertNotIn("distance", stats)
        self.assertNotIn("latlng", stats)
        self.assertNotIn("altitude", stats)
        self.assertNotIn("fixed_altitude", stats)
        self.assertNotIn("torque", stats)

    def test_stream_stats_missing_optional_streams(self):
        """Fehlende optionale Streams verursachen keinen Fehler."""
        class MockClient:
            def get_activity_detail(self, activity_id):
                return {
                    "id": "act-5",
                    "name": "Lockeres Jogging",
                    "start_date": "2026-09-01T06:00:00",
                    "sport": "Run",
                    "distance_km": 5.0,
                    "duration_sec": 1800,
                    "stream_stats": {
                        "heartrate": {
                            "min": 130, "max": 150, "avg": 140,
                            "start_avg": 135, "mid_avg": 142, "end_avg": 145,
                        },
                    },
                    "splits": [],
                }

        analyzer = FitnessAnalyzer(MockClient())
        result = analyzer.get_activity_detail("act-5")

        self.assertEqual(result["id"], "act-5")
        self.assertIn("stream_stats", result)
        self.assertIn("heartrate", result["stream_stats"])
        self.assertNotIn("watts", result["stream_stats"])
        self.assertNotIn("cadence", result["stream_stats"])
        self.assertNotIn("velocity_smooth", result["stream_stats"])
        self.assertNotIn("temp", result["stream_stats"])
        self.assertNotIn("respiration", result["stream_stats"])


if __name__ == "__main__":
    unittest.main()
