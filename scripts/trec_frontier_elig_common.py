"""Frontier vs Qwen eligibility on judged 1-vs-2 pairs.

Prompts and pair IDs are the record. No pass/fail gate. 2021/2022 only.
Patients: seed 20261001. Pair draw: seed 20261002, cap 7 per label per patient.
"""

from __future__ import annotations

import json
from pathlib import Path

from trec_score_common import (  # noqa: E402
    DATA,
    ELIG_SYSTEM_DIGIT,
    PACK,
    QWEN_SCORES,
    SAMPLE_TOPICS,
    YEARS,
    cond_list,
    load_qrels,
    load_shortlist,
)

ROOT = Path(__file__).resolve().parents[1]
PAIRS_PATH = Path(__file__).resolve().parent / "trec_frontier_elig_pairs.json"
REPORT = ROOT / "docs" / "trec_frontier_elig.md"
GPT_SCORES = DATA / "frontier_elig_gpt.json"
QWEN_NEW_SCORES = DATA / "frontier_elig_qwen_trec.json"

PATIENT_SEED = 20261001
PAIR_SEED = 20261002
CAP = 7
GPT_MODEL = "gpt-5.4"
GPT_INPUT_USD = 2.50
GPT_OUTPUT_USD = 15.00
QWEN_MODEL = "Qwen/Qwen2.5-7B-Instruct"

# Continuity baseline. Do not edit. Copied from trec_score_common.ELIG_SYSTEM_DIGIT.
V1_SYSTEM = ELIG_SYSTEM_DIGIT

# NIST wording: 2021 overview + qrels map + 2022 three-point bullets.
# Location and recruitment ignored per the 2022 overview.
TREC_SYSTEM = """You assign a TREC Clinical Trials label from the patient description and the trial text.

This is not a decision that the patient qualifies. Do not say the patient can join the trial.

Ignore whether the trial is still recruiting. Ignore where the trial is located.

Labels, as used by the TREC 2021/2022 assessors:

0 = not relevant. The patient is not relevant for the trial in any way.
1 = excluded. The patient has the condition that the trial is targeting and met the inclusion criteria, but one or more exclusion criteria make the patient ineligible.
2 = eligible. The patient met the inclusion criteria and did not meet any exclusion criteria.

Return JSON only, no other text:
{"label": 0, "p_eligible": 0.00}

label is exactly 0, 1, or 2.
p_eligible is your probability that the correct label is 2, from 0 to 1 inclusive, two decimal places."""


def full_criteria(row: dict) -> str:
    title = (row.get("title") or "").strip()
    conds = "; ".join(cond_list(row))
    parts = [p for p in (title, f"Conditions: {conds}" if conds else "") if p]
    base = "\n".join(parts) or " "
    elig = (row.get("eligibility") or "").strip()
    if elig:
        return f"{base}\nEligibility criteria:\n{elig}"
    body = (row.get("text") or "").strip()
    return f"{base}\nTrial text:\n{body}" if body else base


def user_text(note: str, doc: str) -> str:
    return f"Patient description:\n{note}\n\nTrial record:\n{doc}\n"


def load_pairs() -> dict:
    return json.loads(PAIRS_PATH.read_text(encoding="utf-8"))


def pair_rows(pairs: dict | None = None) -> list[dict]:
    rec = pairs or load_pairs()
    out = []
    for year, topics in (rec.get("years") or {}).items():
        for tid, bucket in topics.items():
            for nct, lab in bucket:
                out.append({"year": str(year), "topic": str(tid), "nct": nct, "label": int(lab)})
    return out
