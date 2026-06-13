"""Layer-1 extract quality gates (no Playwright dependency)."""

from __future__ import annotations

import re


def hf_model_ids(content: str) -> set[str]:
    """Distinct org/model paths in HF listing text (e.g. deepseek-ai/DeepSeek-R1)."""
    return {
        m for m in re.findall(r"\b[\w.-]+/[\w.-]+\b", content)
        if "/" in m and not m.startswith("http")
    }


def is_useful_extract(content: str, goal: str, url: str = "") -> bool:
    """Return False when plain HTML extract is obviously insufficient."""
    if len(content) < 200:
        return False
    interactive_verbs = ("click", "fill", "select", "type", "drag",
                         "filter", "sort", "submit", "navigate", "open")
    if any(v in goal.lower() for v in interactive_verbs):
        return False
    if "huggingface.co/models" in (url or ""):
        # Base URL requires Playwright — never short-circuit to passive extract.
        if "?" not in (url or ""):
            return False
        goal_l = goal.lower()
        want = 3 if "top 3" in goal_l or "top three" in goal_l else 2
        if any(k in goal_l for k in ("top ", "model card", "model cards")):
            if len(hf_model_ids(content)) < want:
                return False
    return True


def goal_requires_interaction(goal: str) -> bool:
    """True when the goal implies visible browser actions (not passive read)."""
    interactive_verbs = ("click", "fill", "select", "type", "drag",
                         "filter", "sort", "submit", "navigate", "open")
    return any(v in goal.lower() for v in interactive_verbs)


def normalize_url_for_goal(url: str, goal: str) -> str:
    """Strip pre-filtered query params when the goal requires interactive work."""
    if not goal_requires_interaction(goal):
        return url
    if "huggingface.co/models" in url and "?" in url:
        return "https://huggingface.co/models"
    return url
