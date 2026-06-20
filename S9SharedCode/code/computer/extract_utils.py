"""Layer 1 extract helpers — AX tree, clipboard, files (no LLM)."""
from __future__ import annotations

import platform
import re
import subprocess
from pathlib import Path

# Goals that need scan→act→verify — passive AX peek is not enough.
_INTERACTIVE_MARKERS = (
    "click", "open", "launch", "list", "type", "press", "scroll", "drag",
    "sidebar", "navigate", "select", "filter", "sort", "submit",
    "top 3", "top three", "explore", "interact", "drive",
    "compute", "calculate", "multiply", "divide",
)


def read_clipboard() -> str:
    """Best-effort clipboard read for the current platform."""
    system = platform.system().lower()
    try:
        if system == "darwin":
            cp = subprocess.run(
                ["pbpaste"], capture_output=True, text=True, check=False, timeout=5,
            )
            return (cp.stdout or "").strip()
        if system == "linux":
            for cmd in (
                ["wl-paste", "--no-newline"],
                ["xclip", "-selection", "clipboard", "-o"],
                ["xsel", "--clipboard", "--output"],
            ):
                try:
                    cp = subprocess.run(
                        cmd, capture_output=True, text=True, check=False, timeout=5,
                    )
                    if cp.returncode == 0 and (cp.stdout or "").strip():
                        return cp.stdout.strip()
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue
        if system == "windows":
            cp = subprocess.run(
                ["powershell", "-command", "Get-Clipboard"],
                capture_output=True, text=True, check=False, timeout=10,
            )
            return (cp.stdout or "").strip()
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return ""


def read_files(paths: list[str]) -> str:
    chunks: list[str] = []
    for raw in paths:
        p = Path(raw).expanduser()
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if text.strip():
            chunks.append(f"--- {p.name} ---\n{text.strip()}")
    return "\n\n".join(chunks)


def ax_tree_text(window_state: dict) -> str:
    return (window_state.get("tree_markdown") or "").strip()


def goal_requires_interaction(goal: str) -> bool:
    g = goal.lower()
    return any(m in g for m in _INTERACTIVE_MARKERS)


def _ax_entry_count(content: str) -> int:
    """Count AT-SPI markdown list entries (lines like '- [0] role ...')."""
    return len(re.findall(r"^\s*-\s*\[\d+\]", content, re.MULTILINE))


def is_useful_extract(
    content: str,
    goal: str,
    *,
    min_chars: int = 40,
    element_count: int | None = None,
    from_files: bool = False,
) -> bool:
    """Return True only when Layer 1 can answer the goal without interaction."""
    if not content or len(content.strip()) < min_chars:
        return False
    if from_files:
        return True
    goal_l = goal.lower()
    if "clipboard" in goal_l and "[clipboard]" not in content:
        return False
    if goal_requires_interaction(goal):
        return False
    # Shallow AX snapshot (single frame / chrome only) — escalate to a11y/vision.
    entries = _ax_entry_count(content)
    if element_count is not None and element_count < 3:
        return False
    if entries > 0 and entries < 2:
        return False
    if ("list" in goal_l or "top 3" in goal_l or "top three" in goal_l) and entries > 0:
        if entries < 3:
            return False
    return True
