import json

from llm.llm_client import LlmClient
from connectors.mcp_client import McpClient

from core.logger import logger


class FitnessAgent:
    def __init__(self, llm_client_instance: LlmClient, mcp_client_instance: McpClient):
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
            "tool": "get_current_ftp",
            "arguments": {{
                "sport_type": "run"
            }},
            "description: "Die Beschreibung des Tools.."
        }}
        ```

        Falls kein Tool passt:

        ```json
        {{
            "status": "failed",
            "tool": "",
            "arguments": {{}},
            "description": ""
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

            Verwendetes Fitness-Tool:
            {tool_name}

            Verwendete Argumente für das Tool:
            {tool_arguments}

            Beschreibung:
            {tool_description}

            Frage des Athleten:
            {pre_question}

            Ergebnis des Fitness-Tools:
            {tool_result}

            Antwort:
            """ 

    async def ask(self, question: str) -> dict:
        tools_description = await self.build_tools_description_for_llm()
        tools = self.ask_for_tool_prompt.format(tools=tools_description, question=question)
        tools_answer = self.llm_client_instance.ask(question=tools)
        tools_answer_string = tools_answer["answer"].replace("json", "").replace("`", "")
        tools_json = json.loads(tools_answer_string)
        
        if tools_json["status"] == "found":
            arguments = tools_json["arguments"]
            if not arguments:
                arguments = ""

            tool_answer = await self.mcp_client_instance.call_tool(tools_json["tool"], arguments)
            if tool_answer.content[0].text:
                tool_result = json.loads(tool_answer.content[0].text)

            if tool_result:
                return self.__generate_answer(pre_question=question, tool_name=tools_json["tool"], tool_arguments=arguments, tool_description=tools_json["description"], tool_result=tool_result)

        return f"Für die Frage '{question}' konnte kein passendes Tool gefunden werden."
        
    def answer(self, question: str) -> dict:
        logger.info("answer? - %s", question)
        return []

    def __generate_answer(self, pre_question: str, tool_name: str, tool_arguments: dict, tool_description: str, tool_result: dict[str, object]):
        generated_question = self.answer_prompt.format(pre_question=pre_question, tool_name=tool_name, tool_arguments=tool_arguments, tool_description=tool_description, tool_result=tool_result)
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
