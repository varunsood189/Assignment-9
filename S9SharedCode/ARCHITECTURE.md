# Assignment 9 — Architecture Note

## Goal

Demonstrate a **browser-capable multi-agent** that completes a real web comparison task Session 8 cannot do reliably (interactive filters, dropdowns, JS-rendered listings), and produce an **8-section HTML replay** of the run.

## Components

| Piece | Role |
|-------|------|
| `flow.py` | S8/S9 orchestrator (NetworkX DAG) — **unchanged** |
| `agent_config.yaml` | Skill catalogue; `browser` entry + `critic: true` on distiller |
| `prompts/planner.md` | Routes comparison queries to `browser → distiller → formatter` |
| `prompts/browser.md` | Four-layer cascade instructions |
| `code/browser/skill.py` | Cascade: extract → deterministic → a11y → vision |
| `skills.py` | Dispatches browser nodes to `browser/skill.py` |
| `replay_viewer.py` | 8-section HTML report from session JSON + browser artifacts |
| `llm_gatewayV9` | LLM + vision routing on `:8109` |

## Typical DAG

```
Planner → Browser (a11y/vision) → Distiller → [auto Critic] → Formatter
```

The planner emits the graph. The browser node walks the cascade and sets `output.path`. The distiller turns raw page text into `fields`. The orchestrator auto-splices a critic on distiller edges and passes `USER_QUERY` so evaluation is grounded. The formatter renders the comparison table.

## Four-layer cascade (cost discipline)

1. **extract** — httpx + trafilatura, $0 LLM  
2. **deterministic** — Playwright + CSS selectors, $0 LLM  
3. **a11y** — Playwright + accessibility tree + cheap text LLM  
4. **vision** — set-of-marks screenshot + VLM (only when cheaper layers fail)

Precondition: **gateway_blocked** when CAPTCHA/login stops the page.

## Assignment tasks (pick one or more)

| Key | Task | Browser entry |
|-----|------|----------------|
| `laptops` | 3 laptops under ₹80k | smartprix / 91mobiles listing |
| `ai_tools` | 5 AI coding tools pricing | per-tool pricing URLs |
| `hf_text_gen` | Top 3 HF text-gen by likes | huggingface.co/models + filters |
| `cnc_training` | 5 CNC institutes Bangalore | Sulekha listing (avoid JustDial) |

## How to run

```bash
# Gateway (separate terminal)
cd "../llm_gatewayV9" && uv run main.py

# Once: Playwright browser
cd code && uv run playwright install chromium

# Primary assignment task (HF text-generation)
./run_assignment.sh

# Any task
./run_assignment.sh laptops
./run_assignment.sh hf_text_gen
./run_assignment.sh all

# Report only
./run_assignment.sh report s9-xxxxxxxx
# or
python3 replay_viewer.py s9-xxxxxxxx
```

Reports land at `code/state/sessions/<sid>/report.html`. Session index: `code/state/sessions/index.html`.

## Replay report sections

1. Original user goal  
2. Planner DAG  
3. Browser path chosen  
4. Browser actions taken  
5. Screenshots / page-state logs  
6. Extracted data  
7. Final comparison table  
8. Turn count and cost summary  

## Submission checklist

- [ ] YouTube demo showing live run + replay HTML  
- [ ] GitHub repo (`S9SharedCode` + `llm_gatewayV9`)  
- [ ] Session trace under `code/state/sessions/<sid>/`  
- [ ] `report.html` with all 8 sections  
- [ ] This architecture note  
- [ ] At least **3 visible browser actions** in the trace (filter, sort, click, scroll, etc.)
