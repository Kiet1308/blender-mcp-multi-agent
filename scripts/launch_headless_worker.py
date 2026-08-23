"""Launch one autonomous Blender MCP headless worker from an agent shell.

The command starts Blender, waits until the extension publishes its registry
record, and prints a compact JSON descriptor that an agent can use for routing.
The Blender process remains alive until its stop file appears or its timeout
expires.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ADDON = ROOT / "blender_extension" / "__init__.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", help="Blender executable; defaults to BLENDER_EXE or PATH")
    parser.add_argument("--runtime-dir", required=True, help="Shared private registry directory")
    parser.add_argument("--label", required=True, help="Unique agent/worker label")
    parser.add_argument("--addon", default=str(DEFAULT_ADDON))
    parser.add_argument("--stop-file", help="Filesystem stop signal; defaults beside runtime")
    parser.add_argument("--timeout", type=float, default=86400.0)
    parser.add_argument("--wait-timeout", type=float, default=45.0)
    parser.add_argument("--log-dir", help="Worker log directory; defaults beside runtime")
    return parser.parse_args()


def find_blender(explicit: str | None) -> str:
    candidates = [explicit, os.getenv("BLENDER_EXE"), shutil.which("blender")]
    if os.name == "nt":
        candidates.extend([
            r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
            r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
        ])
    for candidate in candidates:
        if candidate and Path(candidate).expanduser().is_file():
            return str(Path(candidate).expanduser().resolve())
    raise FileNotFoundError(
        "Blender executable not found; pass --blender or set BLENDER_EXE"
    )


def read_worker_record(runtime: Path, pid: int) -> dict | None:
    for path in sorted(runtime.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if int(record.get("pid", -1)) == pid:
            return record
    return None


def main() -> int:
    args = parse_args()
    runtime = Path(args.runtime_dir).expanduser().resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    stop_file = Path(args.stop_file).expanduser().resolve() if args.stop_file else (
        runtime.parent / f"{args.label}.stop"
    )
    stop_file.parent.mkdir(parents=True, exist_ok=True)
    log_dir = Path(args.log_dir).expanduser().resolve() if args.log_dir else runtime.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{args.label}.log"
    blender = find_blender(args.blender)

    command = [
        blender,
        "--background",
        "--factory-startup",
        "--disable-autoexec",
        "--python",
        str(Path(__file__).with_name("headless_blender.py")),
        "--",
        "--addon",
        str(Path(args.addon).expanduser().resolve()),
        "--runtime-dir",
        str(runtime),
        "--label",
        args.label,
        "--stop-file",
        str(stop_file),
        "--timeout",
        str(args.timeout),
    ]
    with log_file.open("w", encoding="utf-8") as log:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env={**os.environ, "BLENDER_MCP_RUNTIME_DIR": str(runtime)},
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
            start_new_session=(os.name != "nt"),
        )

    deadline = time.monotonic() + max(1.0, args.wait_timeout)
    record = None
    while time.monotonic() < deadline:
        record = read_worker_record(runtime, process.pid)
        if record:
            break
        if process.poll() is not None:
            break
        time.sleep(0.2)

    if record is None:
        details = log_file.read_text(encoding="utf-8", errors="replace")[-4000:]
        raise RuntimeError(
            f"Blender worker {args.label!r} failed to register (exit={process.poll()}).\n{details}"
        )

    print(json.dumps({
        "label": args.label,
        "pid": process.pid,
        "instance_id": record.get("instance_id", ""),
        "port": record.get("port"),
        "runtime_dir": str(runtime),
        "stop_file": str(stop_file),
        "log_file": str(log_file),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
