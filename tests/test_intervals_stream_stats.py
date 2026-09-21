import unittest

from intervals.intervals_client import IntervalsClient


class StreamStatsTests(unittest.TestCase):
    """Tests für die neuen Stream-Statistik-Methoden."""

    def setUp(self):
        self.client = IntervalsClient.__new__(IntervalsClient)

    def test_compute_stream_stats_empty(self):
        self.assertEqual(self.client._compute_stream_stats({}), {})

    def test_compute_stream_stats_ignores_non_numeric(self):
        streams = {
            "heartrate": [140, "invalid", None, 150, 160],
        }
        stats = self.client._compute_stream_stats(streams)
        self.assertEqual(stats["heartrate"]["min"], 140)
        self.assertEqual(stats["heartrate"]["max"], 160)
        self.assertEqual(stats["heartrate"]["avg"], 150.0)

    def test_compute_stream_stats_ignores_booleans(self):
        streams = {
            "moving": [True, False, True, True],
        }
        stats = self.client._compute_stream_stats(streams)
        self.assertNotIn("moving", stats)

    def test_compute_stream_stats_trend_values(self):
        streams = {
            "heartrate": [140] * 30 + [145] * 30 + [155] * 30,
        }
        stats = self.client._compute_stream_stats(streams)
        hr = stats["heartrate"]
        self.assertEqual(hr["start_avg"], 140.0)
        self.assertEqual(hr["mid_avg"], 145.0)
        self.assertEqual(hr["end_avg"], 155.0)

    def test_transpose_streams(self):
        raw_streams = [
            {"type": "time", "data": [0, 30, 60]},
            {"type": "heartrate", "data": [140, 145, 150]},
            {"type": "watts", "data": [200, 210, 190]},
        ]
        transposed = self.client._transpose_streams(raw_streams)
        self.assertEqual(transposed["time"], [0, 30, 60])
        self.assertEqual(transposed["heartrate"], [140, 145, 150])
        self.assertEqual(transposed["watts"], [200, 210, 190])

    def test_transpose_streams_skips_malformed(self):
        raw_streams = [
            {"type": "time", "data": [0, 30]},
            {"type": "invalid"},  # no data
            {"data": [1, 2]},  # no type
            {"type": "heartrate", "data": []},  # empty
        ]
        transposed = self.client._transpose_streams(raw_streams)
        self.assertIn("time", transposed)
        self.assertNotIn("heartrate", transposed)  # empty data → verworfen

    def test_get_activity_streams_uses_correct_endpoint(self):
        calls = []

        def fake_get(endpoint, query_string=None):
            calls.append((endpoint, query_string))
            return [
                {"type": "time", "data": [0, 30, 60]},
                {"type": "heartrate", "data": [140, 145, 150]},
            ]

        self.client._get = fake_get

        streams = self.client.get_activity_streams("test-activity")

        self.assertEqual(len(calls), 1)
        self.assertIn("test-activity", calls[0][0])
        self.assertEqual(calls[0][1], {"includeDefaults": "true"})
        self.assertIn("time", streams)
        self.assertIn("heartrate", streams)

    def test_get_activity_streams_handles_error(self):
        import httpx

        def fake_get(endpoint, query_string=None):
            raise httpx.HTTPError("Error")

        self.client._get = fake_get
        streams = self.client.get_activity_streams("test-activity")
        self.assertEqual(streams, {})


class ActivityDetailTests(unittest.TestCase):
    """Tests für get_activity_detail."""

    def setUp(self):
        self.client = IntervalsClient.__new__(IntervalsClient)

    def test_get_activity_detail_structure(self):
        calls = []

        def fake_get(endpoint, query_string=None):
            calls.append(endpoint)
            if "streams" in endpoint:
                return [
                    {"type": "time", "data": [0, 30, 60]},
                    {"type": "heartrate", "data": [140, 145, 150]},
                    {"type": "watts", "data": [200, 210, 190]},
                ]
            return {
                "id": "act-123",
                "name": "Test Lauf",
                "type": "Run",
                "start_date": "2026-08-15T08:00:00",
                "distance": 10000,
                "moving_time": 3600,
                "average_heartrate": 150,
                "max_heartrate": 170,
                "icu_training_load": 75,
                "icu_intensity": 80,
            }

        self.client._get = fake_get

        result = self.client.get_activity_detail("act-123")

        self.assertEqual(result["id"], "act-123")
        self.assertEqual(result["name"], "Test Lauf")
        self.assertEqual(result["sport"], "Run")
        self.assertEqual(result["distance_km"], 10.0)
        self.assertEqual(result["duration_sec"], 3600)
        self.assertEqual(result["avg_hr"], 150)
        self.assertIn("stream_stats", result)
        self.assertIn("heartrate", result["stream_stats"])
        self.assertIn("watts", result["stream_stats"])
        # Keine doppelten API-Requests: activity-details 1×, streams 1×
        activity_calls = [c for c in calls if "streams" not in c]
        stream_calls = [c for c in calls if "streams" in c]
        self.assertEqual(len(activity_calls), 1)
        self.assertEqual(len(stream_calls), 1)

    def test_get_activity_detail_handles_missing_activity(self):
        import httpx

        def fake_get(endpoint, query_string=None):
            raise httpx.HTTPError("Not found")

        self.client._get = fake_get
        result = self.client.get_activity_detail("missing-act")
        self.assertEqual(result, {})

    def test_get_activity_detail_returns_empty_for_non_dict_response(self):
        self.client._get = lambda endpoint, query_string=None: "not-a-dict"
        result = self.client.get_activity_detail("bad-act")
        self.assertEqual(result, {})

    def test_get_activity_detail_no_extra_requests_on_failure(self):
        """Stellt sicher, dass bei fehlerhafter Aktivität keine Streams/Splits geladen werden."""
        import httpx

        calls = []

        def fake_get(endpoint, query_string=None):
            calls.append(endpoint)
            raise httpx.HTTPError("Not found")

        self.client._get = fake_get
        result = self.client.get_activity_detail("fail-act")

        self.assertEqual(result, {})
        # Nur ein Aufruf (activity-details), keine Streams, keine Splits
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
