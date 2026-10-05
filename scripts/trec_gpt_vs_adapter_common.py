"""GPT-5.4 vs the trained 7B, same 2022 1-versus-2 pairs as 0.779.

Pairs are copied from trec_lora_eval_pairs.json test_2022, not redrawn.
v1 prompt only. 2021 and 2023 are not used.
The system does not say a patient qualifies.
"""

from __future__ import annotations

import json
from pathlib import Path

from trec_score_common import DATA, ELIG_SYSTEM_DIGIT, PACK

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
CONFIG = HERE / "trec_gpt_vs_adapter_config.json"
PAIRS = HERE / "trec_gpt_vs_adapter_pairs.json"
EVAL_PAIRS = HERE / "trec_lora_eval_pairs.json"
OLD_GPT = DATA / "frontier_elig_gpt.json"
GPT_SCORES = DATA / "gpt_vs_adapter_gpt.json"
RESULTS = DATA / "gpt_vs_adapter_results.json"
REPORT = ROOT / "docs" / "trec_gpt_vs_adapter.md"

GPT_MODEL = "gpt-5.4"
GPT_INPUT_USD = 2.50
GPT_OUTPUT_USD = 15.00
SPEND_CAP_USD = 20.0
V1_SYSTEM = ELIG_SYSTEM_DIGIT
BOOT_SEED = 20261004
N_BOOT = 5000


def load_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def load_pairs() -> dict:
    return json.loads(PAIRS.read_text(encoding="utf-8"))


def pair_rows(pairs: dict | None = None) -> list[dict]:
    rec = pairs or load_pairs()
    out = []
    for tid, bucket in (rec.get("topics") or {}).items():
        for nct, lab in bucket:
            out.append({"year": "2022", "topic": str(tid), "nct": nct, "label": int(lab)})
    return out
