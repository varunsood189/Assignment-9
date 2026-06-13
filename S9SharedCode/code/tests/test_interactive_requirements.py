"""Tests for 3+ visible browser action requirement helpers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_parent = _root.parent
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))

_spec = importlib.util.spec_from_file_location(
    "extract_utils", _root / "browser" / "extract_utils.py")
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)

from replay_viewer import count_interactive_browser_actions  # noqa: E402


def test_interactive_goal_blocks_extract() -> None:
    content = "x" * 500
    goal = "Filter Tasks=Text Generation, Sort=Most Likes; extract top 3 cards."
    assert not _mod.is_useful_extract(content, goal, url="https://huggingface.co/models?sort=likes")


def test_base_hf_url_blocks_extract() -> None:
    content = "deepseek-ai/DeepSeek-R1\nmeta-llama/Llama-3.1-8B\nmistralai/Mistral-7B\n" * 20
    goal = "Extract the top 3 model cards."
    assert not _mod.is_useful_extract(content, goal, url="https://huggingface.co/models")


def test_normalize_url_strips_prefilter_when_interactive() -> None:
    url = "https://huggingface.co/models?pipeline_tag=text-generation&sort=likes"
    goal = "Filter Tasks=Text Generation and sort by likes."
    assert _mod.normalize_url_for_goal(url, goal) == "https://huggingface.co/models"


def test_latest_sid_ignores_index_html(tmp_path, monkeypatch) -> None:
    import replay_viewer as rv

    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "index.html").write_text("<html></html>", encoding="utf-8")
    old = sessions / "s9-deadbeef"
    old.mkdir()
    (old / "query.txt").write_text("test query", encoding="utf-8")
    nodes = old / "nodes"
    nodes.mkdir()
    (nodes / "n_001.json").write_text('{"node_id":"n:1","skill":"planner","status":"complete"}')

    monkeypatch.setattr(rv, "SESSIONS_DIR", sessions)
    assert rv.latest_sid() == "s9-deadbeef"


def test_count_interactive_browser_actions() -> None:
    nodes = [{
        "skill": "browser",
        "result": {
            "output": {
                "actions": [
                    {"turn": 1, "actions": [{"type": "click", "mark": 1}]},
                    {"turn": 2, "actions": [{"type": "click", "mark": 2}]},
                    {"turn": 3, "actions": [{"type": "done", "success": True}]},
                ],
            },
        },
    }]
    assert count_interactive_browser_actions(nodes) == 2
