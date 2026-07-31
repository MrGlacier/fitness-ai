import asyncio

from fitness.fitness_agent import FitnessAgent
from llm.llm_client import LlmClient
from connectors.mcp_client import McpClient

async def main():
    mcp_client = McpClient()
    llm_client = LlmClient()
    fitness_agent = FitnessAgent(llm_client_instance=llm_client, mcp_client_instance=mcp_client)

    #question = "Wie hoch ist mein FTP?"
    #question = "Wie war mein letztes Lauftraining?"
    #question = "Wie war mein letztes Training?"
    #question = "An welchem Wochentag trainiere ich in den letzten 30 Tagen am häufigsten?"
    #question = "Anhand meiner aktuellen FTP und meiner Trainings der letzten 7 Tage schlage mir die nächste Radeinheit vor."
    question="Vergleiche meine Lauf- und Radtrainings der letzten 14 Tage und sage mir, welche Disziplin ich zuletzt stärker trainiert habe."
    answer = await fitness_agent.ask(question)
    print(f"Antwort auf '{question}' ist '{answer}'")



if __name__ == "__main__":
    asyncio.run(main())
