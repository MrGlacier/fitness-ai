# Intevals.icu - API Dokumentation
# https://intervals.icu/api-docs.html

from datetime import date, datetime, timedelta
import httpx
import config
from utils import meters_to_km
from models import Workout, Athlete

from logger import logger

intervals_icu_endpoints = {
    "athlete": "/athlete/{athlete_id}",
    "activities": "/athlete/{athlete_id}/activities",
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
            data = [activity for activity in data if activity.get("type") == sport_type]
        
        results = []
        for activity in data:
            converted_activity = self._map_activity_to_workout(activity)
            results.append(converted_activity)

        return results
    

    def get_last_workout(self, sport_type: str) -> Workout | None:
        from_date = date.today() - timedelta(days=30)
        to_date = date.today()
        last_workout = self.get_workouts(from_date=from_date, to_date=to_date, sport_type=sport_type)
        return last_workout[0] if last_workout else None

    def get_athlete_data(self) -> Athlete:
        endpoint = intervals_icu_endpoints["athlete"].format(athlete_id=self.athlete_id)
        athlete = self._get(endpoint)
        return self._map_athlete_data(athlete)

    def test_connection(self) -> dict:
        athlete = self.get_athlete_data()
        return {
            "success": True,
            "athlete": athlete
        }
        

    def _map_activity_to_workout(self, activity: dict) -> Workout:
        #logger.info("Mapping activity %s (%s)", activity.get("id"), activity.get("name"))

        start_date = activity.get("start_date")
        if start_date is None:
            raise ValueError(f"Activity {activity.get('id')} has no start_date")

        distance = activity.get("distance")

        return Workout(
            id=activity["id"],
            name=activity["name"],
            start_time=datetime.fromisoformat(start_date),
            sport=activity["type"],
            distance_km=meters_to_km(distance) if distance is not None else 0.0,
            duration_sec=activity["moving_time"],
            avg_hr=activity.get("average_heartrate"),
            tss=activity.get("icu_training_load"),
        )
    
    def _map_athlete(self, athlete_data: dict) -> Athlete:
        #logger.info("Mapping data %s: (%s)", data.get("id"), data.get("name"))

        return Athlete(
            id=athlete_data["id"],
            name=athlete_data["name"],
            email=athlete_data["email"],
            city=athlete_data["city"],
            timezone=athlete_data["timezone"],
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
