"""Session 10: Computer skill — cascade wrapper around cua-driver.

    Layer 1  — extract (AX tree, clipboard, files) — no LLM
    Layer 2a — deterministic workflows / hotkeys — no LLM
    Layer 2b — A11yComputerDriver (AX + /v1/chat)
    Layer 3  — VisionComputerDriver (SoM + /v1/vision)
    Electron — page/CDP read when metadata requests electron app

Integrated into the Session 8 DAG via skills.py dispatch (same pattern as browser).
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from browser.client import V9Client
from schemas import AgentResult, ComputerOutput, NodeSpec

from .client import CuaDriverClient, CuaDriverError
from .deterministic import (
    match_workflow,
    resolve_calculator_workflow,
    run_workflow,
    extract_calculator_display,
)
from .driver import A11yComputerDriver, DriverConfig, DriverResult, VisionComputerDriver
from .electron import extract_via_page, is_electron_app
from .extract_utils import ax_tree_text, goal_requires_interaction, is_useful_extract, read_clipboard, read_files
from .permissions import check_preconditions
from .target import resolve_target


class ComputerSkill:
    NAME = "computer"

    def __init__(
        self,
        *,
        gateway_url: str = "http://localhost:8109",
        agent_tag: str = "computer",
        a11y_provider_pin: str | None = "gemini",
        vision_provider_pin: str | None = "gemini",
        artifacts_root: str | None = None,
        max_steps_a11y: int = 12,
        max_steps_vision: int = 12,
        wall_clock_s: float = 120.0,
        session: str | None = None,
        cua: CuaDriverClient | None = None,
    ):
        self.gateway_url = gateway_url
        self.agent_tag = agent_tag
        self.a11y_provider_pin = a11y_provider_pin
        self.vision_provider_pin = vision_provider_pin
        self.artifacts_root = Path(artifacts_root) if artifacts_root else None
        self.max_steps_a11y = max_steps_a11y
        self.max_steps_vision = max_steps_vision
        self.wall_clock_s = wall_clock_s
        self.session = session
        self.cua = cua or CuaDriverClient(session=session)

    async def run(self, node: NodeSpec) -> AgentResult:
        goal = str(node.metadata.get("goal") or "complete the desktop task")
        app = str(node.metadata.get("app") or node.metadata.get("application") or "desktop")
        force_path = node.metadata.get("force_path")
        record = bool(node.metadata.get("record", True))
        electron_port = node.metadata.get("electron_debugging_port")
        if electron_port is not None:
            electron_port = int(electron_port)
        t0 = time.time()

        ok, reasons = await check_preconditions(self.cua)
        if not ok:
            return self._pack_error(
                app, goal, "precondition_blocked",
                "; ".join(reasons),
                elapsed=time.time() - t0,
            )

        try:
            pid, window_id, title = await resolve_target(self.cua, node.metadata)
        except (CuaDriverError, RuntimeError) as e:
            return self._pack_error(app, goal, "interaction_failed", str(e), elapsed=time.time() - t0)

        # Empty AX tree after activation → permission / accessibility blocked.
        if force_path not in ("deterministic", "electron") and not node.metadata.get("files"):
            try:
                probe = await self.cua.get_window_state(pid, window_id, capture_mode="ax")
                ec = int(probe.get("element_count") or 0)
                tree = ax_tree_text(probe)
                if ec == 0 and not tree.strip():
                    await self._stop_recording_safe()
                    return self._pack_error(
                        app, goal, "precondition_blocked",
                        "empty accessibility tree after window activation "
                        "(check AT-SPI, QT_ACCESSIBILITY=1, or app focus)",
                        elapsed=time.time() - t0,
                    )
            except CuaDriverError:
                pass

        gateway = V9Client(base_url=self.gateway_url, agent=self.agent_tag, session=self.session)
        artifacts_dir = (
            str(self.artifacts_root / f"computer_{int(t0)}")
            if self.artifacts_root else None
        )
        trajectory_dir: str | None = None
        if record and artifacts_dir:
            trajectory_dir = str(Path(artifacts_dir) / "trajectory")
            Path(trajectory_dir).mkdir(parents=True, exist_ok=True)
            try:
                await self.cua.start_recording(trajectory_dir)
            except CuaDriverError:
                trajectory_dir = None

        # ── Layer 1: extract (AX + clipboard + files) ───────────────────────
        skip_extract = bool(node.metadata.get("workflow")) or bool(node.metadata.get("launch"))
        if force_path not in ("deterministic", "a11y", "vision", "electron") and not skip_extract:
            parts: list[str] = []
            file_paths = node.metadata.get("files") or []
            if isinstance(file_paths, str):
                file_paths = [file_paths]
            file_content = read_files(list(file_paths)) if file_paths else ""
            if file_content:
                parts.append(file_content)
            if node.metadata.get("use_clipboard") or "clipboard" in goal.lower():
                clip = read_clipboard()
                if clip:
                    parts.append(f"[clipboard]\n{clip}")
            ax_state: dict = {}
            try:
                ax_state = await self.cua.get_window_state(
                    pid, window_id, capture_mode="ax",
                )
                parts.append(ax_tree_text(ax_state))
            except CuaDriverError:
                pass
            content = "\n\n".join(p for p in parts if p).strip()
            if is_useful_extract(
                content, goal,
                element_count=int(ax_state.get("element_count") or 0) if ax_state else None,
                from_files=bool(file_content) and not goal_requires_interaction(goal),
            ):
                await self._stop_recording_safe()
                return self._pack(
                    app, goal, "extract", turns=0, content=content,
                    pid=pid, window_id=window_id, trajectory_dir=trajectory_dir,
                    elapsed=time.time() - t0,
                )

        # ── Electron CDP read (when app is Electron) ────────────────────────
        if force_path not in ("deterministic", "a11y", "vision") and (
            is_electron_app(app, title) or force_path == "electron"
        ):
            try:
                text = await extract_via_page(
                    self.cua, pid=pid, window_id=window_id,
                    goal=goal,
                    electron_debugging_port=electron_port,
                )
                electron_ok = bool(text) and (
                    electron_port is not None
                    or "[explorer files]" in text.lower()
                    or force_path == "electron"
                )
                if electron_ok or is_useful_extract(
                    text, goal,
                    element_count=len(text.splitlines()) if text else 0,
                ):
                    await self._stop_recording_safe()
                    return self._pack(
                        app, goal, "electron", turns=0, content=text,
                        pid=pid, window_id=window_id, trajectory_dir=trajectory_dir,
                        elapsed=time.time() - t0,
                    )
                if force_path == "electron" or (electron_port and not text):
                    await self._stop_recording_safe()
                    return self._pack_error(
                        app, goal, "extraction_failed",
                        "electron page extract returned no usable text",
                        elapsed=time.time() - t0,
                    )
            except CuaDriverError:
                if force_path == "electron":
                    await self._stop_recording_safe()
                    return self._pack_error(
                        app, goal, "extraction_failed",
                        "electron page extract failed",
                        elapsed=time.time() - t0,
                    )

        # ── Layer 2a: deterministic workflows ───────────────────────────────
        workflow_key = str(node.metadata.get("workflow") or "")
        wf = None
        calc_expr: str | None = None
        if app.lower() == "calculator" or "calculator" in title.lower():
            wf, calc_expr = resolve_calculator_workflow(
                goal=goal, metadata=node.metadata, workflow_key=workflow_key,
            )
        if not wf:
            wf = match_workflow(app=app, title=title, workflow=workflow_key)
        if wf and force_path not in ("a11y", "vision", "electron") and not electron_port:
            try:
                actions = await run_workflow(self.cua, wf, pid=pid, window_id=window_id)
                verify = await self.cua.get_window_state(pid, window_id, capture_mode="ax")
                content = ax_tree_text(verify)
                if app.lower() == "calculator" or "calculator" in title.lower():
                    result = extract_calculator_display(content)
                    if result:
                        prefix = f"[calculator result] {result}"
                        if calc_expr:
                            prefix += f"  (expression: {calc_expr})"
                        content = f"{prefix}\n\n{content}"
                await self._stop_recording_safe()
                return self._pack(
                    app, goal, "deterministic", turns=len(actions),
                    content=content or None, actions=actions,
                    pid=pid, window_id=window_id, trajectory_dir=trajectory_dir,
                    elapsed=time.time() - t0,
                )
            except CuaDriverError as e:
                if force_path == "deterministic":
                    await self._stop_recording_safe()
                    return self._pack_error(
                        app, goal, "interaction_failed", str(e),
                        elapsed=time.time() - t0,
                    )

        # ── Layer 2b: a11y + LLM ────────────────────────────────────────────
        a11y_art = str(Path(artifacts_dir) / "a11y") if artifacts_dir else None
        if force_path == "vision":
            a11y_result = DriverResult(False, "skipped by force_path=vision")
        else:
            a11y_result = await self._drive(
                A11yComputerDriver, goal, pid, window_id, gateway, a11y_art,
                self.a11y_provider_pin, self.max_steps_a11y,
            )
        if a11y_result.success:
            await self._stop_recording_safe()
            content = await self._enrich_calculator_content(
                a11y_result.extracted, app, title, pid, window_id,
            )
            a11y_result.extracted = content
            return self._pack_driver(
                "a11y", app, goal, a11y_result,
                pid=pid, window_id=window_id, trajectory_dir=trajectory_dir,
                elapsed=time.time() - t0,
            )

        # ── Layer 3: vision SoM ───────────────────────────────────────────────
        vis_art = str(Path(artifacts_dir) / "vision") if artifacts_dir else None
        vis_result = await self._drive(
            VisionComputerDriver, goal, pid, window_id, gateway, vis_art,
            self.vision_provider_pin, self.max_steps_vision,
        )
        await self._stop_recording_safe()
        if vis_result.success:
            content = await self._enrich_calculator_content(
                vis_result.extracted, app, title, pid, window_id,
            )
            vis_result.extracted = content
            return self._pack_driver(
                "vision", app, goal, vis_result,
                pid=pid, window_id=window_id, trajectory_dir=trajectory_dir,
                elapsed=time.time() - t0,
            )

        last_err = vis_result.note or a11y_result.note or "all layers exhausted"
        return self._pack_error(
            app, goal, "interaction_failed",
            f"all layers exhausted; last: {last_err}",
            elapsed=time.time() - t0,
        )

    async def _stop_recording_safe(self) -> None:
        try:
            await self.cua.stop_recording()
        except CuaDriverError:
            pass

    async def replay_trajectory(self, directory: str) -> dict[str, Any]:
        return await self.cua.replay_trajectory(directory)

    async def _enrich_calculator_content(
        self,
        content: str | None,
        app: str,
        title: str,
        pid: int,
        window_id: int,
    ) -> str:
        """Append [calculator result] line when the display value is in AX markdown."""
        if not ("calculator" in app.lower() or "calculator" in (title or "").lower()):
            return content or ""
        text = content or ""
        if "[calculator result]" in text:
            return text
        result = extract_calculator_display(text)
        if not result:
            try:
                verify = await self.cua.get_window_state(
                    pid, window_id, capture_mode="ax",
                )
                ax = ax_tree_text(verify)
                result = extract_calculator_display(ax)
                if result and not text.strip():
                    text = ax
            except CuaDriverError:
                pass
        if result:
            return f"[calculator result] {result}\n\n{text}".strip()
        return text

    async def _drive(self, DriverCls, goal, pid, window_id, gateway, artifacts_dir,
                     provider_pin, max_steps) -> DriverResult:
        if artifacts_dir:
            Path(artifacts_dir).mkdir(parents=True, exist_ok=True)
        cfg = DriverConfig(
            goal=goal, pid=pid, window_id=window_id,
            max_steps=max_steps, max_failures=3,
            artifacts_dir=artifacts_dir, provider=provider_pin,
        )
        drv = DriverCls(self.cua, gateway, cfg)
        result = await drv.run()
        result.turns = len(drv.steps)
        result.actions = [
            {"turn": s.turn, "actions": s.actions, "outcome": s.outcome, "verified": s.verified}
            for s in drv.steps
        ]
        result.extracted = result.extracted or ""
        if not result.extracted and drv._last_scan:
            result.extracted = drv._last_scan.tree_markdown
        return result

    def _pack(self, app, goal, path, *, turns, content=None, actions=None,
              pid=None, window_id=None, trajectory_dir=None, elapsed=0.0) -> AgentResult:
        out = ComputerOutput(
            app=app, goal=goal, path=path, turns=turns,
            content=content, actions=actions or [],
            pid=pid, window_id=window_id, trajectory_dir=trajectory_dir,
        )
        return AgentResult(
            success=True, agent_name=self.NAME,
            output=out.model_dump(), elapsed_s=elapsed,
        )

    def _pack_driver(self, path, app, goal, drv_result, *, pid, window_id,
                     trajectory_dir, elapsed) -> AgentResult:
        out = ComputerOutput(
            app=app, goal=goal, path=path,
            turns=getattr(drv_result, "turns", 0) or 0,
            content=getattr(drv_result, "extracted", None) or None,
            actions=getattr(drv_result, "actions", []) or [],
            pid=pid, window_id=window_id, trajectory_dir=trajectory_dir,
        )
        return AgentResult(
            success=True, agent_name=self.NAME,
            output=out.model_dump(), elapsed_s=elapsed,
        )

    def _pack_error(self, app, goal, code, msg, *, elapsed=0.0) -> AgentResult:
        out = ComputerOutput(app=app or "", goal=goal, path="extract", turns=0)
        return AgentResult(
            success=False, agent_name=self.NAME,
            output=out.model_dump(), error=msg, error_code=code,
            elapsed_s=elapsed,
        )
