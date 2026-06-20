# Session 10 — Computer-Use Agent (Submission Evidence)

**EAG V3 · Session 10** · Linux (X11) · cua-driver 0.5.7

Full architecture: [S9SharedCode/SESSION10_README.md](../S9SharedCode/SESSION10_README.md)

## Constraint checklist

| Constraint | Task | Session | `output.path` |
|------------|------|---------|---------------|
| Zero vision (≥1) | Calculator multiply | `s9-0a0abe10` | `deterministic` |
| Zero vision (≥1) | Note file read | `s9-3894791e` | `extract` |
| Electron + `electron_debugging_port` | VS Code Explorer | `s9-6d234000` | `electron` |
| Vision (≥1) | Calculator keypad | `s9-88310c4c` | `vision` |

## Three primary tasks

### 1. Calculator — Layer 2a deterministic (`calc42`)

- **Query:** Open Calculator and compute 42 times 567; report display result.
- **Session:** `s9-0a0abe10`
- **Path:** `deterministic` — expression parsed from goal → `calculator-eval` workflow (type, click `=`).
- **Result:** `[calculator result] 23814`
- **Trajectory:** `S9SharedCode/code/state/sessions/s9-0a0abe10/computer/*/trajectory/`
- **Report:** `python3 S9SharedCode/replay_viewer.py s9-0a0abe10 --open`

### 2. Note file — Layer 1 extract (`noteread`)

- **Query:** Read `~/assignment9-note.txt` verbatim.
- **Session:** `s9-3894791e`
- **Path:** `extract` — no LLM, no desktop interaction.
- **Trajectory:** `S9SharedCode/code/state/sessions/s9-3894791e/computer/*/trajectory/`
- **Report:** `python3 S9SharedCode/replay_viewer.py s9-3894791e --open`

### 3. VS Code — Electron CDP (`vscodefiles`)

- **Query:** Open VS Code on Assignment-9 with remote debugging; list Explorer entries.
- **Session:** `s9-6d234000`
- **Path:** `electron` — relaunch with `--remote-debugging-port=9222`, CDP `execute_javascript`.
- **Content:** `[explorer files]\nAssignment-9` (+ distiller/formatter chain)
- **Trajectory:** `S9SharedCode/code/state/sessions/s9-6d234000/computer/*/trajectory/`
- **Report:** `python3 S9SharedCode/replay_viewer.py s9-6d234000 --open`

### Bonus — Vision (`calcvision`)

- **Session:** `s9-88310c4c`
- **Path:** `vision` — SoM screenshot clicks on Calculator keypad (no typed expression).
- **Report:** `python3 S9SharedCode/replay_viewer.py s9-88310c4c --open`

## Run commands

```bash
export QT_ACCESSIBILITY=1
cd llm_gatewayV9 && uv run main.py          # terminal 1
cd S9SharedCode && ./run_computer_assignment.sh all
./run_computer_assignment.sh calcvision     # vision evidence
```

## YouTube demo (record manually)

1. `cua-driver serve` (agent cursor visible)
2. Run `./run_computer_assignment.sh calc42`
3. Show `replay_viewer.py` report §3–§5 (path + actions + trajectory)
4. Optionally show `vscodefiles` Electron relaunch

## Failure modes encountered

- **`type_text "42*18="`** does not evaluate — fixed with `click_label: "="`.
- **Hardcoded expression** — fixed with `parse_calculator_expression(goal)`.
- **CDP JSON in `message` field** — fixed with `_parse_page_output()`.
- **LLM hotkeys `control+shift+e`** — fixed: map `control` → `ctrl`, use `hotkey` for combos.
- **Gemini 503** on gateway — browser/computer drivers pause 4.5s between LLM turns.
