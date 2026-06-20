"""Electron / Chromium CDP path via cua-driver `page` tool."""
from __future__ import annotations

import asyncio
import shlex
import subprocess
import urllib.error
import urllib.request
from typing import Any

from .client import CuaDriverClient, CuaDriverError

# Title substrings for supported Electron apps (metadata.app may override).
_ELECTRON_APPS: dict[str, tuple[str, ...]] = {
    "vscode": ("Visual Studio Code", "Code"),
    "cursor": ("Cursor",),
    "slack": ("Slack",),
    "discord": ("Discord",),
    "notion": ("Notion",),
    "obsidian": ("Obsidian",),
}

# App id → list_apps name / bundle_id hints for launch_path lookup.
_APP_LOOKUP: dict[str, tuple[str, ...]] = {
    "vscode": ("Visual Studio Code", "code_code", "code"),
    "cursor": ("Cursor", "cursor"),
    "slack": ("Slack", "slack"),
    "discord": ("Discord", "discord"),
    "notion": ("Notion", "notion"),
    "obsidian": ("Obsidian", "obsidian"),
}

_EXPLORER_JS = """
(() => {
  const seen = new Set();
  const names = [];
  const push = (t) => {
    t = (t || '').trim().replace(/\\s+/g, ' ');
    if (!t || seen.has(t) || t.length > 120) return;
    if (t === 'Outline' || t === 'Timeline' || t === 'Timeline Section') return;
    seen.add(t);
    names.push(t);
  };

  // Expand collapsed workspace folders so child entries appear in the DOM.
  for (const twistie of document.querySelectorAll(
    '.explorer-folders-view .monaco-tl-twistie.collapsed'
  )) {
    try { twistie.click(); } catch (e) {}
  }

  const rows = document.querySelectorAll('.explorer-folders-view .monaco-list-row');
  for (const row of rows) {
    const label = row.querySelector(
      '.monaco-icon-label, .label-name, .explorer-item .label-name'
    );
    if (label) push(label.textContent);
    else {
      const line = (row.textContent || '').trim().split('\\n')[0];
      push(line);
    }
    if (names.length >= 10) break;
  }

  if (names.length < 3) {
    for (const el of document.querySelectorAll(
      '.explorer-folders-view .monaco-icon-label, [data-testid="tree-item"]'
    )) {
      push(el.textContent);
      if (names.length >= 10) break;
    }
  }

  // If only the workspace root is visible, return it plus any open-editor tabs.
  if (names.length < 3) {
    for (const el of document.querySelectorAll('.open-editor .monaco-icon-label')) {
      push(el.textContent);
      if (names.length >= 10) break;
    }
  }

  return names.join('\\n');
})()
"""


def is_electron_app(app: str, title: str = "") -> bool:
    key = app.lower().strip()
    if key in _ELECTRON_APPS:
        return True
    t = title.lower()
    return any(any(p.lower() in t for p in patterns) for patterns in _ELECTRON_APPS.values())


async def _find_launch_path(client: CuaDriverClient, app: str) -> str | None:
    out = await client.list_apps()
    app_l = app.lower()
    hints = _APP_LOOKUP.get(app_l, (app,))
    for entry in out:
        name = str(entry.get("name") or "").lower()
        bundle = str(entry.get("bundle_id") or "").lower()
        for hint in hints:
            h = hint.lower()
            if h in name or h == bundle or h in bundle:
                lp = entry.get("launch_path")
                if lp:
                    return str(lp)
    return None


def _split_launch_command(launch_path: str) -> list[str]:
    return shlex.split(launch_path.strip())


async def _wait_for_cdp(port: int, *, timeout_s: float = 20.0) -> None:
    url = f"http://127.0.0.1:{port}/json/version"
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, OSError):
            await asyncio.sleep(0.5)
    raise CuaDriverError(f"CDP port {port} did not become ready within {timeout_s}s")


async def launch_electron_with_cdp(
    client: CuaDriverClient,
    *,
    app: str,
    port: int,
    open_path: str | None = None,
    kill_existing: bool = False,
) -> None:
    """Relaunch an Electron app with --remote-debugging-port and wire the daemon CDP env."""
    await client.ensure_cdp_port(port)

    launch_path = await _find_launch_path(client, app)
    if not launch_path:
        raise CuaDriverError(f"no launch_path for app {app!r}; install it or set metadata.launch_path")

    if kill_existing:
        out = await client.list_apps()
        app_l = app.lower()
        hints = _APP_LOOKUP.get(app_l, (app,))
        for entry in out:
            name = str(entry.get("name") or "").lower()
            bundle = str(entry.get("bundle_id") or "").lower()
            if any(h.lower() in name or h.lower() == bundle for h in hints):
                if entry.get("pid"):
                    try:
                        await client.kill_app(int(entry["pid"]))
                    except CuaDriverError:
                        pass
        await asyncio.sleep(1.0)

    parts = _split_launch_command(launch_path) + [f"--remote-debugging-port={port}"]
    if open_path:
        parts.append(open_path)
    cmd = " ".join(shlex.quote(p) for p in parts)
    subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    await _wait_for_cdp(port)
    await asyncio.sleep(3.0)


def _parse_page_output(out: dict[str, Any]) -> str:
    """Normalize cua-driver page tool JSON (result, text, or message field)."""
    for key in ("result", "text"):
        val = out.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    msg = str(out.get("message") or "").strip()
    if "cdp.runtime.evaluate.user_gesture:" in msg:
        payload = msg.split(":", 1)[-1].strip()
        if payload.startswith('"') and payload.endswith('"'):
            payload = payload[1:-1]
        return payload
    return msg


async def extract_via_page(
    client: CuaDriverClient,
    *,
    pid: int,
    window_id: int,
    goal: str = "",
    electron_debugging_port: int | None = None,
) -> str:
    """Layer-1-style read through CDP when the target is an Electron shell."""
    if electron_debugging_port:
        await client.ensure_cdp_port(electron_debugging_port)

    goal_l = goal.lower()
    if any(k in goal_l for k in ("sidebar", "explorer", "file", "list")):
        out = await client.page(
            "execute_javascript",
            pid,
            window_id=window_id,
            javascript=_EXPLORER_JS,
        )
        text = _parse_page_output(out)
        if text:
            return f"[explorer files]\n{text}"

    out = await client.page("get_text", pid, window_id=window_id)
    text = _parse_page_output(out)
    if text and not text.startswith("frame "):
        return text

    if electron_debugging_port:
        out = await client.page(
            "execute_javascript",
            pid,
            window_id=window_id,
            javascript="document.body ? document.body.innerText.slice(0, 4000) : ''",
        )
        return _parse_page_output(out)
    return text


async def query_dom(
    client: CuaDriverClient,
    *,
    pid: int,
    window_id: int,
    css_selector: str,
    electron_debugging_port: int | None = None,
) -> list[dict[str, Any]]:
    if electron_debugging_port:
        await client.ensure_cdp_port(electron_debugging_port)
    out = await client.page(
        "query_dom",
        pid,
        window_id=window_id,
        css_selector=css_selector,
    )
    return list(out.get("elements") or out.get("results") or [])
