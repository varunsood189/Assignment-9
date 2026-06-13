"""Assignment 9: run any of the four comparison tasks + HTML replay report.

Usage:
    uv run python run_comparisons.py --list
    uv run python run_comparisons.py 1              # laptops
    uv run python run_comparisons.py hf_text_gen    # HuggingFace
    uv run python run_comparisons.py all
    uv run python run_comparisons.py 1 --no-report  # skip HTML generation
"""

from __future__ import annotations

import asyncio
import sys
import textwrap
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from flow import Executor
from html_report import build_session_index, write_report

TASKS: dict[str, dict] = {
    "laptops": {
        "num": 1,
        "label": "Laptops under ₹80,000",
        "query": (
            "Compare 3 popular laptops available in India under ₹80,000. "
            "For each laptop give the model name, key specs (CPU, RAM, storage, display), "
            "price in INR, and one-line verdict on who it is best for."
        ),
        "why_browser": (
            "Comparison listings on smartprix/91mobiles are JS-rendered; "
            "useful rows appear after the page loads and may need scrolling."
        ),
        "arch_note": textwrap.dedent("""
            Architecture note — Laptops under ₹80,000
            ───────────────────────────────────────────
            Entry: https://www.smartprix.com/laptops/best-laptops-under-80000-list
            Layer 1 extract — may return partial static HTML.
            Layer 2b a11y    — read listing cards (model, specs, price).
            Layer 3 vision   — fallback if cards are visually grouped only.
            DAG: planner → browser → distiller → critic → formatter
        """).strip(),
    },
    "ai_tools": {
        "num": 2,
        "label": "AI coding tools — free vs paid",
        "query": (
            "Compare 5 AI coding assistant tools: GitHub Copilot, Cursor, Tabnine, "
            "Codeium, and Amazon CodeWhisperer. For each tool provide free plan features, "
            "paid plan price and features, and supported IDEs."
        ),
        "why_browser": (
            "Pricing pages use JS tabs/toggles; plan details appear only after interaction."
        ),
        "arch_note": textwrap.dedent("""
            Architecture note — AI coding tools pricing
            ─────────────────────────────────────────────
            Fan-out: one browser node per pricing URL (parallel).
            Cursor, Tabnine, GitHub Copilot, Codeium, AWS CodeWhisperer.
            Layer 2b a11y clicks Monthly/Annual or plan tabs before extract.
            Distiller merges five page texts into structured fields per tool.
        """).strip(),
    },
    "hf_text_gen": {
        "num": 3,
        "label": "HuggingFace text-generation by likes",
        "query": (
            "Compare top 3 Hugging Face text-generation models sorted by likes. "
            "Use the browser on https://huggingface.co/models (base URL). "
            "Perform at least three visible browser actions (filter Tasks, sort by "
            "Most Likes, read model cards). Passive scraping is not acceptable. "
            "For each give model name, organisation, likes, parameter count if listed, "
            "and a one-line description."
        ),
        "why_browser": (
            "huggingface.co/models needs Tasks filter + sort dropdown — both interactive."
        ),
        "arch_note": textwrap.dedent("""
            Architecture note — HF text-generation by likes
            ─────────────────────────────────────────────────
            URL: https://huggingface.co/models
            Goal: filter Tasks=Text Generation, Sort=Most Likes, extract top 3 cards.
            Layer 2b a11y handles filter toggles and sort popover (dropdown fence).
            Expected 4–8 browser turns with $0.00 on free-tier providers.
        """).strip(),
    },
    "cnc_training": {
        "num": 4,
        "label": "CNC/VMC institutes in Bangalore",
        "query": (
            "Compare 5 CNC and VMC operator training institutes in Bangalore. "
            "For each institute give name, location, course duration, approximate fees, "
            "and whether they offer placement support."
        ),
        "why_browser": (
            "Institute listings on JustDial/Sulekha load via JS search results."
        ),
        "arch_note": textwrap.dedent("""
            Architecture note — CNC/VMC training Bangalore
            ────────────────────────────────────────────────
            Entry: JustDial or Sulekha search results for CNC training Bangalore.
            Layer 2b a11y scrolls listing cards; distiller extracts five institutes.
            If gateway_blocked, planner recovery tries alternate directory site.
        """).strip(),
    },
}

_NUM_MAP = {str(t["num"]): k for k, t in TASKS.items()}


def _banner(text: str) -> None:
    print("=" * 72)
    print(text)
    print("=" * 72)


def _list_tasks() -> None:
    print()
    _banner("Assignment 9 — comparison tasks")
    for key, t in TASKS.items():
        print(f"  [{t['num']}] {t['label']}  (key: {key})")
        print(f"      {t['why_browser'][:90]}...")
    print("\nExamples:")
    print("  uv run python run_comparisons.py 1")
    print("  uv run python run_comparisons.py hf_text_gen")
    print("  uv run python run_comparisons.py all")


async def _run_task(key: str, generate_report: bool = True) -> dict:
    t = TASKS[key]
    t0 = time.time()
    print()
    _banner(f"Task {t['num']}: {t['label']}")
    print(f"Query: {t['query'][:100]}...\n")

    sid = ""
    success = False
    try:
        await Executor().run(t["query"])
        sessions_dir = Path(__file__).parent / "state" / "sessions"
        sessions = sorted(
            (p for p in sessions_dir.iterdir() if p.is_dir() and p.name.startswith("s")),
            key=lambda p: p.stat().st_mtime,
        )
        if sessions:
            sid = sessions[-1].name
            sd = sessions_dir / sid
            (sd / "architecture_note.txt").write_text(t["arch_note"], encoding="utf-8")
            (sd / "task_key.txt").write_text(key, encoding="utf-8")
            (Path(__file__).parent / ".last_session_id").write_text(sid, encoding="utf-8")
            success = True
    except Exception as exc:
        print(f"[run_comparisons] failed: {exc}")

    if sid and generate_report:
        try:
            out = write_report(sid)
            print(f"[run_comparisons] report → {out}")
        except Exception as exc:
            print(f"[run_comparisons] report failed: {exc}")

    elapsed = time.time() - t0
    print(f"\n  Session: {sid or '—'}  Elapsed: {elapsed:.1f}s  "
          f"Status: {'✓' if success else '✗'}")
    return {"key": key, "sid": sid, "success": success, "elapsed": elapsed}


async def _run_tasks(keys: list[str], generate_report: bool = True) -> None:
    _banner(f"Running {len(keys)} task(s)")
    results = []
    for key in keys:
        results.append(await _run_task(key, generate_report=generate_report))
    print()
    _banner("Summary")
    for r in results:
        t = TASKS[r["key"]]
        print(f"  {'✓' if r['success'] else '✗'} [{t['num']}] {t['label']}")
        if r["sid"]:
            print(f"     session: {r['sid']}")
            print(f"     report:  state/sessions/{r['sid']}/report.html")
    idx = build_session_index()
    print(f"\nSession index: {idx}")


def _parse_args(argv: list[str]) -> tuple[list[str], bool]:
    generate_report = "--no-report" not in argv
    args = [a for a in argv if not a.startswith("--")]
    if not args or args == ["--list"] or "-l" in argv:
        return [], generate_report
    if "all" in args:
        return list(TASKS.keys()), generate_report
    keys = []
    for arg in args:
        if arg in TASKS:
            keys.append(arg)
        elif arg in _NUM_MAP:
            keys.append(_NUM_MAP[arg])
        else:
            print(f"Unknown task: {arg!r}  (use --list)")
            sys.exit(1)
    return keys, generate_report


def main() -> None:
    argv = sys.argv[1:]
    if not argv or "--list" in argv or "-l" in argv:
        _list_tasks()
        return
    keys, generate_report = _parse_args(argv)
    if not keys:
        _list_tasks()
        return
    asyncio.run(_run_tasks(keys, generate_report=generate_report))


if __name__ == "__main__":
    main()
