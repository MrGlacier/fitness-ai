# test_mcp_client.py

import asyncio

from connectors.mcp_client import McpClient


async def main():
    mcp_client = McpClient()
    #tools = await mcp_client.list_tools()
    #for tool in tools.tools:
    #    print(tool.name)
    result = await mcp_client.call_tool(
        "get_current_ftp",
        {},
    )

    print(result)


if __name__ == "__main__":
    asyncio.run(main())
