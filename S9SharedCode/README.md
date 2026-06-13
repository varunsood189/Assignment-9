# S9SharedCode — Browser Comparison Agent

Session 9 assignment: multi-agent orchestrator + **Browser skill** (four-layer cascade) + HTML replay viewer.

## Quick start

```bash
# 1. Environment
cp ../.env.example ../.env          # fill GEMINI_API_KEY, TAVILY_API_KEY
cd code && uv sync && uv run playwright install chromium

# 2. Gateway (separate terminal, port 8109)
cd ../../llm_gatewayV9 && uv sync && uv run main.py

# 3. Run a demo
cd ../S9SharedCode
./run_demo.sh wipe && ./run_demo.sh hfmodels

# 4. View reports
python3 replay_viewer.py              # 8-section report → report.html
python3 io_replay_viewer.py           # per-node I/O trace → io_report.html
```

## Layout

```
S9SharedCode/
├── run_demo.sh           # Demo runner (hello, hfmodels, cnc, aitools, …)
├── run_assignment.sh     # Assignment comparison tasks + report
├── replay_viewer.py      # 8-section HTML replay
├── io_replay_viewer.py   # Input / output / thinking per node
├── ARCHITECTURE.md       # Short architecture note
├── logs/                 # Demo stdout (gitignored except .gitkeep)
└── code/
    ├── flow.py           # Orchestrator (growing DAG)
    ├── skills.py         # Skill dispatch + planner MCP tools
    ├── browser/          # Four-layer browser cascade
    ├── prompts/          # Planner, browser, distiller, critic, formatter
    ├── demos.py          # Canonical demo registry
    ├── tests/            # pytest suite
    └── state/sessions/   # Run artifacts (gitignored per session)
```

## Demos

| Command | Task |
|---------|------|
| `./run_demo.sh hfmodels` | Top 3 HF text-gen models by likes |
| `./run_demo.sh cnc` | 5 CNC/VMC institutes in Bangalore |
| `./run_demo.sh aitools` | 5 AI coding tools pricing |
| `./run_demo.sh laptops` | 3 laptops under ₹80k |
| `./run_demo.sh wipe` | Clear sessions, FAISS, logs |

## Browser cascade

Cheap path first: **extract** → **deterministic** (if selectors) → **a11y** → **vision**.  
See [../docs/BROWSER_CASCADE.md](../docs/BROWSER_CASCADE.md) and [../README.md](../README.md).

## Tests

```bash
cd code && uv run pytest tests/ -q
```

## What not to commit

Secrets (`.env`), virtualenvs (`.venv/`), session runs (`state/sessions/s9-*`), logs, FAISS index, gateway SQLite DB. See [../docs/GIT.md](../docs/GIT.md).

Before committing from `Assignment 9/`:

```bash
./scripts/git-check.sh
```

## Docs

- [../README.md](../README.md) — full Assignment 9 overview  
- [../docs/SETUP.md](../docs/SETUP.md) — install & env  
- [../docs/GIT.md](../docs/GIT.md) — git workflow  
- [ARCHITECTURE.md](ARCHITECTURE.md) — DAG + replay sections  
