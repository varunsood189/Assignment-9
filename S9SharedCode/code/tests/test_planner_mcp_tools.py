"""Planner must not emit MCP tool names as graph skill nodes."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError

from schemas import NodeSpec
from skills import PLANNER_MCP_TOOLS, _normalize_planner_node


def test_planner_mcp_tool_names_filtered():
    nodes = [
        {"skill": "get_hf_models_url", "inputs": [], "metadata": {"label": "hf_url"}},
        {
            "skill": "browser",
            "inputs": [],
            "metadata": {
                "url": "https://huggingface.co/models?pipeline_tag=text-generation&sort=likes",
                "goal": "Extract top 3 models.",
            },
        },
        {
            "skill": "distiller",
            "inputs": ["n:b1"],
            "metadata": {"label": "d1", "question": "Extract fields."},
        },
        {"skill": "formatter", "inputs": ["USER_QUERY", "n:d1"], "metadata": {"label": "out"}},
    ]
    successors: list[NodeSpec] = []
    for s in nodes:
        if s.get("skill") in PLANNER_MCP_TOOLS:
            continue
        s = _normalize_planner_node(s)
        successors.append(NodeSpec.model_validate(s))

    assert len(successors) == 3
    assert successors[0].skill == "browser"
    assert successors[0].metadata.get("label") == "b1"
    assert "get_hf_models_url" not in {x.skill for x in successors}


def test_normalize_planner_node_adds_browser_label():
    s = _normalize_planner_node(
        {"skill": "browser", "inputs": [], "metadata": {"url": "https://example.com", "goal": "x"}}
    )
    assert s["metadata"]["label"] == "b1"
