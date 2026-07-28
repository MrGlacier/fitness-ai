import json

from llm.llm_client import LlmClient
from connectors.mcp_client import McpClient

from core.logger import logger


class FitnessAgent:
    def __init__(self, llm_client_instance: LlmClient, mcp_client_instance: McpClient):
        logger.info("FitnessAgent::init called")
        self.llm_client_instance = llm_client_instance
        self.mcp_client_instance = mcp_client_instance
        self.prompt = """Du bist ein Tool-Planer für eine Fitness-Anwendung.\
        
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

    async def ask(self, question: str) -> dict:
        tools_description = await self.build_tools_description_for_llm()
        generated_question = self.prompt.format(tools=tools_description, question=question)
        answer = self.llm_client_instance.ask(question=generated_question)
        clean_string = answer["answer"].replace("json", "").replace("`", "")
        parsed_json = json.loads(clean_string)

        if parsed_json["status"] == "found":
            tool_answer = await self.mcp_client_instance.call_tool(parsed_json["tool"], {})
            value = json.loads(tool_answer.content[0].text)["ftp"]

            if value:
                return value

        return f"Für die Frage '{question}' konnte kein passendes Tool gefunden werden."
        
    def answer(self, question: str) -> dict:
        logger.info("answer? - %s", question)
        return []

    async def build_tools_description_for_llm(self):
        tools = await self.mcp_client_instance.list_tools()
        tools_description = []
        for tool in tools.tools:
            tools_description.append({
                "name": tool.name,
                "beschreibung": tool.description
            })

        return tools_description
