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
