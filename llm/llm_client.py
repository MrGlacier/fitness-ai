# LLama.cpp Api Referenz
# https://thushan.github.io/olla/api-reference/llamacpp/

import httpx
import time

from core import config
from llm import prompts
from core.logger import logger

llm_endpoints = {
    "completions": "v1/chat/completions",
}

class LlmClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or config.get_llm_base_url()
        self.httpx_client = httpx.Client(base_url=self.base_url, timeout=None)

    def ask(self, question: str, system_prompt=None) -> dict:
        endpoint = llm_endpoints["completions"]
        post_data = {
            "model": "qwen",
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt if system_prompt else prompts.FITNESS_SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            "temperature": 0
        }

        answer = self._post(endpoint, post_data)
        answer_received = answer["choices"][0]["message"]["content"]

        return {
            "success": True,
            "answer": answer_received
        }
    

    def _post(self, url: str, post_data: dict | None = None) -> dict:
        try:
            start = time.perf_counter()
            response = self.httpx_client.post(url, json=post_data)
            duration = time.perf_counter() - start
            response.raise_for_status()
            response_json = response.json()
            logger.info("LLM antwortete in %.2f Sekunden", duration)
            usage = response_json.get("usage")

            if usage:
                logger.info(
                    "Prompt Tokens: %s | Completion Tokens: %s | Total Tokens: %s",
                    usage.get("prompt_tokens"),
                    usage.get("completion_tokens"),
                    usage.get("total_tokens"),
                )

            return response_json

        except httpx.HTTPStatusError as error:
            logger.exception(
                "LLM API request failed. Status: %s, URL: %s",
                error.response.status_code,
                f"{self.httpx_client.base_url}{url}",
            )
            raise

        except httpx.RequestError as error:
            logger.exception(
                "LLM API request failed. URL: %s",
                f"{self.httpx_client.base_url}{url}",
            )
            raise
