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
        logger.info("ask? - %s", question)

        tools_description = await self.build_tools_description_for_llm()
        logger.info("ask::tools_description - %s", tools_description)

        logger.info("ask::prompt - %s", self.prompt)

        generated_question = self.prompt.format(tools=tools_description, question=question)
        logger.info("ask::generated_question %s", generated_question)

        answer = self.llm_client_instance.ask(question=generated_question)
        logger.info("ask::answer %s", answer)
        # Extrahiere den Tool-Namen
        # 1. Teile den String an der ersten Zeile auf
        #tool_line = answer["answer"].splitlines()[0]
        # 2. Teile die erste Zeile am Doppelpunkt und nimm den Teil danach
        #tool = tool_line.split(":", 1)[1].strip()
        #logger.info("tool %s", tool)

        #ftp = await self.mcp_client_instance.call_tool(tool, {})
        #logger.info("aks::Dein FTP ist: %s", json.loads(ftp.content[0].text)["ftp"])
        return []
        
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
