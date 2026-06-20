# Session 10 — Computer-Use Agent

Desktop automation skill built on [cua-driver](https://cua.ai/docs/cua-driver) with a four-layer cascade (mirroring Session 9 Browser).

## Architecture

| Layer | Name | Cost | Mechanism |
|-------|------|------|-----------|
| 1 | extract | $0 | AT-SPI tree, clipboard, local files |
| 2a | deterministic | $0 | Hotkeys / typed workflows in `workflows.yaml` |
| 2b | a11y | cheap LLM | AX tree + gateway `/v1/chat` with scan→act→verify |
| 3 | vision | vision LLM | Set-of-Marks screenshot + `/v1/vision` |
| — | electron | $0 read | CDP via `page` tool when `metadata.electron_debugging_port` is set |

Every interactive layer follows **scan → act → verify** after each action.

## Prerequisites

```bash
# Python 3.12 + deps
cd S9SharedCode/code && uv sync --python 3.12

# cua-driver + permissions
cua-driver doctor
export QT_ACCESSIBILITY=1   # required for Qt/Electron apps

# Gateway (Gemini routing for computer a11y/vision)
cd llm_gatewayV9 && uv run main.py
```

## Run the three assignment tasks

```bash
cd S9SharedCode
chmod +x run_computer_assignment.sh
./run_computer_assignment.sh all
```

| Task | Layer | Evidence |
|------|-------|----------|
| **calc42** | 2a deterministic | Calculator `42×19=798` via expression parsing, no LLM |
| **noteread** | 1 extract | Reads `~/assignment9-note.txt`, no LLM |
| **vscodefiles** | electron CDP | VS Code relaunched with `--remote-debugging-port=9222` |

Optional vision demo:

```bash
./run_computer_assignment.sh calcvision
```

Direct skill smoke (no planner):

```bash
./run_computer_assignment.sh direct-calc42
./run_computer_assignment.sh direct-vscodefiles
```

## Cascade decisions (why each layer was chosen)

### Task 1 — Calculator 42×19 (`calc42`)

- **Goal** requires launching Calculator and computing — expression parsed from goal (`42 times 19` → `42*19`).
- **Layer 2a** uses `calculator-eval` workflow (Ctrl+L, type expression, click `=`).
- **Zero vision** — no screenshot LLM.

### Task 2 — Note file (`noteread`)

- **Layer 1** reads `metadata.files` directly from disk.
- **Zero vision / zero LLM** — `is_useful_extract(..., from_files=True)` short-circuits.

### Task 3 — VS Code Explorer (`vscodefiles`)

- Electron shell — AT-SPI returns only a shallow frame node.
- **`metadata.electron_debugging_port: 9222`** relaunches VS Code with CDP.
- Daemon restarted with `CUA_DRIVER_CDP_PORT=9222`; `page.execute_javascript` queries `.monaco-icon-label` entries.
- **Zero vision** — DOM read via CDP, not SoM.

### Optional — Calculator keypad (`calcvision`)

- No matching workflow for “click buttons only”.
- Escalates through **2b a11y** then **3 vision** when AX/button resolution fails.

## Failure modes

| Symptom | `error_code` | Fix |
|---------|--------------|-----|
| AT-SPI unreachable | `precondition_blocked` | `cua-driver doctor`, enable a11y bus |
| Empty AX after focus | `precondition_blocked` | `export QT_ACCESSIBILITY=1`, relaunch app |
| CDP JS fails | `extraction_failed` / falls through | Relaunch with `--remote-debugging-port`, restart daemon with `CUA_DRIVER_CDP_PORT` |
| Gemini 503 rate limit | gateway retry + 4.5s pause between turns | keep gateway running, reduce parallel LLM calls |
| Shallow extract on interactive goal | auto-escalate | `goal_requires_interaction()` blocks Layer 1 |

## Trajectories & visualization

After each run:

```bash
# HTML replay (8 sections, computer nodes in §3–§5)
python3 replay_viewer.py <session_id> --open

# Per-turn cua-driver recordings
ls state/sessions/<session_id>/computer/*/trajectory/
```

Enable agent cursor overlay (visible in recordings):

```bash
cua-driver serve   # cursor overlay on by default
```

## Tests

```bash
cd S9SharedCode/code
uv run pytest tests/test_computer.py tests/test_demos.py -q
```

## YouTube demo checklist

1. Start gateway + `cua-driver serve` (agent cursor visible).
2. Run `./run_computer_assignment.sh calc42` — show deterministic layer + trajectory replay.
3. Run `./run_computer_assignment.sh vscodefiles` — show CDP sidebar extract.
4. Open `report.html` from `replay_viewer.py` to show cascade path per node.

## Key files

```
S9SharedCode/code/computer/
  client.py          cua-driver CLI wrapper + CDP daemon restart
  skill.py           four-layer cascade orchestrator
  driver.py          a11y + vision drivers (scan→act→verify)
  electron.py        CDP relaunch + Explorer DOM extract
  extract_utils.py   Layer 1 helpers + interaction detection
  deterministic.py   workflows.yaml runner
  workflows.yaml     hotkey / type sequences
  target.py          pid/window resolution + bring_to_front
```
