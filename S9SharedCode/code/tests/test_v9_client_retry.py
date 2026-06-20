"""V9Client retries transient 503s (gemini cooldown path)."""
from __future__ import annotations

import httpx
import pytest

from browser.client import V9Client


@pytest.mark.asyncio
async def test_post_json_retries_503_then_succeeds(monkeypatch):
    calls = {"n": 0}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json=None):
            calls["n"] += 1
            req = httpx.Request("POST", url, json=json)
            if calls["n"] < 2:
                return httpx.Response(503, request=req, json={"error": "cooldown"})
            return httpx.Response(200, request=req, json={
                "provider": "gemini",
                "model": "gemini-2.5-flash",
                "text": "ok",
                "parsed": None,
                "latency_ms": 1,
                "input_tokens": 1,
                "output_tokens": 1,
            })

    async def noop_sleep(_s):
        return None

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: FakeClient())
    monkeypatch.setattr("browser.client.asyncio.sleep", noop_sleep)

    out = await V9Client(base_url="http://gw")._post_json("/v1/chat", {"x": 1})
    assert out["text"] == "ok"
    assert calls["n"] == 2
