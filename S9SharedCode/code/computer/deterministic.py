"""Layer 2a — known workflow / hotkey sequences from workflows.yaml."""
from __future__ import annotations

import asyncio
import copy
import re
from pathlib import Path
from typing import Any

import yaml

from .client import CuaDriverClient

_WORKFLOWS_PATH = Path(__file__).parent / "workflows.yaml"

# Legacy alias — resolved to calculator-eval with expression from goal/metadata.
_CALCULATOR_LEGACY_WORKFLOWS = frozenset({
    "calculator-multiply-42-18",
    "calculator-read-display",
})


def _load() -> dict[str, Any]:
    if not _WORKFLOWS_PATH.exists():
        return {}
    return yaml.safe_load(_WORKFLOWS_PATH.read_text()) or {}


def parse_calculator_expression(goal: str, metadata: dict[str, Any] | None = None) -> str | None:
    """Extract a gnome-calculator expression from metadata or natural-language goal."""
    meta = metadata or {}
    raw = meta.get("expression") or meta.get("calc") or meta.get("calculation")
    if raw:
        return _normalize_calc_expression(str(raw))

    g = goal.lower().replace("×", "*")
    if any(
        m in g
        for m in (
            "on-screen button", "on screen button", "keypad button",
            "click the button", "typed expression shortcut",
            "do not use a typed", "interacting with the on-screen",
        )
    ):
        return None
    # "42 times 19", "42 * 19", "compute 42*19"
    m = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:times|\*|×)\s*(\d+(?:\.\d+)?)",
        g,
        re.IGNORECASE,
    )
    if m:
        return f"{m.group(1)}*{m.group(2)}"

    m = re.search(r"compute\s+([\d\s*+\-/.()]+)", g, re.IGNORECASE)
    if m:
        return _normalize_calc_expression(m.group(1))

    m = re.search(r"([\d+\-*/().\s]+)\s+and read", g, re.IGNORECASE)
    if m:
        return _normalize_calc_expression(m.group(1))

    return None


def _normalize_calc_expression(expr: str) -> str:
    s = expr.strip()
    s = s.replace("×", "*").replace("x", "*").replace(" ", "")
    s = re.sub(r"\++", "+", s)
    return s


def apply_workflow_vars(spec: dict[str, Any], variables: dict[str, str]) -> dict[str, Any]:
    """Deep-copy workflow spec and substitute {placeholders} in step strings."""
    out = copy.deepcopy(spec)
    steps = out.get("steps") or []
    for step in steps:
        if not isinstance(step, dict):
            continue
        for key, val in list(step.items()):
            if isinstance(val, str):
                for name, repl in variables.items():
                    val = val.replace("{" + name + "}", repl)
                step[key] = val
    return out


def resolve_calculator_workflow(
    *,
    goal: str,
    metadata: dict[str, Any],
    workflow_key: str = "",
) -> tuple[dict[str, Any] | None, str | None]:
    """Return (workflow spec with expression filled in, expression) for calculator tasks."""
    expr = parse_calculator_expression(goal, metadata)
    if not expr:
        return None, None

    key = workflow_key.strip()
    if key in _CALCULATOR_LEGACY_WORKFLOWS or not key:
        key = "calculator-eval"

    spec = match_workflow(workflow=key)
    if not spec:
        spec = match_workflow(workflow="calculator-eval")
    if not spec:
        return None, expr

    return apply_workflow_vars(spec, {"expression": expr}), expr


def extract_calculator_display(ax_markdown: str) -> str | None:
    """Pull the evaluated result from gnome-calculator AX markdown."""
    if not ax_markdown:
        return None
    m = re.search(r'edit bar = "([^"]+)"', ax_markdown)
    if m:
        val = m.group(1).strip()
        if val and not val.endswith("=") and not val.endswith("*"):
            return val
    nums = re.findall(r'label = "(\d+)"', ax_markdown)
    if nums:
        return nums[-1]
    return None


def match_workflow(*, app: str = "", title: str = "", workflow: str = "") -> dict[str, Any] | None:
    data = _load()
    if workflow and workflow in data:
        return data[workflow]
    app_l = app.lower()
    title_l = title.lower()
    for _key, spec in data.items():
        if not isinstance(spec, dict):
            continue
        m_app = str(spec.get("match_app", "")).lower()
        m_title = str(spec.get("match_title", "")).lower()
        if m_app and m_app in app_l and m_app != "calculator":
            return spec
        if m_title and m_title in title_l and m_app != "calculator":
            return spec
    return None


async def run_workflow(
    client: CuaDriverClient,
    spec: dict[str, Any],
    *,
    pid: int,
    window_id: int,
) -> list[dict[str, Any]]:
    """Execute workflow steps; returns action log entries."""
    log: list[dict[str, Any]] = []
    for i, step in enumerate(spec.get("steps") or [], start=1):
        action = step.get("action", "hotkey")
        entry: dict[str, Any] = {"turn": i, "action": action, "step": step}
        if action == "hotkey":
            keys = step.get("keys") or []
            await client.hotkey(pid, list(keys), window_id=window_id)
            entry["outcome"] = "ok"
        elif action == "press_key":
            await client.press_key(pid, step.get("key", "Enter"), window_id=window_id)
            entry["outcome"] = "ok"
        elif action == "type_text":
            await client.type_text(pid, str(step.get("text", "")), window_id=window_id)
            entry["outcome"] = "ok"
        elif action == "wait":
            await asyncio.sleep(float(step.get("ms", 500)) / 1000.0)
            entry["outcome"] = "ok"
        elif action == "click_label":
            state = await client.get_window_state(pid, window_id, capture_mode="ax")
            label = str(step.get("label", ""))
            idx = _find_element_index(state, label)
            if idx is None:
                entry["outcome"] = f"label {label!r} not found"
            else:
                await client.click(pid, window_id=window_id, element_index=idx)
                entry["outcome"] = "ok"
                entry["element_index"] = idx
        elif action == "scroll":
            await client.scroll(
                pid,
                direction=step.get("direction", "down"),
                amount=int(step.get("amount", 3)),
                window_id=window_id,
            )
            entry["outcome"] = "ok"
        else:
            entry["outcome"] = f"unsupported action {action!r}"
        log.append(entry)
    return log


def _find_element_index(state: dict[str, Any], label: str) -> int | None:
    """Find AT-SPI element_index for a push button name in get_window_state output."""
    tree = state.get("tree_markdown") or ""
    pat = rf'-\s*\[(\d+)\]\s*push button\s+"{re.escape(label)}"'
    m = re.search(pat, tree)
    if m:
        return int(m.group(1))
    elements = state.get("elements") or []
    for el in elements:
        if str(el.get("name") or "") == label and el.get("element_index") is not None:
            return int(el["element_index"])
    return None
