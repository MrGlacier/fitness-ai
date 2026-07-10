# LLama.cpp Api Referenz
# https://thushan.github.io/olla/api-reference/llamacpp/

import httpx

import config
from logger import logger

llm_endpoints = {
    "completions": "v1/chat/completions",
}

class LlmClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or config.get_llm_base_url()
        self.httpx_client = httpx.Client(base_url=self.base_url)

    def ask_for_hello(self) -> dict:
        endpoint = llm_endpoints["completions"]
        post_data = {
            "model": "qwen",
            "messages": [
                {
                    "role": "user",
                    "content": "Hallo! Antworte nur mit: Verbindung erfolgreich."
                }
            ],
            "temperature": 0
        }

        logger.info("LLM ask hello %s", endpoint, post_data)

        answer = self._post(endpoint, post_data)
        message_content = answer["choices"][0]["message"]["content"]
        return {
            "success": True,
            "answer": message_content
        }
    
    def _post(self, url: str, post_data: dict | None = None) -> dict:
        #logger.info(f"url: {url}, {query_string}")
        try:
            response = self.httpx_client.post(url, json=post_data)
            response.raise_for_status()
            return response.json()
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