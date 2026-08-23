# Multi-agent Blender headless

This fork keeps the upstream structured Blender MCP surface. It does not add a
second reduced MCP server: run one normal MCP process per agent, and point each
process at one headless Blender worker.

## Start workers automatically

Use one private runtime directory shared by the workers and MCP processes. Give
every worker its own `.blend` input/output directory.

```powershell
python scripts/launch_headless_worker.py `
  --blender "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" `
  --runtime-dir D:/blender-mcp-multi-agent/runtime `
  --label agent-a
```

The launcher starts Blender itself, waits for registration, and prints JSON
containing the `instance_id`, allocated port, stop file, and log path. Repeat it
with a new label for each agent. Use the printed stop file for cleanup; the
worker then exits without requiring a GUI.

Repeat the command with a different label, stop file, and project directory
for `agent-b`, `agent-c`, and so on. The extension allocates a free local port
when 9876 is already occupied and publishes the real endpoint in the registry.

## Pin each MCP process

First call `list_blender_instances` once and copy each `instance_id`. Configure
one MCP entry per agent (all entries expose the same full tool set):

```toml
[mcp_servers.blender_agent_a]
command = "D:/path/to/python/Scripts/blender-mcp.exe"

[mcp_servers.blender_agent_a.env]
BLENDER_MCP_RUNTIME_DIR = "D:/blender-mcp-multi-agent/runtime"
BLENDER_MCP_INSTANCE_ID = "<agent-a-instance-id>"
BLENDER_MCP_AGENT_ID = "agent-a"

[mcp_servers.blender_agent_b]
command = "D:/path/to/python/Scripts/blender-mcp.exe"

[mcp_servers.blender_agent_b.env]
BLENDER_MCP_RUNTIME_DIR = "D:/blender-mcp-multi-agent/runtime"
BLENDER_MCP_INSTANCE_ID = "<agent-b-instance-id>"
BLENDER_MCP_AGENT_ID = "agent-b"
```

`BLENDER_MCP_INSTANCE_ID` is fail-closed: an agent cannot silently connect to a
different Blender if its assigned worker is missing or already claimed.

## No-conflict rules

- one MCP process and one Blender worker per agent;
- never let two workers write the same `.blend`, cache, or output path;
- use `list_blender_instances` to verify identity, then let the MCP process
  auto-claim its pinned instance;
- release the instance when the task ends;
- do not set `BLENDER_PORT` for fleet workers; registry discovery already carries
  the dynamically allocated port.

The bridge, claim lease, node tools, scene tools, provider integrations, and
verification workflow are the same in GUI and headless mode.
