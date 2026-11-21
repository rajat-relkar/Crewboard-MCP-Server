import asyncio
from uuid import uuid4

from dotenv import load_dotenv
from fastmcp import Client
from langchain.agents import create_agent
from langchain.mcp import MCPAdapter
from langchain.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from mcp_server.client_auth import make_oauth

load_dotenv()

mcp_adapter = MCPAdapter(Client("http://127.0.0.1:8083/mcp", auth=make_oauth()))

async def main():
    async with mcp_adapter:
        tools = await mcp_adapter.list_tools()

        agent = create_agent(
            model="groq:openai/gpt-oss-120b",
            tools=tools,
            system_prompt="You are a helpful task management assistant",
            checkpointer=InMemorySaver()
        )

        config = {"configurable": {"thread_id": str(uuid4())}}
        human_question = "Can you please help me"

        while human_question != "q":

            print("Agent Response:\n")
            result = await agent.ainvoke({"messages": [HumanMessage(content=human_question)]}, config=config)

            print(result["messages"][-1].text)

            human_question = input("Human Message (q to exit):\n")


if __name__ == "__main__":
    asyncio.run(main())