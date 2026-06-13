"""Critic input expansion and critic-fail recovery wiring."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from recovery import handle_critic_verdict
from schemas import AgentResult
from skills import _expand_critic_inputs


def test_expand_critic_inputs_includes_distiller_upstream():
    graph_nodes = {
        "n:2": {"skill": "browser", "inputs": [], "status": "complete",
                "result": {"output": {"content": "model data"}}},
        "n:3": {"skill": "distiller", "inputs": ["n:2"], "status": "complete",
                "result": {"output": {"fields": {}}}},
    }
    out = _expand_critic_inputs(["USER_QUERY", "n:3"], graph_nodes)
    assert out == ["USER_QUERY", "n:3", "n:2"]


class _StubGraph:
    def __init__(self):
        from networkx import DiGraph
        self.g = DiGraph()
        self._added = []
        self._counter = 0

    def mark(self, nid, status):
        self.g.nodes[nid]["status"] = status

    def add_node(self, skill, inputs, metadata=None):
        self._counter += 1
        nid = f"n:rec{self._counter}"
        self.g.add_node(nid, skill=skill, inputs=list(inputs),
                        metadata=dict(metadata or {}), status="pending")
        self._added.append((nid, skill, list(inputs), dict(metadata or {})))
        return nid


def test_critic_fail_recovery_includes_browser_upstream():
    g = _StubGraph()
    g.g.add_node("n:2", skill="browser", inputs=[], status="complete", metadata={})
    g.g.add_node("n:3", skill="distiller", inputs=["n:2"], status="complete", metadata={})
    g.g.add_node("n:c", skill="critic", inputs=["USER_QUERY", "n:3"], status="complete",
                 metadata={"target": "n:3", "child": "n:f"})
    g.g.add_node("n:f", skill="formatter", inputs=["n:3"], status="pending", metadata={})
    g.g.add_edge("n:3", "n:c")
    g.g.add_edge("n:c", "n:f")

    handle_critic_verdict(
        "n:c",
        AgentResult(success=True, agent_name="critic",
                    output={"verdict": "fail", "rationale": "test"}),
        g, {}, [],
    )
    assert g._added
    _, _, inputs, _ = g._added[0]
    assert "USER_QUERY" in inputs
    assert "n:3" in inputs
    assert "n:2" in inputs
