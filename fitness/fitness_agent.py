import json

from llm.llm_client import LlmClient
from connectors.mcp_client import McpClient

from core.logger import logger


class FitnessAgent:
    def __init__(self, llm_client_instance: LlmClient, mcp_client_instance: McpClient):
        logger.info("FitnessAgent::init called")
        self.llm_client_instance = llm_client_instance
        self.mcp_client_instance = mcp_client_instance
        self.ask_for_tool_prompt = """Du bist ein Tool-Planer für eine Fitness-Anwendung.\
        
        Deine Aufgabe ist noch nicht, die Benutzerfrage fachlich zu beantworten.
        
        Prüfe ausschließlich, welches der verfügbaren Tools zur Beantwortung der Benutzerfrage geeignet ist.
        
        Verfügbare Tools:
        
        {tools}
        
        Benutzerfrage:
        
        {question}
        
        Antworte ausschließlich mit gültigem JSON.

        Beispiel:

        ```json
        {{
            "status": "found",
            "tool": "get_current_ftp"
        }}
        ```

        Falls kein Tool passt:

        ```json
        {{
            "status": "failed",
            "tool": ""
        }}
        ```
        
        Stelle keine Rückfragen und führe das Tool nicht aus.
        """

        self.answer_prompt = """
            Du bist ein erfahrener Triathlon- und Laufcoach.

            Ein Fitness-Tool hat bereits die benötigten Daten geliefert.
            Deine Aufgabe ist es, dem Athleten das Ergebnis verständlich zu erklären.

            Regeln:
            - Nutze ausschließlich die bereitgestellten Daten.
            - Erfinde keine zusätzlichen Werte oder Fakten.
            - Antworte in maximal 3 kurzen Sätzen.
            - Antworte freundlich und motivierend.

            Frage des Athleten:
            {question}

            Ergebnis des Fitness-Tools:
            {tool_result}

            Antwort:
            """ 

    async def ask(self, question: str) -> dict:
        tools_description = await self.build_tools_description_for_llm()
        generated_question = self.ask_for_tool_prompt.format(tools=tools_description, question=question)
        answer = self.llm_client_instance.ask(question=generated_question)
        clean_string = answer["answer"].replace("json", "").replace("`", "")
        parsed_json = json.loads(clean_string)

        if parsed_json["status"] == "found":
            tool_answer = await self.mcp_client_instance.call_tool(parsed_json["tool"], {})
            tool_result = json.loads(tool_answer.content[0].text)
            if tool_result:
                return self.__generate_answer(pre_question=question, tool_result=tool_result)

        return f"Für die Frage '{question}' konnte kein passendes Tool gefunden werden."
        
    def answer(self, question: str) -> dict:
        logger.info("answer? - %s", question)
        return []

    def __generate_answer(self, pre_question: str, tool_result: dict[str, object]):
        generated_question = self.answer_prompt.format(question=pre_question, tool_result=tool_result)
        answer = self.llm_client_instance.ask(question=generated_question)
        return answer["answer"]

    async def build_tools_description_for_llm(self):
        tools = await self.mcp_client_instance.list_tools()
        tools_description = []
        for tool in tools.tools:
            tools_description.append({
                "name": tool.name,
                "beschreibung": tool.description
            })

        return tools_description
