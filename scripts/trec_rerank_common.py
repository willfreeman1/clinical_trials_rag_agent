"""Shared TREC rerank helpers. Gates committed in 44878a7.

2021/2022 only. Reorder the keyword-hybrid shortlist. Discard nothing.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "trec"
REPORT = ROOT / "docs" / "trec_rerank.md"
THRESHOLDS_COMMIT = "44878a7"
YEARS = (2021, 2022)
DEPTHS = (10, 20, 50, 100, 200)
LLM_YEAR = 2021
LLM_DEPTH = 200
LLM_MODEL = "gpt-4o-mini"
MEDCPT_CE = "ncbi/MedCPT-Cross-Encoder"
GENERIC_CE = "cross-encoder/ms-marco-MiniLM-L-12-v2"
SHORTLIST = DATA / "rerank_shortlists.json"
CE_SCORES = DATA / "rerank_ce_scores.json"
LLM_SCORES = DATA / "rerank_llm_scores.json"
OUT = DATA / "trec_rerank_results.json"

BASELINE_R10 = {2021: 0.057, 2022: 0.074}
BASELINE_FULL = {2021: 0.916, 2022: 0.914}
FULL_DEPTH = {2021: 1570, 2022: 1595}


def load_keywords() -> dict:
    return json.loads((DATA / "keywords.json").read_text(encoding="utf-8"))


def keyword_query(row: dict) -> str:
    summary = str((row or {}).get("summary") or "").strip()
    kws = [str(k).strip() for k in (row or {}).get("keywords") or [] if str(k).strip()]
    parts = []
    if summary:
        parts.append(summary)
    if kws:
        parts.append("; ".join(kws))
    return "\n".join(parts)


def trial_article(row: dict) -> str:
    title = (row.get("title") or "").strip()
    body = (row.get("text") or "").strip()
    if title and body:
        return f"{title}\n{body}"
    return title or body or " "


def dcg(rels: list[int]) -> float:
    return sum((2 ** rel - 1) / math.log2(i + 1) for i, rel in enumerate(rels, start=1))


def ndcg_at(ranked: list[str], labels: dict[str, int], depth: int) -> float | None:
    gained = [int(labels.get(nct, 0)) for nct in ranked[:depth]]
    ideal = sorted((int(v) for v in labels.values()), reverse=True)[:depth]
    denom = dcg(ideal)
    if denom <= 0:
        return None
    return dcg(gained) / denom


def recall_at(ranked: list[str], relevant: set[str], depth: int) -> float | None:
    if not relevant:
        return None
    hit = sum(1 for d in ranked[:depth] if d in relevant)
    return hit / len(relevant)


def precision_at(ranked: list[str], wanted: set[str], depth: int) -> float:
    top = ranked[:depth]
    if not top:
        return 0.0
    return sum(1 for d in top if d in wanted) / len(top)


def mean_ignore_none(values: list[float | None]) -> float | None:
    xs = [v for v in values if v is not None]
    return sum(xs) / len(xs) if xs else None


def wilson(successes: int, total: int, z: float = 1.96) -> dict | None:
    if total == 0:
        return None
    p = successes / total
    out = {"point": round(p, 4), "n": total, "k": successes}
    if total >= 200:
        out["wilson_omitted_n_ge_200"] = True
        return out
    z2 = z * z
    denom = 1 + z2 / total
    center = (p + z2 / (2 * total)) / denom
    margin = z * math.sqrt((p * (1 - p) + z2 / (4 * total)) / total) / denom
    out["low"] = round(max(0.0, center - margin), 4)
    out["high"] = round(min(1.0, center + margin), 4)
    return out


def rerank(shortlist: list[str], scores: dict[str, float]) -> list[str]:
    def key(nct: str) -> tuple[float, int]:
        return (scores.get(nct, float("-inf")), -shortlist.index(nct))

    return sorted(shortlist, key=key, reverse=True)


def stitch_prefix(shortlist: list[str], prefix: list[str]) -> list[str]:
    seen = set(prefix)
    return prefix + [n for n in shortlist if n not in seen]
