"""Session 10 computer skill tests."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from computer.deterministic import match_workflow
from computer.extract_utils import goal_requires_interaction, is_useful_extract, read_files
from computer.permissions import _blocked_reasons
from computer.snapshot import parse_window_state
from computer.skill import ComputerSkill
from computer.target import resolve_target
from schemas import NodeSpec
from recovery import plan_recovery


def test_match_workflow_cursor():
    wf = match_workflow(app="cursor", title="schemas.py - Cursor")
    assert wf is not None
    assert wf.get("match_app") == "cursor"


def test_is_useful_extract():
    assert is_useful_extract("x" * 50, "read file content")
    assert not is_useful_extract("short", "read file content")
    assert not is_useful_extract(
        "- [0] frame \"Cursor\" [actions=[]]",
        "Open Cursor and list the top 3 files in the sidebar",
        element_count=1,
    )
    assert not is_useful_extract(
        "a" * 100,
        "open the app and list files",
        element_count=1,
    )


def test_goal_requires_interaction():
    assert goal_requires_interaction("Open Cursor and list the top 3 files")
    assert not goal_requires_interaction("read the config file contents")


def test_parse_window_state():
    snap = parse_window_state({
        "elements": [{"element_index": 3, "role": "button", "name": "OK",
                      "x": 1, "y": 2, "width": 10, "height": 20}],
        "screenshot_width": 800,
        "screenshot_height": 600,
        "tree_markdown": "# window",
    })
    assert len(snap.elements) == 1
    assert snap.elements[0].id == 3
    assert "OK" in snap.legend()


def test_blocked_reasons_linux_atspi():
    reasons = _blocked_reasons({"atspi": False, "x11": True, "xsend_event": True})
    assert any("AT-SPI" in r for r in reasons)


def test_precondition_recovery_skip():
    d = plan_recovery(
        failed_skill="computer",
        error_text="precondition_blocked: AT-SPI not reachable",
        failed_node_id="n:2",
    )
    assert d.action == "skip"
    assert "permission" in d.note.lower()


@pytest.mark.asyncio
async def test_layer1_extract(tmp_path):
  files = tmp_path / "note.txt"
  files.write_text("alpha beta gamma delta epsilon zeta eta theta iota kappa")
  mock_cua = AsyncMock()
  mock_cua.get_window_state.return_value = {"tree_markdown": ""}
  mock_cua.start_recording = AsyncMock(return_value={})
  mock_cua.stop_recording = AsyncMock(return_value={})
  with patch("computer.skill.check_preconditions", return_value=(True, [])):
    with patch("computer.skill.resolve_target", return_value=(1, 2, "Test")):
      sk = ComputerSkill(cua=mock_cua, session="test")
      node = NodeSpec(
        skill="computer",
        metadata={
          "app": "test",
          "goal": "read the note file",
          "files": [str(files)],
          "record": False,
        },
      )
      result = await sk.run(node)
  assert result.success
  assert result.output["path"] == "extract"
  assert "alpha" in (result.output.get("content") or "")


@pytest.mark.asyncio
async def test_layer2a_deterministic():
  mock_cua = AsyncMock()
  mock_cua.hotkey = AsyncMock(return_value={})
  mock_cua.get_window_state.return_value = {"tree_markdown": "after workflow " * 10}
  mock_cua.start_recording = AsyncMock(return_value={})
  mock_cua.stop_recording = AsyncMock(return_value={})
  with patch("computer.skill.check_preconditions", return_value=(True, [])):
    with patch("computer.skill.resolve_target", return_value=(9, 8, "Cursor")):
      sk = ComputerSkill(cua=mock_cua, session="test")
      node = NodeSpec(
        skill="computer",
        metadata={
          "app": "cursor",
          "goal": "open command palette",
          "workflow": "cursor",
          "force_path": "deterministic",
          "record": False,
        },
      )
      result = await sk.run(node)
  assert result.success
  assert result.output["path"] == "deterministic"
  mock_cua.hotkey.assert_called()


@pytest.mark.asyncio
async def test_precondition_blocked():
  with patch("computer.skill.check_preconditions", return_value=(False, ["no AT-SPI"])):
    sk = ComputerSkill(cua=AsyncMock(), session="test")
    result = await sk.run(NodeSpec(skill="computer", metadata={"goal": "x", "app": "y"}))
  assert not result.success
  assert result.error_code == "precondition_blocked"


@pytest.mark.asyncio
async def test_graph_dispatch_computer():
    from skills import SkillRegistry, run_skill
    from schemas import AgentResult

    reg = SkillRegistry()
    skill = reg.get("computer")
    graph_nodes = {
        "n:1": {
            "skill": "computer",
            "inputs": [],
            "metadata": {"app": "calc", "goal": "test", "label": "c1"},
        },
    }
    fake = AgentResult(success=True, agent_name="computer", output={"path": "extract"}, elapsed_s=0.1)
    with patch("computer.skill.ComputerSkill") as MockSkill:
        inst = MockSkill.return_value
        inst.run = AsyncMock(return_value=fake)
        result, prompt = await run_skill(
            skill, "n:1", graph_nodes, "s10-test", "query", None, memory_hits=[],
        )
    assert result.success
    inst.run.assert_awaited_once()


@pytest.mark.asyncio
async def test_recording_start_stop():
  mock_cua = AsyncMock()
  mock_cua.start_recording = AsyncMock(return_value={"recording": True})
  mock_cua.stop_recording = AsyncMock(return_value={"recording": False})
  sk = ComputerSkill(cua=mock_cua, session="rec-test")
  await sk.cua.start_recording("/tmp/traj")
  await sk.cua.stop_recording()
  mock_cua.start_recording.assert_awaited_once()
  mock_cua.stop_recording.assert_awaited_once()


@pytest.mark.asyncio
async def test_scan_act_verify_flag_in_actions():
  from computer.driver import A11yComputerDriver, DriverConfig
  from browser.client import V9Client

  mock_cua = AsyncMock()
  snap = {
    "elements": [{"element_index": 1, "role": "button", "name": "OK",
                  "x": 0, "y": 0, "width": 10, "height": 10}],
    "screenshot_width": 100, "screenshot_height": 100, "tree_markdown": "tree",
  }
  mock_cua.get_window_state = AsyncMock(return_value=snap)
  mock_cua.press_key = AsyncMock(return_value={})

  mock_gw = AsyncMock()
  mock_gw.chat = AsyncMock(return_value=MagicMock(
    parsed={"thinking": "press enter", "actions": [{"type": "key", "value": "Enter"}]},
    text="", provider="g", model="m", latency_ms=1, input_tokens=1, output_tokens=1,
  ))

  cfg = DriverConfig(goal="test", pid=1, window_id=2, max_steps=1, pause_before_llm_s=0)
  drv = A11yComputerDriver(mock_cua, mock_gw, cfg)
  result = await drv.run()
  assert mock_cua.get_window_state.await_count >= 2
  assert result.steps[0].verified is True


def test_extract_calculator_display():
    from computer.deterministic import extract_calculator_display
    assert extract_calculator_display('edit bar = "756"') == "756"
    assert extract_calculator_display('edit bar = "42*18="') is None


def test_parse_calculator_expression():
    from computer.deterministic import parse_calculator_expression
    assert parse_calculator_expression("Compute 42 times 18 and read the result") == "42*18"
    assert parse_calculator_expression("compute 42*19") == "42*19"
    assert parse_calculator_expression("read display", {"expression": "99+1"}) == "99+1"
    assert parse_calculator_expression("hello world") is None


def test_read_files(tmp_path):
  p = tmp_path / "a.txt"
  p.write_text("hello world from file extract layer one")
  text = read_files([str(p)])
  assert "hello world" in text
