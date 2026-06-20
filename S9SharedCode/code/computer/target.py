"""Resolve pid/window_id from planner metadata."""
from __future__ import annotations

import asyncio
import shlex
import subprocess
from typing import Any

from .client import CuaDriverClient
from .electron import launch_electron_with_cdp

_ELECTRON_TITLE_HINTS = {
    "vscode": ("Visual Studio Code", "Code -"),
    "cursor": ("Cursor",),
    "calculator": ("Calculator",),
    "slack": ("Slack",),
    "discord": ("Discord",),
    "notion": ("Notion",),
    "obsidian": ("Obsidian",),
}

_APP_LAUNCH_HINTS: dict[str, tuple[str, ...]] = {
    "calculator": ("Calculator", "org.gnome.Calculator", "gnome-calculator"),
    "vscode": ("Visual Studio Code", "code_code", "code"),
    "cursor": ("Cursor", "cursor"),
}


async def _find_launch_path(client: CuaDriverClient, app: str) -> str | None:
    out = await client.list_apps()
    app_l = app.lower()
    hints = _APP_LAUNCH_HINTS.get(app_l, (app,))
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


async def resolve_target(
    client: CuaDriverClient,
    metadata: dict[str, Any],
) -> tuple[int, int, str]:
    """Return (pid, window_id, title). Launches app when metadata.launch is true."""
    app = str(metadata.get("app") or metadata.get("application") or "").strip()
    title_q = str(metadata.get("window_title") or metadata.get("title") or "").strip()
    launch = bool(metadata.get("launch", False))
    electron_port = metadata.get("electron_debugging_port")
    open_path = metadata.get("open_path") or metadata.get("folder")
    launch_path = metadata.get("launch_path")

    if launch and bool(metadata.get("kill_existing")) and app and electron_port is None:
        for entry in await client.list_apps():
            name = str(entry.get("name") or "").lower()
            if app.lower() in name and entry.get("pid"):
                try:
                    await client.kill_app(int(entry["pid"]))
                except Exception:
                    pass
        await asyncio.sleep(0.5)

    if launch and electron_port is not None and app:
        await launch_electron_with_cdp(
            client,
            app=app,
            port=int(electron_port),
            open_path=str(open_path) if open_path else None,
            kill_existing=bool(metadata.get("kill_existing", True)),
        )
    elif launch and app:
        if not launch_path and app.lower() == "calculator":
            launch_path = "gnome-calculator --mode=basic"
        if not launch_path:
            launch_path = await _find_launch_path(client, app)
        if launch_path and (" " in str(launch_path) or "--" in str(launch_path)):
            cmd = " ".join(shlex.quote(p) for p in shlex.split(str(launch_path)))
            subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif launch_path:
            await client.launch_app(launch_path=str(launch_path))
        else:
            await client.launch_app(name=app)
        await asyncio.sleep(2.0)

    windows = await client.list_windows()
    candidates = list(windows)

    if title_q:
        for w in candidates:
            if title_q.lower() in (w.get("title") or "").lower():
                pid, wid = int(w["pid"]), int(w["window_id"])
                await _activate(client, pid, wid)
                return pid, wid, str(w.get("title") or "")

    if app:
        hints = _ELECTRON_TITLE_HINTS.get(app.lower(), (app,))
        for hint in hints:
            for w in candidates:
                if hint.lower() in (w.get("title") or "").lower():
                    pid, wid = int(w["pid"]), int(w["window_id"])
                    await _activate(client, pid, wid)
                    return pid, wid, str(w.get("title") or "")

    if candidates:
        w = candidates[0]
        pid, wid = int(w["pid"]), int(w["window_id"])
        await _activate(client, pid, wid)
        return pid, wid, str(w.get("title") or "")

    raise RuntimeError("no target window found; set metadata.app or metadata.window_title")


async def _activate(client: CuaDriverClient, pid: int, window_id: int) -> None:
    try:
        await client.bring_to_front(pid, window_id=window_id)
        await asyncio.sleep(0.3)
    except Exception:
        pass
