# Assignment 9 — Browser Agents & Autonomous Web

**EAG V3 · Session 9**

Multi-agent system that drives a real browser to complete comparison tasks on the live web, then produces a structured comparison table and an **8-section HTML replay report**.

> Copy [`.env.example`](.env.example) → `.env` before running. Session data and secrets are gitignored.  
> Further docs: [S9SharedCode/ARCHITECTURE.md](S9SharedCode/ARCHITECTURE.md) · [docs/SETUP.md](docs/SETUP.md) · [docs/BROWSER_CASCADE.md](docs/BROWSER_CASCADE.md)

---

## Assignment Requirements

### 1. At least three visible browser actions

The agent must perform **≥3 visible browser actions** — not passive scraping from search snippets.

| Accepted actions | Examples on Hugging Face |
|------------------|--------------------------|
| `click` | Open Tasks filter, open Sort menu, pick “Most Likes” |
| `scroll` | Reveal more model cards below the fold |
| `type` / `key` | Search box, confirm with Enter |
| `select` | Dropdown / tab switch |
| `submit` | Apply a filter form |

**Not accepted:** Layer-1 HTTP extract only, or reading pre-rendered search snippets with zero interaction.

**How this repo enforces it:**

- Primary task uses base URL `https://huggingface.co/models` with an interactive goal (filter → sort → read cards).
- `browser/extract_utils.py` skips passive extract when the goal requires interaction.
- `browser/skill.py` strips pre-filtered query params when the goal mentions filter/sort.
- `replay_viewer.py` shows a compliance banner and counts visible actions in §4 and §8.

**Example action log (§4 of replay report):**

```text
Turn 1  click  #12  Tasks filter → Text Generation
Turn 2  click  #28  Sort menu
Turn 3  click  #31  Most Likes
Turn 4  scroll down
Turn 5  done   success=true
```

→ **4 visible actions** (filter, sort, sort-option, scroll) — meets requirement.

---

### 2. Structured comparison table + 8-section replay report

After each run, open:

```text
S9SharedCode/code/state/sessions/<session-id>/report.html
```

Session index (links to all reports):

```text
S9SharedCode/code/state/sessions/index.html
```

The replay viewer (`S9SharedCode/replay_viewer.py`) generates all **8 required sections**:

| § | Section | What it shows | Source |
|---|---------|---------------|--------|
| **1** | **Original user goal** | Verbatim query the user asked | `query.txt` |
| **2** | **Planner DAG** | Visual node graph: planner → browser → distiller → critic → formatter | Session node JSON + planner rationale |
| **3** | **Browser path chosen** | Winning cascade layer: `extract` / `deterministic` / `a11y` / `vision` / `blocked` | `BrowserOutput.path` (+ `gateway_blocked` when blocked) |
| **4** | **Browser actions taken** | Turn-by-turn log: click, scroll, type, key, done | `BrowserOutput.actions` |
| **5** | **Screenshots / page-state logs** | Per-turn PNGs + element legends | `browser/<run>/{a11y\|vision}/turn_*_{raw,marked}.png`, `turn_*_legend.txt` |
| **6** | **Extracted data** | Distiller structured fields + raw browser/researcher content | Distiller `fields`, browser `content` |
| **7** | **Final comparison table** | HTML table built from distiller fields (or formatter markdown table) | `_fields_to_table()` in `replay_viewer.py` |
| **8** | **Turn count & cost summary** | Per-node elapsed time, browser turns, gateway cost by agent | Node results + gateway ledger |

**Compliance banner** (top of report): green ✓ when ≥3 visible actions recorded; red ⚠ when below requirement.

---

## Primary Assignment Task

**Query** (run by `assignment_runner.py`):

> Compare top 3 Hugging Face **text-generation** models sorted by **likes**.  
> Use the browser on `https://huggingface.co/models` (base URL).  
> Perform at least three visible browser actions (filter Tasks, sort by Most Likes, read model cards).  
> For each model: model name, organisation, likes, parameter count (if listed), one-line description.

**Expected DAG:**

```text
Planner → Browser (a11y or vision) → Distiller → [auto Critic] → Formatter
```

**Why browser is required:**

- `huggingface.co/models` is JavaScript-rendered — static fetch returns no model cards.
- Tasks filter and Sort dropdown are interactive widgets — they must be clicked, not URL-encoded.

**Example comparison table (§7):**

| Model Name | Organisation | Likes | Parameter Count | Description |
|------------|--------------|-------|-----------------|-------------|
| deepseek-ai/DeepSeek-R1 | deepseek-ai | 13.4k | 685B | Strong reasoning model |
| meta-llama/Llama-3.1-8B | meta-llama | 12.1k | 8B | General-purpose text generation |
| mistralai/Mistral-7B-v0.3 | mistralai | 9.8k | 7B | Efficient open-weight LLM |

*(Actual rows come from the live run — numbers change on huggingface.co.)*

---

## Quick Start

```bash
# 1. Start the gateway (leave running in its own terminal)
cd llm_gatewayV9
uv run main.py

# 2. Install browser once
cd ../S9SharedCode/code
uv sync && uv run playwright install chromium

# 3. Run assignment + generate report (one command)
cd ..
./run_assignment.sh

# 4. Open the replay report
xdg-open code/state/sessions/index.html
# or for latest session:
python3 replay_viewer.py --open
```

**Other tasks** (all produce the same 8-section report):

```bash
./run_assignment.sh laptops       # 3 laptops under ₹80k
./run_assignment.sh hf_text_gen    # HF text-gen by likes (primary)
./run_assignment.sh ai_tools       # 5 AI coding tools pricing
./run_assignment.sh cnc_training   # CNC institutes Bangalore
./run_assignment.sh all            # run all four
./run_assignment.sh report <sid>   # regenerate report only
```

---

## Replay Report — Section Details

Below is exactly what each section contains in `report.html`.

### §1 Original user goal

The full comparison query as typed by the user, stored in `state/sessions/<sid>/query.txt`.

### §2 Planner DAG

Left-to-right visual of every node executed in the session:

```text
STEP 1        STEP 2        STEP 3        STEP 4        STEP 5
planner   →   browser   →   distiller →   critic    →   formatter
✓ complete    ✓ complete    ✓ complete    ✓ complete    ✓ complete
```

Includes planner rationale and skill chain (`planner → browser → distiller → formatter`).

### §3 Browser path chosen

| Layer | Meaning |
|-------|---------|
| `extract` | Static HTML via httpx + trafilatura ($0 LLM) |
| `deterministic` | Playwright + CSS selectors ($0 LLM) |
| `a11y` | Accessibility tree + text LLM per turn |
| `vision` | Set-of-marks screenshot + vision model per turn |
| `blocked` | CAPTCHA / login wall / Cloudflare (`gateway_blocked`) |

Shows node id, path, turn count, URL, and status per browser node.

### §4 Browser actions taken

Turn-by-turn table for each browser node:

| Turn | Actions | Outcome |
|------|---------|---------|
| 1 | `click #12` | ok |
| 2 | `click #28` | ok |
| 3 | `click #31` | ok |
| 4 | `scroll down` | ok |
| 5 | `done success=true` | done(True) |

Header shows **visible action count** vs the ≥3 requirement.

### §5 Screenshots / page-state logs

- Grid of embedded PNG screenshots (`turn_01_raw.png`, `turn_01_marked.png` for vision layer)
- Collapsible element legends (`turn_01_legend.txt`) — the numbered element list sent to the LLM each turn

Stored under: `state/sessions/<sid>/browser/browser_<timestamp>/{a11y|vision}/`

### §6 Extracted data

- **Distiller fields** — structured key/value pairs prefixed by entity (`model_name`, `likes`, `organisation`, …)
- **Raw browser content** — collapsible page text from the browser node

### §7 Final comparison table

HTML table pivoted from distiller fields. If the formatter also produced a markdown table, both are shown.

Built by `_fields_to_table()` in `replay_viewer.py` from distiller output like:

```json
{
  "deepseek-ai_DeepSeek-R1_model_name": "deepseek-ai/DeepSeek-R1",
  "deepseek-ai_DeepSeek-R1_likes": "13.4k",
  "deepseek-ai_DeepSeek-R1_organisation": "deepseek-ai"
}
```

### §8 Turn count & cost summary

| Metric | Example |
|--------|---------|
| Total nodes | 7 |
| Browser turns | 5 |
| Visible browser actions | 4 (meets requirement) |
| Total elapsed | 47.3s |
| Gateway cost | $0.0021 (planner + browser + distiller + formatter) |

Per-node breakdown: skill, status, elapsed, browser turns, provider.

---

## Browser Cascade (summary)

The browser skill (`S9SharedCode/code/browser/skill.py`) escalates through four layers until one succeeds:

```text
Layer 1  extract        httpx + trafilatura          ($0 LLM)
Layer 2a deterministic  Playwright + CSS selectors  ($0 LLM)
Layer 2b a11y           Playwright + text LLM         (cheap)
Layer 3  vision         Playwright + vision LLM       (expensive)
```

Precondition: **gateway_blocked** stops immediately on CAPTCHA / login wall.

Full cascade reference: [docs/BROWSER_CASCADE.md](docs/BROWSER_CASCADE.md)

---

## Project Structure

```text
Assignment 9/
├── .env.example
├── llm_gatewayV9/              Gateway service (port 8109)
└── S9SharedCode/
    ├── run_assignment.sh       End-to-end runner
    ├── replay_viewer.py        8-section HTML report generator
    └── code/
        ├── assignment_runner.py
        ├── flow.py               Orchestrator (growing DAG)
        ├── browser/skill.py      Four-layer cascade
        ├── html_report.py        Wrapper → replay_viewer
        └── state/sessions/
            ├── index.html        Links to all reports
            └── <session-id>/
                ├── query.txt
                ├── nodes/        Per-node JSON
                ├── browser/      Screenshots + legends
                └── report.html   ← 8-section replay (submission artifact)
```

---

## Submission Checklist

- [ ] Live run completes with **≥3 visible browser actions** (check §4 banner in `report.html`)
- [ ] `report.html` contains all **8 sections** listed above
- [ ] §7 shows a **structured comparison table** (not raw JSON)
- [ ] Session trace persisted under `S9SharedCode/code/state/sessions/<sid>/`
- [ ] Gateway + Playwright installed (`uv sync`, `playwright install chromium`)
- [ ] Repo pushed to GitHub with this README

---

## Dependencies

```bash
cd S9SharedCode/code && uv sync
uv run playwright install chromium
```

Key packages: `playwright`, `pillow`, `trafilatura`, `httpx`, `networkx`, `pydantic`, `faiss-cpu`
