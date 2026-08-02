# Intevals.icu - API Dokumentation
# https://intervals.icu/api-docs.html

from datetime import date, datetime, timedelta
import httpx
from core import config
from core.utils import meters_to_km
from fitness.models import Workout, Athlete, TrainingZones, TrainingStatus

from core.logger import logger

intervals_icu_endpoints = {
    "athlete": "/athlete/{athlete_id}",
    "sport-settings": "/athlete/{athlete_id}/sport-settings/{sport_type}",
    "activities": "/athlete/{athlete_id}/activities",
    "training-status": "/athlete/{athlete_id}/wellness/{for_date}",
}

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
            data = [activity for activity in data if activity.get("type").lower() == sport_type.lower()]
        
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


    def get_recent_workouts(self, days: int, sport_type: str | None = None) -> list[Workout]:
        endpoint = intervals_icu_endpoints["activities"].format(athlete_id=self.athlete_id)
        query_string = {"oldest": date.today() - timedelta(days=days)}
        query_string["newest"] = date.today()

        data = self._get(endpoint, query_string)
        if sport_type:
            # [Ergebnis for Element in Sammlung if Bedingung]
            data = [activity for activity in data if activity.get("type").lower() == sport_type.lower()]

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


    def get_current_training_status(self, for_date: date) -> TrainingStatus:
        endpoint = intervals_icu_endpoints["training-status"].format(
            athlete_id=self.athlete_id,
            for_date=for_date,
        )

        current_training_status = self._get(endpoint)
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

        return Workout(
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
            variability_index = (round(variability_index, 2) if variability_index is not None else None)
        )
    
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

    def _map_training_status(self, traing_status: list) -> TrainingStatus:
        #logger.info(f"_map_training_status: %s", traing_status)

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
