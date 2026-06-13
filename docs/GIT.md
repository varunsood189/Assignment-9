# Git workflow — Assignment 9

Repo root: **`Assignment 9/`** (includes `S9SharedCode/` + `llm_gatewayV9/`).

## First-time setup

```bash
cd "Assignment 9"
cp .env.example .env          # fill GEMINI_API_KEY, TAVILY_API_KEY, etc.
cd S9SharedCode/code && uv sync && uv run playwright install chromium
cd ../../llm_gatewayV9 && uv sync
```

## Initialize git (if needed)

```bash
cd "Assignment 9"
git init
git add .
./scripts/git-check.sh        # must print PASS
git commit -m "Initial commit: Session 9 browser agent + gateway V9"
```

## What to commit

| Track | Examples |
|-------|----------|
| Source | `S9SharedCode/code/**/*.py`, `browser/`, `prompts/` |
| Runners | `run_demo.sh`, `run_assignment.sh`, `replay_viewer.py` |
| Tests | `code/tests/` |
| Lockfiles | `code/uv.lock`, `llm_gatewayV9/uv.lock` |
| Gateway | `llm_gatewayV9/*.py`, `agent_routing.yaml` |
| Docs | `README.md`, `ARCHITECTURE.md`, `docs/` |
| Templates | `.env.example`, `.gitkeep` placeholders |
| Sandbox papers | `code/sandbox/papers/*.md` |

## Never commit

| Ignore | Why |
|--------|-----|
| `.env`, `**/.env` | API keys |
| `**/.venv/` | `uv sync` recreates |
| `code/state/sessions/s9-*/` | Run artifacts, browser PNGs, node JSON |
| `code/state/memory.json`, `index.faiss` | FAISS memory (regenerated) |
| `S9SharedCode/logs/*.log`, `*_replay.html` | Demo output |
| `llm_gatewayV9/*.db` | Cost ledger |
| `usage.json`, `.last_session_id` | Runtime counters |

Empty dirs are kept via `.gitkeep`:

- `S9SharedCode/logs/.gitkeep`
- `S9SharedCode/code/state/sessions/.gitkeep`
- `S9SharedCode/code/state/artifacts/.gitkeep`

## Before every commit

```bash
cd "Assignment 9"
git status
git diff --stat
./scripts/git-check.sh
```

## After clone (regenerate ignored artifacts)

```bash
cp .env.example .env            # add keys
cd S9SharedCode/code && uv sync && uv run playwright install chromium
cd ../../llm_gatewayV9 && uv run main.py   # terminal 1
cd ../S9SharedCode && ./run_demo.sh hfmodels
# report.html is generated under code/state/sessions/<sid>/ (gitignored)
python3 replay_viewer.py
```

## Optional: export one session for submission

Session folders are gitignored by default. To attach a trace to a PR or zip:

```bash
cd S9SharedCode
./run_demo.sh hfmodels
SID=$(ls -t code/state/sessions | head -1)
tar czf "../submission-$SID.tgz" -C code/state/sessions "$SID"
```

Do **not** add the tarball to git if it contains API echoes in prompts.

## Line endings

`.gitattributes` forces LF for `*.py`, `*.sh`, `*.md`. On Windows, use `git config core.autocrlf input`.

## Standalone S9SharedCode copy

If you copy only `S9SharedCode/` elsewhere, its local `.gitignore` still excludes runtime state. You still need `llm_gatewayV9` (or set `LLM_GATEWAY_V9_URL`) and a `.env` with keys.
