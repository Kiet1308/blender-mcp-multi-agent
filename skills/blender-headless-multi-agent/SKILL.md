---
name: blender-headless-multi-agent
description: Run several independent Blender MCP agents in parallel with headless workers, deterministic instance routing, and no shared-file conflicts.
---

# Blender headless multi-agent

Use one full Blender MCP process and one `blender -b` worker per agent.

1. Start each worker with `scripts/headless_blender.py` and the same
   `BLENDER_MCP_RUNTIME_DIR`.
2. Give every worker its own `.blend` input/output directory and stop file.
3. Call `list_blender_instances`, then set the matching `instance_id` as
   `BLENDER_MCP_INSTANCE_ID` in that agent's MCP environment.
4. Use one MCP entry per agent and a distinct `BLENDER_MCP_AGENT_ID` label.
5. Release the Blender claim when the task ends.

Never share a writable `.blend` or output path between agents. Do not route by
port or registry order; the pinned instance ID is fail-closed. See
`docs/MULTI_AGENT_HEADLESS.md` for the short launch/config example.
