"""Exercise three autonomous headless Blender agents with complex scenes."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts" / "launch_headless_worker.py"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender", required=True)
    parser.add_argument("--root", required=True)
    return parser.parse_args()


def launch_worker(blender, runtime, label, log_dir):
    result = subprocess.run(
        [sys.executable, str(LAUNCHER), "--blender", blender, "--runtime-dir", str(runtime), "--label", label, "--log-dir", str(log_dir)],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


def model_code(kind, output):
    kind_literal = repr(kind)
    output_literal = repr(str(Path(output).resolve()))
    return f'''import bpy, math, json
kind = {kind_literal}
output = {output_literal}

def material(name, color, metallic=0.0):
    value = bpy.data.materials.new(name); value.diffuse_color = (*color, 1.0); value.use_nodes = True
    node = value.node_tree.nodes.get("Principled BSDF")
    if node:
        node.inputs["Base Color"].default_value = (*color, 1.0); node.inputs["Metallic"].default_value = metallic
    return value

primary = material(kind + "Primary", (0.08, 0.32, 0.72), 0.5)
accent = material(kind + "Accent", (0.95, 0.24, 0.06), 0.2)
glow = material(kind + "Glow", (0.04, 0.8, 1.0))
stone = material(kind + "Stone", (0.22, 0.28, 0.36))

def cube(name, loc, scale, mat):
    bpy.ops.mesh.primitive_cube_add(location=loc); obj=bpy.context.object; obj.name=name; obj.scale=scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True); obj.data.materials.append(mat); return obj

def sphere(name, loc, radius, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=radius, location=loc)
    obj=bpy.context.object; obj.name=name; obj.data.materials.append(mat); bpy.ops.object.shade_smooth(); return obj

def cylinder(name, loc, radius, depth, mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=radius, depth=depth, location=loc)
    obj=bpy.context.object; obj.name=name; obj.data.materials.append(mat); return obj

def torus(name, loc, major, minor, mat):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor, major_segments=36, minor_segments=10, location=loc)
    obj=bpy.context.object; obj.name=name; obj.data.materials.append(mat); return obj

if kind == "spaceship":
    cube("Fuselage", (0,0,1.6), (2.5,0.72,0.46), primary)
    sphere("Cockpit", (0.75,0,2.15), 0.72, glow)
    for side in (-1,1):
        cube("Wing_%s" % side, (-0.2,side*1.55,1.35), (1.5,0.72,0.09), primary)
        for index in range(5):
            cylinder("Engine_%s_%s" % (side,index), (-2.1+index*0.15,side*0.48,1.3), 0.24, 1.1, accent)
            torus("EngineRing_%s_%s" % (side,index), (-2.65+index*0.15,side*0.48,1.3), 0.27, 0.05, glow)
        for index in range(4): cube("TailFin_%s_%s" % (side,index), (-1.7+index*0.25,side*0.55,2.15), (0.5,0.08,0.5), primary)
elif kind == "castle":
    cube("Keep", (0,0,1.8), (1.8,1.8,1.8), stone)
    for index, (x,y) in enumerate(((-2.2,-2.2),(-2.2,2.2),(2.2,-2.2),(2.2,2.2)), 1):
        cylinder("Tower_%d" % index, (x,y,2.4), 0.72, 4.8, primary)
        cylinder("Roof_%d" % index, (x,y,5.25), 0.95, 1.5, accent)
        for level in range(5): cube("TowerBand_%d_%d" % (index,level), (x,y-0.73,0.9+level), (0.16,0.08,0.18), accent)
    cube("Gate", (0,-1.86,1.0), (0.68,0.14,1.0), accent)
    for index in range(20): cube("WallBlock_%d" % index, ((index-9.5)*0.45,-2.0,0.5), (0.18,0.2,0.35), stone)
elif kind == "solar":
    sphere("Sun", (0,0,2), 1.0, accent)
    for index in range(1,9):
        orbit=1.4+index*0.62; torus("Orbit_%d" % index, (0,0,2), orbit, 0.018, glow); angle=index*0.71
        location=(math.cos(angle)*orbit,math.sin(angle)*orbit,2); sphere("Planet_%d" % index, location, 0.16+index*0.045, primary if index%2 else accent)
        for moon in range(index%3): sphere("Moon_%d_%d" % (index,moon), (location[0]+0.22+moon*0.09,location[1],2), 0.05, stone)
    for index in range(24):
        angle=index*0.47; orbit=5.4+(index%4)*0.08; sphere("Asteroid_%d" % index, (math.cos(angle)*orbit,math.sin(angle)*orbit,2), 0.045, stone)

cube("DisplayBase", (0,0,-0.35), (7,7,0.25), stone)
bpy.ops.object.camera_add(location=(12,-15,10)); bpy.context.scene.camera=bpy.context.object
bpy.ops.object.light_add(type="AREA", location=(4,-6,12)); bpy.context.object.data.energy=1300
bpy.ops.object.light_add(type="AREA", location=(-6,2,6)); bpy.context.object.data.energy=700
bpy.context.scene["complex_test_kind"] = kind; bpy.context.scene["complex_test_object_count"] = len(bpy.data.objects)
print(json.dumps({{"kind":kind,"objects":len(bpy.data.objects),"blend_file":output}}))
'''


async def run_agent(descriptor, kind, output):
    environment = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "BLENDER_MCP_RUNTIME_DIR": descriptor["runtime_dir"],
        "BLENDER_MCP_INSTANCE_ID": descriptor["instance_id"],
        "BLENDER_MCP_AGENT_ID": descriptor["label"],
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
                raise AssertionError(f"{kind}: expected 60 tools, got {len(tools.tools)}")
            listed = await session.call_tool("list_blender_instances", {"validate_live": True})
            if listed.isError:
                raise AssertionError(f"{kind}: discovery failed: {listed}")
            built = await session.call_tool("execute_blender_code", {
                "code": model_code(kind, output),
                "user_prompt": "complex multi-instance acceptance",
                "timeout_seconds": 120,
            })
            if built.isError:
                raise AssertionError(f"{kind}: build failed: {built}")
            verified = await session.call_tool("get_scene_info", {"user_prompt": "verify complex model"})
            if verified.isError:
                raise AssertionError(f"{kind}: readback failed: {verified}")
            saved = await session.call_tool("execute_blender_code", {
                "code": "import bpy; bpy.ops.wm.save_as_mainfile(filepath=%r); print('saved')" % str(output.resolve()),
                "user_prompt": "save verified complex model",
                "timeout_seconds": 120,
            })
            if saved.isError:
                raise AssertionError(f"{kind}: save failed: {saved}")
            released = await session.call_tool("release_blender_instance", {})
            if released.isError:
                raise AssertionError(f"{kind}: release failed: {released}")
            return {"kind": kind, "instance_id": descriptor["instance_id"], "blend_file": str(output), "tool_count": len(tools.tools)}


async def main():
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    runtime = root / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    kinds = ["spaceship", "castle", "solar"]
    descriptors = []
    try:
        for kind in kinds:
            descriptors.append(launch_worker(args.blender, runtime, "complex-" + kind, log_dir))
        outputs = [root / kind / (kind + ".blend") for kind in kinds]
        for output in outputs:
            output.parent.mkdir(parents=True, exist_ok=True)
        results = await asyncio.gather(*(run_agent(d, k, o) for d, k, o in zip(descriptors, kinds, outputs)))
        for result in results:
            if not Path(result["blend_file"]).is_file():
                raise AssertionError("Missing output " + result["blend_file"])
        print(json.dumps({"instances": len(results), "results": results}, indent=2))
    finally:
        for descriptor in descriptors:
            Path(descriptor["stop_file"]).touch()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
