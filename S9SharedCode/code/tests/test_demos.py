"""Tests for demos registry and MCP-exposed helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demos import get_cnc_browser_url, get_demo, get_hf_models_url, hf_models_url, list_demos


def test_list_demos_includes_hfmodels():
    names = list_demos()
    assert "hfmodels" in names
    assert "aitools" in names


def test_get_demo_hfmodels():
    d = get_demo("hfmodels")
    assert d["name"] == "hfmodels"
    assert "text-generation" in d["query"] or "text generation" in d["query"].lower()
    assert "browser_hint" in d
    assert d["browser_hint"]["url"] == "https://huggingface.co/models"
    assert "filter" in d["browser_hint"]["goal"].lower()


def test_get_demo_unknown_raises():
    try:
        get_demo("not-a-demo")
        assert False, "expected KeyError"
    except KeyError as e:
        assert "not-a-demo" in str(e)


def test_hf_models_url_prefiltered():
    url = hf_models_url()
    assert url.startswith("https://huggingface.co/models?")
    assert "pipeline_tag=text-generation" in url
    assert "sort=likes" in url


def test_get_hf_models_url_returns_goal():
    out = get_hf_models_url()
    assert out["url"] == "https://huggingface.co/models"
    assert "filter" in out["goal"].lower()
    assert out["pipeline_tag"] == "text-generation"
    assert "fallback_url" in out
    assert "pipeline_tag=text-generation" in out["fallback_url"]


def test_get_cnc_browser_url_sulekha():
    out = get_cnc_browser_url()
    assert "sulekha.com" in out["url"]
    assert "justdial" not in out["url"]
    assert "Extract" in out["distiller_question"] or "Extract" in out["goal"]


def test_get_demo_cnc_browser_hint():
    d = get_demo("cnc")
    assert "browser" in d["shape"]
    assert "sulekha.com" in d["browser_hint"]["url"]
