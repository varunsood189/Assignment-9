"""io_replay_viewer.py — per-node Input / Output / Thinking HTML report.

Companion to replay_viewer.py. Shows every orchestrator node with:
  - Inputs (wire list + resolved upstream payloads)
  - Thinking / rationale (planner, distiller, critic, browser turns)
  - Output (structured result)
  - Collapsible full prompt_sent and raw JSON

Usage:
    python3 io_replay_viewer.py                  # latest session
    python3 io_replay_viewer.py s9-880b7851
    python3 io_replay_viewer.py s9-880b7851 --open
"""

from __future__ import annotations

import datetime
import json
import pathlib
import re
import sys

from replay_viewer import (
    LOGS_DIR,
    SESSIONS_DIR,
    collapsible,
    e,
    latest_sid,
    load_session,
    pill,
    pre,
)

SCRIPT_DIR = pathlib.Path(__file__).parent


def _node_sort_key(nd: dict) -> tuple[int, str]:
    m = re.match(r"n:(\d+)", nd.get("node_id", ""))
    return (int(m.group(1)) if m else 9999, nd.get("node_id", ""))


def _build_index(nodes: list[dict]) -> dict[str, dict]:
    return {nd["node_id"]: nd for nd in nodes if nd.get("node_id")}


def _json_block(obj, max_chars: int = 8000) -> str:
    try:
        text = json.dumps(obj, indent=2, ensure_ascii=False, default=str)
    except TypeError:
        text = str(obj)
    return pre(text, max_chars)


def _resolve_inputs_html(nd: dict, index: dict[str, dict], query: str) -> str:
    parts: list[str] = []
    wire = nd.get("inputs") or []
    parts.append(f"<p style='margin:0 0 8px;font-size:0.78rem;color:#64748b'>"
                 f"<b>Wires:</b> {e(wire if wire else '(none)')}</p>")

    if not wire:
        return "".join(parts)

    for inp in wire:
        if inp == "USER_QUERY":
            parts.append(
                f"<div style='margin-bottom:10px'>"
                f"<div style='font-size:0.72rem;font-weight:700;color:#6366f1;margin-bottom:4px'>"
                f"USER_QUERY</div>{pre(query, 1500)}</div>"
            )
            continue
        if inp.startswith("n:") and inp in index:
            up = index[inp]
            up_out = (up.get("result") or {}).get("output") or {}
            skill = up.get("skill", "?")
            parts.append(
                f"<div style='margin-bottom:10px'>"
                f"<div style='font-size:0.72rem;font-weight:700;color:#0891b2;margin-bottom:4px'>"
                f"{e(inp)} ({e(skill)})</div>"
                f"{_json_block(up_out, 6000)}</div>"
            )
            continue
        parts.append(
            f"<div style='margin-bottom:8px;font-size:0.78rem;color:#64748b'>"
            f"{e(inp)} <span style='color:#9ca3af'>(unresolved in session dump)</span></div>"
        )
    return "".join(parts)


def _extract_thinking(nd: dict, sid: str) -> list[tuple[str, str]]:
    """Return labelled thinking / rationale snippets for a node."""
    skill = nd.get("skill", "")
    out = (nd.get("result") or {}).get("output") or {}
    items: list[tuple[str, str]] = []

    if skill == "planner":
        if out.get("rationale"):
            items.append(("Planner rationale", str(out["rationale"])))
        plan_nodes = out.get("nodes") or []
        if plan_nodes:
            items.append(("Plan nodes emitted", json.dumps(plan_nodes, indent=2, default=str)))

    elif skill == "distiller":
        if out.get("rationale"):
            items.append(("Distiller rationale", str(out["rationale"])))

    elif skill == "critic":
        verdict = out.get("verdict")
        if verdict:
            items.append(("Verdict", str(verdict)))
        if out.get("rationale"):
            items.append(("Critic rationale", str(out["rationale"])))

    elif skill == "browser":
        goal = out.get("goal")
        if goal:
            items.append(("Browser goal", str(goal)))
        actions = out.get("actions") or []
        for step in actions:
            turn = step.get("turn", "?")
            thinking = step.get("thinking")
            if thinking:
                items.append((f"Turn {turn} thinking", str(thinking)))
            act_list = step.get("actions") or []
            if act_list:
                items.append((
                    f"Turn {turn} actions",
                    json.dumps(act_list, indent=2, default=str),
                ))
            outcome = step.get("outcome")
            if outcome:
                items.append((f"Turn {turn} outcome", str(outcome)))
        # Artifact legends may exist even when actions[] is empty (layer-1 extract)
        browser_root = SESSIONS_DIR / sid / "browser"
        if browser_root.exists():
            legends = sorted(browser_root.rglob("*_legend.txt"))
            for leg in legends[:24]:
                rel = leg.relative_to(browser_root)
                items.append((f"Legend {rel}", leg.read_text(encoding="utf-8", errors="replace")[:4000]))

    elif skill == "researcher":
        if out.get("findings"):
            items.append(("Researcher synthesis", str(out["findings"])[:3000]))

    elif skill == "formatter":
        if out.get("final_answer"):
            items.append(("Formatter draft", str(out["final_answer"])[:4000]))

    return items


def _thinking_html(items: list[tuple[str, str]]) -> str:
    if not items:
        return ("<p style='color:#9ca3af;font-size:0.8rem;margin:0'>"
                "No thinking / rationale recorded for this node.</p>")
    blocks = ""
    for label, text in items:
        blocks += (
            f"<div style='margin-bottom:12px'>"
            f"<div style='font-size:0.72rem;font-weight:700;color:#7c3aed;margin-bottom:4px'>"
            f"{e(label)}</div>{pre(text, 5000)}</div>"
        )
    return blocks


def _output_html(nd: dict) -> str:
    res = nd.get("result") or {}
    out = res.get("output")
    err = res.get("error")
    body = _json_block(out if out is not None else {}, 10000)
    if err:
        body += f"<p style='color:#dc2626;font-size:0.78rem;margin-top:8px'>"
        body += f"<b>Error:</b> {e(err)}</p>"
    return body


def _node_card(nd: dict, index: dict[str, dict], query: str, sid: str) -> str:
    nid = nd.get("node_id", "?")
    skill = nd.get("skill", "?")
    status = nd.get("status", "?")
    elapsed = (nd.get("result") or {}).get("elapsed_s")
    elapsed_s = f"{elapsed:.1f}s" if isinstance(elapsed, (int, float)) else "—"
    provider = (nd.get("result") or {}).get("provider") or "—"
    status_color = "#16a34a" if status == "complete" else "#dc2626"

    thinking_items = _extract_thinking(nd, sid)
    prompt = nd.get("prompt_sent") or ""
    raw = nd.get("result")

    return f"""
<article id="{e(nid.replace(':', '_'))}" style="margin-bottom:28px;border:1px solid #e2e8f0;
  border-radius:12px;overflow:hidden;background:#fff;box-shadow:0 1px 3px #0000000a">
  <header style="padding:14px 18px;background:#f8fafc;border-bottom:1px solid #e2e8f0;
    display:flex;flex-wrap:wrap;align-items:center;gap:10px">
    <span style="font-family:monospace;font-size:0.9rem;font-weight:700;color:#1e293b">{e(nid)}</span>
    {pill(skill)}
    <span style="font-size:0.75rem;font-weight:700;color:{status_color}">{e(status)}</span>
    <span style="font-size:0.72rem;color:#64748b">{e(elapsed_s)} · {e(provider)}</span>
  </header>
  <div style="padding:16px 18px">
    <h3 style="font-size:0.8rem;font-weight:700;color:#0891b2;margin:0 0 8px;text-transform:uppercase;
      letter-spacing:0.04em">Inputs</h3>
    {_resolve_inputs_html(nd, index, query)}

    <h3 style="font-size:0.8rem;font-weight:700;color:#7c3aed;margin:20px 0 8px;text-transform:uppercase;
      letter-spacing:0.04em">Thinking / Rationale</h3>
    {_thinking_html(thinking_items)}

    <h3 style="font-size:0.8rem;font-weight:700;color:#16a34a;margin:20px 0 8px;text-transform:uppercase;
      letter-spacing:0.04em">Output</h3>
    {_output_html(nd)}

    {collapsible("Full prompt sent to skill", pre(prompt, 12000), accent="#64748b") if prompt else ""}
    {collapsible("Raw result JSON", _json_block(raw, 12000), accent="#475569")}
  </div>
</article>"""


def build_io_html(sid: str, query: str, nodes: list[dict]) -> str:
    nodes = sorted(nodes, key=_node_sort_key)
    index = _build_index(nodes)
    cards = "".join(_node_card(nd, index, query, sid) for nd in nodes)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    nav = ""
    for nd in nodes:
        nid = nd["node_id"]
        skill = nd["skill"]
        anchor = nid.replace(":", "_")
        nav += (
            f'<a href="#{e(anchor)}" style="display:block;padding:4px 8px;font-size:0.75rem;'
            f'color:#475569;text-decoration:none;border-radius:4px;margin-bottom:2px" '
            f'onmouseover="this.style.background=\'#f1f5f9\'" '
            f'onmouseout="this.style.background=\'transparent\'">'
            f'{e(nid)} <span style="color:#94a3b8">· {e(skill)}</span></a>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>I/O Replay — {e(sid)}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:system-ui,-apple-system,sans-serif;background:#f1f5f9;color:#1e293b}}
  details>summary::marker{{display:none}}
  details>summary::-webkit-details-marker{{display:none}}
</style>
</head>
<body>
<div style="position:fixed;top:0;left:0;width:200px;height:100vh;overflow-y:auto;
  background:#fff;border-right:1px solid #e2e8f0;padding:14px 8px">
  <div style="font-size:0.65rem;font-weight:700;color:#94a3b8;text-transform:uppercase;
    letter-spacing:0.08em;padding:0 8px;margin-bottom:8px">I/O Replay</div>
  <div style="font-size:0.68rem;color:#94a3b8;padding:0 8px 10px;word-break:break-all">{e(sid)}</div>
  {nav}
  <div style="margin-top:16px;padding:8px;border-top:1px solid #e2e8f0">
    <a href="report.html" style="font-size:0.72rem;color:#4f46e5">← 8-section report</a>
  </div>
</div>
<div style="margin-left:200px;padding:24px 28px;max-width:1100px">
  <p style="font-size:0.72rem;color:#94a3b8;margin-bottom:4px">Node I/O Replay · {e(ts)}</p>
  <h1 style="font-size:1.35rem;font-weight:800;margin-bottom:6px">{e(sid)}</h1>
  <p style="font-size:0.85rem;color:#475569;margin-bottom:24px;line-height:1.5">{e(query)}</p>
  {cards}
</div>
</body>
</html>"""


def write_io_report(sid: str | None = None) -> pathlib.Path:
    if not sid:
        sid = latest_sid()
    query, nodes = load_session(sid)
    page = build_io_html(sid, query, nodes)
    out = SESSIONS_DIR / sid / "io_report.html"
    out.write_text(page, encoding="utf-8")
    log_out = LOGS_DIR / f"{sid}_io_replay.html"
    log_out.write_text(page, encoding="utf-8")
    return out


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    do_open = "--open" in sys.argv

    sid = args[0] if args else None
    if not sid:
        sid = latest_sid()
        print(f"[io-replay] no session id — using latest: {sid}")

    print(f"[io-replay] loading {sid} …")
    _, nodes = load_session(sid)
    print(f"[io-replay] {len(nodes)} nodes")

    out = write_io_report(sid)
    print(f"[io-replay] written → {out}")
    print(f"[io-replay] copy    → {LOGS_DIR / f'{sid}_io_replay.html'}")
    print(f"[io-replay] open:  xdg-open '{out}'")

    if do_open:
        import subprocess
        subprocess.Popen(["xdg-open", str(out)])


if __name__ == "__main__":
    main()
