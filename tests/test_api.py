import unittest
from unittest.mock import AsyncMock, patch

import api


class ChatCompletionHistoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_removes_last_user_message_instead_of_last_message(self):
        request = api.ChatCompletionRequest(
            model="fitness-ai",
            messages=[
                api.ChatMessage(role="user", content="Erste Frage"),
                api.ChatMessage(role="assistant", content="Erste Antwort"),
                api.ChatMessage(role="user", content="Aktuelle Frage"),
                api.ChatMessage(role="assistant", content="Nachfolgende Nachricht"),
            ],
        )

        ask_mock = AsyncMock(return_value="Antwort")
        with patch.object(api.fitness_agent, "ask", ask_mock):
            response = await api.chat_completions(request)

        ask_mock.assert_awaited_once_with(
            question="Aktuelle Frage",
            history=[
                {"role": "user", "content": "Erste Frage"},
                {"role": "assistant", "content": "Erste Antwort"},
                {"role": "assistant", "content": "Nachfolgende Nachricht"},
            ],
        )
        self.assertEqual(
            response["choices"][0]["message"]["content"],
            "Antwort",
        )


if __name__ == "__main__":
    unittest.main()


def test_api_writes_and_coaching_disabled(tmp_path):
    from unittest.mock import Mock
    from fitness.analyst import TrainingAnalyst
    from fitness.archive import AnalystStore
    from fitness.analyst_models import Race
    from tests.test_analyst import plan
    import api
    from fastapi.testclient import TestClient
    from unittest.mock import patch
    service = TrainingAnalyst(Mock(), AnalystStore(tmp_path))
    with patch.object(api, "training_analyst", service), patch.object(api.fitness_agent, "get_training_today_recommendation") as legacy:
        client = TestClient(api.app)
        assert client.post("/dashboard/training-today").status_code == 410
        legacy.assert_not_called()
        assert client.put("/analyst/plans", json=plan().model_dump(mode="json")).status_code == 200
        assert len(client.get("/analyst/plans").json()) == 1
        assert client.put("/analyst/assignment", json={"plan_id": "test", "start_date": "2026-11-16", "end_date": "2026-11-22"}).status_code == 200
        assert client.put("/analyst/assignment", json={"plan_id": "missing", "start_date": "2026-11-16", "end_date": "2026-11-22"}).status_code == 422
        race = Race(name="API Race", date="2026-11-20", target_seconds=4000, source_id="synthetic").model_dump(mode="json")
        created = client.put("/analyst/races", json=race).json()
        changed = client.put("/analyst/races", json=dict(race, target_seconds=3900)).json()
        assert created["id"] == changed["id"]
        assert len(service.store.records("race")) == 1
        assert client.put("/analyst/races", json=dict(race, target_seconds=-1)).status_code == 422
