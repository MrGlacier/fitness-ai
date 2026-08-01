import sys
import asyncio

from fitness.fitness_agent import FitnessAgent
from llm.llm_client import LlmClient
from connectors.mcp_client import McpClient

async def main():
    mcp_client = McpClient()
    llm_client = LlmClient()
    fitness_agent = FitnessAgent(llm_client_instance=llm_client, mcp_client_instance=mcp_client)

    if len(sys.argv) <= 1:
        print(
    """\033[31mBitte mindestens eine Frage übergeben.\033[0m

Beispiel:
PYTHONPATH=. uv run python -m main "Wie hoch ist mein FTP?"
"""
)
        sys.exit(1)
    
    # sys.argv[0] ist der Skriptname, sys.argv[1] ist das erste Argument
    for question in sys.argv[1:]:
        answer = await fitness_agent.ask(question)
        print(f"""Antwort auf die Frage
'{question}'

'{answer}'""")


if __name__ == "__main__":
    asyncio.run(main())
