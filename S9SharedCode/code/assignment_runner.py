"""Assignment 9: Browser Comparison Agent — primary task runner.

Runs the canonical Hugging Face text-generation comparison (filter + sort +
extract top 3 models). This requires interactive browser work that static
web_search + fetch_url cannot do.

Usage:
    uv run python assignment_runner.py
    uv run python html_report.py <session_id>
"""

from __future__ import annotations

import asyncio
import sys
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from flow import Executor
from html_report import (
    build_session_index,
    count_interactive_browser_actions,
    load_session,
    write_report,
)

COMPARISON_QUERY = (
    "Compare top 3 Hugging Face text-generation models sorted by likes. "
    "Use the browser on https://huggingface.co/models (base URL only). "
    "You must perform at least three visible browser actions — such as applying "
    "the Tasks filter, opening the Sort menu, selecting Most Likes, and reading "
    "model cards. Passive scraping from search snippets is not acceptable. "
    "For each model give the model name, organisation, number of likes, "
    "parameter count if listed, and a one-line description of what it is good for."
)

ARCHITECTURE_NOTE = textwrap.dedent("""
    Architecture note — HuggingFace text-generation by likes
    ───────────────────────────────────────────────────────────
    Entry URL: https://huggingface.co/models (base URL only; filters in goal)

    Layer 1  extract       — FAILS: model listing is JavaScript-rendered.
    Layer 2a deterministic — Skipped (no hand-written selectors in metadata).
    Layer 2b a11y          — EXPECTED: filter Tasks=Text Generation, open sort
                             menu, pick Most Likes, read top 3 model cards.
                             4–8 turns, cheap text LLM per turn.
    Layer 3  vision         — Fallback if a11y cannot reach sort popover.

    Orchestrator (flow.py) unchanged. Browser plugs in via agent_config.yaml,
    prompts/browser.md, and the skills.py dispatch branch.

    DAG: planner → browser → distiller → [auto critic] → formatter
    Distiller normalises fields; critic validates against inputs; formatter
    renders the comparison table shown in the replay report §7.
""").strip()


async def run_comparison() -> str:
    print("=" * 72)
    print("Assignment 9 — Browser Comparison Agent")
    print("Task: top-3 HF text-generation models sorted by likes")
    print("=" * 72)
    print(f"\nQuery:\n  {COMPARISON_QUERY}\n")

    executor = Executor()
    await executor.run(COMPARISON_QUERY)

    sessions_dir = Path(__file__).parent / "state" / "sessions"
    sessions = sorted(
        (p for p in sessions_dir.iterdir() if p.is_dir() and p.name.startswith("s")),
        key=lambda p: p.stat().st_mtime,
    )
    if not sessions:
        print("[assignment] warning: no session directory found after run")
        return ""

    sid = sessions[-1].name
    (sessions_dir / sid / "architecture_note.txt").write_text(
        ARCHITECTURE_NOTE, encoding="utf-8"
    )
    (sessions_dir / sid / "task_key.txt").write_text("hf_text_gen", encoding="utf-8")
    (Path(__file__).parent / ".last_session_id").write_text(sid, encoding="utf-8")

    report = write_report(sid)
    build_session_index()

    _, nodes = load_session(sid)
    action_count = count_interactive_browser_actions(nodes)
    action_note = (
        f"✓ {action_count} visible browser actions recorded (requirement: ≥3)"
        if action_count >= 3
        else f"⚠ only {action_count} visible browser actions (requirement: ≥3)"
    )

    print()
    print("=" * 72)
    print(f"Session: {sid}")
    print(f"Report:  {report}")
    print(f"Actions: {action_note}")
    print()
    print(ARCHITECTURE_NOTE)
    print("=" * 72)
    return sid


def main() -> None:
    asyncio.run(run_comparison())


if __name__ == "__main__":
    main()
