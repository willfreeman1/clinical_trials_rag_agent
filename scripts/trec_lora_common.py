"""Shared split and scoring helpers for the eligibility LoRA work.

Splits were frozen in trec_lora_splits.json before any adapter is trained.
2023 is not used. The system does not say a patient qualifies.
"""

from __future__ import annotations

import json
from pathlib import Path

from trec_score_common import SAMPLE_TOPICS

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
SPLITS_PATH = HERE / "trec_lora_splits.json"
CONFIG_PATH = HERE / "trec_lora_config.json"
EVAL_PAIRS_PATH = HERE / "trec_lora_eval_pairs.json"
TRAIN_PAIRS_PATH = HERE / "trec_lora_train_pairs.json"
LOGIT_RESULTS = ROOT / "data" / "trec" / "trec_elig_logit.json"
BASE_SCORES = ROOT / "data" / "trec" / "score_qwen_elig_v1_base.json"
ADAPTER_SCORES = ROOT / "data" / "trec" / "score_qwen_elig_lora.json"
ADAPTER_DIR = ROOT / "data" / "trec" / "lora_adapter"
BASE_RESULTS = ROOT / "data" / "trec" / "trec_lora_base_results.json"
JUNK_PAIRS_PATH = HERE / "trec_lora_junk_pairs.json"
JUNK_SCORES = ROOT / "data" / "trec" / "score_qwen_elig_lora_junk.json"
CI_RESULTS = ROOT / "data" / "trec" / "trec_lora_ci.json"
ADAPTER_LR1E5 = ROOT / "data" / "trec" / "lora_adapter_lr1e5"

FEATURE_NAMES = (
    "topical_title_cond_digit",
    "topical_title_cond_cont",
    "topical_slice_digit",
    "topical_slice_cont",
    "mini",
    "medcpt_ce_raw",
    "medcpt_ce_keywords",
    "rank_frac",
)


def load_splits() -> dict:
    raw = json.loads(SPLITS_PATH.read_text(encoding="utf-8"))
    if raw.get("dev_2021") != SAMPLE_TOPICS["2021"]:
        raise SystemExit("dev_2021 does not match SAMPLE_TOPICS 2021")
    if raw.get("eval_sample_2022") != SAMPLE_TOPICS["2022"]:
        raise SystemExit("eval_sample_2022 does not match SAMPLE_TOPICS 2022")
    return raw


def auroc(pos: list[float], neg: list[float]) -> float | None:
    if not pos or not neg:
        return None
    from sklearn.metrics import roc_auc_score

    y = [1] * len(pos) + [0] * len(neg)
    s = list(pos) + list(neg)
    return float(roc_auc_score(y, s))


def split_auroc(rows: list[dict], key: str) -> dict:
    pos = [r[key] for r in rows if r["label"] == 2 and r.get(key) is not None]
    neg = [r[key] for r in rows if r["label"] == 1 and r.get(key) is not None]
    by: dict[str, list[dict]] = {}
    for r in rows:
        if r.get(key) is None or r["label"] not in (1, 2):
            continue
        by.setdefault(r["tid"], []).append(r)
    per = []
    for group in by.values():
        p = [x[key] for x in group if x["label"] == 2]
        n = [x[key] for x in group if x["label"] == 1]
        val = auroc(p, n)
        if val is not None:
            per.append(val)
    return {
        "n1": len(neg),
        "n2": len(pos),
        "n_patients_both": len(per),
        "pooled": auroc(pos, neg),
        "macro": (sum(per) / len(per)) if per else None,
    }


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.3f}"
