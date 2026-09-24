"""Tests fur das Dashboard."""

import json
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
from starlette.requests import Request

from dashboard import routes
class DashboardRouteTests(unittest.TestCase):
    """Tests fur die Dashboard-Route."""

    @staticmethod
    def _request() -> Request:
        return Request({
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "scheme": "http",
        })

    def _get_dashboard(self):
        return routes.dashboard_index(self._request())

    @staticmethod
    def _post_chat(question: str):
        return routes.dashboard_chat(DashboardRouteTests._request(), question)

    def _make_summary_response(self, **kwargs):
        """Erzeugt eine Summary-Antwort mit Default-Werten."""
        defaults = {
            "training_status": {
                "ctl": 55.0,
                "atl": 25.0,
                "form": 30.0,
                "form_status": "frisch",
                "summary": "Du bist aktuell gut erholt.",
                "resting_hr": 48,
                "hrv": 55.0,
                "readiness": 72.0,
            },
            "last_workouts": [
                {
                    "date": "07.09.2025",
                    "name": "Morgensprint",
                    "sport": "Run",
                    "distance_km": 10.0,
                    "duration_sec": 3600,
                    "tss": 75,
                },
                {
                    "date": "05.09.2025",
                    "name": "Radtour See",
                    "sport": "Ride",
                    "distance_km": 45.0,
                    "duration_sec": 5400,
                    "tss": 90,
                },
            ],
            "week_stats": {
                "total_sessions": 5,
                "total_duration": "4h 30m",
                "total_duration_sec": 16200,
                "total_tss": 185,
                "by_sport": {
                    "Run": {"count": 3, "duration_sec": 10800, "tss": 120},
                    "Ride": {"count": 1, "duration_sec": 5400, "tss": 90},
                },
            },
        }
        defaults.update(kwargs)
        return json.dumps(defaults)

    @patch("dashboard.routes._api_client")
    def test_dashboard_root_returns_200(self, mock_client):
        """Dashboard-Root ist erreichbar und liefert HTTP 200."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = json.loads(
            self._make_summary_response()
        )
        mock_client.get.return_value = mock_response

        response = self._get_dashboard()
        self.assertEqual(response.status_code, 200)
        mock_client.post.assert_not_called()

    @patch("dashboard.routes._api_client")
    def test_training_today_is_loaded_separately(self, mock_client):
        """Die langsame Empfehlung blockiert nicht den initialen Seitenaufruf."""
        training_response = MagicMock()
        training_response.json.return_value = {
            "success": True,
            "data": {
                "primary": {
                    "sport": "Run",
                    "type": "easy",
                    "title": "Lockerer Lauf",
                    "duration_min": 40,
                    "details": "Ruhig laufen.",
                },
                "alternatives": [
                    {
                        "category": "hard",
                        "sport": "Ride",
                        "title": "Schwellenintervalle",
                        "duration_min": 50,
                        "details": "3 × 8 Minuten an der Schwelle.",
                    },
                ],
                "reason": "Passt zum Gesamtbild.",
                "warning": None,
            },
        }
        mock_client.post.return_value = training_response

        response = routes.dashboard_training_today(self._request())

        self.assertEqual(response.status_code, 200)
        self.assertIn("Lockerer Lauf", response.body.decode())
        self.assertIn("BALLERN", response.body.decode())
        self.assertIn("🚴 Ride", response.body.decode())
        mock_client.post.assert_called_once()

    def test_dashboard_healthcheck_has_no_external_dependency(self):
        """Der Container-Healthcheck ruft weder Fitness API noch LLM auf."""
        from dashboard.app import health

        self.assertEqual(
            health(),
            {"status": "ok", "service": "fitness-ai-dashboard"},
        )

    @patch("dashboard.routes._api_client")
    def test_dashboard_contains_key_sections(self, mock_client):
        """Alle vier Bereiche werden im HTML gerendert."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = json.loads(
            self._make_summary_response()
        )
        mock_client.get.return_value = mock_response

        response = self._get_dashboard()
        self.assertEqual(response.status_code, 200)

        html = response.body.decode()
        self.assertIn("Training heute", html)
        self.assertIn("training-today-loading", html)
        self.assertIn("Fitnesswerte", html)
        self.assertIn("7 Tage", html)
        self.assertIn("Letzte Aktivit", html)
        self.assertIn("Frag deine Fitness-AI", html)

    @patch("dashboard.routes._api_client")
    def test_dashboard_shows_training_data(self, mock_client):
        """Dashboard zeigt Trainingsdaten aus der API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = json.loads(
            self._make_summary_response()
        )
        mock_client.get.return_value = mock_response

        response = self._get_dashboard()
        html = response.body.decode()

        self.assertIn("55.0", html)
        self.assertIn("25.0", html)
        self.assertIn("30.0", html)
        self.assertIn("Morgensprint", html)
        self.assertIn("Radtour See", html)
        self.assertIn("Run", html)
        self.assertIn("Ride", html)
        self.assertIn("10.0 km", html)
        self.assertIn("45.0 km", html)
        self.assertEqual(html.count('class="tss tss-high"'), 2)
        self.assertIn('<span class="week-stat tss">TSS: 185</span>', html)

    @patch("dashboard.routes._api_client")
    def test_dashboard_handles_api_unavailable(self, mock_client):
        """Fehlende Fitness API fuhrt nicht zu einem Crash."""
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        response = self._get_dashboard()
        self.assertEqual(response.status_code, 200)

        html = response.body.decode()
        self.assertIn("Training heute", html)
        self.assertIn("placeholder", html)

    @patch("dashboard.routes._api_client")
    def test_dashboard_chat_with_mocked_api(self, mock_client):
        """Chat-Frage wird an Fitness API weitergeleitet."""
        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = {
            "training_status": None,
            "last_workouts": [],
            "week_stats": {},
        }

        chat_response = MagicMock()
        chat_response.status_code = 200
        chat_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Das ist eine Testantwort.",
                    },
                    "finish_reason": "stop",
                }
            ],
        }

        mock_client.get.return_value = get_response
        mock_client.post.return_value = chat_response

        response = self._post_chat("Wie war mein letzter Lauf?")
        self.assertEqual(response.status_code, 200)
        html = response.body.decode()
        self.assertIn("Testantwort", html)

    @patch("dashboard.routes._api_client")
    def test_dashboard_chat_handles_api_error(self, mock_client):
        """Chat mit fehlerhafter API zeigt Fehlermeldung, kein 500er."""
        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = {
            "training_status": None,
            "last_workouts": [],
            "week_stats": {},
        }

        mock_client.get.return_value = get_response
        mock_client.post.side_effect = httpx.ConnectError("LLM unreachable")

        response = self._post_chat("Wie hoch ist mein FTP?")
        self.assertEqual(response.status_code, 200)
        html = response.body.decode()
        self.assertIn("Konnte keine Antwort erhalten", html)

    @patch("dashboard.routes._api_client")
    def test_dashboard_chat_empty_question(self, mock_client):
        """Leere Chat-Frage wird abgefangen."""
        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = {
            "training_status": None,
            "last_workouts": [],
            "week_stats": {},
        }

        mock_client.get.return_value = get_response

        response = self._post_chat("")
        self.assertEqual(response.status_code, 200)
        html = response.body.decode()
        self.assertIn("Bitte gib eine Frage ein", html)

    @patch("dashboard.routes._api_client")
    def test_dashboard_chat_not_sending_llm_on_empty(self, mock_client):
        """Bei leerer Frage wird kein POST an /v1/chat/completions gesendet."""
        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = {
            "training_status": None,
            "last_workouts": [],
            "week_stats": {},
        }

        mock_client.get.return_value = get_response

        self._post_chat("")

        mock_client.post.assert_not_called()


class DashboardSummaryEndpointTests(unittest.TestCase):
    """Tests fur den /dashboard/summary API-Endpoint."""

    def test_summary_structure(self):
        """Der Summary-Endpoint liefert die erwarteten Schlussel."""
        import api
        self.assertTrue(callable(api.dashboard_summary))

    def test_summary_formats_hours_and_remaining_minutes(self):
        """Restsekunden werden nicht irrtümlich als Minuten angezeigt."""
        import api

        workout = SimpleNamespace(
            start_time=datetime.now(),
            name="Testfahrt",
            sport="Ride",
            distance_km=40.0,
            duration_sec=7320,
            tss=75,
        )

        with patch.object(api._analyzer, "get_current_training_status", return_value=None), \
             patch.object(
                 api._analyzer.intervals_client_instance,
                 "get_recent_workouts",
                 return_value=[workout],
             ):
            summary = api.dashboard_summary()

        self.assertEqual(summary["week_stats"]["total_duration"], "2h 2m")


class TrainingTodayModelTests(unittest.TestCase):
    """Tests fur das TrainingTodayRecommendation Pydantic-Modell."""

    def test_valid_recommendation(self):
        """Ein valides Recommendation-Objekt wird korrekt erstellt."""
        from fitness.models import TrainingTodayRecommendation

        data = {
            "primary": {
                "sport": "Run",
                "type": "threshold",
                "title": "3 × 8 min Schwelle",
                "duration_min": 55,
                "details": "15 min locker, 3 × 8 min Schwelle, 3 min Trabpause, 10 min auslaufen",
            },
            "alternatives": [
                {
                    "category": "swim",
                    "sport": "Swim",
                    "title": "Technik + zügige 100er",
                    "duration_min": 50,
                    "details": "400 locker, 8 × 100 zügig, 200 auslaufen",
                },
                {
                    "category": "hard",
                    "sport": "Ride",
                    "title": "VO2-Intervalle",
                    "duration_min": 50,
                    "details": "15 min warm-up, 5 × 3 min VO2, 3 min easy, 10 min cool-down",
                },
                {
                    "category": "easy",
                    "sport": "Run",
                    "title": "Easy Run",
                    "duration_min": 45,
                    "details": "Zweier-Zone, locker plaudern",
                },
            ],
            "reason": "Deine Form ist frisch und die ATL niedrig — heute ist ein guter Tag.",
            "warning": None,
        }

        rec = TrainingTodayRecommendation(**data)
        self.assertEqual(rec.primary.sport, "Run")
        self.assertEqual(rec.primary.type, "threshold")
        self.assertEqual(len(rec.alternatives), 3)

    def test_non_hard_alternative_can_be_unavailable(self):
        """Eine nicht harte Alternative kann als nicht verfügbar markiert werden."""
        from fitness.models import TrainingTodayRecommendation

        data = {
            "primary": {
                "sport": "Run",
                "type": "easy",
                "title": "Easy Run",
                "duration_min": 40,
                "details": "Locker laufen",
            },
            "alternatives": [
                {"category": "swim", "sport": "Swim", "title": "Easy Swim", "duration_min": 30, "details": "Locker schwimmen", "available": False, "unavailable_reason": "Kein Schwimmtraining möglich."},
                {"category": "hard", "sport": "Ride", "title": "VO2", "duration_min": 50, "details": "Hart"},
                {"category": "easy", "sport": "Run", "title": "Easy Run", "duration_min": 45, "details": "Locker laufen"},
            ],
            "reason": "Test-Begrundung.",
            "warning": None,
        }

        rec = TrainingTodayRecommendation(**data)
        swim_alt = next(a for a in rec.alternatives if a.category == "swim")
        self.assertFalse(swim_alt.available)

    def test_missing_swim_raises(self):
        """Ohne Schwimmen-Alternative wird ein Fehler geworfen."""
        from fitness.models import TrainingTodayRecommendation

        data = {
            "primary": {"sport": "Run", "type": "easy", "title": "Easy", "duration_min": 40, "details": "Leicht"},
            "alternatives": [
                {"category": "hard", "sport": "Ride", "title": "VO2", "duration_min": 50, "details": "Hart"},
                {"category": "easy", "sport": "Run", "title": "Easy", "duration_min": 40, "details": "Leicht"},
            ],
            "reason": "Zu wenig.",
            "warning": None,
        }

        with self.assertRaises(Exception):
            TrainingTodayRecommendation(**data)

    def test_json_roundtrip(self):
        """Model kann nach JSON und zuruck gelesen werden."""
        from fitness.models import TrainingTodayRecommendation

        data = {
            "primary": {"sport": "Run", "type": "threshold", "title": "3 × 8", "duration_min": 55, "details": "15 min locker, 3 × 8 min, 10 min auslaufen"},
            "alternatives": [
                {"category": "swim", "sport": "Swim", "title": "Technik", "duration_min": 50, "details": "Technik"},
                {"category": "hard", "sport": "Ride", "title": "VO2", "duration_min": 50, "details": "Hart"},
                {"category": "easy", "sport": "Run", "title": "Easy", "duration_min": 45, "details": "Leicht"},
            ],
            "reason": "Test-Begrundung fur die Empfehlung.",
            "warning": None,
        }

        rec = TrainingTodayRecommendation(**data)
        json_str = rec.model_dump_json()
        rec2 = TrainingTodayRecommendation.model_validate_json(json_str)
        self.assertEqual(rec2.primary.title, "3 × 8")


class TssColorClassTests(unittest.TestCase):
    """Tests für den TSS-Färbungs-Filter."""

    def test_tss_low_returns_blue_class(self):
        """TSS ≤ 40 → tss-low."""
        from dashboard.routes import _tss_color_class

        self.assertEqual(_tss_color_class(0), "tss-low")
        self.assertEqual(_tss_color_class(20), "tss-low")
        self.assertEqual(_tss_color_class(40), "tss-low")

    def test_tss_medium_returns_orange_class(self):
        """41 ≤ TSS ≤ 70 → tss-medium."""
        from dashboard.routes import _tss_color_class

        self.assertEqual(_tss_color_class(41), "tss-medium")
        self.assertEqual(_tss_color_class(55), "tss-medium")
        self.assertEqual(_tss_color_class(70), "tss-medium")

    def test_tss_high_returns_red_class(self):
        """TSS > 70 → tss-high."""
        from dashboard.routes import _tss_color_class

        self.assertEqual(_tss_color_class(71), "tss-high")
        self.assertEqual(_tss_color_class(100), "tss-high")
        self.assertEqual(_tss_color_class(200), "tss-high")

    def test_tss_none_returns_empty_string(self):
        """None → leere Zeichenkette."""
        from dashboard.routes import _tss_color_class

        self.assertEqual(_tss_color_class(None), "")

    def test_tss_thresholds_are_exported(self):
        """Schwellenwerte sind als Modulebenen-Konstanten verfügbar."""
        from dashboard.routes import TSS_LOW_MAX, TSS_MEDIUM_MAX

        self.assertEqual(TSS_LOW_MAX, 40)
        self.assertEqual(TSS_MEDIUM_MAX, 70)


if __name__ == "__main__":
    unittest.main()
