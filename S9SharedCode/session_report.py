"""session_report.py  —  generate a self-contained HTML inspection report
for one S9 orchestrator session.

Usage:
    python session_report.py <session-id>
    python session_report.py s9-3bf2adf5

    # latest session automatically:
    python session_report.py

The HTML file is written to logs/<session-id>.html and a path is printed.
Open it in any browser — no server needed.
"""

from __future__ import annotations

import html
import json
import pathlib
import sys
import datetime

# ── paths ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR  = pathlib.Path(__file__).parent
SESSIONS_DIR = SCRIPT_DIR / "code" / "state" / "sessions"
LOGS_DIR    = SCRIPT_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)


# ── skill colours ─────────────────────────────────────────────────────────────

SKILL_COLORS = {
    "planner":          ("#4f46e5", "#eef2ff"),   # indigo
    "researcher":       ("#0891b2", "#ecfeff"),   # cyan
    "browser":          ("#7c3aed", "#f5f3ff"),   # violet
    "distiller":        ("#d97706", "#fffbeb"),   # amber
    "critic":           ("#dc2626", "#fef2f2"),   # red
    "formatter":        ("#16a34a", "#f0fdf4"),   # green
    "retriever":        ("#0284c7", "#e0f2fe"),   # sky
    "summariser":       ("#9333ea", "#faf5ff"),   # purple
    "coder":            ("#b45309", "#fef3c7"),   # yellow-brown
    "sandbox_executor": ("#64748b", "#f8fafc"),   # slate
}

STATUS_BADGE = {
    "complete": ("✓", "#16a34a", "#dcfce7"),
    "failed":   ("✗", "#dc2626", "#fee2e2"),
    "skipped":  ("–", "#6b7280", "#f3f4f6"),
    "running":  ("…", "#d97706", "#fef3c7"),
    "pending":  ("○", "#6b7280", "#f3f4f6"),
}


def skill_badge(skill: str) -> str:
    fg, bg = SKILL_COLORS.get(skill, ("#374151", "#f9fafb"))
    return (f'<span style="background:{bg};color:{fg};border:1px solid {fg}33;'
            f'padding:2px 8px;border-radius:999px;font-size:0.75rem;'
            f'font-weight:600;letter-spacing:0.04em">{skill}</span>')


def status_badge(status: str) -> str:
    icon, fg, bg = STATUS_BADGE.get(status, ("?", "#374151", "#f3f4f6"))
    return (f'<span style="background:{bg};color:{fg};border:1px solid {fg}44;'
            f'padding:2px 8px;border-radius:999px;font-size:0.75rem;font-weight:700">'
            f'{icon} {status}</span>')


def e(text: str) -> str:
    """HTML-escape a string."""
    return html.escape(str(text))


def collapsible(label: str, content_html: str, open_: bool = False,
                accent: str = "#4f46e5") -> str:
    open_attr = " open" if open_ else ""
    return f"""
<details{open_attr} style="margin-top:10px;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden">
  <summary style="padding:8px 14px;cursor:pointer;background:#f9fafb;
    font-size:0.82rem;font-weight:600;color:{accent};user-select:none;
    list-style:none;display:flex;align-items:center;gap:6px">
    <span style="font-size:0.7rem">▶</span> {label}
  </summary>
  <div style="padding:12px 14px;background:#fff;border-top:1px solid #e5e7eb">
    {content_html}
  </div>
</details>"""


def preblock(text: str, max_chars: int = 8000) -> str:
    truncated = str(text)
    note = ""
    if len(truncated) > max_chars:
        truncated = truncated[:max_chars]
        note = f'<p style="color:#9ca3af;font-size:0.75rem;margin:4px 0 0">… truncated to {max_chars:,} chars</p>'
    return (f'<pre style="margin:0;padding:10px;background:#0f172a;color:#e2e8f0;'
            f'border-radius:6px;font-size:0.72rem;line-height:1.5;'
            f'overflow-x:auto;white-space:pre-wrap;word-break:break-word">'
            f'{e(truncated)}</pre>{note}')


def json_block(obj, max_chars: int = 6000) -> str:
    text = json.dumps(obj, indent=2, ensure_ascii=False)
    return preblock(text, max_chars)


# ── node card ─────────────────────────────────────────────────────────────────

def render_node(node: dict) -> str:
    nid    = node["node_id"]
    skill  = node["skill"]
    status = node["status"]
    result = node.get("result") or {}
    output = result.get("output") or {}
    error  = result.get("error")
    provider = result.get("provider", "")
    elapsed  = result.get("elapsed_s", 0)
    prompt   = node.get("prompt_sent", "")
    successors = result.get("successors") or []
    inputs = node.get("inputs", [])

    fg, bg = SKILL_COLORS.get(skill, ("#374151", "#f9fafb"))

    # ── header ────────────────────────────────────────────────────────────────
    header = f"""
<div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
  <code style="font-size:0.9rem;font-weight:700;color:#374151">{e(nid)}</code>
  {skill_badge(skill)}
  {status_badge(status)}
  <span style="margin-left:auto;font-size:0.75rem;color:#9ca3af">
    {f"{elapsed:.1f}s" if elapsed else ""}
    {"· " + e(provider) if provider else ""}
  </span>
</div>"""

    # ── inputs row ────────────────────────────────────────────────────────────
    inp_pills = " ".join(
        f'<code style="background:#f1f5f9;padding:1px 6px;border-radius:4px;'
        f'font-size:0.72rem">{e(i)}</code>' for i in inputs
    )
    if inp_pills:
        header += f'<div style="margin-top:6px;font-size:0.75rem;color:#6b7280">inputs: {inp_pills}</div>'

    # ── skill-specific highlight ───────────────────────────────────────────────
    highlight = ""
    if skill == "planner":
        rationale = output.get("rationale", "")
        nodes_plan = output.get("nodes") or []
        if rationale:
            highlight = (f'<p style="margin:8px 0;font-size:0.82rem;color:#4338ca;'
                         f'font-style:italic">💭 {e(rationale)}</p>')
        if nodes_plan:
            rows = "".join(
                f'<tr>'
                f'<td style="padding:4px 8px">{skill_badge(n.get("skill","?"))}</td>'
                f'<td style="padding:4px 8px;font-size:0.75rem;color:#374151">'
                f'{e(", ".join(n.get("inputs", [])))}</td>'
                f'<td style="padding:4px 8px;font-size:0.75rem;color:#6b7280">'
                f'{e(str(n.get("metadata", {})))}</td>'
                f'</tr>'
                for n in nodes_plan
            )
            highlight += f"""
<div style="overflow-x:auto;margin-top:6px">
<table style="width:100%;border-collapse:collapse;font-size:0.8rem">
  <thead><tr style="background:#eef2ff">
    <th style="padding:4px 8px;text-align:left;color:#4f46e5">skill</th>
    <th style="padding:4px 8px;text-align:left;color:#4f46e5">inputs</th>
    <th style="padding:4px 8px;text-align:left;color:#4f46e5">metadata</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table></div>"""

    elif skill == "critic":
        verdict = output.get("verdict", "")
        rationale = output.get("rationale", "")
        vcolor = "#16a34a" if verdict == "pass" else "#dc2626"
        vbg    = "#dcfce7" if verdict == "pass" else "#fee2e2"
        highlight = (f'<div style="margin:8px 0;padding:8px 12px;background:{vbg};'
                     f'border-left:4px solid {vcolor};border-radius:4px">'
                     f'<span style="font-weight:700;color:{vcolor};font-size:0.85rem">'
                     f'Verdict: {e(verdict.upper())}</span>'
                     + (f'<p style="margin:4px 0 0;font-size:0.8rem;color:#374151">{e(rationale)}</p>' if rationale else "")
                     + '</div>')

    elif skill == "formatter":
        final = output.get("final_answer", "")
        if final:
            highlight = (f'<div style="margin:8px 0;padding:12px;background:#f0fdf4;'
                         f'border:1px solid #86efac;border-radius:6px">'
                         f'<div style="font-size:0.75rem;font-weight:600;color:#16a34a;'
                         f'margin-bottom:6px">✅ FINAL ANSWER</div>'
                         f'<pre style="margin:0;white-space:pre-wrap;word-break:break-word;'
                         f'font-size:0.82rem;color:#14532d;font-family:sans-serif">{e(final)}</pre></div>')

    elif skill == "researcher":
        findings = output.get("findings", "")
        question = output.get("question", "")
        sources  = output.get("sources") or []
        if question:
            highlight += (f'<p style="margin:6px 0;font-size:0.8rem;color:#0891b2">'
                          f'🔍 {e(question)}</p>')
        if sources:
            srcs = " · ".join(
                f'<a href="{e(s.get("url","#"))}" target="_blank" '
                f'style="color:#0891b2;font-size:0.72rem">{e(s.get("title") or s.get("url",""))}</a>'
                for s in sources[:5]
            )
            highlight += f'<div style="margin-top:4px">{srcs}</div>'
        if findings:
            highlight += collapsible("Findings", preblock(findings, 3000),
                                     open_=False, accent="#0891b2")

    elif skill == "distiller":
        fields = output.get("fields") or {}
        rationale = output.get("rationale", "")
        if fields:
            rows = "".join(
                f'<tr><td style="padding:3px 8px;font-weight:600;color:#92400e;'
                f'font-size:0.78rem;white-space:nowrap">{e(k)}</td>'
                f'<td style="padding:3px 8px;font-size:0.78rem;color:#374151">{e(str(v))}</td></tr>'
                for k, v in fields.items()
            )
            highlight = f"""
<div style="overflow-x:auto;margin-top:6px">
<table style="border-collapse:collapse;font-size:0.8rem">
  <tbody>{rows}</tbody>
</table></div>"""
        if rationale:
            highlight += (f'<p style="margin:6px 0 0;font-size:0.78rem;color:#78716c;'
                          f'font-style:italic">{e(rationale)}</p>')

    elif skill == "browser":
        content = output.get("content", "")
        err_code = output.get("error_code", "")
        path_used = output.get("path", "")
        final_url = output.get("final_url", "")
        if err_code:
            highlight = (f'<div style="padding:8px 12px;background:#fee2e2;border-left:4px solid #dc2626;'
                         f'border-radius:4px;font-size:0.8rem;color:#7f1d1d">'
                         f'⛔ {e(err_code)} — {e(output.get("reason",""))}</div>')
        else:
            meta_parts = []
            if path_used: meta_parts.append(f"layer: <b>{e(path_used)}</b>")
            if final_url: meta_parts.append(f'<a href="{e(final_url)}" target="_blank" style="color:#7c3aed">{e(final_url[:80])}</a>')
            if meta_parts:
                highlight = f'<p style="margin:4px 0;font-size:0.75rem;color:#6b7280">{" · ".join(meta_parts)}</p>'
            if content:
                highlight += collapsible("Page content", preblock(content, 3000),
                                         open_=False, accent="#7c3aed")

    # ── error block ───────────────────────────────────────────────────────────
    if error:
        highlight += (f'<div style="margin-top:8px;padding:8px 12px;background:#fef2f2;'
                      f'border-left:4px solid #dc2626;border-radius:4px;'
                      f'font-size:0.78rem;color:#7f1d1d;word-break:break-all">'
                      f'⚠ {e(error[:400])}</div>')

    # ── collapsibles ──────────────────────────────────────────────────────────
    details = ""
    details += collapsible("Prompt sent to LLM", preblock(prompt, 6000),
                            open_=False, accent="#6b7280")
    details += collapsible("Raw output JSON", json_block(output),
                            open_=False, accent="#374151")
    if successors:
        details += collapsible(f"Successors scheduled ({len(successors)})",
                               json_block(successors, 3000),
                               open_=False, accent="#4f46e5")

    return f"""
<div id="{e(nid.replace(':','-'))}"
     style="margin-bottom:16px;padding:14px 16px;background:{bg};
            border:1px solid {fg}33;border-radius:10px;
            border-left:4px solid {fg}">
  {header}
  {highlight}
  {details}
</div>"""


# ── session loader ─────────────────────────────────────────────────────────────

def load_session(sid: str) -> tuple[str, list[dict]]:
    session_dir = SESSIONS_DIR / sid
    nodes_dir   = session_dir / "nodes"
    if not nodes_dir.exists():
        raise FileNotFoundError(f"Session not found: {session_dir}")

    nodes = []
    for f in sorted(nodes_dir.glob("n_*.json")):
        try:
            nodes.append(json.loads(f.read_text()))
        except Exception as ex:
            print(f"  [warn] could not parse {f.name}: {ex}")

    query_file = session_dir / "query.txt"
    query = query_file.read_text().strip() if query_file.exists() else "(query not saved)"
    return query, nodes


# ── stats bar ─────────────────────────────────────────────────────────────────

def stats_bar(nodes: list[dict]) -> str:
    from collections import Counter
    skill_counts  = Counter(n["skill"]  for n in nodes)
    status_counts = Counter(n["status"] for n in nodes)
    total_elapsed = sum(
        (n.get("result") or {}).get("elapsed_s", 0) for n in nodes
    )
    providers = Counter(
        (n.get("result") or {}).get("provider", "") for n in nodes
        if (n.get("result") or {}).get("provider")
    )

    skill_pills = " ".join(
        f'{skill_badge(s)} <span style="font-size:0.75rem;color:#6b7280">×{c}</span>'
        for s, c in sorted(skill_counts.items())
    )
    status_pills = " ".join(
        f'{status_badge(st)} <span style="font-size:0.75rem;color:#6b7280">×{c}</span>'
        for st, c in sorted(status_counts.items())
    )
    prov_str = " · ".join(f"{p} ×{c}" for p, c in providers.most_common())

    return f"""
<div style="display:flex;flex-wrap:wrap;gap:16px;padding:14px 16px;
            background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;
            margin-bottom:20px;font-size:0.8rem">
  <div><b style="color:#374151">Nodes:</b> {len(nodes)}</div>
  <div><b style="color:#374151">Total time:</b> {total_elapsed:.1f}s</div>
  <div><b style="color:#374151">Providers:</b> {e(prov_str) or "—"}</div>
  <div style="width:100%"><b style="color:#374151">Skills: </b>{skill_pills}</div>
  <div style="width:100%"><b style="color:#374151">Status: </b>{status_pills}</div>
</div>"""


# ── nav sidebar links ──────────────────────────────────────────────────────────

def nav_links(nodes: list[dict]) -> str:
    fg_map = {s: SKILL_COLORS.get(s, ("#374151", "#f9fafb"))[0] for s in SKILL_COLORS}
    links = ""
    for n in nodes:
        nid   = n["node_id"]
        skill = n["skill"]
        status= n["status"]
        fg    = fg_map.get(skill, "#374151")
        icon  = STATUS_BADGE.get(status, ("?",)*3)[0]
        links += (f'<a href="#{e(nid.replace(":","-"))}" '
                  f'style="display:block;padding:4px 10px;text-decoration:none;'
                  f'color:{fg};font-size:0.78rem;border-left:3px solid {fg}33;'
                  f'margin-bottom:2px;white-space:nowrap" '
                  f'title="{e(skill)}">'
                  f'<code>{e(nid)}</code> {icon} {e(skill)}</a>')
    return links


# ── page assembly ──────────────────────────────────────────────────────────────

def build_html(sid: str, query: str, nodes: list[dict]) -> str:
    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    node_html    = "\n".join(render_node(n) for n in nodes)
    sidebar      = nav_links(nodes)
    stats        = stats_bar(nodes)

    # find final answer if formatter ran
    final_answer = ""
    for n in reversed(nodes):
        if n["skill"] == "formatter" and n["status"] == "complete":
            fa = (n.get("result") or {}).get("output", {}).get("final_answer", "")
            if fa:
                final_answer = fa
                break

    final_banner = ""
    if final_answer:
        final_banner = f"""
<div style="margin-bottom:24px;padding:16px;background:#f0fdf4;
            border:2px solid #86efac;border-radius:10px">
  <div style="font-size:0.8rem;font-weight:700;color:#16a34a;margin-bottom:8px">
    ✅ FINAL ANSWER
  </div>
  <pre style="margin:0;white-space:pre-wrap;word-break:break-word;
              font-size:0.88rem;color:#14532d;font-family:system-ui,sans-serif">
{e(final_answer)}</pre>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Session {e(sid)}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: system-ui, -apple-system, sans-serif;
          background: #f1f5f9; color: #1e293b; }}
  details > summary::marker {{ display: none; }}
  details[open] > summary > span:first-child {{ transform: rotate(90deg); display:inline-block; }}
  a {{ color: inherit; }}
  @media (max-width: 768px) {{
    #sidebar {{ display: none; }}
    #main {{ margin-left: 0 !important; }}
  }}
</style>
</head>
<body>

<!-- sidebar -->
<div id="sidebar" style="position:fixed;top:0;left:0;width:180px;height:100vh;
     overflow-y:auto;background:#fff;border-right:1px solid #e2e8f0;
     padding:16px 0;z-index:100">
  <div style="padding:0 10px 12px;font-size:0.7rem;font-weight:700;
              color:#94a3b8;text-transform:uppercase;letter-spacing:0.08em">
    Nodes
  </div>
  {sidebar}
</div>

<!-- main -->
<div id="main" style="margin-left:180px;padding:24px 28px;max-width:1100px">

  <!-- page header -->
  <div style="margin-bottom:20px">
    <div style="font-size:0.75rem;color:#94a3b8;margin-bottom:4px">
      Session Inspector · generated {e(generated_at)}
    </div>
    <h1 style="font-size:1.3rem;font-weight:700;color:#1e293b;margin-bottom:6px">
      {e(sid)}
    </h1>
    <div style="padding:10px 14px;background:#fff;border:1px solid #e2e8f0;
                border-radius:8px;font-size:0.85rem;color:#374151;line-height:1.5">
      <b>Query:</b> {e(query)}
    </div>
  </div>

  {stats}
  {final_banner}

  <!-- nodes -->
  {node_html}

</div>
</body>
</html>"""


# ── CLI ────────────────────────────────────────────────────────────────────────

def latest_session() -> str:
    sessions = sorted(SESSIONS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    if not sessions:
        raise RuntimeError("No sessions found.")
    return sessions[0].name


def main() -> None:
    if len(sys.argv) >= 2:
        sid = sys.argv[1]
    else:
        sid = latest_session()
        print(f"[report] no session id given — using latest: {sid}")

    print(f"[report] loading session {sid} …")
    query, nodes = load_session(sid)
    print(f"[report] {len(nodes)} nodes found")

    html_content = build_html(sid, query, nodes)
    out_path = LOGS_DIR / f"{sid}.html"
    out_path.write_text(html_content, encoding="utf-8")
    print(f"[report] written → {out_path}")
    print(f"[report] open in browser:  xdg-open '{out_path}'")


if __name__ == "__main__":
    main()
