# mcp_client.py

from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from core.logger import logger


class McpClient:
    def __init__(self):
        project_dir = Path(__file__).resolve().parent

        self.server_params = StdioServerParameters(
            command="uv",
            args=[
                "run",
                "python",
                "-m",
                "connectors.mcp_server",
            ],
            cwd=str(project_dir.parent),
        )

    async def list_tools(self):
        #logger.info("MCP-Tools werden abgerufen")

        async with stdio_client(self.server_params) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(
                read_stream,
                write_stream,
            ) as session:
                await session.initialize()
                return await session.list_tools()
            

    async def call_tool(self, tool_name: str, arguments: dict):
        logger.info(
            "MCP-Tool wird aufgerufen: %s mit %s",
            tool_name,
            arguments,
        )

        async with stdio_client(self.server_params) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(
                read_stream,
                write_stream,
            ) as session:
                await session.initialize()

                return await session.call_tool(
                    tool_name,
                    arguments,
                )
