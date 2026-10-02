"""Diagnose the keyword-hybrid shortlist. Gates in 697d808. 2021/2022 only.

No fusion change. No section ranking. Count TREC labels in the 1,570.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_hybrid_common import (  # noqa: E402
    RETRIEVE_N,
    SNAPSHOT,
    YEAR_SNAP,
    load_docs,
    load_topics,
    pool_ids,
    qrels_by_topic,
    recall_at,
)
from trec_hybrid_eval import (  # noqa: E402
    bm25_rank,
    build_bm25,
    load_keywords,
    topic_queries,
)
from trec_rerank_common import FULL_DEPTH, SHORTLIST, YEARS, mean_ignore_none, wilson  # noqa: E402

THRESHOLDS_COMMIT = "697d808"
OUT = Path(__file__).resolve().parents[1] / "data" / "trec" / "trec_shortlist_diagnosis.json"
REPORT = Path(__file__).resolve().parents[1] / "docs" / "trec_shortlist_diagnosis.md"
GUESS_RELEVANT = 144
GUESS_JUNK_SHARE = 0.91


def bucket(nct: str, labels: dict[str, int]) -> str:
    if nct not in labels:
        return "unjudged"
    rel = labels[nct]
    if rel == 2:
        return "eligible"
    if rel == 1:
        return "excluded"
    return "judged_0"


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def eval_year(year: int, short: dict, keywords: dict) -> dict:
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
    per_topic = []
    kw_junk = defaultdict(lambda: {"junk": 0, "elig": 0, "excl": 0, "in_short": 0, "topics": 0})

    for tid, trow in yshort.items():
        labels = qrels.get(tid, {})
        shortlist = trow["shortlist"]
        counts = {"eligible": 0, "excluded": 0, "judged_0": 0, "unjudged": 0}
        for nct in shortlist:
            counts[bucket(nct, labels)] += 1
        n = len(shortlist) or 1
        eligible = {n for n, r in labels.items() if r == 2 and n in ncts_set}
        excluded = {n for n, r in labels.items() if r == 1 and n in ncts_set}
        judged0 = {n for n, r in labels.items() if r == 0 and n in ncts_set}
        row = {
            "topic": tid,
            "n_shortlist": len(shortlist),
            "counts": counts,
            "shares": {k: counts[k] / n for k in counts},
            "n_eligible_pool": len(eligible),
            "n_excluded_pool": len(excluded),
            "n_judged0_pool": len(judged0),
            "recall_eligible": recall_at(shortlist, eligible, depth),
            "recall_excluded": recall_at(shortlist, excluded, depth),
            "disease_relevant": counts["eligible"] + counts["excluded"],
            "junk": counts["judged_0"] + counts["unjudged"],
        }
        per_topic.append(row)

        kw_queries = topic_queries(topics[tid], year_kw.get(tid), "kw")
        lists = bm25_rank(bm25, ncts, kw_queries, RETRIEVE_N)
        short_set = set(shortlist)
        for kw, ranking in zip(kw_queries, lists):
            rec = kw_junk[kw]
            rec["topics"] += 1
            for nct in ranking:
                if nct not in short_set:
                    continue
                rec["in_short"] += 1
                b = bucket(nct, labels)
                if b in ("judged_0", "unjudged"):
                    rec["junk"] += 1
                elif b == "eligible":
                    rec["elig"] += 1
                elif b == "excluded":
                    rec["excl"] += 1
        print(
            f"  {year} topic {tid} elig={counts['eligible']} excl={counts['excluded']} "
            f"j0={counts['judged_0']} unj={counts['unjudged']}",
            flush=True,
        )

    n_topics = len(per_topic)
    mean_counts = {k: mean_ignore_none([r["counts"][k] for r in per_topic]) for k in ("eligible", "excluded", "judged_0", "unjudged")}
    mean_shares = {k: mean_ignore_none([r["shares"][k] for r in per_topic]) for k in mean_counts}
    mean_relevant = mean_ignore_none([r["disease_relevant"] for r in per_topic])
    mean_junk = mean_ignore_none([r["junk"] for r in per_topic])
    mean_junk_share = mean_ignore_none([r["junk"] / r["n_shortlist"] for r in per_topic])
    mean_rel_share = mean_ignore_none([r["disease_relevant"] / r["n_shortlist"] for r in per_topic])
    rec_el = mean_ignore_none([r["recall_eligible"] for r in per_topic])
    rec_ex = mean_ignore_none([r["recall_excluded"] for r in per_topic])

    kw_rows = []
    for kw, rec in kw_junk.items():
        tot = rec["in_short"]
        kw_rows.append(
            {
                "keyword": kw,
                "topics": rec["topics"],
                "hits_in_shortlist": tot,
                "junk": rec["junk"],
                "eligible": rec["elig"],
                "excluded": rec["excl"],
                "junk_share": (rec["junk"] / tot) if tot else None,
            }
        )
    kw_rows.sort(key=lambda r: r["junk"], reverse=True)

    junk_majority = bool(mean_junk_share is not None and mean_junk_share > 0.5)
    relevant_majority = bool(mean_rel_share is not None and mean_rel_share > 0.5)
    excluded_majority = bool(mean_shares["excluded"] is not None and mean_shares["excluded"] > 0.5)
    near_guess = bool(
        mean_relevant is not None
        and 80 <= mean_relevant <= 220
        and mean_junk_share is not None
        and mean_junk_share >= 0.80
    )
    if excluded_majority or relevant_majority:
        decision = "stop_retrieval_did_its_job"
    elif junk_majority and near_guess:
        decision = "run_2_and_3"
    else:
        decision = "follow_diagnosis_do_not_run_written_tasks"

    return {
        "n_collection": len(ncts),
        "shortlist_depth": depth,
        "n_topics": n_topics,
        "mean_counts": mean_counts,
        "mean_shares": mean_shares,
        "mean_disease_relevant": mean_relevant,
        "mean_junk": mean_junk,
        "mean_junk_share": mean_junk_share,
        "mean_relevant_share": mean_rel_share,
        "recall_eligible_at_full": rec_el,
        "recall_excluded_at_full": rec_ex,
        "guess_disease_relevant": GUESS_RELEVANT,
        "junk_majority": junk_majority,
        "relevant_majority": relevant_majority,
        "excluded_majority": excluded_majority,
        "near_guess": near_guess,
        "decision": decision,
        "top_junk_keywords": kw_rows[:30],
        "topics": per_topic,
    }


def write_report(results: dict) -> None:
    lines = [
        "# What is in the TREC shortlist (2021/2022 only)",
        "",
        f"Gates committed in `{THRESHOLDS_COMMIT}` before any composition count.",
        "2023 was not run. Same keyword-hybrid shortlist as the rerank run.",
        "Nothing discarded. No reader. No trained ranker.",
        "",
        "The 68/17/16 split is of **all judgments**, not of the shortlist.",
        "The 144 / 91% figure is what you get if excluded trials are retrieved",
        "at the same rate as eligible ones. That is the estimate under test.",
        "",
        "## Composition of the shortlist (mean per patient)",
        "",
        "| Year | Eligible (2) | Excluded (1) | Judged 0 | Unjudged | Disease-relevant (1+2) | Junk (0 + unjudged) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for year in YEARS:
        y = results["years"][str(year)]
        c = y["mean_counts"]
        lines.append(
            f"| {year} | {c['eligible']:.1f} ({pct(y['mean_shares']['eligible'])}) | "
            f"{c['excluded']:.1f} ({pct(y['mean_shares']['excluded'])}) | "
            f"{c['judged_0']:.1f} ({pct(y['mean_shares']['judged_0'])}) | "
            f"{c['unjudged']:.1f} ({pct(y['mean_shares']['unjudged'])}) | "
            f"{y['mean_disease_relevant']:.1f} ({pct(y['mean_relevant_share'])}) | "
            f"{y['mean_junk']:.1f} ({pct(y['mean_junk_share'])}) |"
        )
    lines += [
        "",
        "## Retrieval rate at 6% of collection",
        "",
        "| Year | Eligible recall | Excluded recall |",
        "|---|---:|---:|",
    ]
    for year in YEARS:
        y = results["years"][str(year)]
        lines.append(
            f"| {year} | {pct(y['recall_eligible_at_full'])} | {pct(y['recall_excluded_at_full'])} |"
        )
    lines += [
        "",
        "## Against the estimate",
        "",
        results["verdict"],
        "",
        "## Keywords that contribute the most junk in the shortlist",
        "",
        "A trial can be hit by several keywords. These counts are BM25 top-1000",
        "hits that also sit in the fused shortlist, summed over patients.",
        "",
        "| Year | Keyword | Patients | Hits in shortlist | Junk share | Eligible | Excluded |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for year in YEARS:
        for row in results["years"][str(year)]["top_junk_keywords"][:15]:
            lines.append(
                f"| {year} | {row['keyword']} | {row['topics']} | {row['hits_in_shortlist']} | "
                f"{pct(row['junk_share'])} | {row['eligible']} | {row['excluded']} |"
            )
    lines += [
        "",
        "## Decision",
        "",
        f"`{results['decision']}`",
        "",
        "Per-patient JSON: `data/trec/trec_shortlist_diagnosis.json`.",
        "No overall accuracy. The system does not say a patient qualifies.",
        "",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    short = json.loads(SHORTLIST.read_text(encoding="utf-8"))
    keywords = load_keywords()
    years = {}
    for year in YEARS:
        years[str(year)] = eval_year(year, short, keywords)
    decisions = {y: years[str(y)]["decision"] for y in YEARS}
    if all(d == "run_2_and_3" for d in decisions.values()):
        verdict = (
            "The estimate holds. Junk is the majority of the shortlist and "
            "disease-relevant volume is near 144. Retrieval is imprecise. "
            "Tasks 2 and 3 have a premise."
        )
        decision = "run_2_and_3"
    elif any(d == "stop_retrieval_did_its_job" for d in decisions.values()):
        verdict = (
            "The estimate does not hold in the direction that matters: the "
            "shortlist is mostly disease-relevant or mostly excluded. "
            "Retrieval did its job. Tasks 2 and 3 will not cheaply clean it."
        )
        decision = "stop_retrieval_did_its_job"
    else:
        bits = []
        for year in YEARS:
            y = years[str(year)]
            bits.append(
                f"{year}: {y['mean_disease_relevant']:.0f} disease-relevant "
                f"(guess 144), junk {pct(y['mean_junk_share'])} "
                f"(guess 91%), excluded recall {pct(y['recall_excluded_at_full'])} "
                f"vs eligible {pct(y['recall_eligible_at_full'])}."
            )
        verdict = (
            "The mix is not the written 144/91% picture and not an excluded-"
            "majority either. Follow the diagnosis, not the written tasks. "
            + " ".join(bits)
        )
        decision = "follow_diagnosis_do_not_run_written_tasks"

    slim = {}
    for year, pack in years.items():
        slim[year] = {k: v for k, v in pack.items() if k != "topics"}
        slim[year]["n_topics_detail"] = len(pack["topics"])
        slim[year]["topics"] = [
            {
                "topic": r["topic"],
                "counts": r["counts"],
                "shares": r["shares"],
                "disease_relevant": r["disease_relevant"],
                "junk": r["junk"],
                "recall_eligible": r["recall_eligible"],
                "recall_excluded": r["recall_excluded"],
            }
            for r in pack["topics"]
        ]

    results = {
        "thresholds_commit": THRESHOLDS_COMMIT,
        "years_run": list(YEARS),
        "year_2023": "not_run",
        "years": slim,
        "decision": decision,
        "verdict": verdict,
    }
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    write_report(results)
    print(verdict, flush=True)
    print(f"decision={decision}", flush=True)
    print(f"wrote {OUT} and {REPORT}", flush=True)


if __name__ == "__main__":
    main()
