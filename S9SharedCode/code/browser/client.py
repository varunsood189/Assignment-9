"""Framework-free client for llm_gatewayV9.

Plain httpx — no LangChain, no provider SDKs. The shipped Browser skill
talks to the gateway over HTTP, the same way every other S-session skill
does. Provider rotation, retries, agent tagging are the gateway's job.

Two methods: `vision()` hits /v1/vision for Layer-3 set-of-marks calls,
`chat()` hits /v1/chat for Layer-2b a11y-text calls (no image, cheaper,
doesn't require a vision-capable provider). `cost_by_agent()` queries the
gateway's V8 ledger so tests can pull real numbers.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Optional

import httpx

# Gemini (the default browser pin) enforces a 4s inter-call cooldown in the
# gateway router. Multi-turn browser runs fire one /v1/chat per turn with
# only ~0.5s between the click and the next LLM call — turn 4 routinely
# hits 503 before the cooldown clears unless we pace or retry client-side.
_RETRYABLE_STATUS = frozenset({429, 502, 503, 504})
_MAX_POST_ATTEMPTS = 8
_COOLDOWN_SLEEP_S = 4.5


@dataclass
class GatewayResult:
    """Normalised reply from either /v1/vision or /v1/chat."""
    parsed: dict | None
    text: str
    provider: str
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int


# Back-compat alias — the early SoM driver imports `VisionResult`.
VisionResult = GatewayResult


class V9Client:
    """One client, two methods: vision() and chat(). Both speak to V9."""
    def __init__(
        self,
        base_url: str = "http://localhost:8109",
        agent: str = "s9_browser",
        timeout: float = 120.0,
        session: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.agent = agent
        self.timeout = timeout
        # Default session tag for ledger attribution. Per-call overrides win.
        self.session = session

    async def _post_json(self, path: str, body: dict[str, Any]) -> dict:
        """POST with retries on gateway rate-limit / transient 503s."""
        url = f"{self.base_url}{path}"
        last_exc: Exception | None = None
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            for attempt in range(_MAX_POST_ATTEMPTS):
                try:
                    r = await c.post(url, json=body)
                    if r.status_code in _RETRYABLE_STATUS:
                        if attempt >= _MAX_POST_ATTEMPTS - 1:
                            r.raise_for_status()
                        wait = _COOLDOWN_SLEEP_S if r.status_code == 503 else min(2.0 * (2 ** attempt), 10.0)
                        await asyncio.sleep(wait)
                        continue
                    r.raise_for_status()
                    return r.json()
                except httpx.HTTPStatusError as e:
                    last_exc = e
                    code = e.response.status_code
                    if code in _RETRYABLE_STATUS and attempt < _MAX_POST_ATTEMPTS - 1:
                        wait = _COOLDOWN_SLEEP_S if code == 503 else min(2.0 * (2 ** attempt), 10.0)
                        await asyncio.sleep(wait)
                        continue
                    raise
        if last_exc:
            raise last_exc
        raise RuntimeError(f"POST {path} failed after {_MAX_POST_ATTEMPTS} attempts")

    @staticmethod
    def _normalise(d: dict) -> GatewayResult:
        return GatewayResult(
            parsed=d.get("parsed"),
            text=d.get("text") or "",
            provider=d.get("provider", ""),
            model=d.get("model", ""),
            latency_ms=int(d.get("latency_ms") or 0),
            input_tokens=int(d.get("input_tokens") or 0),
            output_tokens=int(d.get("output_tokens") or 0),
        )

    async def vision(
        self,
        image_data_url: str,
        prompt: str,
        *,
        schema: Optional[dict] = None,
        schema_name: str = "out",
        system: Optional[str] = None,
        max_tokens: int = 1024,
        session: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> GatewayResult:
        body: dict[str, Any] = {
            "image": image_data_url,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": 0.0,
            "agent": self.agent,
        }
        if schema:        body["schema"] = schema
        if schema:        body["schema_name"] = schema_name
        if system:        body["system"] = system
        s = session or self.session
        if s:             body["session"] = s
        if model:         body["model"] = model
        if provider:      body["provider"] = provider

        return self._normalise(await self._post_json("/v1/vision", body))

    async def chat(
        self,
        prompt: str,
        *,
        schema: Optional[dict] = None,
        schema_name: str = "out",
        system: Optional[str] = None,
        max_tokens: int = 1024,
        session: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> GatewayResult:
        """Plain text-only call. Used by the Layer-2b a11y driver: legend +
        goal in, action JSON out. Skipping the image cuts ~1K input tokens
        per turn vs vision()."""
        body: dict[str, Any] = {
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.0,
            "agent": self.agent,
        }
        if schema:
            body["response_format"] = {
                "type": "json_schema", "schema": schema,
                "name": schema_name, "strict": True,
            }
        if system:    body["system"] = system
        s = session or self.session
        if s:         body["session"] = s
        if model:     body["model"] = model
        if provider:  body["provider"] = provider

        return self._normalise(await self._post_json("/v1/chat", body))

    async def cost_by_agent(self, agent: Optional[str] = None,
                            session: Optional[str] = None) -> dict:
        """Pull the V9 ledger for this agent/session — tests use it to
        report real numbers rather than wall-clock estimates."""
        params: dict[str, Any] = {}
        if agent:   params["agent"] = agent
        if session: params["session"] = session
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.get(f"{self.base_url}/v1/cost/by_agent", params=params)
            r.raise_for_status()
            return r.json()


# Back-compat alias.
V9VisionClient = V9Client
