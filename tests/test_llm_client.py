import unittest
from unittest.mock import Mock

from llm.llm_client import LlmClient, LlmResponseError


class LlmClientResponseTests(unittest.TestCase):
    def setUp(self):
        self.client = LlmClient.__new__(LlmClient)

    def test_ask_disables_thinking_and_returns_content(self):
        self.client._post = Mock(return_value={
            "choices": [{
                "message": {"content": '{"status":"ok"}'},
                "finish_reason": "stop",
            }],
            "usage": {"completion_tokens": 6},
        })

        result = self.client.ask("Test")

        self.assertEqual(result["answer"], '{"status":"ok"}')
        post_data = self.client._post.call_args.args[1]
        self.assertEqual(
            post_data["chat_template_kwargs"],
            {"enable_thinking": False},
        )

    def test_ask_rejects_missing_choices(self):
        self.client._post = Mock(return_value={"choices": []})

        with self.assertRaisesRegex(LlmResponseError, "keine Auswahl"):
            self.client.ask("Test")

    def test_ask_rejects_empty_content_instead_of_using_reasoning(self):
        self.client._post = Mock(return_value={
            "choices": [{
                "message": {
                    "content": "",
                    "reasoning_content": "Interner Gedankentext",
                },
                "finish_reason": "length",
            }],
            "usage": {"completion_tokens": 128},
        })

        with self.assertRaisesRegex(LlmResponseError, "keinen Antworttext"):
            self.client.ask("Test", step_name="TEST")


if __name__ == "__main__":
    unittest.main()
