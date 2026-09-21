import json
import unittest
from datetime import date
from types import SimpleNamespace

from pydantic import ValidationError

from fitness.fitness_agent import FitnessAgent
from fitness.models import TrainingTodayRecommendation
from intervals.intervals_client import IntervalsClient
from llm.prompts import TRAINING_TODAY_SYSTEM_PROMPT


def recommendation_json(**overrides) -> str:
    data = {
        "primary": {
            "sport": "Run",
            "type": "easy",
            "title": "Lockerer Lauf",
            "duration_min": 40,
            "details": "10 Minuten einlaufen, 20 Minuten locker, 10 Minuten auslaufen.",
        },
        "alternatives": [
            {
                "category": "swim",
                "sport": "Swim",
                "title": "Technikschwimmen",
                "duration_min": 35,
                "details": "Ruhige Technikserien mit langen Pausen.",
            },
            {
                "category": "hard",
                "sport": "Ride",
                "title": "Schwellenintervalle",
                "duration_min": 50,
                "details": "Heute nicht vorgesehen.",
                "available": False,
                "unavailable_reason": (
                    "Die intensive Einheit gestern und der Wettkampf in zwei Tagen "
                    "sprechen heute gegen zusätzliche Belastung."
                ),
            },
            {
                "category": "easy",
                "sport": "Ride",
                "title": "Lockere Rolle",
                "duration_min": 40,
                "details": "Durchgehend locker und ohne Belastungsspitzen.",
            },
        ],
        "reason": (
            "Die intensive Einheit gestern und der Wettkampf in zwei Tagen machen "
            "eine lockere Einheit heute zur passenderen Option."
        ),
        "warning": "Wettkampf in zwei Tagen — zusätzliche Ermüdung heute vermeiden.",
    }
    data.update(overrides)
    return json.dumps(data)


class TrainingTodayPromptAndModelTests(unittest.TestCase):
    def test_prompt_does_not_use_absolute_atl_threshold(self):
        self.assertNotIn("ATL (acute load, > ~40)", TRAINING_TODAY_SYSTEM_PROMPT)
        self.assertIn("ATL niemals isoliert", TRAINING_TODAY_SYSTEM_PROMPT)
        self.assertIn("bevorstehende Wettkämpfe", TRAINING_TODAY_SYSTEM_PROMPT)

    def test_unsupported_risk_claim_is_rejected(self):
        data = json.loads(recommendation_json())
        data["reason"] = (
            "Wegen deiner aktuellen Werte würde eine harte Einheit dein "
            "Verletzungsrisiko erhöhen."
        )

        with self.assertRaisesRegex(ValidationError, "Risikoaussage"):
            TrainingTodayRecommendation.model_validate(data)

    def test_isolated_atl_assessment_is_rejected(self):
        data = json.loads(recommendation_json())
        data["reason"] = "ATL ist mit 43.11 zu hoch, deshalb solltest du heute locker trainieren."

        with self.assertRaisesRegex(ValidationError, "ATL darf nicht isoliert"):
            TrainingTodayRecommendation.model_validate(data)

    def test_unavailable_hard_alternative_requires_reason(self):
        data = json.loads(recommendation_json())
        hard = next(alt for alt in data["alternatives"] if alt["category"] == "hard")
        hard.pop("unavailable_reason")

        with self.assertRaisesRegex(ValidationError, "unavailable_reason"):
            TrainingTodayRecommendation.model_validate(data)

    def test_contextual_unavailable_hard_alternative_is_valid_json(self):
        recommendation = TrainingTodayRecommendation.model_validate_json(
            recommendation_json()
        )
        hard = next(
            alt for alt in recommendation.alternatives if alt.category.value == "hard"
        )
        self.assertFalse(hard.available)


class FakeLlmClient:
    def __init__(self, answers):
        self.answers = iter(answers)
        self.questions = []

    def ask(self, **kwargs):
        self.questions.append(kwargs["question"])
        return {"answer": next(self.answers)}


class FakeIntervalsClient:
    def __init__(self):
        self.workout_calls = []
        self.event_calls = []

    def get_workouts(self, from_date, to_date):
        self.workout_calls.append((from_date, to_date))
        return []

    def get_upcoming_events(self, days_ahead, reference_date=None):
        self.event_calls.append((days_ahead, reference_date))
        return [{
            "name": "Testlauf",
            "date": "2026-09-23",
            "distance_days": 2,
            "category": "RACE_A",
            "sport": "Run",
        }]


class FakeAnalyzer:
    def __init__(self):
        self.intervals_client_instance = FakeIntervalsClient()

    def get_current_training_status(self, for_date):
        return SimpleNamespace(
            ctl=51.0,
            atl=43.11,
            form=7.89,
            form_status="frisch",
            summary="Kurz- und Langzeitbelastung werden gemeinsam betrachtet.",
            resting_hr=48,
            hrv=62.0,
            sleep_secs=27000,
            sleep_quality=4,
            sleep_score=82.0,
            readiness=78.0,
        )

    def get_current_ftp(self, sport):
        return {"sport_type": sport, "ftp": None}


class TrainingTodayAgentTests(unittest.TestCase):
    def test_retry_receives_validation_feedback_and_event_context(self):
        llm = FakeLlmClient(["not-json", f"```json\n{recommendation_json()}\n```"])
        analyzer = FakeAnalyzer()
        agent = FitnessAgent(llm, SimpleNamespace(), analyzer=analyzer)

        recommendation = agent.get_training_today_recommendation(
            for_date=date(2026, 9, 21)
        )

        self.assertEqual(recommendation.primary.type.value, "easy")
        self.assertEqual(len(llm.questions), 2)
        self.assertIn("Testlauf", llm.questions[0])
        self.assertIn("vorherige Antwort war ungültig", llm.questions[1])
        self.assertEqual(len(analyzer.intervals_client_instance.workout_calls), 1)
        self.assertEqual(
            analyzer.intervals_client_instance.event_calls,
            [(21, date(2026, 9, 21))],
        )


class UpcomingEventsTests(unittest.TestCase):
    def test_events_query_and_mapping_use_intervals_contract(self):
        client = IntervalsClient.__new__(IntervalsClient)
        client.athlete_id = "athlete"
        captured = {}

        def fake_get(endpoint, query):
            captured["endpoint"] = endpoint
            captured["query"] = query
            return [
                {
                    "id": 1,
                    "name": "A-Wettkampf",
                    "start_date_local": "2026-09-23T09:00:00",
                    "category": "RACE_A",
                    "type": "Run",
                    "distance": 10000,
                },
                {
                    "id": 2,
                    "name": "Geplantes Training",
                    "start_date_local": "2026-09-22T09:00:00",
                    "category": "WORKOUT",
                    "type": "Ride",
                },
            ]

        client._get = fake_get
        events = client.get_upcoming_events(21, reference_date=date(2026, 9, 21))

        self.assertEqual(captured["query"], {
            "oldest": "2026-09-21",
            "newest": "2026-10-12",
        })
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["distance_days"], 2)
        self.assertEqual(events[0]["sport"], "Run")


if __name__ == "__main__":
    unittest.main()
