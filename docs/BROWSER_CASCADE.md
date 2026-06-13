# Browser four-layer cascade (reference)

Implemented in `S9SharedCode/code/browser/skill.py`.

```
                    page blocked?
                         │
                         ▼
              gateway_blocked ──► STOP (Planner recovery)
                         │
Layer 1  extract (httpx + trafilatura, $0 LLM)
         │ not useful?
         ▼
Layer 2a deterministic (Playwright + metadata.selectors, $0 LLM)
         │ no selectors or failed?
         ▼
Layer 2b a11y (Playwright + legend → /v1/chat)
         │ turn cap / no success?
         ▼
Layer 3  vision (set-of-marks → /v1/vision)
         │ exhausted?
         ▼
         interaction_failed
```

## Output field

Winning layer is recorded as `BrowserOutput.path`:

`extract` | `deterministic` | `a11y` | `vision`

Visible in terminal trace, session JSON, and `replay_viewer.py` §3.

## Assignment requirement

At least **three visible browser actions** (search, scroll, filter, click, etc.).  
Layer 2b/3 turn logs in `state/sessions/<sid>/browser/` satisfy this when extract alone is insufficient.

## Further reading

Full detail: [../README.md](../README.md) (§ Browser Skill — Four-Layer Cascade).
