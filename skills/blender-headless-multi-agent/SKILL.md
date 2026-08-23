---
name: blender-headless-multi-agent
description: Run several independent Blender MCP agents in parallel with headless workers, deterministic instance routing, and no shared-file conflicts.
---

# Blender headless multi-agent

The agent owns the lifecycle. Do not ask the user to open Blender manually.

1. Create a private workspace for the task and one subdirectory per agent.
2. Start Blender automatically from the agent shell:

   ```powershell
   python scripts/launch_headless_worker.py `
     --blender "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" `
     --runtime-dir D:/blender-fleet/runtime `
     --label agent-a
   ```

   Save the JSON descriptor printed by the launcher. It contains the
   `instance_id`, registry port, stop file, and log path.
3. Call `list_blender_instances`, verify the label/file identity, and claim the
   exact `instance_id`. If the MCP process is started for this agent, set
   `BLENDER_MCP_INSTANCE_ID` and `BLENDER_MCP_AGENT_ID` before starting it.
4. Build and verify the model through the full Blender MCP tools. Save only to
   that agent's own `.blend` and output paths.
5. Call `release_blender_instance`, then create the launcher's stop file to
   shut down Blender. Read the worker log if startup or a command fails.

For parallel work, repeat steps 1–5 with distinct labels, directories, MCP
processes, and writable files. Never reuse a port or route by registry order.

Never share a writable `.blend` or output path between agents. Do not route by
port or registry order; the pinned instance ID is fail-closed. See
`docs/MULTI_AGENT_HEADLESS.md` for the short launch/config example.
