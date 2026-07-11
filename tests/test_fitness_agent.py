import asyncio

from fitness.fitness_agent import FitnessAgent
from llm.llm_client import LlmClient
from connectors.mcp_client import McpClient

from core.logger import logger

async def main():
    mcp_client = McpClient()
    llm_client = LlmClient()
    fa_client = FitnessAgent(llm_client_instance=llm_client, mcp_client_instance=mcp_client)
    tools = await mcp_client.list_tools()
    tool_list = []
    for tool in tools.tools:
        tool_list.append({
            "name": tool.name,
            "beschreibung": tool.description
        })

    genereler_prompt = """Du bist ein Tool-Planer für eine Fitness-Anwendung.\

Deine Aufgabe ist noch nicht, die Benutzerfrage fachlich zu beantworten.

Prüfe ausschließlich, welches der verfügbaren Tools zur Beantwortung der Benutzerfrage geeignet ist.

Verfügbare Tools:

{tools}

Benutzerfrage:

{question}

Antworte ausschließlich in diesem Format:

Tool: <Name des passenden Tools>
Begründung: <kurze Begründung>

Falls kein Tool geeignet ist, antworte:

Tool: keines
Begründung: <kurze Begründung>

Stelle keine Rückfragen und führe das Tool nicht aus.
"""

    tools_description = build_tool_description(tool_list)
    question1 = "Wie hoch ist meine aktuelle FTP?"
    question = genereler_prompt.format(tools=tools_description, question=question1)
    answer1 = fa_client.answer(question)

    question2 = "Zeige mir mein letztes Lauftraining."
    question = genereler_prompt.format(tools=tools_description, question=question2)
    answer2  = fa_client.answer(question)

    question3 = "Welche Herzfrequenzzonen habe ich?"
    question = genereler_prompt.format(tools=tools_description, question=question3)
    answer3  = fa_client.answer(question)

    question4 = "Ich bin 170 cm groß und wiege 66 kg. Wie hoch ist mein BMI?"
    question = genereler_prompt.format(tools=tools_description, question=question4)
    answer4  = fa_client.answer(question)

    print(f"Frage1: {question1}: {answer1}")
    print(f"Frage2: {question2}: {answer2}")
    print(f"Frage3: {question3}: {answer3}")
    print(f"Frage4: {question4}: {answer4}")


def build_tool_description(tool_list):
    answer = "Du hast folgende Tools zur Verfügung:"
    for tool in tool_list:
        answer += f"- {tool.get("name")}: {tool.get("beschreibung")}"
    
    return answer

if __name__ == "__main__":
    asyncio.run(main())
