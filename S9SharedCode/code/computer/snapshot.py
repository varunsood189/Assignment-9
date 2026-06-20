"""Adapt cua-driver window snapshots for set-of-marks annotation."""
from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

from browser.highlight import annotate, to_data_url


@dataclass
class DesktopElement:
    """Minimal Element-shaped record for browser.highlight.annotate."""

    id: int
    tag: str
    role: str
    name: str
    x: float
    y: float
    w: float
    h: float


@dataclass
class DesktopSnapshot:
    elements: list[DesktopElement]
    viewport_w: int
    viewport_h: int
    dpr: float = 1.0
    tree_markdown: str = ""
    screenshot_png_b64: str | None = None

    def legend(self) -> str:
        lines = []
        for el in self.elements:
            label = el.name or el.role or el.tag
            lines.append(f"[{el.id}]<{el.tag} role={el.role!r}>{label}</{el.tag}>")
        return "\n".join(lines)


def parse_window_state(state: dict[str, Any]) -> DesktopSnapshot:
    elements: list[DesktopElement] = []
    for raw in state.get("elements") or []:
        idx = int(raw.get("element_index", len(elements)))
        elements.append(DesktopElement(
            id=idx,
            tag=str(raw.get("role") or "element"),
            role=str(raw.get("role") or ""),
            name=str(raw.get("name") or ""),
            x=float(raw.get("x", 0)),
            y=float(raw.get("y", 0)),
            w=float(raw.get("width", raw.get("w", 0))),
            h=float(raw.get("height", raw.get("h", 0))),
        ))
    return DesktopSnapshot(
        elements=elements,
        viewport_w=int(state.get("screenshot_width") or 800),
        viewport_h=int(state.get("screenshot_height") or 600),
        tree_markdown=str(state.get("tree_markdown") or ""),
        screenshot_png_b64=state.get("screenshot_png_b64"),
    )


def marked_screenshot_data_url(snap: DesktopSnapshot) -> str | None:
    if not snap.screenshot_png_b64:
        return None
    raw = base64.b64decode(snap.screenshot_png_b64)
    # highlight.Element expects .id .tag .role .name .x .y .w .h
    class _El:
        def __init__(self, d: DesktopElement):
            self.id = d.id
            self.tag = d.tag
            self.role = d.role
            self.name = d.name
            self.x = d.x
            self.y = d.y
            self.w = d.w
            self.h = d.h
    marked = annotate(raw, [_El(e) for e in snap.elements], snap.dpr)
    return to_data_url(marked)
