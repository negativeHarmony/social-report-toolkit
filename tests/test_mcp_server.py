import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = StdioServerParameters(
    command=sys.executable, args=["-m", "social_report_toolkit.mcp_server"]
)


async def _with_session(action):
    async with stdio_client(SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await action(session)


def run(action):
    return asyncio.run(_with_session(action))


def test_lists_all_tools():
    async def action(session):
        result = await session.list_tools()
        return {tool.name for tool in result.tools}
        assert run(action) == {"pull_youtube", "clean_dataset", "build_report", "export_csv"}


def test_rejects_empty_channel_list():
    async def action(session):
        return await session.call_tool("pull_youtube", {"handles": []})
    assert run(action).is_error


def test_rejects_path_traversal_id():
    async def action(session):
        return await session.call_tool("export_csv", {"dataset_id": "../../../.env"})
    assert run(action).is_error