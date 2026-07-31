import json

from llm.llm_client import LlmClient
from connectors.mcp_client import McpClient

from core.logger import logger


class FitnessAgent:
    def __init__(
        self,
        llm_client_instance: LlmClient,
        mcp_client_instance: McpClient,
    ):
        self.llm_client_instance = llm_client_instance
        self.mcp_client_instance = mcp_client_instance

        self.ask_for_tool_prompt = """
        Du bist ein Tool-Planer für eine Fitness-Anwendung.

        Deine Aufgabe ist noch nicht, die Benutzerfrage fachlich zu beantworten.

        Prüfe ausschließlich, welche der verfügbaren Tools zur Beantwortung
        der Benutzerfrage benötigt werden.

        Wähle alle benötigten Tools aus.

        Verfügbare Tools:

        {tools}

        Benutzerfrage:

        {question}

        Antworte ausschließlich mit gültigem JSON.

        Beispiel:

        ```json
        {{
            "status": "found",
            "tools": [
                {{
                    "tool": "get_current_ftp",
                    "arguments": {{
                        "sport_type": "ride"
                    }},
                    "description": "Liefert die aktuelle FTP."
                }},
                {{
                    "tool": "get_recent_workouts",
                    "arguments": {{
                        "days": 7,
                        "sport_type": "ride"
                    }},
                    "description": "Liefert die Radtrainings der letzten sieben Tage."
                }}
            ]
        }}
        ```

        Falls kein Tool passt:

        ```json
        {{
            "status": "failed",
            "tools": []
        }}
        ```

        Stelle keine Rückfragen und führe die Tools nicht aus.
        """

        self.answer_prompt = """
        Du bist ein erfahrener Triathlon- und Ausdauertrainer.

        Du erhältst:

        - die ursprüngliche Frage des Nutzers
        - die verwendeten Fitness-Tools
        - die Argumente der Tools
        - die Ergebnisse der Tools

        Deine Aufgabe ist es, daraus eine verständliche Antwort zu formulieren.

        Regeln:

        - Verwende ausschließlich die Informationen aus den Tool-Ergebnissen.
        - Erfinde keine Werte, Daten oder Fakten.
        - Interpretiere Messwerte nur, wenn dies anhand der vorhandenen Daten eindeutig möglich ist.
        - Wenn eine Bewertung nicht eindeutig möglich ist, beschränke dich auf die Beschreibung der Messwerte.
        - Erfinde keine Bedeutung oder Einordnung von Kennzahlen.
        - Erkläre Fachbegriffe kurz und einfach, wenn sie in der Antwort vorkommen.
        - Falls die Tools kein Ergebnis liefern, erkläre dies verständlich.
        - Verwende kein Markdown.
        - Antworte ausschließlich mit der fertigen Antwort.
        - Falls Informationen fehlen, sage das ausdrücklich.
        - Bewerte Trainingswerte nur, wenn die Tool-Ergebnisse selbst bereits eine Bewertung enthalten.
        - Werte wie TSS, Herzfrequenz, Pace, Leistung oder Dauer dürfen nicht eigenständig als gut, schlecht, leicht, schwer oder intensiv eingeordnet werden.
        - Antworte freundlich, aber ohne unbelegte Motivation oder Lob.

        Frage des Athleten:

        {pre_question}

        Verwendete Fitness-Tools und Ergebnisse:

        {tool_results}

        Antwort:
        """

    async def ask(self, question: str) -> str:
        tools_description = await self.build_tools_description_for_llm()
        tool_prompt = self.ask_for_tool_prompt.format(
            tools=tools_description,
            question=question,
        )

        tools_answer = self.llm_client_instance.ask(question=tool_prompt)
        tools_answer_string = (
            tools_answer["answer"]
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        tools_json = json.loads(tools_answer_string)
        if tools_json["status"] != "found":
            return (
                f"Für die Frage '{question}' konnte kein passendes "
                f"Tool gefunden werden."
            )

        tool_results = []

        for tool in tools_json["tools"]:
            tool_name = tool["tool"]
            tool_arguments = tool.get("arguments", {})
            tool_description = tool.get("description", "")

            logger.info(
                "Tool wird ausgeführt: %s mit %s",
                tool_name,
                tool_arguments,
            )

            tool_answer = await self.mcp_client_instance.call_tool(
                tool_name,
                tool_arguments,
            )

            if tool_answer.structuredContent is not None:
                tool_result = tool_answer.structuredContent.get("result")
            elif tool_answer.content and tool_answer.content[0].text:
                tool_result = json.loads(tool_answer.content[0].text)
            else:
                tool_result = None

            tool_results.append({
                "tool": tool_name,
                "arguments": tool_arguments,
                "description": tool_description,
                "result": tool_result,
            })

        return self.__generate_answer(
            pre_question=question,
            tool_results=tool_results,
        )

    def __generate_answer(
        self,
        pre_question: str,
        tool_results: list[dict],
    ) -> str:
        tool_results_json = json.dumps(
            tool_results,
            ensure_ascii=False,
            default=str,
        )

        generated_question = self.answer_prompt.format(
            pre_question=pre_question,
            tool_results=tool_results_json,
        )

        answer = self.llm_client_instance.ask(
            question=generated_question,
        )

        return answer["answer"]

    async def build_tools_description_for_llm(self) -> list[dict]:
        tools = await self.mcp_client_instance.list_tools()
        tools_description = []

        for tool in tools.tools:
            tools_description.append({
                "name": tool.name,
                "argumente": tool.inputSchema,
                "beschreibung": tool.description,
            })

        return tools_description
    