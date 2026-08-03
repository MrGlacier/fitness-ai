import unittest

from intervals.intervals_client import IntervalsClient


class IntervalsClientDetailMappingTests(unittest.TestCase):
    def setUp(self):
        self.client = IntervalsClient.__new__(IntervalsClient)

    def test_maps_icu_interval_fields(self):
        splits = self.client._map_intervals_to_workout_splits([
            {
                "type": "WORK",
                "distance": 1000.0,
                "moving_time": 300,
                "average_speed": 3.333,
                "average_heartrate": 155,
                "max_heartrate": 168,
                "average_watts": 280,
                "average_cadence": 88.5,
                "total_elevation_gain": 12.0,
            }
        ])

        self.assertEqual(len(splits), 1)
        self.assertEqual(splits[0].distance_km, 1.0)
        self.assertEqual(splits[0].pace_sec_per_km, 300.0)
        self.assertEqual(splits[0].avg_watts, 280)
        self.assertEqual(splits[0].split_type, "WORK")

    def test_get_workout_details_uses_verified_activity_endpoint(self):
        calls = []

        def fake_get(endpoint, query_string=None):
            calls.append((endpoint, query_string))
            return {
                "type": "Run",
                "icu_intervals": [
                    {
                        "distance": 1000.0,
                        "moving_time": 300,
                    }
                ],
            }

        self.client._get = fake_get

        splits = self.client.get_workout_details("activity-1")

        self.assertEqual(
            calls,
            [("/activity/activity-1", {"intervals": "true"})],
        )
        self.assertEqual(len(splits), 1)

    def test_get_workout_details_uses_stream_fallback(self):
        calls = []
        streams = self._build_streams(sample_count=21, distance_step=100)

        def fake_get(endpoint, query_string=None):
            calls.append((endpoint, query_string))
            if endpoint == "/activity/activity-1":
                return {"type": "Run", "icu_intervals": []}
            return streams

        self.client._get = fake_get

        splits = self.client.get_workout_details("activity-1")

        self.assertEqual(calls[0][0], "/activity/activity-1")
        self.assertEqual(calls[1][0], "/activity/activity-1/streams.json")
        self.assertEqual(len(splits), 2)

    def test_builds_kilometer_splits_from_run_streams(self):
        streams = self._build_streams(sample_count=21, distance_step=100)

        splits = self.client._map_streams_to_workout_splits(streams, "Run")

        self.assertEqual(len(splits), 2)
        self.assertAlmostEqual(splits[0].distance_km, 1.0, places=1)
        self.assertIsNotNone(splits[0].avg_hr)

    def test_builds_compact_time_sections_from_ride_streams(self):
        streams = self._build_streams(
            sample_count=61,
            time_step=60,
            distance_step=500,
        )

        splits = self.client._map_streams_to_workout_splits(streams, "Ride")

        self.assertGreaterEqual(len(splits), 5)
        self.assertLessEqual(len(splits), 8)
        self.assertIsNotNone(splits[0].avg_watts)

    def test_missing_required_streams_returns_empty_list(self):
        streams = [{"type": "heartrate", "data": [140, 145]}]

        splits = self.client._map_streams_to_workout_splits(streams, "Run")

        self.assertEqual(splits, [])

    def _build_streams(
        self,
        sample_count: int,
        time_step: int = 30,
        distance_step: int = 100,
    ) -> list[dict]:
        return [
            {
                "type": "time",
                "data": [index * time_step for index in range(sample_count)],
            },
            {
                "type": "distance",
                "data": [index * distance_step for index in range(sample_count)],
            },
            {
                "type": "heartrate",
                "data": [140 + index % 5 for index in range(sample_count)],
            },
            {
                "type": "watts",
                "data": [220 + index % 10 for index in range(sample_count)],
            },
            {
                "type": "cadence",
                "data": [85 + index % 3 for index in range(sample_count)],
            },
            {
                "type": "altitude",
                "data": [100 + index * 0.5 for index in range(sample_count)],
            },
            {
                "type": "moving",
                "data": [True for _ in range(sample_count)],
            },
        ]


if __name__ == "__main__":
    unittest.main()
