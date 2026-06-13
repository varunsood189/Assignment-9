"""Live terminal trace for orchestrator nodes (inputs / output / rationale)."""

from __future__ import annotations

import json
from typing import Any


def _clip(text: str, limit: int = 280) -> str:
    t = (text or "").replace("\n", " ").strip()
    return t if len(t) <= limit else t[: limit - 1] + "…"


def _fields_preview(fields: dict) -> str:
    if not fields:
        return "(empty)"
    parts = [f"{k}={_clip(str(v), 60)}" for k, v in list(fields.items())[:6]]
    extra = len(fields) - len(parts)
    suffix = f" (+{extra} more)" if extra > 0 else ""
    return ", ".join(parts) + suffix


def _node_metadata(graph_nodes: Any, node_id: str) -> dict:
    """Read metadata from a node-id map or a NetworkX graph."""
    if hasattr(graph_nodes, "nodes"):
        nd = graph_nodes.nodes.get(node_id)
        if isinstance(nd, dict):
            return nd.get("metadata") or {}
        return {}
    if isinstance(graph_nodes, dict):
        entry = graph_nodes.get(node_id, {})
        if isinstance(entry, dict):
            return entry.get("metadata") or {}
    return {}


def trace_node(
    node_id: str,
    skill: str,
    node_inputs: list[str],
    result: Any,
    graph_nodes: Any,
) -> None:
    """Print a compact I/O trace after each node completes."""
    out = getattr(result, "output", None) or {}
    print(f"    ┌─ trace {node_id} ({skill})", flush=True)
    print(f"    │  inputs: {node_inputs or []}", flush=True)

    if skill == "planner":
        print(f"    │  rationale: {_clip(out.get('rationale', ''), 320)}", flush=True)
        nodes = out.get("nodes") or []
        skills = [n.get("skill") if isinstance(n, dict) else "?" for n in nodes]
        print(f"    │  plan: {' → '.join(skills) if skills else '(none)'}", flush=True)
    elif skill == "browser":
        content = out.get("content") or ""
        print(f"    │  path: {out.get('path')}  url: {_clip(out.get('url', ''), 80)}", flush=True)
        print(f"    │  content: {_clip(content, 400)}", flush=True)
    elif skill == "distiller":
        fields = out.get("fields") if isinstance(out.get("fields"), dict) else {}
        print(f"    │  fields: {_fields_preview(fields)}", flush=True)
        print(f"    │  rationale: {_clip(out.get('rationale', ''), 200)}", flush=True)
    elif skill == "critic":
        print(f"    │  verdict: {out.get('verdict', '?')}", flush=True)
        print(f"    │  rationale: {_clip(out.get('rationale', ''), 320)}", flush=True)
    elif skill == "formatter":
        print(f"    │  answer: {_clip(out.get('final_answer', ''), 500)}", flush=True)
    elif skill == "researcher":
        print(f"    │  findings: {_clip(out.get('findings', ''), 400)}", flush=True)
    else:
        try:
            print(f"    │  output: {_clip(json.dumps(out, default=str), 400)}", flush=True)
        except TypeError:
            print(f"    │  output: {_clip(str(out), 400)}", flush=True)

    meta = _node_metadata(graph_nodes, node_id)
    if isinstance(meta, dict) and meta.get("failure_report"):
        print(f"    │  failure: {_clip(str(meta['failure_report']), 200)}", flush=True)
    err = getattr(result, "error", None)
    if err:
        print(f"    │  error: {_clip(str(err), 200)}", flush=True)
    print(f"    └─", flush=True)
