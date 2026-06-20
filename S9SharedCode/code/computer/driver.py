"""Computer drivers — Layer 2b (a11y) and Layer 3 (vision SoM) via cua-driver.

Enforces scan → act → verify: after every action the window is re-snapshotted
before the next action or turn proceeds.
"""
from __future__ import annotations

import asyncio
import base64
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from browser.client import V9Client
from browser.driver import ACTION_SCHEMA

from .client import CuaDriverClient
from .snapshot import DesktopSnapshot, marked_screenshot_data_url, parse_window_state

SYSTEM_PROMPT_VISION = (
    "You are a desktop automation agent. Each turn you receive a screenshot with "
    "numbered dashed boxes over interactive elements plus a text legend. Emit "
    "actions: click(mark), type(mark,value), key(value), scroll(direction), "
    "drag(from_x,from_y,to_x,to_y), wait(seconds), done(success,note). "
    "Verify progress toward the goal each turn."
)

SYSTEM_PROMPT_A11Y = (
    "You are a desktop automation agent. Each turn you receive ONLY the "
    "accessibility tree legend (no screenshot). Emit the same action vocabulary. "
    "Prefer element_index via `mark` over raw coordinates."
)


@dataclass
class StepRecord:
    turn: int
    thinking: str
    actions: list[dict]
    outcome: str
    provider: str = ""
    model: str = ""
    latency_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    verified: bool = True


@dataclass
class DriverConfig:
    goal: str
    pid: int
    window_id: int
    max_steps: int = 12
    max_failures: int = 3
    artifacts_dir: Optional[str] = None
    pause_between_steps: float = 0.5
    pause_before_llm_s: float = 4.5
    provider: Optional[str] = None
    model: Optional[str] = None


@dataclass
class DriverResult:
    success: bool
    note: str
    steps: list[StepRecord] = field(default_factory=list)
    extracted: str = ""
    actions: list[dict] = field(default_factory=list)
    turns: int = 0


class BaseComputerDriver:
    SYSTEM_PROMPT: str = ""
    LAYER_NAME: str = "base"

    def __init__(self, cua: CuaDriverClient, gateway: V9Client, config: DriverConfig):
        self.cua = cua
        self.gateway = gateway
        self.config = config
        self.steps: list[StepRecord] = []
        self._last_llm_end = 0.0
        self._last_scan: DesktopSnapshot | None = None

    async def _scan(self, *, capture_mode: str = "som") -> DesktopSnapshot:
        raw = await self.cua.get_window_state(
            self.config.pid,
            self.config.window_id,
            capture_mode=capture_mode,
        )
        snap = parse_window_state(raw)
        self._last_scan = snap
        return snap

    def _history_text(self) -> str:
        if not self.steps:
            return "(no actions yet)"
        lines = []
        for s in self.steps[-5:]:
            acts = ", ".join(
                f"{a['type']}({a.get('mark') or a.get('value', '')})"
                for a in s.actions[:3]
            )
            lines.append(f"turn {s.turn}: {acts} → {s.outcome}")
        return "\n".join(lines)

    async def _decide(self, snap: DesktopSnapshot, turn: int):
        raise NotImplementedError

    async def _dispatch_one(self, action: dict, snap: DesktopSnapshot) -> str:
        t = action.get("type")
        pid = self.config.pid
        wid = self.config.window_id
        if t == "click":
            mark = action.get("mark")
            if mark is not None:
                await self.cua.click(pid, window_id=wid, element_index=int(mark))
            else:
                await self.cua.click(
                    pid, window_id=wid,
                    x=float(action.get("x", 0)),
                    y=float(action.get("y", 0)),
                )
            return "ok"
        if t == "type":
            mark = action.get("mark")
            val = action.get("value", "")
            if mark is not None:
                await self.cua.click(pid, window_id=wid, element_index=int(mark))
            await self.cua.type_text(pid, val, window_id=wid)
            return "ok"
        if t == "key":
            val = str(action.get("value", "Enter"))
            norm = val.lower().replace("control", "ctrl").replace("command", "meta")
            if "+" in norm:
                await self.cua.hotkey(
                    pid, [p.strip() for p in norm.split("+") if p.strip()],
                    window_id=wid,
                )
            else:
                await self.cua.press_key(pid, norm, window_id=wid)
            return "ok"
        if t == "scroll":
            await self.cua.scroll(
                pid,
                direction=action.get("direction", "down"),
                amount=int(action.get("amount", 3)),
                window_id=wid,
            )
            return "ok"
        if t == "drag":
            await self.cua.drag(
                pid,
                float(action.get("from_x", 0)),
                float(action.get("from_y", 0)),
                float(action.get("to_x", 0)),
                float(action.get("to_y", 0)),
                window_id=wid,
            )
            return "ok"
        if t == "wait":
            await asyncio.sleep(float(action.get("seconds", 0.5)))
            return "ok"
        if t == "done":
            return "ok"
        return f"error: unknown action {t!r}"

    async def step(self, turn: int) -> tuple[bool, bool, str]:
        if turn > 1 and self.config.pause_before_llm_s > 0 and self._last_llm_end:
            wait = self.config.pause_before_llm_s - (time.monotonic() - self._last_llm_end)
            if wait > 0:
                await asyncio.sleep(wait)

        snap = await self._scan(capture_mode="ax" if self.LAYER_NAME == "a11y" else "som")
        parsed, result = await self._decide(snap, turn)
        self._last_llm_end = time.monotonic()

        if not parsed:
            rec = StepRecord(
                turn, "", [],
                f"error: parsed output missing; raw={result.text[:120]!r}",
                result.provider, result.model, result.latency_ms,
                result.input_tokens, result.output_tokens,
                verified=False,
            )
            self.steps.append(rec)
            return False, False, "no parsed output"

        thinking = parsed.get("thinking", "")
        actions = parsed.get("actions") or []
        outcomes: list[str] = []
        done_seen, success_seen, done_note = False, False, ""
        current_snap = snap

        for a in actions:
            if a.get("type") == "done":
                done_seen = True
                success_seen = bool(a.get("success", False))
                done_note = a.get("note", "")
                outcomes.append(f"done({success_seen})")
                break
            try:
                outcome = await self._dispatch_one(a, current_snap)
            except Exception as e:
                outcome = f"error: {type(e).__name__}: {e}"
            outcomes.append(outcome)
            if outcome.startswith("error"):
                break
            # verify after EVERY action — mandatory re-scan
            try:
                current_snap = await self._scan(
                    capture_mode="ax" if self.LAYER_NAME == "a11y" else "som",
                )
            except Exception as e:
                outcomes.append(f"verify_error: {e}")
                break
            await asyncio.sleep(self.config.pause_between_steps)

        rec = StepRecord(
            turn=turn, thinking=thinking, actions=actions,
            outcome=" | ".join(outcomes) or "ok",
            provider=result.provider, model=result.model,
            latency_ms=result.latency_ms,
            tokens_in=result.input_tokens, tokens_out=result.output_tokens,
            verified=not any(o.startswith("verify_error") for o in outcomes),
        )
        self.steps.append(rec)
        return done_seen, success_seen, done_note

    async def run(self) -> DriverResult:
        failures = 0
        for turn in range(1, self.config.max_steps + 1):
            print(f"    [computer/{self.LAYER_NAME}] turn {turn}/{self.config.max_steps}",
                  flush=True)
            done, success, note = await self.step(turn)
            if self.steps:
                last = self.steps[-1]
                if last.thinking:
                    print(f"      thinking: {last.thinking[:200]}", flush=True)
                acts = ", ".join(
                    f"{a.get('type')}({a.get('mark') or a.get('value', '')})"
                    for a in (last.actions or [])[:3]
                )
                if acts:
                    print(f"      actions: {acts} → {last.outcome[:80]}", flush=True)
            last = self.steps[-1]
            if "error" in last.outcome:
                failures += 1
                if failures >= self.config.max_failures:
                    return DriverResult(
                        False, f"giveup after {failures} consecutive failures",
                        steps=self.steps,
                    )
            else:
                failures = 0
            if done:
                extracted = ""
                if self._last_scan:
                    extracted = self._last_scan.tree_markdown
                return DriverResult(success, note, steps=self.steps, extracted=extracted)
        return DriverResult(False, f"step cap reached ({self.config.max_steps})", steps=self.steps)

    def _save_artifacts(self, turn: int, snap: DesktopSnapshot, *, marked: bytes | None = None):
        if not self.config.artifacts_dir:
            return
        d = Path(self.config.artifacts_dir)
        d.mkdir(parents=True, exist_ok=True)
        if snap.screenshot_png_b64:
            (d / f"turn_{turn:02d}_raw.png").write_bytes(
                base64.b64decode(snap.screenshot_png_b64),
            )
        if marked:
            (d / f"turn_{turn:02d}_marked.png").write_bytes(marked)
        (d / f"turn_{turn:02d}_legend.txt").write_text(snap.legend(), encoding="utf-8")


class A11yComputerDriver(BaseComputerDriver):
    SYSTEM_PROMPT = SYSTEM_PROMPT_A11Y
    LAYER_NAME = "a11y"

    async def _decide(self, snap: DesktopSnapshot, turn: int):
        self._save_artifacts(turn, snap)
        prompt = (
            f"GOAL: {self.config.goal}\n\n"
            f"INTERACTIVE ELEMENTS ({len(snap.elements)}):\n{snap.legend()}\n\n"
            f"TREE:\n{snap.tree_markdown[:4000]}\n\n"
            f"RECENT ACTIONS:\n{self._history_text()}\n\n"
            f"What is the next set of actions?"
        )
        result = await self.gateway.chat(
            prompt, system=self.SYSTEM_PROMPT,
            schema=ACTION_SCHEMA, schema_name="AgentOutput", max_tokens=1024,
            provider=self.config.provider, model=self.config.model,
        )
        return result.parsed, result


class VisionComputerDriver(BaseComputerDriver):
    SYSTEM_PROMPT = SYSTEM_PROMPT_VISION
    LAYER_NAME = "vision"

    async def _decide(self, snap: DesktopSnapshot, turn: int):
        data_url = marked_screenshot_data_url(snap)
        if not data_url:
            raise RuntimeError("vision layer requires screenshot from get_window_state")
        marked_bytes = base64.b64decode(data_url.split(",", 1)[1])
        self._save_artifacts(turn, snap, marked=marked_bytes)
        prompt = (
            f"GOAL: {self.config.goal}\n\n"
            f"VIEWPORT: {snap.viewport_w}x{snap.viewport_h}\n"
            f"INTERACTIVE ELEMENTS ({len(snap.elements)}):\n{snap.legend()}\n\n"
            f"RECENT ACTIONS:\n{self._history_text()}\n\n"
            f"What is the next set of actions?"
        )
        result = await self.gateway.vision(
            data_url, prompt, system=self.SYSTEM_PROMPT,
            schema=ACTION_SCHEMA, schema_name="AgentOutput", max_tokens=1024,
            provider=self.config.provider, model=self.config.model,
        )
        return result.parsed, result
