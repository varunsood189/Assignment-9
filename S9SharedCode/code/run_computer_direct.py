#!/usr/bin/env python3
"""Run a Computer skill task directly (bypass planner) for smoke tests.

Usage:
  uv run python run_computer_direct.py calc42
  uv run python run_computer_direct.py noteread
  uv run python run_computer_direct.py vscodefiles
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from demos import get_demo
from computer.skill import ComputerSkill
from schemas import NodeSpec

ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / "state" / "sessions" / "direct-computer"


def _expand_paths(hint: dict) -> dict:
    out = dict(hint)
    if files := out.get("files"):
        out["files"] = [str(Path(f).expanduser()) for f in files]
    for key in ("open_path", "folder"):
        if out.get(key):
            out[key] = str(Path(str(out[key])).expanduser())
    return out


async def main(task_id: str) -> int:
    demo = get_demo(task_id)
    hint = _expand_paths(demo.get("computer_hint") or {})
    if not hint:
        print(f"No computer_hint for demo {task_id!r}", file=sys.stderr)
        return 2

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    skill = ComputerSkill(
        artifacts_root=str(ARTIFACTS),
        session=f"direct-{task_id}",
    )
    node = NodeSpec(
        skill="computer",
        metadata={
            "label": task_id,
            **hint,
        },
    )
    print(f"[direct] task={task_id} metadata={json.dumps(node.metadata, indent=2)}")
    result = await skill.run(node)
    print(json.dumps({
        "success": result.success,
        "error": result.error,
        "error_code": result.error_code,
        "output": result.output,
        "elapsed_s": result.elapsed_s,
    }, indent=2))
    return 0 if result.success else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: run_computer_direct.py <calc42|noteread|vscodefiles|calcvision>", file=sys.stderr)
        sys.exit(2)
    raise SystemExit(asyncio.run(main(sys.argv[1])))
