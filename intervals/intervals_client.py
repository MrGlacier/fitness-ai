# Intevals.icu - API Dokumentation
# https://intervals.icu/api-docs.html

from datetime import date, datetime, timedelta
from math import ceil

import httpx

from core import config
from core.utils import meters_to_km
from fitness.models import (
    Athlete,
    TrainingStatus,
    TrainingZones,
    Workout,
    WorkoutSplit,
)

from core.logger import logger

intervals_icu_endpoints = {
    "athlete": "/athlete/{athlete_id}",
    "sport-settings": "/athlete/{athlete_id}/sport-settings/{sport_type}",
    "activities": "/athlete/{athlete_id}/activities",
    "activity-details": "/activity/{activity_id}",
    "activity-streams": "/activity/{activity_id}/streams.json",
    "training-status": "/athlete/{athlete_id}/wellness/{for_date}",
}

WORKOUT_STREAM_TYPES = (
    "time,distance,heartrate,watts,cadence,altitude,"
    "velocity_smooth,moving"
)


class IntervalsClient:
    def __init__(self, base_url: str | None = None):
        self.basic_auth = httpx.BasicAuth(username=config.get_intervals_icu_username(), password=config.get_intervals_icu_api_key())
        self.base_url = base_url or config.get_intervals_icu_api_url()
        self.client = httpx.Client(base_url=self.base_url, auth=self.basic_auth)
        self.athlete_id = config.get_intervals_icu_athlete_id()

    def get_workouts(
        self,
        from_date: date,
        to_date: date,
        sport_type: str | None = None
    ) -> list[Workout]:
        endpoint = intervals_icu_endpoints["activities"].format(athlete_id=self.athlete_id)
        query_string = {"oldest": from_date}
        if to_date is not None:
            query_string["newest"] = to_date

        data = self._get(endpoint, query_string)
        if sport_type:
            # [Ergebnis for Element in Sammlung if Bedingung]
            data = [
                activity
                for activity in data
                if str(activity.get("type", "")).lower() == sport_type.lower()
            ]
        
        results = []
        for activity in data:
            converted_activity = self._map_activity_to_workout(activity)
            results.append(converted_activity)

        return results
    

    def get_last_workout(self, sport_type: str | None = None) -> Workout | None:
        from_date = date.today() - timedelta(days=30)
        to_date = date.today()

        workouts = self.get_workouts(
            from_date=from_date,
            to_date=to_date,
            sport_type=sport_type,
        )

        if not workouts:
            return None

        return max(workouts, key=lambda workout: workout.start_time)


    def get_workout_details(self, activity_id: str) -> list[WorkoutSplit]:
        endpoint = intervals_icu_endpoints["activity-details"].format(
            activity_id=activity_id,
        )

        try:
            activity = self._get(endpoint, {"intervals": "true"})
        except httpx.HTTPError:
            logger.warning("No activity details available for %s", activity_id)
            return []

        if not isinstance(activity, dict):
            logger.warning(
                "Unexpected activity details response for %s: %s",
                activity_id,
                type(activity).__name__,
            )
            return []

        intervals = activity.get("icu_intervals")
        if isinstance(intervals, list) and intervals:
            splits = self._map_intervals_to_workout_splits(intervals)
            if splits:
                return splits

        streams_endpoint = intervals_icu_endpoints["activity-streams"].format(
            activity_id=activity_id,
        )

        try:
            streams = self._get(
                streams_endpoint,
                {"types": WORKOUT_STREAM_TYPES},
            )
        except httpx.HTTPError:
            logger.warning("No activity streams available for %s", activity_id)
            return []

        if not isinstance(streams, list):
            logger.warning(
                "Unexpected activity streams response for %s: %s",
                activity_id,
                type(streams).__name__,
            )
            return []

        return self._map_streams_to_workout_splits(
            streams=streams,
            sport_type=activity.get("type"),
        )


    def get_recent_workouts(self, days: int, sport_type: str | None = None) -> list[Workout]:
        endpoint = intervals_icu_endpoints["activities"].format(athlete_id=self.athlete_id)
        query_string = {"oldest": date.today() - timedelta(days=days)}
        query_string["newest"] = date.today()

        data = self._get(endpoint, query_string)
        if sport_type:
            # [Ergebnis for Element in Sammlung if Bedingung]
            data = [
                activity
                for activity in data
                if str(activity.get("type", "")).lower() == sport_type.lower()
            ]

        results = []
        for activity in data:
            converted_activity = self._map_activity_to_workout(activity)
            results.append(converted_activity)

        return results


    def get_athlete(self) -> Athlete:
        endpoint = intervals_icu_endpoints["athlete"].format(athlete_id=self.athlete_id)
        athlete = self._get(endpoint)
        return self._map_athlete(athlete)


    def get_training_zones(self, sport_type: str | None = None) -> list[TrainingZones]:
        if sport_type:
            sport_type = sport_type[0].upper() + sport_type[1:]
            
        endpoint = intervals_icu_endpoints["sport-settings"].format(
            athlete_id=self.athlete_id,
            sport_type=sport_type or "",
        )
        #logger.info("get_training_zones - %s", endpoint)
        training_zones = self._get(endpoint)
        return self._map_training_zones(training_zones)


    def get_current_training_status(self, for_date: date) -> TrainingStatus | None:
        endpoint = intervals_icu_endpoints["training-status"].format(
            athlete_id=self.athlete_id,
            for_date=for_date,
        )

        try:
            current_training_status = self._get(endpoint)
        except httpx.HTTPError:
            logger.warning("No wellness data available for %s", for_date)
            return None

        if not isinstance(current_training_status, dict):
            logger.warning(
                "Unexpected wellness response for %s: %s",
                for_date,
                type(current_training_status).__name__,
            )
            return None

        return self._map_training_status(current_training_status)


    def test_connection(self) -> dict:
        athlete = self.get_athlete()
        return {
            "success": True,
            "athlete": athlete
        }
        

    def _map_activity_to_workout(self, activity: dict) -> Workout:
        start_date = activity.get("start_date")
        if start_date is None:
            raise ValueError(f"Activity {activity.get('id')} has no start_date")

        distance = activity.get("distance")
        intensity = activity.get("icu_intensity")
        average_cadence = activity.get("average_cadence")
        elevation_gain = activity.get("total_elevation_gain")
        decoupling = activity.get("decoupling")
        weighted_avg_watts = activity.get("icu_weighted_avg_watts")
        variability_index = activity.get("icu_variability_index")

        workout =  Workout(
            id = activity["id"],
            name = activity["name"],
            start_time = datetime.fromisoformat(start_date),
            sport = activity["type"],
            distance_km = meters_to_km(distance) if distance is not None else 0.0,
            duration_sec = activity["moving_time"],
            avg_hr = activity.get("average_heartrate"),
            tss = activity.get("icu_training_load"),
            intensity = round(intensity, 2) if intensity is not None else None,
            max_hr = activity.get("max_heartrate"),
            average_cadence = round(average_cadence, 1) if average_cadence is not None else None,
            elevation_gain = round(elevation_gain, 1) if elevation_gain is not None else None,
            decoupling = round(decoupling, 2) if decoupling is not None else None,
            weighted_avg_watts = round(weighted_avg_watts, 1) if weighted_avg_watts is not None else None,
            rpe = activity.get("icu_rpe"),
            comment = activity.get("description"),
            variability_index = (round(variability_index, 2) if variability_index is not None else None),
        )

        return workout

    def _map_intervals_to_workout_splits(
        self,
        intervals: list[dict],
    ) -> list[WorkoutSplit]:
        splits = []

        for index, interval in enumerate(intervals, start=1):
            if not isinstance(interval, dict):
                continue

            distance = interval.get("distance")
            distance_km = (
                meters_to_km(distance) if distance is not None else None
            )
            duration_sec = interval.get("moving_time")
            if duration_sec is None:
                duration_sec = interval.get("elapsed_time")

            average_speed = interval.get("average_speed")
            pace_sec_per_km = None
            if duration_sec is not None and distance_km:
                pace_sec_per_km = round(duration_sec / distance_km, 1)

            splits.append(
                WorkoutSplit(
                    index=index,
                    label=interval.get("label"),
                    split_type=interval.get("type"),
                    distance_km=distance_km,
                    duration_sec=duration_sec,
                    pace_sec_per_km=pace_sec_per_km,
                    avg_speed_kmh=(
                        round(average_speed * 3.6, 2)
                        if average_speed is not None
                        else None
                    ),
                    avg_hr=interval.get("average_heartrate"),
                    max_hr=interval.get("max_heartrate"),
                    avg_watts=interval.get("average_watts"),
                    avg_cadence=interval.get("average_cadence"),
                    elevation_gain=interval.get("total_elevation_gain"),
                )
            )

        return splits

    def _map_streams_to_workout_splits(
        self,
        streams: list[dict],
        sport_type: str | None,
    ) -> list[WorkoutSplit]:
        stream_data = {
            stream.get("type"): stream.get("data")
            for stream in streams
            if isinstance(stream, dict) and isinstance(stream.get("data"), list)
        }
        times = stream_data.get("time")
        distances = stream_data.get("distance")

        if not times or not distances or len(times) != len(distances):
            return []

        if times[0] is None or times[-1] is None:
            return []

        sport_type_normalized = (sport_type or "").lower()
        sections = []

        if sport_type_normalized == "run":
            section_start = 0
            initial_distance = next(
                (distance for distance in distances if distance is not None),
                None,
            )
            if initial_distance is None:
                return []

            next_boundary = initial_distance + 1000

            for index, distance in enumerate(distances):
                if distance is None or distance < next_boundary:
                    continue

                sections.append((section_start, index))
                section_start = index + 1
                next_boundary += 1000

            if section_start < len(times) - 1:
                sections.append((section_start, len(times) - 1))

        elif sport_type_normalized == "ride":
            total_duration = times[-1] - times[0]
            if total_duration <= 0:
                return []

            section_duration = max(600, ceil(total_duration / 8 / 60) * 60)
            section_start = 0
            next_boundary = times[0] + section_duration

            for index, current_time in enumerate(times):
                if current_time is None or current_time < next_boundary:
                    continue

                sections.append((section_start, index))
                section_start = index + 1
                next_boundary += section_duration

            if section_start < len(times) - 1:
                sections.append((section_start, len(times) - 1))

        else:
            return []

        return [
            self._build_stream_split(
                index=index,
                start_index=start_index,
                end_index=end_index,
                stream_data=stream_data,
            )
            for index, (start_index, end_index) in enumerate(sections, start=1)
            if end_index > start_index
        ]

    def _build_stream_split(
        self,
        index: int,
        start_index: int,
        end_index: int,
        stream_data: dict[str, list],
    ) -> WorkoutSplit:
        times = stream_data["time"]
        distances = stream_data["distance"]
        moving = stream_data.get("moving")
        if moving is not None and len(moving) != len(times):
            moving = None

        duration_sec = 0
        for item_index in range(start_index + 1, end_index + 1):
            if moving is not None and moving[item_index] is False:
                continue

            previous_time = times[item_index - 1]
            current_time = times[item_index]
            if previous_time is None or current_time is None:
                continue

            duration_sec += max(0, current_time - previous_time)

        start_distance = distances[start_index]
        end_distance = distances[end_index]
        distance_m = (
            end_distance - start_distance
            if start_distance is not None and end_distance is not None
            else 0
        )
        distance_km = round(distance_m / 1000, 2) if distance_m > 0 else None
        pace_sec_per_km = (
            round(duration_sec / distance_km, 1)
            if duration_sec > 0 and distance_km
            else None
        )
        avg_speed_kmh = (
            round(distance_km / (duration_sec / 3600), 2)
            if duration_sec > 0 and distance_km
            else None
        )

        sample_indexes = [
            item_index
            for item_index in range(start_index, end_index + 1)
            if moving is None or moving[item_index] is not False
        ]
        altitude = stream_data.get("altitude")
        if altitude is not None and len(altitude) != len(times):
            altitude = None
        elevation_gain = None
        if altitude is not None:
            elevation_gain = 0.0
            for item_index in range(start_index + 1, end_index + 1):
                previous = altitude[item_index - 1]
                current = altitude[item_index]
                if previous is not None and current is not None and current > previous:
                    elevation_gain += current - previous
            elevation_gain = round(elevation_gain, 1)

        heartrate_values = self._stream_values(
            stream_data.get("heartrate"),
            sample_indexes,
        )

        return WorkoutSplit(
            index=index,
            distance_km=distance_km,
            duration_sec=round(duration_sec) if duration_sec > 0 else None,
            pace_sec_per_km=pace_sec_per_km,
            avg_speed_kmh=avg_speed_kmh,
            avg_hr=(
                round(sum(heartrate_values) / len(heartrate_values))
                if heartrate_values
                else None
            ),
            max_hr=round(max(heartrate_values)) if heartrate_values else None,
            avg_watts=self._stream_average(
                stream_data.get("watts"),
                sample_indexes,
            ),
            avg_cadence=self._stream_average(
                stream_data.get("cadence"),
                sample_indexes,
            ),
            elevation_gain=elevation_gain,
        )

    def _stream_average(
        self,
        stream: list | None,
        sample_indexes: list[int],
    ) -> float | None:
        values = self._stream_values(stream, sample_indexes)
        if not values:
            return None

        return round(sum(values) / len(values), 1)

    def _stream_values(
        self,
        stream: list | None,
        sample_indexes: list[int],
    ) -> list[float]:
        if stream is None:
            return []

        return [
            stream[index]
            for index in sample_indexes
            if index < len(stream) and stream[index] is not None
        ]
    
    def _map_athlete(self, athlete_data: dict) -> Athlete:
        return Athlete(
            id=athlete_data["id"],
            name=athlete_data["name"],
            email=athlete_data["email"],
            city=athlete_data.get("city"),
            timezone=athlete_data["timezone"],
        )
    
    def _map_training_zones(self, training_zones: dict | list) -> list[TrainingZones]:
        training_zones_mapped = []
        
        if isinstance(training_zones, dict):
            training_zones = [training_zones]

        for training_zone in training_zones:
            if "types" not in training_zone:
                logger.info("Training zone without types: %s", training_zone.keys())

            current_training_zone = TrainingZones(
                types=training_zone.get("types", []),
                ftp=training_zone.get("ftp"),
                indoor_ftp=training_zone.get("indoor_ftp"),
                lthr=training_zone.get("lthr"),
                max_hr=training_zone.get("max_hr"),
                threshold_pace=training_zone.get("threshold_pace"),
                pace_units=training_zone.get("pace_units"),
                power_zones=training_zone.get("power_zones"),
                power_zone_names=training_zone.get("power_zone_names"),
                hr_zones=training_zone.get("hr_zones"),
                hr_zone_names=training_zone.get("hr_zone_names"),
                pace_zones=training_zone.get("pace_zones"),
                pace_zone_names=training_zone.get("pace_zone_names"),
            )

            training_zones_mapped.append(current_training_zone)
        
        return training_zones_mapped

    def _map_training_status(self, traing_status: dict) -> TrainingStatus:
        return TrainingStatus(
            date=date.fromisoformat(traing_status.get("id")),
            ctl=round(traing_status.get("ctl"), 2)
            if traing_status.get("ctl") is not None else None,
            atl=round(traing_status.get("atl"), 2)
            if traing_status.get("atl") is not None else None,
            form=traing_status.get("form"),
            form_status=traing_status.get("form_status"),
            summary=traing_status.get("summary"),
            resting_hr=traing_status.get("restingHR"),
            hrv=round(traing_status.get("hrv"), 2) if traing_status.get("hrv") is not None else None,
            sleep_secs=traing_status.get("sleepSecs"),
            sleep_quality=traing_status.get("sleepQuality"),
            sleep_score=(
                round(traing_status.get("sleepScore"), 2)
                if traing_status.get("sleepScore") is not None
                else None
            ),
            readiness=(
                round(traing_status.get("readiness"), 2)
                if traing_status.get("readiness") is not None
                else None
            ),
        )
    
    def _get(self, url: str, query_string: dict | None = None) -> dict | list:
        #logger.info(f"url: {url}, {query_string}")
        try:
            response = self.client.get(url, params=query_string)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as error:
            logger.exception(
                "Intervals API request failed. Status: %s, URL: %s",
                error.response.status_code,
                f"{self.client.base_url}{url}",
            )
            raise
        except httpx.RequestError as error:
            logger.exception(
                "Intervals API request failed. URL: %s",
                f"{self.client.base_url}{url}",
            )
            raise
