"""Weighted fusion + section down-rank. Gates in c178dc4. Reorder existing shortlist.

2021/2022 only. Nothing discarded. No reader. No trained ranker.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parent))

from keyword_section_check import split_sections  # noqa: E402
from trec_hybrid_common import (  # noqa: E402
    RETRIEVE_N,
    RRF_K,
    SNAPSHOT,
    YEAR_SNAP,
    load_docs,
    load_topics,
    pool_ids,
    qrels_by_topic,
    recall_at,
    tokenize,
)
from trec_hybrid_eval import (  # noqa: E402
    QUERY_ENC,
    bm25_rank,
    build_bm25,
    dense_rank,
    encode_queries,
    topic_queries,
)
from trec_rerank_common import (  # noqa: E402
    DEPTHS,
    FULL_DEPTH,
    SHORTLIST,
    YEARS,
    mean_ignore_none,
)
from trec_rerank_eval import topic_metrics  # noqa: E402

THRESHOLDS_COMMIT = "c178dc4"
OUT = Path(__file__).resolve().parents[1] / "data" / "trec" / "trec_shortlist_fix.json"
REPORT = Path(__file__).resolve().parents[1] / "docs" / "trec_shortlist_fix.md"

STOP = {
    "the", "a", "an", "of", "to", "for", "on", "in", "and", "or", "with",
    "by", "from", "into", "as", "at", "is", "are",
}
OFFICIAL = ("baseline", "idf_rrf", "bm25_sum", "section_mult", "section_tie", "idf_section")


def content_tokens(text: str) -> list[str]:
    return [t for t in tokenize(text or "") if t not in STOP and len(t) >= 2]


def token_df(ncts: list[str], docs: dict) -> Counter:
    df: Counter = Counter()
    for nct in ncts:
        row = docs[nct]
        toks = set(tokenize((row.get("title") or "") + " " + (row.get("text") or "")))
        for t in toks:
            df[t] += 1
    return df


def keyword_idf(kw: str, df: Counter, n: int) -> float:
    toks = content_tokens(kw)
    if not toks:
        return 0.0
    return max(math.log((n + 1) / (df.get(t, 0) + 1)) for t in toks)


def norm(s: str) -> str:
    return " ".join(tokenize(s or ""))


def section_side(kw: str, eligibility: str) -> str:
    parts = split_sections(eligibility or "")
    if parts["mode"] == "no_header" or not (eligibility or "").strip():
        return "unsplit"
    needle = norm(kw)
    toks = set(content_tokens(kw))

    def hit(text: str) -> bool:
        if not text:
            return False
        nt = norm(text)
        if needle and needle in nt:
            return True
        if toks and toks <= set(tokenize(text)):
            return True
        return False

    in_i = hit(parts["inclusion"])
    in_e = hit(parts["exclusion"])
    if in_i and in_e:
        return "both"
    if in_e:
        return "exclusion_only"
    if in_i:
        return "inclusion_only"
    return "neither"


def fuse_scores(
    rankings: list[list[str]],
    kw_weights: list[float],
    keywords: list[str],
    docs: dict,
    section_cache: dict,
    excl_mult: float = 1.0,
    both_mult: float = 1.0,
) -> dict[str, float]:
    scores: dict[str, float] = defaultdict(float)
    for ranking, w, kw in zip(rankings, kw_weights, keywords):
        for rank, nct in enumerate(ranking, start=1):
            ww = w
            if excl_mult != 1.0 or both_mult != 1.0:
                key = (kw, nct)
                if key not in section_cache:
                    row = docs.get(nct) or {}
                    section_cache[key] = section_side(kw, row.get("eligibility") or "")
                side = section_cache[key]
                if side == "exclusion_only":
                    ww *= excl_mult
                elif side == "both":
                    ww *= both_mult
            scores[nct] += ww / (RRF_K + rank)
    return scores


def order_shortlist(shortlist: list[str], scores: dict[str, float]) -> list[str]:
    return sorted(shortlist, key=lambda n: (scores.get(n, float("-inf")), -shortlist.index(n)), reverse=True)


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def agg(rows: list[dict]) -> dict:
    out = {
        "eligible_recall": {str(d): mean_ignore_none([r["eligible_recall"][str(d)] for r in rows]) for d in DEPTHS},
        "p10_eligible": mean_ignore_none([r["p10_eligible"] for r in rows]),
        "ndcg10": mean_ignore_none([r["ndcg10"] for r in rows]),
        "recall_at_full": mean_ignore_none([r.get("recall_at_full") for r in rows]),
    }
    return out


def eval_year(year: int, short: dict, keywords: dict, q_model, q_tok) -> dict:
    snap = YEAR_SNAP[year]
    docs = load_docs(SNAPSHOT[snap]["docs"])
    ncts = [nct for nct in pool_ids(year) if nct in docs]
    ncts_set = set(ncts)
    qrels = qrels_by_topic(year)
    topics = load_topics(year)
    year_kw = keywords.get(str(year), {})
    yshort = short["years"][str(year)]["topics"]
    depth = FULL_DEPTH[year]
    print(f"year {year} collection {len(ncts)}", flush=True)

    bm25 = build_bm25(ncts, docs)
    df = token_df(ncts, docs)
    idx_dir = Path(__file__).resolve().parents[1] / "data" / "trec" / f"index_{snap}"
    medcpt_all = np.load(idx_dir / "medcpt.npy")
    chunk_all = json.loads((idx_dir / "chunk_nct.json").read_text(encoding="utf-8"))
    chunk_vecs, chunk_nct = [], []
    for vec, nct in zip(medcpt_all, chunk_all):
        if nct in ncts_set:
            chunk_vecs.append(vec)
            chunk_nct.append(nct)
    chunk_vecs = np.asarray(chunk_vecs)

    arm_rows = {name: [] for name in OFFICIAL}
    arm_rows["probe_idf_full"] = []
    section_cache: dict = {}
    pos = {n: i for i, n in enumerate(ncts)}

    for tid, trow in yshort.items():
        labels = qrels.get(tid, {})
        shortlist = trow["shortlist"]
        eligible = {n for n, r in labels.items() if r == 2 and n in ncts_set}
        kw_queries = topic_queries(topics[tid], year_kw.get(tid), "kw")
        weights = [keyword_idf(k, df, len(ncts)) for k in kw_queries]
        ones = [1.0] * len(kw_queries)
        bm_lists = bm25_rank(bm25, ncts, kw_queries, RETRIEVE_N)
        qv = encode_queries(kw_queries, q_model, q_tok)
        med_lists = dense_rank(qv, chunk_vecs, ncts, chunk_nct, RETRIEVE_N)
        rankings = bm_lists + med_lists
        kw_twice = kw_queries + kw_queries
        w_twice = weights + weights
        ones_twice = ones + ones

        s_base = fuse_scores(rankings, ones_twice, kw_twice, docs, section_cache)
        s_idf = fuse_scores(rankings, w_twice, kw_twice, docs, section_cache)
        s_sec = fuse_scores(rankings, ones_twice, kw_twice, docs, section_cache, excl_mult=0.25, both_mult=0.75)
        s_both = fuse_scores(rankings, w_twice, kw_twice, docs, section_cache, excl_mult=0.25, both_mult=0.75)

        bm25_sum: dict[str, float] = defaultdict(float)
        short_set = set(shortlist)
        for q in kw_queries:
            toks = tokenize(q)
            if not toks:
                continue
            raw = bm25.get_scores(toks)
            for nct in shortlist:
                bm25_sum[nct] += float(raw[pos[nct]])

        excl_counts = []
        for nct in shortlist:
            n_ex = 0
            for kw in kw_queries:
                key = (kw, nct)
                if key not in section_cache:
                    row = docs.get(nct) or {}
                    section_cache[key] = section_side(kw, row.get("eligibility") or "")
                if section_cache[key] == "exclusion_only":
                    n_ex += 1
            excl_counts.append((s_base.get(nct, 0.0), -n_ex, -shortlist.index(nct)))
        tie_order = [n for n, _ in sorted(zip(shortlist, excl_counts), key=lambda kv: kv[1], reverse=True)]

        ranked = {
            "baseline": shortlist,
            "idf_rrf": order_shortlist(shortlist, s_idf),
            "bm25_sum": order_shortlist(shortlist, bm25_sum),
            "section_mult": order_shortlist(shortlist, s_sec),
            "section_tie": tie_order,
            "idf_section": order_shortlist(shortlist, s_both),
        }
        probe = [d for d, _ in sorted(s_idf.items(), key=lambda kv: -kv[1])[:depth]]
        ranked["probe_idf_full"] = probe

        for name, order in ranked.items():
            row = topic_metrics(order, labels, ncts_set)
            row["recall_at_full"] = recall_at(order, eligible, depth)
            arm_rows[name].append(row)
        print(f"  {year} topic {tid} kws={len(kw_queries)}", flush=True)

    return {
        "n_collection": len(ncts),
        "shortlist_depth": depth,
        "n_topics": len(yshort),
        "arms": {name: agg(rows) for name, rows in arm_rows.items()},
    }


def write_report(results: dict) -> None:
    lines = [
        "# Weighted fusion and section ranking (2021/2022 only)",
        "",
        f"Gates committed in `{THRESHOLDS_COMMIT}` before any new ranking score.",
        "Official arms reorder the existing shortlist. Nothing discarded.",
        "Unweighted RRF is the published TrialGPT fusion. IDF weights are a departure.",
        "Section split reuses `split_sections`. Exclusion-only is down-ranked, never dropped.",
        "2023 was not run. No reader. No trained ranker.",
        "",
        "## Eligible recall",
        "",
        "| Year | Arm | @10 | @20 | @50 | @100 | @200 | Full shortlist |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for year in YEARS:
        for name, pack in results["years"][str(year)]["arms"].items():
            er = pack["eligible_recall"]
            lines.append(
                f"| {year} | {name} | {pct(er.get('10'))} | {pct(er.get('20'))} | "
                f"{pct(er.get('50'))} | {pct(er.get('100'))} | {pct(er.get('200'))} | "
                f"{pct(pack.get('recall_at_full'))} |"
            )
    lines += [
        "",
        "## Gates",
        "",
        f"| Check | Result |",
        f"|---|---|",
        f"| Best official 2021 Recall@10 | {pct(results['best_2021_r10'])} ({results['best_arm']}) |",
        f"| Full-shortlist recall unchanged | {results['full_depth_unchanged']} |",
        f"| Probe R@6% vs 91.6%/91.4% | {results['probe_note']} |",
        f"| Gate | {results['gate']} |",
        "",
        results["verdict"],
        "",
        "JSON: `data/trec/trec_shortlist_fix.json`. No overall accuracy.",
        "The system does not say a patient qualifies.",
        "",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    short = json.loads(SHORTLIST.read_text(encoding="utf-8"))
    keywords = json.loads((Path(__file__).resolve().parents[1] / "data" / "trec" / "keywords.json").read_text(encoding="utf-8"))
    print(f"loading {QUERY_ENC}", flush=True)
    q_tok = AutoTokenizer.from_pretrained(QUERY_ENC)
    q_model = AutoModel.from_pretrained(QUERY_ENC)
    q_model.eval()
    years = {}
    with torch.no_grad():
        for year in YEARS:
            years[str(year)] = eval_year(year, short, keywords, q_model, q_tok)

    y21 = years["2021"]["arms"]
    official_r10 = {n: y21[n]["eligible_recall"]["10"] for n in OFFICIAL}
    best_arm = max(official_r10, key=lambda n: official_r10[n] or -1)
    best = official_r10[best_arm]
    full_ok = True
    for year in YEARS:
        base = years[str(year)]["arms"]["baseline"]["recall_at_full"]
        for name in OFFICIAL:
            got = years[str(year)]["arms"][name]["recall_at_full"]
            if got is None or base is None or abs(got - base) > 1e-9:
                full_ok = False
    p21 = years["2021"]["arms"]["probe_idf_full"]["recall_at_full"]
    p22 = years["2022"]["arms"]["probe_idf_full"]["recall_at_full"]
    probe_note = f"2021 {pct(p21)} / 2022 {pct(p22)}"

    if not full_ok:
        gate = "full_depth_moved"
        verdict = "BUG: official arms moved full-shortlist recall. Reordering cannot do that."
    elif best is None or best < 0.057:
        gate = "hurts"
        verdict = f"STOP: best official 2021 Recall@10 is {pct(best)} ({best_arm}), at or below 5.7%."
    elif best < 0.087:
        gate = "not_a_pipeline_change"
        verdict = (
            f"Best official 2021 Recall@10 is {pct(best)} ({best_arm}). Beats 5.7% but under "
            f"+3 points (8.7%). Do not replace unweighted RRF."
        )
    elif best < 0.114:
        gate = "plus_three_not_double"
        verdict = (
            f"Best official 2021 Recall@10 is {pct(best)} ({best_arm}), at least +3 points, "
            f"short of doubling (11.4%). Report it; it is a cheap gain, not the rerank bar."
        )
    else:
        gate = "cleared_rerank_double"
        verdict = (
            f"Best official 2021 Recall@10 is {pct(best)} ({best_arm}), at or above 11.4%. "
            f"This cheap reordering did what the reranker did not. Label IDF fusion as a "
            f"departure from TrialGPT if 2a or 2+3 won."
        )

    results = {
        "thresholds_commit": THRESHOLDS_COMMIT,
        "years_run": list(YEARS),
        "year_2023": "not_run",
        "best_arm": best_arm,
        "best_2021_r10": best,
        "full_depth_unchanged": full_ok,
        "probe_note": probe_note,
        "gate": gate,
        "verdict": verdict,
        "years": years,
    }
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    write_report(results)
    print(verdict, flush=True)
    print(f"wrote {OUT} and {REPORT}", flush=True)
    if gate in {"hurts", "full_depth_moved"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
