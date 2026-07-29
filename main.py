import asyncio

from fitness.fitness_agent import FitnessAgent
from llm.llm_client import LlmClient
from connectors.mcp_client import McpClient

async def main():
    mcp_client = McpClient()
    llm_client = LlmClient()
    fitness_agent = FitnessAgent(llm_client_instance=llm_client, mcp_client_instance=mcp_client)

    #question = "Wie hoch ist mein FTP?"
    question = "Wie war mein letztes Lauftraining?"
    answer = await fitness_agent.ask(question)
    print(f"Antwort auf '{question}' ist '{answer}'")



if __name__ == "__main__":
    asyncio.run(main())
