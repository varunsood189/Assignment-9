# Setup

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Chromium for Playwright

## 1. Clone and configure secrets

```bash
cd "Assignment 9"
cp .env.example .env
# Edit .env — minimum: GEMINI_API_KEY=...
# For researcher demos: TAVILY_API_KEY=...
```

Never commit `.env`. Only `.env.example` is tracked.

## 2. Install S9SharedCode

```bash
cd S9SharedCode/code
uv sync
uv run playwright install chromium
```

Optional: copy `code/.env.example` → `code/.env` if you keep code-local overrides.

## 3. Install and start llm_gatewayV9

```bash
cd ../../llm_gatewayV9   # from S9SharedCode/code
uv sync
uv run main.py           # listens on http://localhost:8109
```

Verify:

```bash
curl -s http://localhost:8109/health || curl -s http://localhost:8109/docs
```

## 4. Run

```bash
cd ../S9SharedCode
./run_demo.sh hfmodels
python3 replay_viewer.py
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `lxml` build fails / “libxml2 and libxslt development packages” | Use Python 3.12 (not 3.14): `uv python install 3.12 && uv sync --python 3.12`. If you must stay on 3.14: `sudo apt install libxml2-dev libxslt1-dev python3-dev build-essential` then retry `uv sync`. |
| `Executable doesn't exist` (Playwright) | `cd code && uv run playwright install chromium` |
| No LLM output / 502 | Gateway not running on `:8109` |
| JustDial / HTTP2 errors on CNC | Use Sulekha URL via `get_cnc_browser_url()` — see demos.py |
| Stale FAISS hits from old demos | `./run_demo.sh wipe` before a clean run |

## Provider routing

All skills route through **llm_gatewayV9** on port **8109**. Agent pins live in `llm_gatewayV9/agent_routing.yaml`. Default in this repo: **Gemini** for planner, distiller, critic, formatter, and browser layers.
