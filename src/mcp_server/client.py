"""Call the running MCP server's tools, the way a MCP client would.

Start the server first in another terminal:
    uv run python -m mcp_server.server
Then run:
    uv run python client.py
"""
import asyncio

from fastmcp import Client

from mcp_server.client_auth import make_oauth

SERVER_URL = "http://127.0.0.1:8083/mcp"

async def get_tools_from_server():
    async with Client(SERVER_URL, auth=make_oauth()) as client:
        tools = await client.list_tools()
        print("Tools:", [tool.name for tool in tools])

    return tools

async def create_task_using_mcp() -> None:
    async with Client(SERVER_URL, auth=make_oauth()) as client:
        result = await client.call_tool(
            "create_task",
            {"title": "this is third task", 
             "description": "this is a test"},
        )
        print("Created:", result.data)

async def update_task_status_from_mcp():
    async with Client(SERVER_URL, auth=make_oauth()) as client:
        result = await client.call_tool(
            "update_task_status",
            {
                "task_id":"1",
                "status":"in progress"
            }
        )

        print(result.data)
    return result.data

async def list_task_using_mcp():
    async with Client(SERVER_URL, auth=make_oauth()) as client:
        result = await client.call_tool(
            "list_tasks"
        )
        print(result.data)
    return result.data

if __name__ == "__main__":
    # asyncio.run(get_tools_from_server())
    asyncio.run(list_task_using_mcp())
    asyncio.run(update_task_status_from_mcp())
    asyncio.run(list_task_using_mcp())
    # asyncio.run(create_task_using_mcp())
