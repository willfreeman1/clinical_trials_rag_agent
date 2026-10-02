"""Condition-field baseline vs keyword hybrid. 2021/2022 only.

Gates committed in 9ffa03b before any match rate. No 2023. No six-name
code. No trial text to an LLM. No reranker.
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_hybrid_common import (  # noqa: E402
    DATA,
    DEPTHS,
    SNAPSHOT,
    YEAR_SNAP,
    load_docs,
    load_topics,
    mean_ignore_none,
    pool_ids,
    qrels_by_topic,
    recall_at,
    rrf,
)
from trec_hybrid_eval import (  # noqa: E402
    QUERY_ENC,
    bm25_rank,
    build_bm25,
    dense_rank,
    encode_queries,
    fuse,
    load_keywords,
    topic_queries,
)

THRESHOLDS_COMMIT = "9ffa03b"
YEARS = (2021, 2022)
OUT = DATA / "trec_condition_baseline.json"
REPORT = Path(__file__).resolve().parents[1] / "docs" / "trec_condition_baseline.md"

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


def norm_text(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def tokens(s: str) -> set[str]:
    return {t for t in norm_text(s).split() if t not in STOP and len(t) >= 2}


def empty_conditions(conds) -> bool:
    if not conds:
        return True
    return all(not str(c).strip() for c in conds)


def pack_conditions(conds: list[str]) -> tuple[list[str], list[set[str]]]:
    norms, toks = [], []
    for raw in conds or []:
        n = norm_text(str(raw))
        norms.append(n)
        toks.append(tokens(str(raw)))
    return norms, toks


def strict_hit(term_n: str, cond_ns: list[str]) -> bool:
    if not term_n:
        return False
    return any(c == term_n for c in cond_ns if c)


def loose_hit(term_n: str, term_t: set[str], cond_ns: list[str], cond_ts: list[set[str]]) -> bool:
    if not term_n:
        return False
    for cn, ct in zip(cond_ns, cond_ts):
        if not cn:
            continue
        if cn == term_n:
            return True
        if term_n in cn or cn in term_n:
            return True
        if term_t and (term_t & ct):
            return True
    return False


def restrict_lists(rankings: list[list[str]], keep: set[str]) -> list[list[str]]:
    return [[d for d in ranking if d in keep] for ranking in rankings]


def reading(filter_r: float | None, retr_r: float | None) -> str:
    if filter_r is None or retr_r is None:
        return "n/a"
    if filter_r + 0.03 >= retr_r:
        return "within_3"
    if filter_r + 0.10 < retr_r:
        return "more_than_10_worse"
    return "between"


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def pts(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}"


def mean_int(values: list[int]) -> float:
    return sum(values) / len(values) if values else 0.0


def eval_year(year: int, keywords: dict, q_model, q_tok) -> dict:
    snap = YEAR_SNAP[year]
    meta = SNAPSHOT[snap]
    docs = load_docs(meta["docs"])
    ncts = [nct for nct in pool_ids(year) if nct in docs]
    ncts_set = set(ncts)
    qrels = qrels_by_topic(year)
    topics = load_topics(year)
    year_kw = keywords.get(str(year), {})
    print(f"year {year} collection {len(ncts)} topics {len(topics)}", flush=True)

    cond_pack = {}
    empty_ids = []
    for nct in ncts:
        conds = docs[nct].get("conditions") or []
        cond_pack[nct] = pack_conditions(conds)
        if empty_conditions(conds):
            empty_ids.append(nct)
    empty_set = set(empty_ids)

    bm25 = build_bm25(ncts, docs)
    idx_dir = DATA / f"index_{snap}"
    all_ncts = json.loads((idx_dir / "nctids.json").read_text(encoding="utf-8"))
    medcpt_all = np.load(idx_dir / "medcpt.npy")
    chunk_all = json.loads((idx_dir / "chunk_nct.json").read_text(encoding="utf-8"))
    chunk_vecs = []
    chunk_nct = []
    for vec, nct in zip(medcpt_all, chunk_all):
        if nct in ncts_set:
            chunk_vecs.append(vec)
            chunk_nct.append(nct)
    chunk_vecs = np.asarray(chunk_vecs)

    topn = len(ncts)
    pct6 = max(1, int(round(0.06 * len(ncts))))
    depths = list(DEPTHS) + [pct6]

    per_topic = []
    judged = [tid for tid in topics if qrels.get(tid)]
    for tid in judged:
        labels = qrels[tid]
        eligible = {n for n, r in labels.items() if r == 2 and n in ncts_set}
        relevant = {n for n, r in labels.items() if r >= 1 and n in ncts_set}
        kw_row = year_kw.get(tid) or {}
        kw_queries = topic_queries(topics[tid], kw_row, "kw")
        disease = (kw_row.get("keywords") or [None])[0] or ""
        term_n = norm_text(disease)
        term_t = tokens(disease)

        strict_ids = []
        loose_ids = []
        for nct in ncts:
            cns, cts = cond_pack[nct]
            if strict_hit(term_n, cns):
                strict_ids.append(nct)
            if loose_hit(term_n, term_t, cns, cts):
                loose_ids.append(nct)
        strict_set = set(strict_ids)
        loose_set = set(loose_ids)

        q_kw = encode_queries(kw_queries, q_model, q_tok)
        bm25_kw = bm25_rank(bm25, ncts, kw_queries, topn)
        med_kw = dense_rank(q_kw, chunk_vecs, ncts, chunk_nct, topn)
        hybrid = fuse(bm25_kw + med_kw)
        combo = fuse(restrict_lists(bm25_kw, loose_set) + restrict_lists(med_kw, loose_set))

        def filter_stats(kept: list[str]) -> dict:
            kept_set = set(kept)
            k = len(kept_set)
            elig_hit = len(kept_set & eligible)
            return {
                "retained": k,
                "share_of_pool": k / len(ncts) if ncts else None,
                "eligible_recall": (elig_hit / len(eligible)) if eligible else None,
                "eligible_in_filter": elig_hit,
                "n_eligible": len(eligible),
                "hybrid_at_k": recall_at(hybrid, eligible, k) if eligible else None,
                "zero_retain": k == 0,
            }

        strict_s = filter_stats(strict_ids)
        loose_s = filter_stats(loose_ids)
        missed = sorted(eligible - loose_set)
        miss_examples = []
        for nct in missed[:8]:
            miss_examples.append(
                {
                    "nct_id": nct,
                    "conditions": docs[nct].get("conditions") or [],
                    "title": (docs[nct].get("title") or "")[:160],
                    "empty_conditions": nct in empty_set,
                }
            )
        empty_eligible = sum(1 for n in eligible if n in empty_set)
        combo_recalls = {str(d): recall_at(combo, eligible, d) for d in depths}
        hybrid_recalls = {str(d): recall_at(hybrid, eligible, d) for d in depths}

        row = {
            "topic": tid,
            "disease_term": disease,
            "n_keywords": len(kw_queries),
            "n_eligible": len(eligible),
            "n_relevant": len(relevant),
            "empty_eligible": empty_eligible,
            "strict": strict_s,
            "loose": loose_s,
            "hybrid_at_6pct": recall_at(hybrid, eligible, pct6) if eligible else None,
            "combo_at_6pct": recall_at(combo, eligible, pct6) if eligible else None,
            "combo_eligible_recalls": combo_recalls,
            "hybrid_eligible_recalls": hybrid_recalls,
            "loose_miss_examples": miss_examples,
            "loose_vs_hybrid_k": reading(loose_s["eligible_recall"], loose_s["hybrid_at_k"]),
        }
        per_topic.append(row)
        print(
            f"  {year} topic {tid} term={disease!r} loose={loose_s['retained']} "
            f"elig={pct(loose_s['eligible_recall'])} hyb@k={pct(loose_s['hybrid_at_k'])}",
            flush=True,
        )

    def agg_filter(key: str) -> dict:
        rec = [r[key]["eligible_recall"] for r in per_topic]
        hyb = [r[key]["hybrid_at_k"] for r in per_topic]
        retained = [r[key]["retained"] for r in per_topic]
        shares = [r[key]["share_of_pool"] for r in per_topic]
        zero = sum(1 for r in per_topic if r[key]["zero_retain"])
        micro_hit = sum(r[key]["eligible_in_filter"] for r in per_topic)
        micro_n = sum(r[key]["n_eligible"] for r in per_topic)
        filt_mean = mean_ignore_none(rec)
        hyb_mean = mean_ignore_none(hyb)
        return {
            "mean_retained": mean_int(retained),
            "median_retained": float(np.median(retained)) if retained else 0.0,
            "mean_share_of_pool": mean_ignore_none(shares),
            "mean_eligible_recall": filt_mean,
            "mean_hybrid_at_k": hyb_mean,
            "gap_points": None
            if filt_mean is None or hyb_mean is None
            else hyb_mean - filt_mean,
            "reading": reading(filt_mean, hyb_mean),
            "zero_retain_topics": zero,
            "zero_retain_wilson": wilson(zero, len(per_topic)),
            "micro_eligible_recall": (micro_hit / micro_n) if micro_n else None,
            "micro_eligible_wilson": wilson(micro_hit, micro_n) if micro_n else None,
        }

    def mean_depth(field: str) -> dict:
        out = {}
        for d in depths:
            out[str(d)] = mean_ignore_none([r[field].get(str(d)) for r in per_topic])
        return out

    empty_eligible_n = sum(r["empty_eligible"] for r in per_topic)
    eligible_n = sum(r["n_eligible"] for r in per_topic)
    losses = [
        r
        for r in per_topic
        if r["loose"]["eligible_recall"] is not None
        and r["loose"]["hybrid_at_k"] is not None
        and r["loose"]["eligible_recall"] + 0.10 < r["loose"]["hybrid_at_k"]
    ]
    return {
        "n_collection": len(ncts),
        "pct6": pct6,
        "n_topics": len(per_topic),
        "empty_conditions_trials": len(empty_ids),
        "empty_conditions_share": len(empty_ids) / len(ncts) if ncts else None,
        "empty_eligible_trials": empty_eligible_n,
        "empty_eligible_share": (empty_eligible_n / eligible_n) if eligible_n else None,
        "strict": agg_filter("strict"),
        "loose": agg_filter("loose"),
        "combo_eligible_at_depth": mean_depth("combo_eligible_recalls"),
        "hybrid_eligible_at_depth": mean_depth("hybrid_eligible_recalls"),
        "mean_combo_at_6pct": mean_ignore_none([r["combo_at_6pct"] for r in per_topic]),
        "mean_hybrid_at_6pct": mean_ignore_none([r["hybrid_at_6pct"] for r in per_topic]),
        "loose_losses": [
            {
                "topic": r["topic"],
                "disease_term": r["disease_term"],
                "retained": r["loose"]["retained"],
                "eligible_recall": r["loose"]["eligible_recall"],
                "hybrid_at_k": r["loose"]["hybrid_at_k"],
                "n_eligible": r["n_eligible"],
                "empty_eligible": r["empty_eligible"],
                "miss_examples": r["loose_miss_examples"],
            }
            for r in losses
        ],
        "topics": per_topic,
    }


def write_report(results: dict) -> None:
    lines = [
        "# TREC condition-field baseline (2021/2022 only)",
        "",
        f"Gates committed in `{THRESHOLDS_COMMIT}` before any match rate or matched-depth recall.",
        "2023 was not run. No six-name code. No trial text to an LLM. No reranker.",
        "Disease term is the first already-generated keyword. Strict is normalised equality.",
        "Loose is strict, or substring either way, or token overlap.",
        "Keyword hybrid is the same BM25 + MedCPT + RRF as `docs/trec_hybrid_retrieval.md`.",
        "Combination is the loose filter first, then that hybrid inside the survivors.",
        "",
        "## Empty or unmatchable",
        "",
        "| Year | Pool trials with empty conditions | Eligible trials with empty conditions | Patients with zero loose matches |",
        "|---|---:|---:|---:|",
    ]
    for year in YEARS:
        y = results["years"][str(year)]
        zw = y["loose"]["zero_retain_wilson"] or {}
        zero = f"{y['loose']['zero_retain_topics']}/{y['n_topics']}"
        if "low" in zw:
            zero += f" ({zw['low']:.1%}–{zw['high']:.1%})"
        lines.append(
            f"| {year} | {y['empty_conditions_trials']}/{y['n_collection']} "
            f"({pct(y['empty_conditions_share'])}) | "
            f"{y['empty_eligible_trials']} ({pct(y['empty_eligible_share'])}) | {zero} |"
        )

    lines += [
        "",
        "## Filter vs keyword hybrid at matched depth",
        "",
        "Per patient, *k* is how many trials the filter kept. Hybrid is scored at that same *k*.",
        "Headline reading is from **loose**.",
        "",
        "| Year | Strength | Mean *k* | Mean share of pool | Filter eligible recall | Hybrid @ *k* | Gap | Reading |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for year in YEARS:
        y = results["years"][str(year)]
        for strength in ("strict", "loose"):
            a = y[strength]
            lines.append(
                f"| {year} | {strength} | {a['mean_retained']:.1f} | "
                f"{pct(a['mean_share_of_pool'])} | {pct(a['mean_eligible_recall'])} | "
                f"{pct(a['mean_hybrid_at_k'])} | {pts(a['gap_points'])} pts | {a['reading']} |"
            )

    lines += [
        "",
        "## Combination (loose filter, then keyword hybrid)",
        "",
        "| Year | Hybrid @ 6% of pool | Combo @ 6% of pool | Loose filter recall (all survivors) |",
        "|---|---:|---:|---:|",
    ]
    for year in YEARS:
        y = results["years"][str(year)]
        lines.append(
            f"| {year} | {pct(y['mean_hybrid_at_6pct'])} | {pct(y['mean_combo_at_6pct'])} | "
            f"{pct(y['loose']['mean_eligible_recall'])} |"
        )

    lines += [
        "",
        "## Combination and hybrid at fixed depths (eligible recall)",
        "",
        "| Year | System | @10 | @20 | @50 | @100 | @200 | @500 | @6% |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for year in YEARS:
        y = results["years"][str(year)]
        p6 = str(y["pct6"])
        for name, field in (("hybrid", "hybrid_eligible_at_depth"), ("combo", "combo_eligible_at_depth")):
            s = y[field]
            lines.append(
                f"| {year} | {name} | {pct(s.get('10'))} | {pct(s.get('20'))} | "
                f"{pct(s.get('50'))} | {pct(s.get('100'))} | {pct(s.get('200'))} | "
                f"{pct(s.get('500'))} | {pct(s.get(p6))} |"
            )

    lines += [
        "",
        "## Reading",
        "",
        results["verdict"],
        "",
        "## Patients the loose filter loses by more than 10 points",
        "",
    ]
    any_loss = False
    for year in YEARS:
        losses = results["years"][str(year)]["loose_losses"]
        if not losses:
            lines.append(f"{year}: none.")
            lines.append("")
            continue
        any_loss = True
        lines.append(f"### {year} ({len(losses)} topics)")
        lines.append("")
        for row in losses:
            lines.append(
                f"- **Topic {row['topic']}** `{row['disease_term']}`: "
                f"filter {pct(row['eligible_recall'])} vs hybrid {pct(row['hybrid_at_k'])} "
                f"at k={row['retained']}; {row['n_eligible']} eligible, "
                f"{row['empty_eligible']} with empty conditions."
            )
            for ex in row["miss_examples"][:4]:
                cond = "; ".join(ex["conditions"]) or "(empty)"
                lines.append(f"  - {ex['nct_id']}: {cond}")
        lines.append("")
    if not any_loss:
        lines.append("No topic was more than 10 points behind hybrid at matched depth.")
        lines.append("")

    lines += [
        "## Per patient",
        "",
        "| Year | Topic | Disease term | Loose *k* | Share | Filter recall | Hybrid @ *k* | Combo @ 6% |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for year in YEARS:
        for r in results["years"][str(year)]["topics"]:
            lines.append(
                f"| {year} | {r['topic']} | {r['disease_term']} | "
                f"{r['loose']['retained']} | {pct(r['loose']['share_of_pool'])} | "
                f"{pct(r['loose']['eligible_recall'])} | {pct(r['loose']['hybrid_at_k'])} | "
                f"{pct(r['combo_at_6pct'])} |"
            )
    lines += [
        "",
        "Per-topic JSON, including strict rows and missed eligible examples, is in "
        "`data/trec/trec_condition_baseline.json`.",
        "No overall accuracy. The system does not say a patient qualifies.",
        "",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    keywords = load_keywords()
    print(f"loading {QUERY_ENC}", flush=True)
    q_tok = AutoTokenizer.from_pretrained(QUERY_ENC)
    q_model = AutoModel.from_pretrained(QUERY_ENC)
    q_model.eval()
    years = {}
    for year in YEARS:
        years[str(year)] = eval_year(year, keywords, q_model, q_tok)

    readings = {y: years[str(y)]["loose"]["reading"] for y in YEARS}
    bits = []
    for year in YEARS:
        a = years[str(year)]["loose"]
        bits.append(
            f"{year}: loose filter {pct(a['mean_eligible_recall'])} vs hybrid "
            f"{pct(a['mean_hybrid_at_k'])} at matched depth ({a['reading']}; "
            f"mean k={a['mean_retained']:.0f})."
        )
    if all(r == "within_3" for r in readings.values()):
        verdict = (
            "STOP reading retrieval as a first stage. The free conditions field "
            "comes within 3 points of keyword hybrid at matched depth on both "
            "years. Retrieval is not earning itself; it is a database query with "
            "extra steps. " + " ".join(bits)
        )
    elif any(r == "more_than_10_worse" for r in readings.values()):
        verdict = (
            "Retrieval is doing real work beyond disease matching on at least "
            "one year. Patients the loose filter loses by more than 10 points "
            "are listed below. " + " ".join(bits)
        )
    else:
        verdict = (
            "Between the 3-point and 10-point bands. Report both numbers, and "
            "report the filter's retained-trial count: a cheaper filter at "
            "similar recall is still the better first stage. " + " ".join(bits)
        )

    slim_years = {}
    for year, pack in years.items():
        topics_slim = []
        for r in pack["topics"]:
            topics_slim.append(
                {
                    "topic": r["topic"],
                    "disease_term": r["disease_term"],
                    "n_eligible": r["n_eligible"],
                    "empty_eligible": r["empty_eligible"],
                    "strict": r["strict"],
                    "loose": r["loose"],
                    "hybrid_at_6pct": r["hybrid_at_6pct"],
                    "combo_at_6pct": r["combo_at_6pct"],
                    "loose_vs_hybrid_k": r["loose_vs_hybrid_k"],
                    "loose_miss_examples": r["loose_miss_examples"],
                }
            )
        slim_years[year] = {k: v for k, v in pack.items() if k != "topics"}
        slim_years[year]["topics"] = topics_slim

    results = {
        "thresholds_commit": THRESHOLDS_COMMIT,
        "years_run": list(YEARS),
        "year_2023": "not_run",
        "disease_term": "first_keyword",
        "snapshots": {"2021": "2021-04-27", "2022": "2021-04-27"},
        "years": slim_years,
        "readings": readings,
        "verdict": verdict,
    }
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    write_report(results)
    print(verdict, flush=True)
    print(f"wrote {OUT} and {REPORT}", flush=True)


if __name__ == "__main__":
    with torch.no_grad():
        main()
