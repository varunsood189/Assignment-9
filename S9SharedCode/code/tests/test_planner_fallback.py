"""Planner fallback when model returns empty JSON on CNC recovery."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from skills import _planner_fallback_plan


def test_planner_fallback_cnc_after_justdial_fail():
    q = (
        "Compare 5 CNC and VMC operator training institutes in Bangalore. "
        "For each institute give the name, location, course duration, "
        "approximate fees, and whether they offer placement support."
    )
    fr = (
        "node=n:2 skill=browser reason=upstream_failure error="
        "ERR_HTTP2_PROTOCOL_ERROR at https://www.justdial.com/..."
    )
    plan = _planner_fallback_plan(q, fr)
    assert plan is not None
    nodes = plan["nodes"]
    assert nodes[0]["skill"] == "browser"
    assert "sulekha.com" in nodes[0]["metadata"]["url"]
    assert len(nodes) == 3


def test_planner_fallback_laptops():
    q = (
        "Compare 3 popular laptops available in India under ₹80,000. "
        "For each laptop give the model name, key specs (CPU, RAM, storage, "
        "display), price in INR, and one-line verdict on who it is best for."
    )
    plan = _planner_fallback_plan(q, None)
    assert plan is not None
    nodes = plan["nodes"]
    assert len(nodes) == 4
    assert [n["skill"] for n in nodes[:3]] == ["researcher"] * 3
    assert nodes[3]["skill"] == "formatter"


def test_planner_fallback_critic_distiller():
    fr = (
        "critic failed target=n:3 child=n:4 rationale=The distiller incorrectly "
        "extracted the likes for Llama-3.1-8B-Instruct as '9'..."
    )
    plan = _planner_fallback_plan("hf models query", fr)
    assert plan is not None
    assert len(plan["nodes"]) == 1
    assert plan["nodes"][0]["skill"] == "formatter"
    assert "n:3" in plan["nodes"][0]["inputs"]


def test_planner_fallback_none_for_unrelated_query():
    assert _planner_fallback_plan("hello", None) is None
