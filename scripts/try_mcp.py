import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = StdioServerParameters(
    command=sys.executable,
    args=["-m", "social_report_toolkit.mcp_server"],
    env=dict(os.environ),
    cwd=os.getcwd(),
)


async def call(session, tool, arguments):
    result = await session.call_tool(tool, arguments)
    text = result.content[0].text
    if result.is_error:
        raise RuntimeError(f"{tool} failed: {text}")
    return json.loads(text)


async def main():
    async with stdio_client(SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            summary = await call(session, "pull_youtube", {
                "handles": ["@fallontonight", "@ColbertLateShow", "@JimmyKimmelLive"],
                "limit": 10,
            })
            print("pull_youtube ->", json.dumps(summary, indent=2))

            cleaned = await call(session, "clean_dataset", {"dataset_id": summary["dataset_id"]})
            print("clean_dataset ->", json.dumps(cleaned, indent=2))

            export = await call(session, "export_csv", {"dataset_id": cleaned["dataset_id"]})
            print("export_csv ->", json.dumps(export, indent=2))


asyncio.run(main())