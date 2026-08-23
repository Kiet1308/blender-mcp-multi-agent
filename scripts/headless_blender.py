"""Run the full Blender MCP extension as a headless worker.

Usage (the arguments after ``--`` are consumed by this script)::

    blender -b --factory-startup --python scripts/headless_blender.py -- \
      --addon blender_extension/__init__.py \
      --runtime-dir .runtime/agent-a \
      --label agent-a \
      --stop-file .runtime/agent-a.stop \
      --timeout 3600

Each process publishes one registry record and exposes the same bridge and
tool surface as the GUI extension.  Give every worker its own runtime folder,
input .blend, and output .blend path; never make two agents write the same
file at the same time.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import time
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--addon", required=True, help="Path to extension __init__.py")
    parser.add_argument("--runtime-dir", required=True, help="Private registry directory")
    parser.add_argument("--label", default="headless-agent", help="Human-readable worker label")
    parser.add_argument("--stop-file", help="Stop when this file appears")
    parser.add_argument("--timeout", type=float, default=3600.0)
    parser.add_argument("--scene-label", default="", help="Optional scene name for discovery")
    return parser.parse_args(values)


def load_addon(path: Path):
    # Loading the extension from its __init__.py keeps this launcher useful
    # from a checkout and avoids requiring a GUI installation step.
    module_name = "blender_mcp_headless_extension"
    spec = importlib.util.spec_from_file_location(
        module_name,
        path,
        submodule_search_locations=[str(path.parent)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load Blender MCP extension: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    args = parse_args()
    runtime = Path(args.runtime_dir).expanduser().resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    os.environ["BLENDER_MCP_RUNTIME_DIR"] = str(runtime)

    addon = load_addon(Path(args.addon).expanduser().resolve())
    addon.register()
    if args.scene_label:
        bpy.context.scene.name = args.scene_label

    server = addon.BlenderMCPServer()
    bpy.types.blendermcp_server = server
    server.start()
    if not server.running or not server.socket:
        raise RuntimeError("Blender MCP bridge failed to start")

    stop_file = Path(args.stop_file).expanduser().resolve() if args.stop_file else None
    deadline = time.monotonic() + max(1.0, args.timeout)

    print(
        f"BlenderMCP headless worker '{args.label}' started "
        f"(instance={addon._BLENDER_MCP_INSTANCE_ID}, port={server.port})",
        flush=True,
    )

    # Keep this startup script alive deliberately.  Blender exits as soon as
    # a background Python script returns; polling here both keeps the worker
    # process alive and executes queued commands on Blender's main thread.
    next_heartbeat = time.monotonic() + 2.0
    while True:
        server.process_headless_commands()
        now = time.monotonic()
        if now >= next_heartbeat:
            server._write_registry_record()
            next_heartbeat = now + 2.0
        if (stop_file is not None and stop_file.exists()) or now >= deadline:
            break
        time.sleep(0.01)

    addon.unregister()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
