# Assignment 9 — Browser Agents & Autonomous Web

**EAG V3 · Session 9**

> **Git / docs index:** [S9SharedCode/README.md](S9SharedCode/README.md) · [docs/SETUP.md](docs/SETUP.md) · [docs/GIT.md](docs/GIT.md) · [docs/BROWSER_CASCADE.md](docs/BROWSER_CASCADE.md)  
> Copy [`.env.example`](.env.example) → `.env` before running. Session data and secrets are gitignored.

A multi-agent AI system that drives a real browser to answer comparison questions on the live web. Built on top of the Session 8 growing-graph orchestrator — the Browser skill plugs in through `agent_config.yaml` without any changes to the orchestrator itself.

---

## Quick Start

```bash
# 1. Start the gateway (leave running in its own terminal)
cd llm_gatewayV9
uv run main.py

# 2. Run the comparison task
cd S9SharedCode/code
uv run python assignment_runner.py

# 3. Generate the HTML report
uv run python html_report.py

# OR — do all three steps with one command:
cd S9SharedCode
./run_assignment.sh
```

---

## Project Structure

```
Assignment 9/
├── .env                              ← API keys (Gemini, Groq, NVIDIA, etc.)
│
├── llm_gatewayV9/                    ← Gateway service (port 8109)
│   ├── main.py                       ← FastAPI server entry point
│   ├── router.py                     ← Provider failover logic
│   ├── providers.py                  ← Gemini / Groq / NVIDIA adapters
│   ├── agent_routing.yaml            ← Per-agent provider pins
│   └── gateway_v9.db                 ← SQLite cost ledger
│
└── S9SharedCode/
    ├── run_assignment.sh             ← End-to-end runner script
    └── code/
        ├── flow.py                   ← Orchestrator: growing DAG executor
        ├── skills.py                 ← Skill registry + per-node dispatcher
        ├── agent_config.yaml         ← Skill catalogue (yaml)
        ├── schemas.py                ← Pydantic contracts (AgentResult, BrowserOutput, etc.)
        ├── recovery.py               ← Failure classification + recovery decisions
        ├── persistence.py            ← Session state to/from disk
        ├── memory.py                 ← FAISS vector memory
        ├── replay.py                 ← CLI session replay viewer
        │
        ├── browser/                  ← The Browser skill (Session 9 addition)
        │   ├── skill.py              ← Cascade wrapper (the main entry point)
        │   ├── driver.py             ← A11yDriver and SetOfMarksDriver
        │   ├── dom.py                ← Interactive-element enumeration (JS + Python)
        │   ├── highlight.py          ← Set-of-marks annotation (Pillow)
        │   └── client.py             ← V9 gateway HTTP client
        │
        ├── prompts/
        │   ├── planner.md            ← Planner instructions and DAG examples
        │   ├── browser.md            ← Browser skill prompt
        │   ├── distiller.md          ← Distiller prompt
        │   ├── critic.md             ← Critic prompt
        │   └── formatter.md          ← Formatter prompt
        │
        ├── assignment_runner.py      ← Runs the comparison task
        ├── html_report.py            ← Generates the HTML replay report
        │
        └── state/
            └── sessions/
                ├── index.html        ← Links to all session reports
                └── <session-id>/
                    ├── query.txt
                    ├── graph.json
                    ├── nodes/        ← Per-node JSON state files
                    ├── browser/      ← Screenshots per turn
                    └── report.html   ← Generated HTML report
```

---

## The Browser Skill — Four-Layer Cascade

The Browser skill (`browser/skill.py`) always tries the cheapest path first and escalates only when it fails. The path actually used is recorded in `BrowserOutput.path`.

### Path 1: `extract`

**Code:** `browser/skill.py` → `_fetch_html()` + `_extract()`  
**Libraries:** `httpx` (HTTP client), `trafilatura` (article extractor)  
**LLM cost:** $0.00 — no model is called  
**Browser:** none — plain HTTP GET  

```
httpx.get(url)  →  trafilatura.extract(html)  →  content
```

**Fires when:** A plain HTTP download returns useful article text.  
**Fails when:**
- The page content is JavaScript-rendered (the raw HTML contains no data)
- The `goal` contains interactive verbs: `click`, `fill`, `select`, `type`, `drag`, `filter`, `sort`, `submit`, `navigate`
- Extracted content is fewer than 200 characters
- The page returns a CAPTCHA or Cloudflare challenge (`gateway_blocked`)

**Output fields set:**
- `path = "extract"`
- `turns = 0`
- `content` = extracted article text
- `final_url` = URL after any redirects

---

### Path 2a: `deterministic`

**Code:** `browser/skill.py` → `_try_deterministic()`  
**Libraries:** `playwright` (headless Chrome)  
**LLM cost:** $0.00 — no model is called  
**Browser:** headless Chromium  

```
page.goto(url)
for each step in metadata.selectors:
    page.locator(step["selector"]).click() / .fill()
trafilatura.extract(page.content())  →  content
```

**Fires when:** The Planner passes `metadata.selectors` — a list of explicit CSS selector steps. Example:
```yaml
metadata:
  selectors:
    - {action: "click", selector: "input[name=q]"}
    - {action: "fill",  selector: "input[name=q]", value: "python tutorial"}
    - {action: "key",   value: "Enter"}
```

**Supported actions:** `click`, `fill`, `key`  
**Fails when:** Any selector is not found on the page (visible + timeout 8s). Falls through to Layer 2b — does NOT raise an error.

**Output fields set:**
- `path = "deterministic"`
- `turns` = number of selector steps executed
- `content` = extracted text after all steps
- `final_url` = final page URL

---

### Path 2b: `a11y`

**Code:** `browser/skill.py` → `_drive(A11yDriver, ...)`  
**Driver:** `browser/driver.py` → `A11yDriver`  
**Element enumeration:** `browser/dom.py` → `enumerate_interactives()`  
**Libraries:** `playwright`, gateway `/v1/chat`  
**LLM cost:** cheap text model per turn (no image sent)  
**Browser:** headless Chromium  

**How it works per turn:**
1. `enumerate_interactives(page)` runs a JavaScript snippet in the page that collects every visible interactive element — `<a>`, `<button>`, `<input>`, `<select>`, elements with `role=button/tab/menuitem/etc.`, `cursor:pointer` elements. SVG primitives and nested duplicates are deduped.
2. Each element becomes a legend line: `[42]<button>Sort: Most Downloads</button>`
3. The legend (text only, no screenshot) is sent to the cheap text LLM via `/v1/chat` with the goal and recent action history.
4. The model returns a JSON action list: `[{"type":"click","mark":42}]`
5. The action is dispatched by `driver.py` → `_dispatch()`.
6. Repeat up to `max_steps_a11y` (default 12) turns.

**Action vocabulary:**

| Action | Parameters | What it does |
|---|---|---|
| `click` | `mark` (int) | Click the centre of element #mark |
| `type` | `mark`, `value`, `clear?` | Focus element, optionally select-all, then type |
| `key` | `value` | Press a keyboard key (Enter, Tab, Escape, ArrowDown…) |
| `scroll` | `direction`, `amount?` | Scroll the page (up / down / left / right) |
| `wait` | `seconds` | Sleep to let the page settle |
| `done` | `success`, `note` | Finish; success=true if goal is met |

**Critical a11y rules (enforced in prompt):**
- Max 2 actions per turn
- Dropdown triggers (names ending in `▾` or `:`) must be the ONLY action in their turn — the popover options only appear in the next turn
- Never bundle `done` with other actions

**Artifacts saved per turn** (when `artifacts_dir` is set):
- `turn_01_raw.png` — raw screenshot of the page state
- `turn_01_legend.txt` — the element legend sent to the model

**Fires when:** Layer 1 fails AND no selectors were provided (or selectors failed).  
**Fails when:** `max_steps_a11y` turns exhausted without `done(success=true)`. Falls through to Layer 3.

**Output fields set:**
- `path = "a11y"`
- `turns` = number of turns taken by the A11yDriver
- `content` = page text extracted after final turn
- `actions` = list of `{turn, actions, outcome}` dicts
- `final_url` = final page URL

---

### Path 3: `vision`

**Code:** `browser/skill.py` → `_drive(SetOfMarksDriver, ...)`  
**Driver:** `browser/driver.py` → `SetOfMarksDriver`  
**Annotation:** `browser/highlight.py` → `annotate()`  
**Libraries:** `playwright`, `Pillow`, gateway `/v1/vision`  
**LLM cost:** vision model per turn (screenshot + prompt)  
**Browser:** headless Chromium  

**How it works per turn:**
1. Same `enumerate_interactives()` as a11y — gets element bounding boxes.
2. `page.screenshot()` captures the current viewport as PNG bytes.
3. `highlight.annotate(png, elements, dpr)` draws **dashed numbered boxes** over every element using Pillow:
   - Colour-coded by tag: blue=links, green=buttons, orange=inputs, purple=selects, red=other
   - DPR-scaled: CSS pixels × devicePixelRatio so boxes land correctly on retina screenshots
   - Number badge: filled rect + white text in top-left corner of each box
4. The annotated PNG is base64-encoded and sent to `/v1/vision` alongside the legend and goal.
5. The vision model picks a box number; the driver dispatches the click.

**Artifacts saved per turn** (when `artifacts_dir` is set):
- `turn_01_raw.png` — raw screenshot before annotation
- `turn_01_marked.png` — annotated screenshot with numbered boxes
- `turn_01_legend.txt` — the element legend

**Fires when:** Both a11y and all earlier layers exhausted without success.  
**Also fires when:** `metadata.force_path = "vision"` is set (bypasses a11y entirely — used in tests).

**Output fields set:**
- `path = "vision"`
- `turns` = number of turns taken by SetOfMarksDriver
- `content` = page text extracted after final turn
- `actions` = list of `{turn, actions, outcome}` dicts
- `final_url` = final page URL

---

### Precondition: `gateway_blocked`

**Code:** `browser/skill.py` → `detect_gateway_block()`  
**Checked at:** Layer 1 (on raw HTML) AND after page load in Playwright (on rendered HTML)

This is checked before and during every layer. If the page is a block page, the skill returns immediately with `error_code="gateway_blocked"` — no further layers are attempted.

**Detected patterns:**

| Type | Markers |
|---|---|
| CAPTCHA | "Let's confirm you are human", "Robot Check", "Please verify you are a human" |
| hCaptcha | `class="h-captcha"`, `data-hcaptcha-widget-id` |
| reCAPTCHA | `class="g-recaptcha"`, `g-recaptcha-response` |
| Cloudflare | "Checking your browser before accessing", `cf-browser-verification`, `cf-challenge-running` |
| Login wall | "You must be logged in", "Sign in to continue", "Please log in to continue" |

**What the orchestrator does:** The Planner receives `gateway_blocked` in the failure report and its prompt tells it: *"Do NOT retry the same URL — pick a different source or hand back to the user."*

---

## Cascade Decision Flow

```
BrowserSkill.run(NodeSpec)
│
├─ fetch HTML via httpx
│   ├─ HTTP error → skip Layer 1, fall through
│   ├─ gateway_blocked → return error_code="gateway_blocked"  STOP
│   ├─ _is_useful_extract() passes → return path="extract"    STOP
│   └─ not useful → continue
│
├─ metadata.selectors provided?
│   ├─ YES → _try_deterministic()
│   │   ├─ all selectors found & executed → return path="deterministic"  STOP
│   │   └─ any selector missing → fall through to a11y
│   └─ NO → skip Layer 2a
│
├─ force_path == "vision"?
│   ├─ YES → skip a11y entirely
│   └─ NO → run A11yDriver (up to max_steps_a11y turns)
│       ├─ gateway_blocked detected after render → return error_code="gateway_blocked"  STOP
│       ├─ done(success=true) within turn cap → return path="a11y"  STOP
│       └─ turn cap hit or max failures → fall through
│
└─ run SetOfMarksDriver (up to max_steps_vision turns)
    ├─ gateway_blocked detected → return error_code="gateway_blocked"  STOP
    ├─ done(success=true) within turn cap → return path="vision"  STOP
    └─ turn cap hit → return error_code="interaction_failed"  STOP
```

---

## Error Codes (`AgentResult.error_code`)

Defined in `schemas.py`. Only the Browser skill sets these; other skills leave `error_code=None`.

| Code | Meaning | Orchestrator action |
|---|---|---|
| `gateway_blocked` | CAPTCHA / login wall / Cloudflare stopped the page | Planner re-routes to a different URL or tells the user |
| `extraction_failed` | Page rendered but no useful content extracted | Recovery planner tries a different approach |
| `interaction_failed` | Turn cap reached without completing the goal | Recovery planner retries with different metadata |
| `timeout` | Wall-clock cap hit (default 90s) | Recovery planner retries |
| `vlm_unavailable` | All vision providers refused (503/refused) | Recovery planner falls back to a11y-only attempt |

---

## `BrowserOutput` Schema

```python
class BrowserOutput(BaseModel):
    url: str                  # The URL passed in metadata.url
    goal: str                 # The goal passed in metadata.goal
    path: Literal[
        "extract",            # Layer 1 succeeded
        "deterministic",      # Layer 2a succeeded
        "a11y",               # Layer 2b succeeded
        "vision",             # Layer 3 succeeded
    ]
    turns: int                # Number of turns the winning layer took (0 for extract/deterministic)
    content: str | None       # Extracted page text (for extract/deterministic/a11y/vision)
    actions: list[dict]       # Per-turn action log from the winning driver [{turn, actions, outcome}]
    final_url: str | None     # Page URL after all navigation
```

---

## How to Invoke the Browser Skill (Planner syntax)

The Planner emits a `browser` node like this:

```json
{
  "skill": "browser",
  "inputs": [],
  "metadata": {
    "label": "b1",
    "url": "https://huggingface.co/models",
    "goal": "Filter Tasks=Text-to-Image, Sort=Most Downloads; extract the top 3 model cards with name, downloads, likes, and description."
  }
}
```

**Rules:**
- Always assign a `metadata.label` so the downstream distiller can reference it as `"n:b1"`
- Pass the **base URL** — do not pre-encode filters in the query string; describe them in `goal` instead
- Do NOT set `force_path` in production — let the cascade decide
- Do NOT list `USER_QUERY` in `inputs` — scope via `goal` instead

---

## Recovery Flow

When a node fails, `flow.py` calls `recovery.plan_recovery()`:

| Failure reason | Action | Note |
|---|---|---|
| `transient` (502/503/504/timeout) | `skip` | Gateway already retried; no re-plan |
| `validation_error` (malformed NodeSpec) | `skip` | Prompt bug, not a runtime issue |
| `upstream_failure` on planner | `skip` | Would cause infinite planner loop |
| `upstream_failure` on any other skill | `replan` | New Planner node queued with failure report + prior successful node ids |

When a **Critic** fails (verdict=`"fail"`):
1. The downstream formatter node is marked `skipped`
2. A new Planner node is queued with `failure_report` containing the critic's rationale
3. A per-target cap prevents infinite critic-fail loops (second failure → branch abandoned)

---

## Session State on Disk

Every run persists to `state/sessions/<session-id>/`:

```
state/sessions/s8-69e0995c/
├── query.txt                     ← Verbatim user query
├── graph.json                    ← NetworkX DAG (node_link_data format)
├── nodes/
│   ├── n_001.json                ← NodeState for node n:1 (planner)
│   ├── n_002.json                ← NodeState for node n:2 (browser)
│   └── ...
├── browser/
│   └── browser_<timestamp>/
│       ├── a11y/
│       │   ├── turn_01_raw.png   ← Raw screenshot, turn 1
│       │   ├── turn_01_legend.txt
│       │   └── ...
│       └── vision/
│           ├── turn_01_raw.png
│           ├── turn_01_marked.png ← Set-of-marks annotated screenshot
│           ├── turn_01_legend.txt
│           └── ...
├── architecture_note.txt         ← Written by assignment_runner.py
└── report.html                   ← Generated by html_report.py
```

---

## Viewing Reports

```bash
# Generate report for the most recent session
cd S9SharedCode/code
uv run python html_report.py

# Generate report for a specific session
uv run python html_report.py s8-69e0995c

# Generate reports for ALL sessions at once
for sid in $(ls state/sessions/); do uv run python html_report.py "$sid"; done

# Open the session index (links to all reports)
xdg-open state/sessions/index.html

# CLI text replay (node by node, press Enter to advance)
uv run python replay.py s8-69e0995c
```

---

## Assignment Task

**Query:**
> *"Compare the top 3 Hugging Face text-to-image models sorted by most downloads. For each model provide: model name, number of downloads, number of likes, and a one-line description of what it does."*

**Why this needs Browser (not just `fetch_url`):**
- `huggingface.co/models` renders its listing entirely in JavaScript — the raw HTML contains no model cards
- The filter (text-to-image) and sort (most downloads) are interactive widgets — they must be clicked, not URL-encoded

**Cascade path taken:** `vision` (Layer 3)
- Layer 1 failed: JS-rendered content
- Layer 2b (a11y): 12 turns, turn cap exhausted without completing the goal
- Layer 3 (vision): 5 turns with set-of-marks → `done(success=true)`
- Final URL: `https://huggingface.co/models?pipeline_tag=text-to-image&sort=downloads`

**Result:**

| Rank | Model | Downloads | Likes |
|---|---|---|---|
| 1 | tencent/HunyuanImage-3.0 | 1.07M | 1.09k |
| 2 | black-forest-labs/FLUX.1-dev | 1.02M | 13.1k |
| 3 | Tongyi-MAI/Z-Image-Turbo | 865k | 4.79k |

---

## Dependencies

```toml
# S9SharedCode/code/pyproject.toml (key packages)
playwright>=1.47      # headless browser control
pillow>=10.0          # set-of-marks annotation
trafilatura>=1.12     # article text extraction
httpx                 # HTTP client for Layer 1
faiss-cpu>=1.8.0      # vector memory (Session 7)
networkx>=3.2         # DAG orchestration (Session 8)
pydantic>=2.13.4      # typed contracts between all layers
```

Install once:
```bash
cd S9SharedCode/code && uv sync
uv run playwright install chromium
```
