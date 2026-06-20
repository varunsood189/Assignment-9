"""replay_viewer.py — 8-section assignment replay report.

Generates a self-contained HTML page from a session directory.
All 8 required sections are included:
  1. Original user goal
  2. Planner DAG
  3. Browser path chosen (extract / deterministic / a11y / vision / blocked)
  4. Browser actions taken (turn-by-turn)
  5. Screenshots / page-state logs (embedded as base64)
  6. Extracted data
  7. Final comparison table
  8. Turn count and cost summary

Usage:
    python replay_viewer.py                   # latest session
    python replay_viewer.py s9-3bf2adf5
    python replay_viewer.py s9-3bf2adf5 --open   # open in browser immediately
"""
from __future__ import annotations

import base64
import datetime
import html
import json
import pathlib
import sys
from collections import defaultdict

# ── paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = pathlib.Path(__file__).parent
SESSIONS_DIR = SCRIPT_DIR / "code" / "state" / "sessions"
LOGS_DIR     = SCRIPT_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# ── helpers ───────────────────────────────────────────────────────────────────
SKILL_COLOR = {
    "planner":          ("#4f46e5", "#eef2ff"),
    "researcher":       ("#0891b2", "#ecfeff"),
    "browser":          ("#7c3aed", "#f5f3ff"),
    "computer":         ("#0d9488", "#f0fdfa"),
    "distiller":        ("#d97706", "#fffbeb"),
    "critic":           ("#dc2626", "#fef2f2"),
    "formatter":        ("#16a34a", "#f0fdf4"),
    "retriever":        ("#0284c7", "#e0f2fe"),
    "summariser":       ("#9333ea", "#faf5ff"),
    "coder":            ("#b45309", "#fef3c7"),
    "sandbox_executor": ("#64748b", "#f8fafc"),
}

def e(t): return html.escape(str(t))

def fg(skill):  return SKILL_COLOR.get(skill, ("#374151","#f9fafb"))[0]
def bg(skill):  return SKILL_COLOR.get(skill, ("#374151","#f9fafb"))[1]

def pill(skill):
    f,b = SKILL_COLOR.get(skill, ("#374151","#f9fafb"))
    return (f'<span style="background:{b};color:{f};border:1px solid {f}44;'
            f'padding:2px 9px;border-radius:999px;font-size:0.72rem;font-weight:700">'
            f'{e(skill)}</span>')

def section(num, title, body, accent="#4f46e5"):
    return f"""
<section style="margin-bottom:32px">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">
    <span style="background:{accent};color:#fff;width:28px;height:28px;border-radius:50%;
      display:flex;align-items:center;justify-content:center;
      font-size:0.8rem;font-weight:700;flex-shrink:0">{num}</span>
    <h2 style="font-size:1.05rem;font-weight:700;color:#1e293b;margin:0">{title}</h2>
  </div>
  <div style="padding-left:38px">{body}</div>
</section>"""

def card(body, border="#e2e8f0", bg_color="#fff"):
    return (f'<div style="background:{bg_color};border:1px solid {border};'
            f'border-radius:10px;padding:16px 18px">{body}</div>')

def pre(text, max_chars=4000):
    t = str(text)
    note = ""
    if len(t) > max_chars:
        t = t[:max_chars]
        note = f'<p style="color:#9ca3af;font-size:0.72rem;margin:4px 0 0">… truncated</p>'
    return (f'<pre style="margin:0;padding:10px;background:#0f172a;color:#e2e8f0;'
            f'border-radius:6px;font-size:0.72rem;line-height:1.6;'
            f'overflow-x:auto;white-space:pre-wrap;word-break:break-word">'
            f'{e(t)}</pre>{note}')

def collapsible(label, body, open_=False, accent="#6b7280"):
    oa = " open" if open_ else ""
    return f"""
<details{oa} style="border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;margin-top:8px">
  <summary style="padding:7px 13px;cursor:pointer;background:#f9fafb;
    font-size:0.8rem;font-weight:600;color:{accent};list-style:none">
    ▶ {label}
  </summary>
  <div style="padding:12px 14px;background:#fff;border-top:1px solid #e5e7eb">
    {body}
  </div>
</details>"""

# ── load session ──────────────────────────────────────────────────────────────
def _is_session_dir(path: pathlib.Path) -> bool:
    """True for session directories (s9-abc123), not index.html or other files."""
    return path.is_dir() and path.name.startswith("s")


def _session_dirs() -> list[pathlib.Path]:
    if not SESSIONS_DIR.exists():
        return []
    return sorted(
        (p for p in SESSIONS_DIR.iterdir() if _is_session_dir(p)),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def load_session(sid):
    sd = SESSIONS_DIR / sid
    if not _is_session_dir(sd):
        raise RuntimeError(f"Not a session directory: {sid!r}")
    nodes = []
    nodes_dir = sd / "nodes"
    if nodes_dir.is_dir():
        for f in sorted(nodes_dir.glob("n_*.json")):
            try:
                nodes.append(json.loads(f.read_text()))
            except Exception:
                pass
    qf = sd / "query.txt"
    query = qf.read_text().strip() if qf.exists() else ""
    return query, nodes


def latest_sid():
    sess = _session_dirs()
    if not sess:
        raise RuntimeError(
            f"No sessions found under {SESSIONS_DIR} "
            "(expected directories named s9-…)"
        )
    return sess[0].name

# ── screenshot embedding ──────────────────────────────────────────────────────
def find_screenshots(sid):
    """Return list of (label, base64_png) for browser + computer turn screenshots."""
    shots = []
    for sub in ("browser", "computer"):
        root = SESSIONS_DIR / sid / sub
        if not root.exists():
            continue
        for run_dir in sorted(root.iterdir()):
            for layer_dir in sorted(run_dir.iterdir()):
                layer_shots = []
                for f in sorted(layer_dir.glob("turn_*_marked.png")):
                    try:
                        data = base64.b64encode(f.read_bytes()).decode()
                        layer_shots.append((f"{sub}/{layer_dir.name} / {f.stem}", data))
                    except Exception:
                        pass
                if not layer_shots:
                    for f in sorted(layer_dir.glob("turn_*_raw.png")):
                        try:
                            data = base64.b64encode(f.read_bytes()).decode()
                            layer_shots.append((f"{sub}/{layer_dir.name} / {f.stem}", data))
                        except Exception:
                            pass
                shots.extend(layer_shots)
    return shots

def find_legends(sid):
    """Return list of (label, text) for browser + computer legend files."""
    legends = []
    for sub in ("browser", "computer"):
        root = SESSIONS_DIR / sid / sub
        if not root.exists():
            continue
        for run_dir in sorted(root.iterdir()):
            for layer_dir in sorted(run_dir.iterdir()):
                for f in sorted(layer_dir.glob("turn_*_legend.txt")):
                    try:
                        legends.append((f"{sub}/{layer_dir.name} / {f.stem}", f.read_text(encoding="utf-8")))
                    except Exception:
                        pass
    return legends


# ── browser action compliance ─────────────────────────────────────────────────
VISIBLE_ACTION_TYPES = frozenset({
    "click", "type", "key", "scroll", "drag", "select", "submit",
})


def count_interactive_browser_actions(nodes) -> int:
    """Count non-terminal browser actions (click, scroll, filter, etc.)."""
    count = 0
    for nd in nodes:
        if nd.get("skill") != "browser":
            continue
        out = (nd.get("result") or {}).get("output", {}) or {}
        for step in out.get("actions") or []:
            for action in step.get("actions") or []:
                if action.get("type") in VISIBLE_ACTION_TYPES:
                    count += 1
    return count


def browser_action_compliance_banner(nodes) -> str:
    """Banner showing whether the session meets the ≥3 visible actions requirement."""
    count = count_interactive_browser_actions(nodes)
    browser_nodes = [n for n in nodes if n.get("skill") == "browser"]
    if not browser_nodes:
        return ""
    ok = count >= 3
    border = "#86efac" if ok else "#fca5a5"
    bg = "#f0fdf4" if ok else "#fef2f2"
    color = "#166534" if ok else "#991b1b"
    icon = "✓" if ok else "⚠"
    msg = (
        f"{icon} <b>{count}</b> visible browser action(s) recorded "
        f"(requirement: ≥3 — filter, sort, click, scroll, type, etc.). "
        f"Passive extract-only paths do not satisfy this."
        if ok
        else f"{icon} Only <b>{count}</b> visible browser action(s) recorded "
             f"(requirement: ≥3). Re-run with an interactive goal on the base URL."
    )
    return (
        f'<div style="margin-bottom:24px;padding:12px 16px;background:{bg};'
        f'border:1px solid {border};border-radius:10px;font-size:0.85rem;color:{color}">'
        f'{msg}</div>'
    )


def _action_compliance_summary(nodes) -> str:
    count = count_interactive_browser_actions(nodes)
    ok = count >= 3
    color = "#16a34a" if ok else "#dc2626"
    label = "meets requirement" if ok else "below requirement (need ≥3)"
    return (
        f'<div><b style="color:#374151">Visible browser actions:</b> '
        f'<span style="color:{color};font-weight:700">{count}</span> '
        f'<span style="color:#64748b">({label})</span></div>'
    )

def sec1_goal(query):
    return card(
        f'<p style="font-size:1rem;color:#1e293b;margin:0;line-height:1.6">'
        f'🎯 {e(query)}</p>',
        border="#6366f1", bg_color="#eef2ff"
    )


# ── Section 2: Planner DAG ────────────────────────────────────────────────────
def sec2_dag(nodes):
    """Build a visual left-to-right DAG of the session's nodes."""
    # Build adjacency: node_id → list of child node_ids
    id_to_node = {n["node_id"]: n for n in nodes}
    children = defaultdict(list)
    parents  = defaultdict(list)
    for n in nodes:
        for inp in n.get("inputs", []):
            if inp.startswith("n:") and inp in id_to_node:
                children[inp].append(n["node_id"])
                parents[n["node_id"]].append(inp)

    # BFS to assign columns (generation)
    roots = [n["node_id"] for n in nodes if not parents[n["node_id"]]]
    col = {}
    queue = list(roots)
    for r in roots: col[r] = 0
    visited = set(roots)
    while queue:
        cur = queue.pop(0)
        for ch in children[cur]:
            col[ch] = max(col.get(ch, 0), col[cur] + 1)
            if ch not in visited:
                visited.add(ch)
                queue.append(ch)

    max_col = max(col.values(), default=0)
    cols = defaultdict(list)
    for nid, c in col.items(): cols[c].append(nid)

    status_icon = {"complete": "✓", "failed": "✗", "skipped": "–", "pending": "○"}
    status_color = {"complete": "#16a34a", "failed": "#dc2626",
                    "skipped": "#9ca3af", "pending": "#d97706"}

    col_html = ""
    for c in range(max_col + 1):
        nodes_in_col = cols[c]
        node_boxes = ""
        for nid in nodes_in_col:
            nd = id_to_node[nid]
            sk = nd["skill"]
            st = nd["status"]
            f, b = SKILL_COLOR.get(sk, ("#374151","#f9fafb"))
            sc = status_color.get(st, "#9ca3af")
            si = status_icon.get(st, "?")
            elapsed = (nd.get("result") or {}).get("elapsed_s", 0)
            node_boxes += f"""
<div style="background:{b};border:2px solid {f};border-radius:8px;
  padding:7px 10px;margin-bottom:8px;min-width:110px;text-align:center">
  <div style="font-size:0.7rem;font-weight:700;color:{f}">{e(sk)}</div>
  <div style="font-size:0.65rem;color:{sc};margin-top:2px">
    {si} {e(st)} {f"· {elapsed:.1f}s" if elapsed else ""}
  </div>
  <div style="font-size:0.62rem;color:#94a3b8;margin-top:2px">{e(nid)}</div>
</div>"""
        col_html += f"""
<div style="display:flex;flex-direction:column;align-items:center;min-width:130px">
  <div style="font-size:0.65rem;color:#94a3b8;margin-bottom:6px;font-weight:600">
    STEP {c+1}
  </div>
  {node_boxes}
</div>"""
        if c < max_col:
            col_html += """
<div style="display:flex;align-items:center;padding:0 6px;color:#94a3b8;
  font-size:1.2rem;align-self:flex-start;margin-top:28px">→</div>"""

    total = len(nodes)
    complete = sum(1 for n in nodes if n["status"] == "complete")
    failed   = sum(1 for n in nodes if n["status"] == "failed")

    plan_html = ""
    for nd in nodes:
        if nd["skill"] != "planner":
            continue
        out = (nd.get("result") or {}).get("output", {}) or {}
        plan_nodes = out.get("nodes") or []
        rationale = out.get("rationale", "")
        if rationale or plan_nodes:
            skills = [n.get("skill", "?") for n in plan_nodes if isinstance(n, dict)]
            plan_html = (
                f'<div style="margin-bottom:12px;padding:10px 14px;background:#eef2ff;'
                f'border:1px solid #c7d2fe;border-radius:8px;font-size:0.82rem">'
                f'<div style="font-weight:700;color:#4338ca;margin-bottom:4px">'
                f'Planner emission ({e(nd["node_id"])})</div>'
                + (f'<div style="color:#64748b;margin-bottom:6px">{e(rationale)}</div>' if rationale else "")
                + (f'<code style="color:#4338ca">{" → ".join(skills) if skills else "(empty plan)"}</code>'
                   if plan_nodes or not rationale else "")
                + f'</div>'
            )
        break

    summary = (f'<div style="margin-bottom:10px;font-size:0.8rem;color:#64748b">'
               f'Total nodes: <b>{total}</b> · '
               f'<span style="color:#16a34a">✓ {complete} complete</span> · '
               f'<span style="color:#dc2626">✗ {failed} failed</span>'
               f'</div>')

    dag_html = (f'<div style="display:flex;flex-direction:row;align-items:flex-start;'
                f'overflow-x:auto;padding:12px;background:#f8fafc;'
                f'border:1px solid #e2e8f0;border-radius:10px">'
                f'{col_html}</div>')
    return plan_html + summary + dag_html


_FIELD_SUFFIXES = (
    "model_name", "organisation", "organization", "likes", "parameter_count",
    "description", "verdict", "best_for", "price_inr", "price", "cpu", "ram",
    "storage", "display", "model", "name", "location", "duration", "fees",
    "placement_support", "free_plan", "paid_price",
)


def _latest_distiller_fields(nodes) -> tuple[str, dict] | tuple[None, None]:
    for nd in reversed(nodes):
        if nd["skill"] != "distiller" or nd["status"] != "complete":
            continue
        fields = (nd.get("result") or {}).get("output", {}).get("fields")
        if isinstance(fields, dict) and fields:
            return nd["node_id"], fields
    return None, None


def _fields_to_table(fields: dict) -> str | None:
    """Pivot distiller key=value fields into a comparison table when possible."""
    if not fields or len(fields) < 2:
        return None
    rows_by_entity: dict[str, dict[str, str]] = defaultdict(dict)
    for key, val in fields.items():
        k = str(key)
        matched = False
        for suf in sorted(_FIELD_SUFFIXES, key=len, reverse=True):
            token = f"_{suf}"
            if k.endswith(token):
                entity = k[: -len(token)] or suf
                rows_by_entity[entity][suf.replace("_", " ")] = str(val)
                matched = True
                break
        if not matched:
            rows_by_entity["_other"][k] = str(val)
    if len(rows_by_entity) == 1 and "_other" in rows_by_entity:
        return None
    all_cols: list[str] = []
    for row in rows_by_entity.values():
        for c in row:
            if c not in all_cols:
                all_cols.append(c)
    if not all_cols:
        return None
    th = "".join(
        f'<th style="padding:8px 12px;text-align:left;font-size:0.8rem;color:#1e293b;'
        f'white-space:nowrap">{e(c.title())}</th>'
        for c in all_cols
    )
    trs = ""
    for i, (entity, row) in enumerate(sorted(rows_by_entity.items())):
        if entity == "_other":
            continue
        bg_row = "#fff" if i % 2 == 0 else "#f8fafc"
        tds = "".join(
            f'<td style="padding:8px 12px;font-size:0.8rem;color:#374151;'
            f'border-top:1px solid #f1f5f9">{e(row.get(c, "—"))}</td>'
            for c in all_cols
        )
        trs += f'<tr style="background:{bg_row}">{tds}</tr>'
    if not trs:
        return None
    return (
        f'<div style="overflow-x:auto">'
        f'<table style="width:100%;border-collapse:collapse;border:1px solid #e2e8f0">'
        f'<thead style="background:#fffbeb"><tr>{th}</tr></thead>'
        f'<tbody>{trs}</tbody></table></div>'
    )


# ── Section 3: Browser Path ───────────────────────────────────────────────────
def sec3_browser_path(nodes):
    browser_nodes = [n for n in nodes if n["skill"] == "browser"]
    computer_nodes = [n for n in nodes if n["skill"] == "computer"]
    if not browser_nodes and not computer_nodes:
        return card('<p style="color:#9ca3af;margin:0">No browser or computer nodes in this session.</p>')

    rows = ""
    path_icons = {
        "extract":       ("⚡", "#0891b2", "Static HTML — cheapest path"),
        "deterministic": ("🎯", "#7c3aed", "CSS/XPath selectors"),
        "a11y":          ("♿", "#d97706", "Accessibility tree (text-only LLM)"),
        "vision":        ("👁",  "#dc2626", "Set-of-Marks vision model"),
        "blocked":       ("⛔", "#dc2626", "Gateway blocked (CAPTCHA/login)"),
    }
    for nd in browser_nodes:
        out = (nd.get("result") or {}).get("output", {}) or {}
        path   = out.get("path", "—")
        turns  = out.get("turns", 0)
        goal   = out.get("goal", "")
        url    = out.get("url", "")
        status = nd["status"]
        err    = (nd.get("result") or {}).get("error", "") or ""
        icon, color, desc = path_icons.get(path, ("❓", "#64748b", path))
        status_color = "#16a34a" if status == "complete" else "#dc2626"
        rows += f"""
<tr style="border-bottom:1px solid #f1f5f9">
  <td style="padding:8px 10px;font-size:0.78rem;font-weight:600;color:#374151">{e(nd["node_id"])}</td>
  <td style="padding:8px 10px">
    <span style="font-size:1.1rem">{icon}</span>
    <span style="font-size:0.78rem;font-weight:700;color:{color};margin-left:4px">{e(path)}</span>
    <div style="font-size:0.7rem;color:#9ca3af">{e(desc)}</div>
  </td>
  <td style="padding:8px 10px;font-size:0.78rem;color:#374151">{turns}</td>
  <td style="padding:8px 10px;font-size:0.72rem;color:#64748b;max-width:220px;word-break:break-all">{e(url[:80])}</td>
  <td style="padding:8px 10px;font-size:0.78rem;color:{status_color};font-weight:700">{e(status)}</td>
</tr>"""
        if err:
            rows += f"""<tr><td colspan="5" style="padding:4px 10px 8px;font-size:0.72rem;color:#dc2626">
              ⚠ {e(err[:200])}</td></tr>"""

    comp_path_icons = {
        "extract": ("⚡", "#0891b2", "AX / clipboard / files"),
        "deterministic": ("🎯", "#7c3aed", "Known workflow / hotkeys"),
        "a11y": ("♿", "#d97706", "AX tree + text LLM"),
        "vision": ("👁", "#dc2626", "Set-of-Marks vision"),
        "electron": ("🖥", "#2563eb", "Electron CDP page extract"),
    }
    for nd in computer_nodes:
        out = (nd.get("result") or {}).get("output", {}) or {}
        path = out.get("path", "—")
        turns = out.get("turns", 0)
        app = out.get("app", "")
        status = nd["status"]
        err = (nd.get("result") or {}).get("error", "") or ""
        icon, color, desc = comp_path_icons.get(path, ("❓", "#64748b", path))
        status_color = "#16a34a" if status == "complete" else "#dc2626"
        rows += f"""
<tr style="border-bottom:1px solid #f1f5f9">
  <td style="padding:8px 10px;font-size:0.78rem;font-weight:600;color:#374151">{e(nd["node_id"])}</td>
  <td style="padding:8px 10px">
    <span style="font-size:1.1rem">{icon}</span>
    <span style="font-size:0.78rem;font-weight:700;color:{color};margin-left:4px">{e(path)}</span>
    <div style="font-size:0.7rem;color:#9ca3af">{e(desc)}</div>
  </td>
  <td style="padding:8px 10px;font-size:0.78rem;color:#374151">{turns}</td>
  <td style="padding:8px 10px;font-size:0.72rem;color:#64748b;max-width:220px;word-break:break-all">{e(app[:80])}</td>
  <td style="padding:8px 10px;font-size:0.78rem;color:{status_color};font-weight:700">{e(status)}</td>
</tr>"""
        if err:
            rows += f"""<tr><td colspan="5" style="padding:4px 10px 8px;font-size:0.72rem;color:#dc2626">
              ⚠ {e(err[:200])}</td></tr>"""

    return f"""
<div style="overflow-x:auto">
<table style="width:100%;border-collapse:collapse">
  <thead><tr style="background:#f8fafc">
    <th style="padding:8px 10px;text-align:left;font-size:0.75rem;color:#64748b">Node</th>
    <th style="padding:8px 10px;text-align:left;font-size:0.75rem;color:#64748b">Layer chosen</th>
    <th style="padding:8px 10px;text-align:left;font-size:0.75rem;color:#64748b">Turns</th>
    <th style="padding:8px 10px;text-align:left;font-size:0.75rem;color:#64748b">URL</th>
    <th style="padding:8px 10px;text-align:left;font-size:0.75rem;color:#64748b">Status</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table></div>"""


# ── Section 4: Browser Actions ────────────────────────────────────────────────
def sec4_actions(nodes):
    browser_nodes = [n for n in nodes if n["skill"] == "browser"]
    computer_nodes = [n for n in nodes if n["skill"] == "computer"]
    if not browser_nodes and not computer_nodes:
        return card('<p style="color:#9ca3af;margin:0">No browser or computer nodes in this session.</p>')

    count = count_interactive_browser_actions(nodes)
    html_out = ""
    if browser_nodes:
        html_out = (
            f'<div style="margin-bottom:12px;padding:8px 12px;background:#faf5ff;'
            f'border:1px solid #ddd6fe;border-radius:8px;font-size:0.8rem;color:#5b21b6">'
            f'Visible browser actions: <b>{count}</b> · requirement: ≥3 '
            f'(click, scroll, filter, sort, type…)'
            f'</div>'
        )
    elif computer_nodes:
        html_out = (
            f'<div style="margin-bottom:12px;padding:8px 12px;background:#f0fdfa;'
            f'border:1px solid #99f6e4;border-radius:8px;font-size:0.8rem;color:#0f766e">'
            f'Computer skill actions recorded below (Session 10 — browser ≥3 rule does not apply).'
            f'</div>'
        )

    for nd in browser_nodes + computer_nodes:
        out     = (nd.get("result") or {}).get("output", {}) or {}
        actions = out.get("actions") or []
        path    = out.get("path", "—")
        goal    = out.get("goal", "")
        nid     = nd["node_id"]
        skill   = nd["skill"]

        if not actions:
            html_out += (f'<p style="color:#9ca3af;font-size:0.8rem">'
                         f'{nid} — no actions recorded (layer: {e(path)})</p>')
            continue

        action_type_color = {
            "click": "#4f46e5", "type": "#0891b2", "key": "#7c3aed",
            "scroll": "#d97706", "drag": "#9333ea", "wait": "#64748b",
            "done": "#16a34a",
        }
        rows = ""
        for step in actions:
            turn = step.get("turn", "?")
            step_actions = step.get("actions") or []
            outcome = step.get("outcome", "")
            ok = "error" not in str(outcome).lower()
            outcome_color = "#16a34a" if ok else "#dc2626"
            act_pills = ""
            if step_actions:
                for a in step_actions:
                    atype = a.get("type", "?")
                    detail = ""
                    if atype in ("click", "type"):
                        detail = f" #{a.get('mark','?')}"
                        if atype == "type":
                            detail += f" ← {str(a.get('value',''))[:30]}"
                    elif atype == "key":
                        detail = f" {a.get('value','')}"
                    elif atype == "scroll":
                        detail = f" {a.get('direction','')} {a.get('amount','')}"
                    elif atype == "done":
                        detail = f" success={a.get('success','?')}"
                    color = action_type_color.get(atype, "#374151")
                    act_pills += (f'<span style="background:{color}22;color:{color};'
                                  f'border:1px solid {color}44;padding:1px 7px;'
                                  f'border-radius:999px;font-size:0.7rem;margin-right:4px;'
                                  f'font-weight:600">{e(atype)}{e(detail)}</span>')
            elif step.get("action") or step.get("step"):
                # Layer 2a deterministic workflow log from computer skill.
                act_name = str(step.get("action") or "?")
                step_detail = step.get("step") or {}
                detail = ""
                if isinstance(step_detail, dict):
                    if step_detail.get("text"):
                        detail = f" {str(step_detail['text'])[:40]}"
                    elif step_detail.get("label"):
                        detail = f" {step_detail['label']!s}"
                    elif step_detail.get("keys"):
                        detail = f" {'+'.join(str(k) for k in step_detail['keys'])}"
                    elif step_detail.get("key"):
                        detail = f" {step_detail['key']}"
                color = action_type_color.get(act_name, "#0d9488")
                act_pills = (f'<span style="background:{color}22;color:{color};'
                             f'border:1px solid {color}44;padding:1px 7px;'
                             f'border-radius:999px;font-size:0.7rem;margin-right:4px;'
                             f'font-weight:600">{e(act_name)}{e(detail)}</span>')
            rows += f"""
<tr style="border-bottom:1px solid #f1f5f9">
  <td style="padding:6px 10px;font-size:0.75rem;font-weight:700;color:#64748b;white-space:nowrap">Turn {turn}</td>
  <td style="padding:6px 10px">{act_pills}</td>
  <td style="padding:6px 10px;font-size:0.72rem;color:{outcome_color}">{e(str(outcome)[:120])}</td>
</tr>"""

        f_color, _ = SKILL_COLOR.get(skill, ("#7c3aed", "#f5f3ff"))
        html_out += f"""
<div style="margin-bottom:16px;border:1px solid #ddd6fe;border-radius:10px;overflow:hidden">
  <div style="background:#f5f3ff;padding:8px 14px;border-bottom:1px solid #ddd6fe">
    <span style="font-weight:700;color:#7c3aed;font-size:0.82rem">{e(nid)}</span>
    <span style="font-size:0.75rem;color:#9ca3af;margin-left:8px">layer: {e(path)} · {len(actions)} turns</span>
    <div style="font-size:0.72rem;color:#64748b;margin-top:2px">Goal: {e(goal[:120])}</div>
  </div>
  <div style="overflow-x:auto">
  <table style="width:100%;border-collapse:collapse">
    <thead><tr style="background:#faf5ff">
      <th style="padding:6px 10px;text-align:left;font-size:0.72rem;color:#7c3aed">Turn</th>
      <th style="padding:6px 10px;text-align:left;font-size:0.72rem;color:#7c3aed">Actions</th>
      <th style="padding:6px 10px;text-align:left;font-size:0.72rem;color:#7c3aed">Outcome</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table></div>
</div>"""

    return html_out or card('<p style="color:#9ca3af;margin:0">No actions recorded.</p>')


# ── Section 5: Screenshots ────────────────────────────────────────────────────
def sec5_screenshots(sid):
    shots = find_screenshots(sid)
    legends = find_legends(sid)

    if not shots and not legends:
        return card('<p style="color:#9ca3af;margin:0">No screenshots or page-state logs found in artifacts.</p>')

    html_out = ""
    # Screenshots grid
    if shots:
        grid = ""
        for label, b64 in shots[:24]:   # cap at 24 to keep file size sane
            grid += f"""
<div style="border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;background:#fff">
  <div style="padding:4px 8px;background:#f8fafc;font-size:0.65rem;color:#64748b">{e(label)}</div>
  <img src="data:image/png;base64,{b64}"
       style="width:100%;display:block;max-height:300px;object-fit:contain" loading="lazy"/>
</div>"""
        html_out += (f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));'
                     f'gap:12px;margin-bottom:16px">{grid}</div>')

    # Legend files
    if legends:
        leg_html = ""
        for label, text in legends[:12]:
            leg_html += collapsible(f"Legend: {label}", pre(text, 2000), accent="#7c3aed")
        html_out += f'<div style="margin-top:8px">{leg_html}</div>'

    return html_out


# ── Section 6: Extracted Data ─────────────────────────────────────────────────
def sec6_extracted(nodes):
    items = []

    did, fields = _latest_distiller_fields(nodes)
    if fields:
        table = _fields_to_table(fields)
        body = table or pre(json.dumps(fields, indent=2, ensure_ascii=False), 4000)
        items.append(
            f'<div style="margin-bottom:14px">'
            f'<div style="font-size:0.78rem;font-weight:700;color:#d97706;margin-bottom:6px">'
            f'{e(did)} (distiller — structured fields, {len(fields)} keys)</div>'
            f'{body}</div>'
        )

    for nd in nodes:
        if nd["skill"] not in ("browser", "computer", "researcher", "retriever"):
            continue
        out = (nd.get("result") or {}).get("output", {}) or {}
        content = out.get("content") or out.get("findings") or out.get("chunks", "")
        sources = out.get("sources") or []
        actions = out.get("actions") or []
        if not content and not actions:
            continue
        src_links = " · ".join(
            f'<a href="{e(s.get("url","#"))}" target="_blank" '
            f'style="color:#0891b2;font-size:0.72rem">{e(s.get("title") or s.get("url",""))}</a>'
            for s in (sources or [])[:5]
        )
        f_c, _ = SKILL_COLOR.get(nd["skill"], ("#374151", "#f9fafb"))
        action_note = ""
        if actions:
            action_note = (
                f'<p style="font-size:0.75rem;color:#64748b;margin:4px 0">'
                f'{len(actions)} browser turn(s) recorded — see §4</p>'
            )
        items.append(
            f'<div style="margin-bottom:12px">'
            f'<div style="font-size:0.78rem;font-weight:700;color:{f_c};margin-bottom:4px">'
            f'{e(nd["node_id"])} ({e(nd["skill"])})'
            + (f' — {src_links}' if src_links else "")
            + f'</div>'
            + action_note
            + (collapsible(f"Raw content ({len(str(content))} chars)", pre(str(content), 3000), accent=f_c)
               if content else "")
            + f'</div>'
        )

    return "".join(items) or card('<p style="color:#9ca3af;margin:0">No extracted data found.</p>')


# ── Section 7: Final Comparison Table ─────────────────────────────────────────
def sec7_table(nodes):
    final_answer = ""
    for nd in reversed(nodes):
        if nd["skill"] == "formatter" and nd["status"] == "complete":
            fa = (nd.get("result") or {}).get("output", {}).get("final_answer", "")
            if fa:
                final_answer = fa
                break

    _, fields = _latest_distiller_fields(nodes)
    if fields:
        dist_table = _fields_to_table(fields)
        if dist_table:
            raw_col = collapsible("Formatter narrative", pre(final_answer, 4000), accent="#64748b") if final_answer else ""
            return (
                f'<p style="font-size:0.8rem;color:#64748b;margin:0 0 10px">'
                f'Built from distiller structured fields (§6).</p>'
                + dist_table + raw_col
            )

    if not final_answer:
        return card('<p style="color:#9ca3af;margin:0">No formatter completed in this session (node cap hit before formatter ran).</p>')

    # Try to detect a markdown table in the answer
    lines = final_answer.strip().splitlines()
    table_lines = [l for l in lines if "|" in l]

    if len(table_lines) >= 3:
        # Parse markdown table → HTML
        def parse_row(row):
            return [c.strip() for c in row.strip().strip("|").split("|")]

        header_row = parse_row(table_lines[0])
        body_rows  = [parse_row(l) for l in table_lines[2:] if not all(c.strip("-:") == "" for c in l.split("|"))]

        th = "".join(f'<th style="padding:8px 12px;text-align:left;font-size:0.8rem;color:#1e293b;white-space:nowrap">{e(h)}</th>' for h in header_row)
        trs = ""
        for i, row in enumerate(body_rows):
            bg_row = "#fff" if i % 2 == 0 else "#f8fafc"
            tds = "".join(f'<td style="padding:8px 12px;font-size:0.8rem;color:#374151;border-top:1px solid #f1f5f9">{e(c)}</td>' for c in row)
            trs += f'<tr style="background:{bg_row}">{tds}</tr>'

        table_html = (f'<div style="overflow-x:auto">'
                      f'<table style="width:100%;border-collapse:collapse;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden">'
                      f'<thead style="background:#f0fdf4"><tr>{th}</tr></thead>'
                      f'<tbody>{trs}</tbody>'
                      f'</table></div>')
        raw_col = collapsible("Raw final answer text", pre(final_answer, 4000), accent="#64748b")
        return table_html + raw_col

    # No table detected — show as formatted text
    return (f'<div style="padding:14px;background:#f0fdf4;border:1px solid #86efac;border-radius:8px">'
            f'<pre style="margin:0;white-space:pre-wrap;word-break:break-word;'
            f'font-size:0.85rem;color:#14532d;font-family:system-ui,sans-serif">{e(final_answer)}</pre>'
            f'</div>')


# ── Section 8: Turn Count and Cost Summary ────────────────────────────────────
def _gateway_cost_summary(sid: str) -> str:
    try:
        sys.path.insert(0, str(SCRIPT_DIR / "code"))
        from gateway import LLM, ensure_gateway
        ensure_gateway()
        data = LLM().cost_by_agent(session=sid)
        agents = data.get("by_agent") or data.get("agents") or {}
        if not agents:
            return ""
        parts = []
        total_usd = 0.0
        for name, info in sorted(agents.items()):
            if not isinstance(info, dict):
                continue
            usd = float(info.get("cost_usd") or info.get("usd") or 0)
            total_usd += usd
            tin = info.get("input_tokens") or info.get("tokens_in") or 0
            tout = info.get("output_tokens") or info.get("tokens_out") or 0
            parts.append(f"{name}: ${usd:.4f} ({tin}+{tout} tok)")
        if not parts:
            return ""
        return (
            f'<div style="margin-bottom:12px;padding:10px 14px;background:#ecfdf5;'
            f'border:1px solid #86efac;border-radius:8px;font-size:0.8rem">'
            f'<b>Gateway cost (session={e(sid)}):</b> ${total_usd:.4f}<br>'
            f'{" · ".join(e(p) for p in parts)}</div>'
        )
    except Exception:
        return ""


def sec8_summary(nodes, sid: str = ""):
    from collections import Counter

    total_turns  = 0
    total_tokens_in  = 0
    total_tokens_out = 0
    total_elapsed    = 0.0
    providers    = Counter()
    skill_totals = defaultdict(lambda: {"count":0,"elapsed":0.0,"turns":0})

    rows = ""
    for nd in nodes:
        res  = nd.get("result") or {}
        sk   = nd["skill"]
        st   = nd["status"]
        out  = res.get("output") or {}
        elapsed = res.get("elapsed_s", 0) or 0
        prov    = res.get("provider", "") or ""
        turns   = out.get("turns", 0) or 0

        total_elapsed += elapsed
        total_turns   += turns
        if prov: providers[prov] += 1

        skill_totals[sk]["count"]   += 1
        skill_totals[sk]["elapsed"] += elapsed
        skill_totals[sk]["turns"]   += turns

        status_color = "#16a34a" if st == "complete" else "#dc2626"
        f_c, _ = SKILL_COLOR.get(sk, ("#374151","#f9fafb"))
        rows += f"""
<tr style="border-bottom:1px solid #f1f5f9">
  <td style="padding:6px 10px;font-size:0.75rem;font-weight:600;color:#374151">{e(nd["node_id"])}</td>
  <td style="padding:6px 10px">{pill(sk)}</td>
  <td style="padding:6px 10px;font-size:0.75rem;color:{status_color};font-weight:700">{e(st)}</td>
  <td style="padding:6px 10px;font-size:0.75rem;color:#374151">{elapsed:.1f}s</td>
  <td style="padding:6px 10px;font-size:0.75rem;color:#374151">{turns or "—"}</td>
  <td style="padding:6px 10px;font-size:0.72rem;color:#9ca3af">{e(prov)}</td>
</tr>"""

    prov_str = ", ".join(f"{p} ×{c}" for p, c in providers.most_common())

    cost_html = _gateway_cost_summary(sid) if sid else ""

    totals_html = f"""
<div style="display:flex;flex-wrap:wrap;gap:16px;padding:14px 16px;
  background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;margin-bottom:16px">
  <div><b style="color:#374151">Total nodes:</b> {len(nodes)}</div>
  <div><b style="color:#374151">Browser turns:</b> {total_turns}</div>
  {_action_compliance_summary(nodes)}
  <div><b style="color:#374151">Total elapsed:</b> {total_elapsed:.1f}s</div>
  <div><b style="color:#374151">Providers:</b> {e(prov_str) or "—"}</div>
</div>{cost_html}"""

    table_html = f"""
<div style="overflow-x:auto">
<table style="width:100%;border-collapse:collapse">
  <thead><tr style="background:#f8fafc">
    <th style="padding:6px 10px;text-align:left;font-size:0.72rem;color:#64748b">Node</th>
    <th style="padding:6px 10px;text-align:left;font-size:0.72rem;color:#64748b">Skill</th>
    <th style="padding:6px 10px;text-align:left;font-size:0.72rem;color:#64748b">Status</th>
    <th style="padding:6px 10px;text-align:left;font-size:0.72rem;color:#64748b">Elapsed</th>
    <th style="padding:6px 10px;text-align:left;font-size:0.72rem;color:#64748b">Browser turns</th>
    <th style="padding:6px 10px;text-align:left;font-size:0.72rem;color:#64748b">Provider</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table></div>"""

    return totals_html + table_html


# ── Architecture note (optional, written by assignment runners) ───────────────
def load_architecture_note(sid: str) -> str:
    p = SESSIONS_DIR / sid / "architecture_note.txt"
    return p.read_text(encoding="utf-8").strip() if p.exists() else ""


def sec0_architecture(note: str) -> str:
    if not note:
        return ""
    return section(
        0,
        "Architecture Note",
        card(f'<pre style="margin:0;white-space:pre-wrap;word-break:break-word;'
             f'font-size:0.82rem;color:#334155;font-family:system-ui,sans-serif">'
             f'{e(note)}</pre>', border="#cbd5e1", bg_color="#f8fafc"),
        "#475569",
    )


# ── page assembly ─────────────────────────────────────────────────────────────
def build_html(sid, query, nodes, arch_note: str = ""):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    s0 = sec0_architecture(arch_note)
    compliance = browser_action_compliance_banner(nodes)
    s1 = section(1, "Original User Goal",        sec1_goal(query),              "#6366f1")
    s2 = section(2, "Planner DAG",               sec2_dag(nodes),               "#4f46e5")
    s3 = section(3, "Browser Path Chosen",        sec3_browser_path(nodes),      "#7c3aed")
    s4 = section(4, "Browser Actions Taken",      sec4_actions(nodes),           "#7c3aed")
    s5 = section(5, "Screenshots / Page-State Logs", sec5_screenshots(sid),     "#0891b2")
    s6 = section(6, "Extracted Data",             sec6_extracted(nodes),         "#0891b2")
    s7 = section(7, "Final Comparison Table",     sec7_table(nodes),             "#16a34a")
    s8 = section(8, "Turn Count & Cost Summary",  sec8_summary(nodes, sid),           "#64748b")

    nav = "".join(
        f'<a href="#s{i}" style="text-decoration:none;color:#64748b;font-size:0.78rem;'
        f'padding:4px 10px;border-radius:6px;display:block;margin-bottom:2px;'
        f'white-space:nowrap" onmouseover="this.style.background=\'#f1f5f9\'" '
        f'onmouseout="this.style.background=\'transparent\'">'
        f'<span style="background:#e2e8f0;color:#374151;border-radius:50%;'
        f'width:18px;height:18px;display:inline-flex;align-items:center;'
        f'justify-content:center;font-size:0.65rem;font-weight:700;margin-right:6px">{i}</span>'
        f'{t}</a>'
        for i, t in [
            (1,"User Goal"),(2,"Planner DAG"),(3,"Browser Path"),
            (4,"Actions"),(5,"Screenshots"),(6,"Extracted Data"),
            (7,"Comparison Table"),(8,"Cost Summary"),
        ]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Replay Viewer — {e(sid)}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:system-ui,-apple-system,sans-serif;background:#f1f5f9;color:#1e293b}}
  details>summary::marker{{display:none}}
  @media(max-width:768px){{#sidebar{{display:none}}#main{{margin-left:0!important}}}}
</style>
</head>
<body>

<div id="sidebar" style="position:fixed;top:0;left:0;width:190px;height:100vh;
  overflow-y:auto;background:#fff;border-right:1px solid #e2e8f0;padding:16px 8px;z-index:100">
  <div style="font-size:0.65rem;font-weight:700;color:#94a3b8;
    text-transform:uppercase;letter-spacing:0.08em;padding:0 8px;margin-bottom:10px">
    Replay Viewer
  </div>
  <div style="font-size:0.7rem;color:#94a3b8;padding:0 8px;margin-bottom:12px;
    word-break:break-all">{e(sid)}</div>
  {nav}
</div>

<div id="main" style="margin-left:190px;padding:28px 32px;max-width:1200px">

  <div style="margin-bottom:24px">
    <div style="font-size:0.72rem;color:#94a3b8;margin-bottom:4px">
      Session Replay Viewer · {e(ts)}
    </div>
    <h1 style="font-size:1.4rem;font-weight:800;color:#1e293b">{e(sid)}</h1>
  </div>

  {f'<div id="s0">{s0}</div>' if s0 else ''}
  {compliance}
  <div id="s1">{s1}</div>
  <div id="s2">{s2}</div>
  <div id="s3">{s3}</div>
  <div id="s4">{s4}</div>
  <div id="s5">{s5}</div>
  <div id="s6">{s6}</div>
  <div id="s7">{s7}</div>
  <div id="s8">{s8}</div>

</div>
</body>
</html>"""


def build_report(sid: str | None = None) -> str:
    """Build HTML report for a session. Returns the HTML string."""
    if not sid:
        sid = latest_sid()
    query, nodes = load_session(sid)
    arch = load_architecture_note(sid)
    return build_html(sid, query, nodes, arch_note=arch)


def write_report(sid: str | None = None) -> pathlib.Path:
    """Write report.html into the session dir and logs/. Returns primary path."""
    if not sid:
        sid = latest_sid()
    page = build_report(sid)
    session_out = SESSIONS_DIR / sid / "report.html"
    session_out.parent.mkdir(parents=True, exist_ok=True)
    session_out.write_text(page, encoding="utf-8")
    log_out = LOGS_DIR / f"{sid}_replay.html"
    log_out.write_text(page, encoding="utf-8")
    return session_out


def build_session_index() -> pathlib.Path:
    """Build an index.html listing all sessions with report links."""
    rows = ""
    for sd in _session_dirs():
        qf = sd / "query.txt"
        query = qf.read_text(encoding="utf-8").strip()[:120] if qf.exists() else "—"
        tk = sd / "task_key.txt"
        task = tk.read_text(encoding="utf-8").strip() if tk.exists() else ""
        report = sd / "report.html"
        has_report = report.exists()
        mtime = datetime.datetime.fromtimestamp(sd.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        link = f'<a href="{e(sd.name)}/report.html" style="color:#4f46e5">report</a>' if has_report else '<span style="color:#9ca3af">—</span>'
        rows += f"""<tr>
  <td style="padding:8px 12px;font-family:monospace;font-size:0.82rem">{e(sd.name)}</td>
  <td style="padding:8px 12px;font-size:0.82rem">{e(task or "—")}</td>
  <td style="padding:8px 12px;font-size:0.82rem;color:#475569">{e(query)}</td>
  <td style="padding:8px 12px;font-size:0.82rem">{mtime}</td>
  <td style="padding:8px 12px">{link}</td>
</tr>"""

    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>Session Index</title>
<style>body{{font-family:system-ui,sans-serif;background:#f8fafc;padding:24px;color:#1e293b}}
table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden}}
th{{background:#f1f5f9;text-align:left;padding:8px 12px;font-size:0.75rem;color:#64748b}}
</style></head><body>
<h1 style="font-size:1.25rem;margin-bottom:16px">Assignment 9 — Session Index</h1>
<table><thead><tr>
  <th>Session</th><th>Task</th><th>Query</th><th>Run at</th><th>Report</th>
</tr></thead><tbody>{rows or '<tr><td colspan="5" style="padding:12px">No sessions yet.</td></tr>'}</tbody></table>
</body></html>"""
    out = SESSIONS_DIR / "index.html"
    out.write_text(page, encoding="utf-8")
    return out


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    do_open = "--open" in sys.argv
    do_index = "--index" in sys.argv

    if do_index:
        idx = build_session_index()
        print(f"[replay] index → {idx}")
        return

    sid = args[0] if args else None
    if not sid:
        sid = latest_sid()
        print(f"[replay] no session id given — using latest: {sid}")

    print(f"[replay] loading session {sid} …")
    _, nodes = load_session(sid)
    print(f"[replay] {len(nodes)} nodes found")

    out = write_report(sid)
    print(f"[replay] written → {out}")
    print(f"[replay] copy    → {LOGS_DIR / f'{sid}_replay.html'}")
    build_session_index()
    print(f"[replay] open:  xdg-open '{out}'")

    if do_open:
        import subprocess
        subprocess.Popen(["xdg-open", str(out)])

if __name__ == "__main__":
    main()
