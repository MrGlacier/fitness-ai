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


class LlmResponseError(RuntimeError):
    """Die LLM-API hat keine verwendbare Chat-Antwort geliefert."""


class LlmClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | httpx.Timeout = 300.0,
    ):
        self.base_url = base_url or config.get_llm_base_url()
        request_timeout = (
            httpx.Timeout(timeout, connect=10.0)
            if isinstance(timeout, (int, float))
            else timeout
        )
        self.httpx_client = httpx.Client(
            base_url=self.base_url,
            timeout=request_timeout,
        )

    def ask(
        self,
        question: str,
        system_prompt=None,
        max_tokens: int | None = None,
        step_name: str = "LLM",
        timeout: float | httpx.Timeout | None = None,
    ) -> dict:
        endpoint = llm_endpoints["completions"]
        post_data: dict = {
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
            "temperature": 0,
            "chat_template_kwargs": {
                "enable_thinking": False,
            },
        }

        if max_tokens is not None:
            post_data["max_tokens"] = max_tokens

        answer = self._post(
            endpoint,
            post_data,
            step_name=step_name,
            timeout=timeout,
        )

        choices = answer.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LlmResponseError(
                f"[{step_name}] LLM-Antwort enthält keine Auswahl (choices)."
            )

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise LlmResponseError(
                f"[{step_name}] Erstes LLM-Choice hat ein ungültiges Format."
            )

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise LlmResponseError(
                f"[{step_name}] LLM-Choice enthält keine gültige Nachricht."
            )

        answer_received = message.get("content")
        finish_reason = first_choice.get("finish_reason")
        usage = answer.get("usage", {})
        completion_tokens = (
            usage.get("completion_tokens") if isinstance(usage, dict) else None
        )

        if not isinstance(answer_received, str) or not answer_received.strip():
            logger.warning(
                "[%s] WARNUNG: LLM-Antwort ist leer! finish_reason=%s, completion_tokens=%s",
                step_name,
                finish_reason,
                completion_tokens,
            )
            logger.debug(
                "[%s] Felder der LLM-Nachricht: %s",
                step_name,
                sorted(message.keys()),
            )
            raise LlmResponseError(
                f"[{step_name}] LLM lieferte keinen Antworttext "
                f"(finish_reason={finish_reason}, "
                f"completion_tokens={completion_tokens})."
            )

        return {
            "success": True,
            "answer": answer_received,
        }

    def _post(
        self,
        url: str,
        post_data: dict | None = None,
        step_name: str = "LLM",
        timeout: float | httpx.Timeout | None = None,
    ) -> dict:
        try:
            start = time.perf_counter()
            if timeout is None:
                response = self.httpx_client.post(url, json=post_data)
            else:
                response = self.httpx_client.post(
                    url,
                    json=post_data,
                    timeout=timeout,
                )
            duration = time.perf_counter() - start
            response.raise_for_status()
            try:
                response_json = response.json()
            except ValueError as error:
                raise LlmResponseError(
                    f"[{step_name}] LLM-API lieferte kein gültiges JSON."
                ) from error

            if not isinstance(response_json, dict):
                raise LlmResponseError(
                    f"[{step_name}] LLM-API lieferte kein JSON-Objekt."
                )
            usage = response_json.get("usage")

            completion_tokens = (
                usage.get("completion_tokens") if isinstance(usage, dict) else None
            )
            prompt_tokens = (
                usage.get("prompt_tokens") if isinstance(usage, dict) else None
            )

            if completion_tokens and prompt_tokens:
                logger.info(
                    "[%s] %s in %.2f Sekunden – Prompt: %s Tokens | Antwort: %s Tokens",
                    step_name,
                    url,
                    duration,
                    prompt_tokens,
                    completion_tokens,
                )
            else:
                logger.info(
                    "[%s] %s in %.2f Sekunden",
                    step_name,
                    url,
                    duration,
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
