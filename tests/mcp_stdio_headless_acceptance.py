"""Smoke the full MCP stdio surface against a pinned headless worker."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-dir", required=True)
    parser.add_argument("--instance-id", required=True)
    return parser.parse_args()


async def run() -> int:
    args = parse_args()
    environment = {
        **os.environ,
        "BLENDER_MCP_RUNTIME_DIR": os.path.abspath(args.runtime_dir),
        "BLENDER_MCP_INSTANCE_ID": args.instance_id,
        "BLENDER_MCP_AGENT_ID": "stdio-acceptance",
    }
    params = StdioServerParameters(
        command=sys.executable,
        args=["-c", "from blender_mcp.app import main; main()"],
        env=environment,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            if len(tools.tools) != 60:
                raise AssertionError(f"full tool surface changed: {len(tools.tools)}")
            instances = await session.call_tool("list_blender_instances", {"validate_live": True})
            if instances.isError:
                raise AssertionError(f"instance discovery failed: {instances}")
            scene = await session.call_tool(
                "get_scene_info",
                {"user_prompt": "headless acceptance"},
            )
            if scene.isError:
                raise AssertionError(f"pinned headless route failed: {scene}")
            active = await session.call_tool("get_active_blender_instance", {})
            if active.isError:
                raise AssertionError(f"active-instance query failed: {active}")
            released = await session.call_tool("release_blender_instance", {})
            if released.isError:
                raise AssertionError(f"release failed: {released}")
            print(f"MCP_HEADLESS_ACCEPTANCE tools={len(tools.tools)} instance={args.instance_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
