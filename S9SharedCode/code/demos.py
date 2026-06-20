"""Canonical demo registry for run_demo.sh tasks.

Exposed to the Planner via MCP tools (list_demos, get_demo, get_hf_models_url).
Single source of truth for demo queries and recommended browser URLs/goals.
"""

from __future__ import annotations

from urllib.parse import urlencode

# pipeline_tag values match huggingface.co/models filter API
HF_DEFAULT_PIPELINE = "text-generation"
HF_DEFAULT_SORT = "likes"
HF_BASE_URL = "https://huggingface.co/models"


def hf_models_url(
    pipeline_tag: str = HF_DEFAULT_PIPELINE,
    sort: str = HF_DEFAULT_SORT,
) -> str:
    """Pre-filtered HuggingFace models listing (recovery fallback only)."""
    return f"{HF_BASE_URL}?{urlencode({'pipeline_tag': pipeline_tag, 'sort': sort})}"


def hf_models_goal_interactive(*, limit: int = 3) -> str:
    """Goal that requires filter + sort + read — satisfies the 3+ action requirement."""
    return (
        f"On the Hugging Face models page, perform at least three visible browser "
        f"actions: (1) filter Tasks=Text Generation, (2) sort by Most Likes, "
        f"(3) read the top {limit} model cards. "
        f"For each card extract: name, organisation, likes, parameter count if "
        f"listed, and a one-line description. "
        f"Passive scraping from search snippets is not acceptable."
    )


def hf_models_goal(*, limit: int = 3) -> str:
    """Passive read goal — only for recovery when interactive widgets fail."""
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
            "by most likes? Use the browser on https://huggingface.co/models "
            "and perform at least three visible actions (filter, sort, read cards). "
            "For each give the model name, organisation, number of likes, "
            "parameter count if listed, and a one-line description of what it "
            "is good for."
        ),
        "shape": "planner -> browser -> distiller -> CRITIC -> formatter",
        "browser_hint": {
            "url": HF_BASE_URL,
            "goal": hf_models_goal_interactive(),
            "fallback_url": hf_models_url(),
            "fallback_goal": hf_models_goal(),
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
    # Session 10 — Computer skill assignment tasks
    "calc42": {
        "query": (
            "Open the Calculator app and compute 42 times 567. "
            "Report the numeric result shown on the display."
        ),
        "shape": "planner -> computer -> formatter",
        "computer_hint": {
            "app": "calculator",
            "launch": True,
            "launch_path": "gnome-calculator --mode=basic",
            "kill_existing": True,
            "workflow": "calculator-eval",
            "goal": "Compute the expression from USER_QUERY and read the display result.",
        },
    },
    "calca11y": {
        "query": (
            "Open Calculator in basic mode. Click the on-screen keypad buttons "
            "to compute 7 plus 3 (press 7, then plus, then 3, then equals). "
            "Do not type the expression with the keyboard. Report the numeric "
            "result on the display."
        ),
        "shape": "planner -> computer -> formatter",
        "computer_hint": {
            "app": "calculator",
            "launch": True,
            "launch_path": "gnome-calculator --mode=basic",
            "kill_existing": True,
            "goal": (
                "Click Calculator keypad buttons 7 + 3 = using the GUI only "
                "(no keyboard expression shortcut). Read the display result."
            ),
        },
    },
    "noteread": {
        "query": (
            "Read the file ~/assignment9-note.txt and return its full text verbatim."
        ),
        "shape": "planner -> computer -> formatter",
        "computer_hint": {
            "app": "desktop",
            "goal": "Read assignment9-note.txt via Layer-1 file extract (no LLM).",
            "files": ["~/assignment9-note.txt"],
        },
    },
    "vscodefiles": {
        "query": (
            "Open Visual Studio Code on the Assignment-9 project folder with "
            "remote debugging enabled, then list the top 3 file or folder names "
            "visible in the Explorer sidebar."
        ),
        "shape": "planner -> computer -> distiller -> formatter",
        "computer_hint": {
            "app": "vscode",
            "launch": True,
            "kill_existing": True,
            "electron_debugging_port": 9222,
            "open_path": "~/Documents/workspace/Assignment-9",
            "goal": (
                "List the top 3 entries in the VS Code Explorer sidebar via "
                "Electron CDP (metadata.electron_debugging_port=9222)."
            ),
        },
        "distiller_question": (
            "Extract the top 3 file or folder names from the VS Code Explorer sidebar."
        ),
    },
    "calcvision": {
        "query": (
            "Open Calculator and compute 99 times 99 by interacting with the "
            "on-screen buttons (do not use a typed expression shortcut). "
            "Report the result shown on the display."
        ),
        "shape": "planner -> computer -> formatter",
        "computer_hint": {
            "app": "calculator",
            "launch": True,
            "goal": (
                "Click Calculator keypad buttons to compute 99×99; escalate to "
                "a11y or vision layers as needed."
            ),
        },
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
    if hint := entry.get("computer_hint"):
        out["computer_hint"] = dict(hint)
    if dq := entry.get("distiller_question"):
        out["distiller_question"] = dq
    return out


def get_hf_models_url(
    pipeline_tag: str = HF_DEFAULT_PIPELINE,
    sort: str = HF_DEFAULT_SORT,
) -> dict:
    return {
        "url": HF_BASE_URL,
        "pipeline_tag": pipeline_tag,
        "sort": sort,
        "goal": hf_models_goal_interactive(),
        "fallback_url": hf_models_url(pipeline_tag=pipeline_tag, sort=sort),
        "fallback_goal": hf_models_goal(),
        "note": (
            "PRIMARY: base URL + interactive goal (filter Tasks, sort by likes, "
            "read cards — at least 3 visible browser actions). "
            "Use fallback_url + fallback_goal ONLY when filter widgets fail or "
            "the step cap is hit after one retry."
        ),
    }
