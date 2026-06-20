"""Subprocess client for the real `cua-driver` CLI (no mocks).

Every tool maps to: `cua-driver call <tool_name> '<json>'`
Daemon lifecycle: `cua-driver serve` / `cua-driver status` / `cua-driver stop`
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from typing import Any

_CUA_BIN = shutil.which("cua-driver") or "cua-driver"


class CuaDriverError(RuntimeError):
    """Raised when cua-driver is missing or a tool call fails."""


class CuaDriverClient:
    """Thin async wrapper around the cua-driver CLI."""

    def __init__(self, *, binary: str | None = None, session: str | None = None):
        self.binary = binary or _CUA_BIN
        self.session = session

    def _require_binary(self) -> None:
        if not shutil.which(self.binary) and self.binary == _CUA_BIN:
            raise CuaDriverError(
                "cua-driver not found on PATH. Install from "
                "https://cua.ai/docs/cua-driver/guide/getting-started/installation "
                "then verify with: cua-driver --version"
            )

    async def call(self, tool: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        self._require_binary()
        payload = dict(args or {})
        if self.session and "session" not in payload:
            payload["session"] = self.session
        cmd = [self.binary, "call", tool, json.dumps(payload)]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_b, stderr_b = await proc.communicate()
        stdout = stdout_b.decode(errors="replace").strip()
        stderr = stderr_b.decode(errors="replace").strip()
        if proc.returncode != 0:
            raise CuaDriverError(stderr or stdout or f"cua-driver call {tool} failed")
        if not stdout:
            return {}
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            # Some tools (e.g. launch_app on Linux) emit human-readable text.
            return {"message": stdout, "ok": True}

    def status_text(self) -> str:
        self._require_binary()
        cp = subprocess.run(
            [self.binary, "status"],
            capture_output=True,
            text=True,
            check=False,
        )
        return (cp.stdout or cp.stderr or "").strip()

    async def ensure_daemon(self) -> None:
        """Start the background daemon when `cua-driver status` reports it down."""
        self._require_binary()
        if "not running" not in self.status_text().lower():
            return
        subprocess.Popen(
            [self.binary, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(30):
            await asyncio.sleep(0.5)
            if "not running" not in self.status_text().lower():
                return
        raise CuaDriverError("cua-driver daemon failed to start within 15s")

    async def health_check(self) -> dict[str, Any]:
        await self.ensure_daemon()
        return await self.call("check_permissions")

    async def list_windows(self) -> list[dict[str, Any]]:
        out = await self.call("list_windows")
        return list(out.get("windows") or [])

    async def get_window_state(
        self,
        pid: int,
        window_id: int,
        *,
        capture_mode: str = "som",
        query: str | None = None,
    ) -> dict[str, Any]:
        args: dict[str, Any] = {
            "pid": pid,
            "window_id": window_id,
            "capture_mode": capture_mode,
        }
        if query:
            args["query"] = query
        return await self.call("get_window_state", args)

    async def click(self, pid: int, *, window_id: int | None = None,
                    element_index: int | None = None,
                    x: float | None = None, y: float | None = None) -> dict[str, Any]:
        args: dict[str, Any] = {"pid": pid}
        if window_id is not None:
            args["window_id"] = window_id
        if element_index is not None:
            args["element_index"] = element_index
        if x is not None:
            args["x"] = x
        if y is not None:
            args["y"] = y
        return await self.call("click", args)

    async def type_text(self, pid: int, text: str, *, window_id: int | None = None) -> dict[str, Any]:
        args: dict[str, Any] = {"pid": pid, "text": text}
        if window_id is not None:
            args["window_id"] = window_id
        return await self.call("type_text", args)

    async def press_key(self, pid: int, key: str, *, window_id: int | None = None) -> dict[str, Any]:
        args: dict[str, Any] = {"pid": pid, "key": key}
        if window_id is not None:
            args["window_id"] = window_id
        return await self.call("press_key", args)

    async def hotkey(self, pid: int, keys: list[str], *, window_id: int | None = None) -> dict[str, Any]:
        args: dict[str, Any] = {"pid": pid, "keys": keys}
        if window_id is not None:
            args["window_id"] = window_id
        return await self.call("hotkey", args)

    async def scroll(self, pid: int, *, direction: str = "down", amount: int = 3,
                     window_id: int | None = None) -> dict[str, Any]:
        args: dict[str, Any] = {"pid": pid, "direction": direction, "amount": amount}
        if window_id is not None:
            args["window_id"] = window_id
        return await self.call("scroll", args)

    async def drag(self, pid: int, from_x: float, from_y: float,
                   to_x: float, to_y: float, *, window_id: int | None = None) -> dict[str, Any]:
        args: dict[str, Any] = {
            "pid": pid,
            "from_x": from_x,
            "from_y": from_y,
            "to_x": to_x,
            "to_y": to_y,
        }
        if window_id is not None:
            args["window_id"] = window_id
        return await self.call("drag", args)

    async def launch_app(self, *, name: str | None = None,
                         launch_path: str | None = None,
                         urls: list[str] | None = None) -> dict[str, Any]:
        args: dict[str, Any] = {}
        if launch_path:
            args["launch_path"] = launch_path
        elif name:
            args["name"] = name
        if urls:
            args["urls"] = urls
        return await self.call("launch_app", args)

    async def list_apps(self) -> list[dict[str, Any]]:
        out = await self.call("list_apps")
        return list(out.get("apps") or [])

    async def bring_to_front(self, pid: int, *, window_id: int | None = None) -> dict[str, Any]:
        args: dict[str, Any] = {"pid": pid}
        if window_id is not None:
            args["window_id"] = window_id
        return await self.call("bring_to_front", args)

    async def kill_app(self, pid: int) -> dict[str, Any]:
        return await self.call("kill_app", {"pid": pid})

    async def ensure_cdp_port(self, port: int) -> None:
        """Restart the daemon with CUA_DRIVER_CDP_PORT so Linux CDP page actions work."""
        self._require_binary()
        subprocess.run(
            [self.binary, "stop"],
            capture_output=True,
            text=True,
            check=False,
        )
        env = os.environ.copy()
        env["CUA_DRIVER_CDP_PORT"] = str(port)
        subprocess.Popen(
            [self.binary, "serve"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(30):
            await asyncio.sleep(0.5)
            if "not running" not in self.status_text().lower():
                return
        raise CuaDriverError(f"cua-driver daemon failed to restart with CDP port {port}")

    async def page(self, action: str, pid: int, *, window_id: int | None = None,
                   javascript: str | None = None, css_selector: str | None = None,
                   selector: str | None = None,
                   remote_debugging_port: int | None = None) -> dict[str, Any]:
        args: dict[str, Any] = {"action": action, "pid": pid}
        if window_id is not None:
            args["window_id"] = window_id
        if javascript is not None:
            args["javascript"] = javascript
        if css_selector is not None:
            args["css_selector"] = css_selector
        if selector is not None:
            args["selector"] = selector
        if remote_debugging_port is not None:
            args["remote_debugging_port"] = remote_debugging_port
        return await self.call("page", args)

    async def start_recording(self, output_dir: str, *, record_video: bool = False) -> dict[str, Any]:
        return await self.call("start_recording", {
            "output_dir": output_dir,
            "record_video": record_video,
        })

    async def stop_recording(self) -> dict[str, Any]:
        return await self.call("stop_recording")

    async def replay_trajectory(self, directory: str, *, delay_ms: int = 500,
                                stop_on_error: bool = True) -> dict[str, Any]:
        return await self.call("replay_trajectory", {
            "dir": directory,
            "delay_ms": delay_ms,
            "stop_on_error": stop_on_error,
        })

    async def start_session(self, session_id: str) -> dict[str, Any]:
        return await self.call("start_session", {"session": session_id})

    async def end_session(self, session_id: str) -> dict[str, Any]:
        return await self.call("end_session", {"session": session_id})
