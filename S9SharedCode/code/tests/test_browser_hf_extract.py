"""HF layer-1 extract gate — reject noisy listing text missing model ids."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "extract_utils", _root / "browser" / "extract_utils.py")
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
is_useful_extract = _mod.is_useful_extract

HF_URL = "https://huggingface.co/models?pipeline_tag=text-generation&sort=likes"
HF_GOAL = "Read the visible model listing. Extract the top 3 model cards."

NOISY_ONE_MODEL = """deepseek-ai/DeepSeek-R1
Text Generation • 685B • Updated • 5.59M • • 13.4k
Text Generation • 8B • Updated • 1.19M • • 6.57k
Text Generation • 8B • Updated • 9.87M • • 6.06k
""" + ("Text Generation • 8B • Updated • 1.19M • • 6.57k\n" * 20)


def test_hf_noisy_extract_rejected_when_few_model_ids() -> None:
    assert not is_useful_extract(NOISY_ONE_MODEL, HF_GOAL, url=HF_URL)


def test_hf_extract_accepted_with_three_model_ids() -> None:
    content = NOISY_ONE_MODEL + """
meta-llama/Llama-3.1-8B
mistralai/Mistral-7B-v0.3
"""
    assert is_useful_extract(content, HF_GOAL, url=HF_URL)
