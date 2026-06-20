# Session 10 — What I Built & What I Ran

**EAG V3 · Computer-Use Agent** · Linux (X11) · [cua-driver](https://cua.ai/docs/cua-driver)

Hi — this is a short write-up of my Session 10 work on desktop automation. I extended the Session 9 multi-agent stack with a **Computer skill** that drives real desktop apps through a four-layer cascade (extract → deterministic workflows → a11y LLM → vision), wired into the existing planner / formatter pipeline.

Detailed architecture: [S9SharedCode/SESSION10_README.md](S9SharedCode/SESSION10_README.md)  
Submission evidence: [docs/SESSION10_SUBMISSION.md](docs/SESSION10_SUBMISSION.md)  
Run logs: [readme_assignment10.md](readme_assignment10.md)

---

## What I implemented

| Area | What changed |
|------|----------------|
| **Computer skill** | New `S9SharedCode/code/computer/` package — cascade orchestrator, cua-driver client, deterministic workflows, Electron/CDP path, Layer-1 file extract |
| **Integration** | Planner prompt + `agent_config.yaml` route desktop goals to `computer`; replay viewer shows computer nodes in §3–§5 |
| **Assignment runner** | `S9SharedCode/run_computer_assignment.sh` — one command per task, writes trajectories under `state/sessions/<id>/computer/` |
| **Tests** | `tests/test_computer.py`, gateway retry test, pytest wired in the runner |
| **Docs** | Session 10 README, submission checklist, setup notes |

The cascade mirrors Session 9 Browser: try the cheapest layer first, escalate only when the goal needs interaction or the current layer fails.

| Layer | Name | Mechanism |
|-------|------|-----------|
| 1 | extract | Read local files / clipboard — no LLM, no UI clicks |
| 2a | deterministic | Hotkeys & typed sequences from `workflows.yaml` |
| 2b | a11y | AT-SPI tree + gateway chat (scan → act → verify) |
| 3 | vision | Set-of-Marks screenshot clicks |
| — | electron | CDP `execute_javascript` when `electron_debugging_port` is set |

---

## Tasks I ran (latest local sessions)

Prerequisites:

```bash
export QT_ACCESSIBILITY=1
cua-driver doctor
cd llm_gatewayV9 && uv run main.py          # terminal 1 — port 8109
cd S9SharedCode && ./run_computer_assignment.sh <task>
python3 replay_viewer.py <session_id> --open
```

### 1. Calculator — deterministic (`calc42`) ✅

- **Goal:** Open Calculator and compute 42 × 567; report the display result.
- **Session:** `s9-217c0339`
- **Path:** `deterministic` — expression parsed from the goal, `calculator-eval` workflow (type expression, click `=`).
- **Result:** `23814` (correct)
- **Notes:** Zero vision, zero LLM on the computer node. Planner → computer → formatter in ~26s.

### 2. Note file — extract (`noteread`) ✅

- **Goal:** Read `~/assignment9-note.txt` verbatim.
- **Session:** `s9-41084835`
- **Path:** `extract` — direct file read, no desktop interaction.
- **Result:** Full note text returned unchanged.
- **Notes:** Fastest run (~0.3s on the computer node). Good example of Layer 1 short-circuiting.

### 3. VS Code Explorer — Electron CDP (`vscodefiles`) ⚠️ mostly

- **Goal:** Open VS Code on the project with remote debugging; list top 3 Explorer entries.
- **Session:** `s9-6bb40247`
- **Path:** `electron` — relaunch with `--remote-debugging-port=9222`, CDP JS query.
- **Result:** Two sidebar names extracted (`Assignment-10/…`, `Assignment-9/…`); distiller + critic passed, but answer said “top 2” not 3.
- **Notes:** CDP path works; I think the DOM selector or tree depth only surfaced two `.monaco-icon-label` entries on my machine.

### 4. Calculator keypad — vision demo (`calcvision`) ⚠️ needs work

- **Goal:** Compute 99 × 99 by **clicking on-screen buttons** (no typed expression shortcut).
- **Session:** `s9-e85f9150`
- **Path taken:** `deterministic` (typed `99*99`) — not the intended a11y/vision path.
- **Result:** Numeric answer `9801` is correct, but the formatter honestly reported that the shortcut was used instead of button clicks.
- **Notes:** Expression parsing in Layer 2a is “too good” — it wins before a11y/vision get a fair shot when the goal mentions numbers. I’d like feedback on how to gate deterministic when the user explicitly forbids typing.

---

## Bugs I hit and fixed along the way

- Calculator `type_text "42*567="` did not evaluate → fixed by clicking the `=` button after typing.
- Hardcoded expressions → replaced with `parse_calculator_expression(goal)`.
- CDP JSON landing in the wrong field → `_parse_page_output()` cleanup.
- LLM hotkey combos like `control+shift+e` → normalized to `ctrl` + proper `hotkey` calls.
- Gemini 503 bursts → 4.5s pause between LLM turns in browser/computer drivers.

(Full list: [docs/SESSION10_SUBMISSION.md](docs/SESSION10_SUBMISSION.md))

---

## How to reproduce

```bash
cd S9SharedCode
./run_computer_assignment.sh all          # calc42 + noteread + vscodefiles
./run_computer_assignment.sh calcvision   # optional keypad demo
./run_computer_assignment.sh tests        # pytest
```

Replay reports:

```bash
python3 replay_viewer.py s9-217c0339 --open   # calc42
python3 replay_viewer.py s9-41084835 --open   # noteread
python3 replay_viewer.py s9-6bb40247 --open   # vscodefiles
python3 io_replay_viewer.py --open            # I/O-focused view of latest session
```

---

## Feedback I’d appreciate

If you have a few minutes, I’d love thoughts on any of these — rough notes are fine:

1. **Cascade gating** — When a goal says “click buttons only” or “no typed shortcut”, should deterministic be skipped entirely, or should workflow metadata carry an explicit `allow_expression_parse: false` flag?

2. **VS Code CDP extract** — Any better selectors or traversal for Monaco Explorer items? I only got 2 of 3 requested names.

3. **Layer escalation clarity** — Is the scan → act → verify loop obvious enough in the replay HTML, or should each trajectory step label which layer attempted the action?

4. **Assignment scope** — For Session 10, is `noteread` (Layer 1 file extract) useful as a demo task, or should submissions stick to strictly interactive desktop goals?

5. **Anything I missed** — Failure modes, test gaps, or docs that would have saved you time on setup (AT-SPI, `QT_ACCESSIBILITY`, gateway, snap VS Code, etc.).

You can reply in the course thread, open a GitHub issue, or comment on the PR — whatever’s easiest. Thanks for reading.

---

**Repo:** [varunsood189/Assignment-9](https://github.com/varunsood189/Assignment-9) (Sessions 9–10)  
**Author:** Varun Sood · `varunsood189@gmail.com`
