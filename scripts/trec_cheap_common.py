"""Cheap topical pass helpers. Gates committed before any keep/drop score.

2021/2022 only. Shortlist is already computed. This pass may drop trials.
Uncertainty keeps. Full criteria is not the default document text.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "trec"
SAMPLE = DATA / "cheap_pass_sample.json"
SHORTLIST = DATA / "rerank_shortlists.json"
KEYWORDS = DATA / "keywords.json"
GPU_SCORES = DATA / "cheap_pass_gpu.json"
MINI_SCORES = DATA / "cheap_pass_mini.json"
LEXICAL_SCORES = DATA / "cheap_pass_lexical.json"
RESULTS = DATA / "cheap_pass_results.json"
PACK = DATA / "cheap_pass_pack.json"
REPORT = ROOT / "docs" / "trec_cheap_pass.md"

YEARS = (2021, 2022)
SEED = 20261001
PER_YEAR = 15
RECALL_SHIP = 0.90
RECALL_STOP = 0.80
RETENTION_MAX = 0.50
CE_KEEP_LOGIT = 0.0
ELIG_SLICE_CHARS = 800
RETRIEVAL_ELIGIBLE = {2021: 0.916, 2022: 0.914}
FULL_DEPTH = {2021: 1570, 2022: 1595}
QWEN_MODEL = "Qwen/Qwen2.5-7B-Instruct"
CE_MODEL = "ncbi/MedCPT-Cross-Encoder"
MINI_MODEL = "gpt-4o-mini"
MINI_INPUT_USD = 0.15
MINI_OUTPUT_USD = 0.60

STOP = {
    "the",
    "a",
    "an",
    "of",
    "to",
    "for",
    "on",
    "in",
    "and",
    "or",
    "with",
    "by",
    "from",
    "into",
    "as",
    "at",
    "is",
    "are",
}

LLM_SYSTEM = """You decide whether a clinical-trial record could conceivably be about this patient's problem.

This is not an eligibility decision. Do not say whether the patient can join the trial.
Ask only: could this trial conceivably be about this patient's problem?

KEEP if the trial might be about any of the patient's main problems, a synonym, a parent condition, or a related disease area.
DROP only if the trial is clearly about a different disease or situation.
UNSURE if you cannot tell. Unsure keeps the trial.

Return only JSON: {"decisions": [{"nct_id": "...", "decision": "keep"}, ...]}
decision must be keep, drop, or unsure."""


def load_sample() -> dict:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def load_shortlist() -> dict:
    return json.loads(SHORTLIST.read_text(encoding="utf-8"))


def load_keywords() -> dict:
    return json.loads(KEYWORDS.read_text(encoding="utf-8"))


def summary_query(kw_row: dict) -> str:
    return str((kw_row or {}).get("summary") or "").strip() or " "


def first_keyword(kw_row: dict) -> str:
    kws = [str(k).strip() for k in (kw_row or {}).get("keywords") or [] if str(k).strip()]
    return kws[0] if kws else ""


def cond_list(row: dict) -> list[str]:
    raw = row.get("conditions") or []
    if isinstance(raw, str):
        return [raw] if raw.strip() else []
    return [str(c).strip() for c in raw if str(c).strip()]


def title_cond_text(row: dict) -> str:
    title = (row.get("title") or "").strip()
    conds = "; ".join(cond_list(row))
    parts = [p for p in (title, f"Conditions: {conds}" if conds else "") if p]
    return "\n".join(parts) or " "


def title_cond_slice_text(row: dict) -> str:
    base = title_cond_text(row)
    elig = (row.get("eligibility") or "").strip()[:ELIG_SLICE_CHARS]
    if elig:
        return f"{base}\nEligibility (opening):\n{elig}"
    return base


def title_body_text(row: dict) -> str:
    title = (row.get("title") or "").strip()
    body = (row.get("text") or "").strip()
    if title and body:
        return f"{title}\n{body}"
    return title or body or " "


DOC_TEXT = {
    "title_cond": title_cond_text,
    "title_cond_slice": title_cond_slice_text,
    "title_body_512": title_body_text,
}


def parse_llm_decision(raw) -> str:
    val = str(raw or "").strip().lower()
    if "drop" in val and "keep" not in val:
        return "drop"
    if "unsure" in val:
        return "unsure"
    if "keep" in val:
        return "keep"
    return "unsure"


def keep_from_decision(decision: str) -> bool:
    return decision != "drop"


def keep_from_ce_logit(logit: float | None) -> bool:
    if logit is None:
        return True
    return float(logit) > CE_KEEP_LOGIT


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


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def gate_label(recall: float | None, retention: float | None) -> str:
    if recall is None or retention is None:
        return "n/a"
    if recall < RECALL_STOP:
        return "reject_recall"
    if recall < RECALL_SHIP:
        return "mixed_recall"
    if retention > RETENTION_MAX:
        return "fail_retention"
    return "clears"


def topic_counts(shortlist: list[str], labels: dict[str, int], kept: set[str]) -> dict:
    relevant = {n for n, r in labels.items() if r >= 1 and n in shortlist}
    eligible = {n for n, r in labels.items() if r == 2 and n in shortlist}
    kept_rel = relevant & kept
    kept_elig = eligible & kept
    return {
        "n_short": len(shortlist),
        "n_kept": len(kept),
        "n_relevant": len(relevant),
        "n_relevant_kept": len(kept_rel),
        "n_eligible": len(eligible),
        "n_eligible_kept": len(kept_elig),
        "recall": (len(kept_rel) / len(relevant)) if relevant else None,
        "eligible_recall": (len(kept_elig) / len(eligible)) if eligible else None,
        "retention": (len(kept) / len(shortlist)) if shortlist else None,
    }


def pooled_from_topics(rows: list[dict]) -> dict:
    rel_k = sum(r["n_relevant_kept"] for r in rows)
    rel_n = sum(r["n_relevant"] for r in rows)
    elig_k = sum(r["n_eligible_kept"] for r in rows)
    elig_n = sum(r["n_eligible"] for r in rows)
    kept = sum(r["n_kept"] for r in rows)
    short = sum(r["n_short"] for r in rows)
    recalls = [r["recall"] for r in rows if r["recall"] is not None]
    rets = [r["retention"] for r in rows if r["retention"] is not None]
    eligs = [r["eligible_recall"] for r in rows if r["eligible_recall"] is not None]
    recall = (rel_k / rel_n) if rel_n else None
    retention = (kept / short) if short else None
    return {
        "n_topics": len(rows),
        "n_short": short,
        "n_kept": kept,
        "n_relevant": rel_n,
        "n_relevant_kept": rel_k,
        "n_eligible": elig_n,
        "n_eligible_kept": elig_k,
        "recall_micro": recall,
        "recall_macro": mean(recalls),
        "eligible_recall_micro": (elig_k / elig_n) if elig_n else None,
        "eligible_recall_macro": mean(eligs),
        "retention_micro": retention,
        "retention_macro": mean(rets),
        "recall_wilson": wilson(rel_k, rel_n),
        "retention_wilson": wilson(kept, short),
        "gate": gate_label(recall, retention),
    }


def openai_key() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENAI_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("OPENAI_API_KEY is missing")


def norm_text(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def tokens(s: str) -> set[str]:
    return {t for t in norm_text(s).split() if t not in STOP and len(t) >= 2}


def loose_hit(term: str, texts: list[str]) -> bool:
    term_n = norm_text(term)
    term_t = tokens(term)
    if not term_n:
        return False
    for raw in texts:
        cn = norm_text(raw)
        ct = tokens(raw)
        if not cn:
            continue
        if cn == term_n or term_n in cn or cn in term_n:
            return True
        if term_t and (term_t & ct):
            return True
    return False
