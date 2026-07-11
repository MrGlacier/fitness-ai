from llm.llm_client import LlmClient
from connectors.mcp_client import McpClient

from core.logger import logger


class FitnessAgent:
    def __init__(self, llm_client_instance: LlmClient, mcp_client_instance: McpClient):
        self.llm_client_instance = llm_client_instance
        self.mcp_client_instance = mcp_client_instance

    def answer(self, question: str) -> dict:
        return self.llm_client_instance.ask(question=question)
