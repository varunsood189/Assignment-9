"""Canonical demo registry for run_demo.sh tasks.

Exposed to the Planner via MCP tools (list_demos, get_demo, get_hf_models_url).
Single source of truth for demo queries and recommended browser URLs/goals.
"""

from __future__ import annotations

from urllib.parse import urlencode

# pipeline_tag values match huggingface.co/models filter API
HF_DEFAULT_PIPELINE = "text-generation"
HF_DEFAULT_SORT = "likes"


def hf_models_url(
    pipeline_tag: str = HF_DEFAULT_PIPELINE,
    sort: str = HF_DEFAULT_SORT,
) -> str:
    """Pre-filtered HuggingFace models listing (avoids interactive filter clicks)."""
    return f"https://huggingface.co/models?{urlencode({'pipeline_tag': pipeline_tag, 'sort': sort})}"


def hf_models_goal(*, limit: int = 3) -> str:
    return (
        f"Read the visible model listing (already filtered and sorted). "
        f"Extract the top {limit} model cards: name, organisation, likes, "
        f"parameter count if listed, and a one-line description."
    )


DEMO_REGISTRY: dict[str, dict] = {
    "hello": {
        "query": "hello",
        "shape": "planner -> formatter",
    },
    "shannon": {
        "query": (
            "When was Claude Shannon born and when did he die? "
            "Name three of his contributions to information theory."
        ),
        "shape": "planner -> researcher -> formatter",
    },
    "populations": {
        "query": (
            "Find the populations of London, Paris, Berlin and tell me "
            "which two are closest in size."
        ),
        "shape": "planner -> researcher x 3 (parallel) -> formatter",
    },
    "structured": {
        "query": (
            "Compare the populations of Mumbai, Cairo, and Lagos and identify "
            "which is growing fastest. Return structured fields per city."
        ),
        "shape": "planner -> researcher x N -> distiller -> CRITIC -> formatter",
    },
    "fail": {
        "query": "Summarise the contents of /nonexistent/path.txt for me.",
        "shape": "planner -> formatter (graceful fail)",
    },
    "browser": {
        "query": (
            "What are the top 3 most-liked open-source LLM releases on "
            "Hugging Face from the past week? For each give model name, "
            "parameter count, and one-line description."
        ),
        "shape": "planner -> browser -> distiller? -> formatter",
    },
    "laptops": {
        "query": (
            "Compare 3 popular laptops available in India under ₹80,000. "
            "For each laptop give the model name, key specs (CPU, RAM, storage, "
            "display), price in INR, and one-line verdict on who it is best for."
        ),
        "shape": "planner -> researcher x 3 (parallel) -> formatter",
        "browser_hint": {
            "url": "https://www.smartprix.com/laptops/best-laptops-under-80000-list",
            "goal": (
                "Extract the top 3 laptops: model name, CPU, RAM, storage, "
                "display, price in INR."
            ),
        },
    },
    "aitools": {
        "query": (
            "Compare 5 AI coding assistant tools: GitHub Copilot, Cursor, "
            "Tabnine, Codeium, and Amazon CodeWhisperer. For each tool provide: "
            "free plan features, paid plan price and features, and supported IDEs."
        ),
        "shape": "planner -> browser x 5 (parallel) -> distiller -> CRITIC -> formatter",
    },
    "hfmodels": {
        "query": (
            "What are the top 3 text-generation models on Hugging Face sorted "
            "by most likes? For each give the model name, organisation, number "
            "of likes, parameter count if listed, and a one-line description "
            "of what it is good for."
        ),
        "shape": "planner -> browser -> distiller -> CRITIC -> formatter",
        "browser_hint": {
            "url": hf_models_url(),
            "goal": hf_models_goal(),
            "url_interactive_fallback": "https://huggingface.co/models",
            "goal_interactive": (
                "Filter Tasks=Text Generation, Sort=Most Likes; extract top 3 "
                "model cards with name, organisation, likes, parameter count, "
                "and description."
            ),
        },
    },
    "cnc": {
        "query": (
            "Compare 5 CNC and VMC operator training institutes in Bangalore. "
            "For each institute give the name, location, course duration, "
            "approximate fees, and whether they offer placement support."
        ),
        "shape": "planner -> browser -> distiller -> CRITIC -> formatter",
        "browser_hint": {
            "url": "https://www.sulekha.com/cnc-programming-training/bangalore",
            "goal": (
                "Scroll the institute listing. Extract 5 CNC/VMC training "
                "institutes in Bangalore: name, location/area, course duration, "
                "approximate fees, and whether placement support is offered."
            ),
            "fallback_url": (
                "https://www.sulekha.com/cnc-programming-training/bangalore"
            ),
            "note": (
                "Avoid justdial.com — Playwright often fails with "
                "ERR_HTTP2_PROTOCOL_ERROR / bot blocks. Prefer Sulekha listing."
            ),
        },
        "distiller_question": (
            "Extract name, location, course duration, approximate fees, and "
            "placement support for 5 CNC/VMC training institutes."
        ),
    },
}


def get_cnc_browser_url(*, use_fallback: bool = False) -> dict:
    """Canonical browser URL/goal for the CNC Bangalore institutes demo."""
    hint = DEMO_REGISTRY["cnc"]["browser_hint"]
    url = hint["fallback_url"] if use_fallback else hint["url"]
    return {
        "url": url,
        "goal": hint["goal"],
        "distiller_question": DEMO_REGISTRY["cnc"]["distiller_question"],
        "note": hint["note"],
    }


def list_demos() -> list[str]:
    return sorted(DEMO_REGISTRY)


def get_demo(name: str) -> dict:
    key = name.strip().lower()
    if key not in DEMO_REGISTRY:
        known = ", ".join(list_demos())
        raise KeyError(f"unknown demo {name!r}; known: {known}")
    entry = DEMO_REGISTRY[key]
    out = {
        "name": key,
        "query": entry["query"],
        "shape": entry["shape"],
    }
    if hint := entry.get("browser_hint"):
        out["browser_hint"] = dict(hint)
    return out


def get_hf_models_url(
    pipeline_tag: str = HF_DEFAULT_PIPELINE,
    sort: str = HF_DEFAULT_SORT,
) -> dict:
    url = hf_models_url(pipeline_tag=pipeline_tag, sort=sort)
    return {
        "url": url,
        "pipeline_tag": pipeline_tag,
        "sort": sort,
        "goal": hf_models_goal(),
        "note": (
            "Use this URL in browser metadata when interactive filter clicks "
            "fail or hit the step cap. Page is pre-sorted; read visible cards only."
        ),
    }
