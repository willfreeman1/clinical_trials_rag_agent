"""Score rerank arms. Gates in 44878a7. 2021/2022 only."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_hybrid_common import load_docs, pool_ids, qrels_by_topic  # noqa: E402
from trec_hybrid_common import SNAPSHOT, YEAR_SNAP  # noqa: E402
from trec_rerank_common import (  # noqa: E402
    BASELINE_FULL,
    BASELINE_R10,
    CE_SCORES,
    DATA,
    DEPTHS,
    FULL_DEPTH,
    LLM_DEPTH,
    LLM_SCORES,
    LLM_YEAR,
    OUT,
    REPORT,
    SHORTLIST,
    THRESHOLDS_COMMIT,
    YEARS,
    mean_ignore_none,
    ndcg_at,
    precision_at,
    recall_at,
    rerank,
    stitch_prefix,
)

ARMS_CE = (
    ("medcpt_ce_keywords", "truncate", "medcpt_ce", "keywords"),
    ("medcpt_ce_raw", "truncate", "medcpt_ce", "raw"),
    ("msmarco_ce_keywords", "truncate", "msmarco_ce", "keywords"),
    ("msmarco_ce_raw", "truncate", "msmarco_ce", "raw"),
)


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def topic_metrics(ranked: list[str], labels: dict[str, int], ncts_set: set[str]) -> dict:
    eligible = {n for n, r in labels.items() if r == 2 and n in ncts_set}
    relevant = {n for n, r in labels.items() if r >= 1 and n in ncts_set}
    out = {
        "eligible_recall": {str(d): recall_at(ranked, eligible, d) for d in DEPTHS},
        "relevant_recall": {str(d): recall_at(ranked, relevant, d) for d in DEPTHS},
        "p10_eligible": precision_at(ranked, eligible, 10),
        "p10_relevant": precision_at(ranked, relevant, 10),
        "ndcg10": ndcg_at(ranked, labels, 10),
        "n_eligible": len(eligible),
    }
    return out


def agg(rows: list[dict]) -> dict:
    return {
        "eligible_recall": {
            str(d): mean_ignore_none([r["eligible_recall"][str(d)] for r in rows]) for d in DEPTHS
        },
        "relevant_recall": {
            str(d): mean_ignore_none([r["relevant_recall"][str(d)] for r in rows]) for d in DEPTHS
        },
        "p10_eligible": mean_ignore_none([r["p10_eligible"] for r in rows]),
        "p10_relevant": mean_ignore_none([r["p10_relevant"] for r in rows]),
        "ndcg10": mean_ignore_none([r["ndcg10"] for r in rows]),
        "recall_at_full": mean_ignore_none([r.get("recall_at_full") for r in rows]),
    }


def ce_map(ce: dict, mode: str, model: str, qname: str, year: str, tid: str) -> dict[str, float]:
    try:
        return {k: float(v) for k, v in ce[mode][model][qname][year][tid].items()}
    except (KeyError, TypeError):
        return {}


def main() -> None:
    short = json.loads(SHORTLIST.read_text(encoding="utf-8"))
    ce = json.loads(CE_SCORES.read_text(encoding="utf-8")) if CE_SCORES.exists() else {}
    llm = json.loads(LLM_SCORES.read_text(encoding="utf-8")) if LLM_SCORES.exists() else {}
    llm_scores = llm.get("scores") or {}
    have_chunk = bool(ce.get("chunk_max"))
    years_out = {}
    for year in YEARS:
        snap = YEAR_SNAP[year]
        docs = load_docs(SNAPSHOT[snap]["docs"])
        ncts_set = {n for n in pool_ids(year) if n in docs}
        qrels = qrels_by_topic(year)
        depth_full = FULL_DEPTH[year]
        yshort = short["years"][str(year)]["topics"]
        arm_rows = {"baseline": []}
        for name, *_ in ARMS_CE:
            arm_rows[name] = []
        if have_chunk:
            for name, *_ in ARMS_CE:
                arm_rows[name + "_chunk"] = []
        if year == LLM_YEAR:
            arm_rows["llm_raw_top200"] = []
        for tid, trow in yshort.items():
            labels = qrels.get(tid, {})
            shortlist = trow["shortlist"]
            base_m = topic_metrics(shortlist, labels, ncts_set)
            base_m["recall_at_full"] = recall_at(
                shortlist, {n for n, r in labels.items() if r == 2 and n in ncts_set}, depth_full
            )
            arm_rows["baseline"].append(base_m)
            for name, mode, model, qname in ARMS_CE:
                scores = ce_map(ce, mode, model, qname, str(year), tid)
                ranked = rerank(shortlist, scores) if scores else list(shortlist)
                row = topic_metrics(ranked, labels, ncts_set)
                row["recall_at_full"] = recall_at(
                    ranked, {n for n, r in labels.items() if r == 2 and n in ncts_set}, depth_full
                )
                arm_rows[name].append(row)
                if have_chunk:
                    cscores = ce_map(ce, "chunk_max", model, qname, str(year), tid)
                    cr = rerank(shortlist, cscores) if cscores else list(shortlist)
                    crow = topic_metrics(cr, labels, ncts_set)
                    crow["recall_at_full"] = recall_at(
                        cr, {n for n, r in labels.items() if r == 2 and n in ncts_set}, depth_full
                    )
                    arm_rows[name + "_chunk"].append(crow)
            if year == LLM_YEAR:
                prefix = rerank(shortlist[:LLM_DEPTH], {k: float(v) for k, v in (llm_scores.get(tid) or {}).items()})
                ranked = stitch_prefix(shortlist, prefix)
                row = topic_metrics(ranked, labels, ncts_set)
                row["recall_at_full"] = recall_at(
                    ranked, {n for n, r in labels.items() if r == 2 and n in ncts_set}, depth_full
                )
                arm_rows["llm_raw_top200"].append(row)
        years_out[str(year)] = {
            "n_topics": len(yshort),
            "shortlist_depth": depth_full,
            "arms": {name: agg(rows) for name, rows in arm_rows.items()},
        }

    y21 = years_out["2021"]["arms"]
    r10s = {name: pack["eligible_recall"]["10"] for name, pack in y21.items()}
    best_name = max(r10s, key=lambda n: r10s[n] or -1)
    best_r10 = r10s[best_name]
    full_ok = {}
    for year in YEARS:
        for name, pack in years_out[str(year)]["arms"].items():
            if name == "llm_raw_top200":
                continue
            got = pack.get("recall_at_full")
            exp = years_out[str(year)]["arms"]["baseline"].get("recall_at_full")
            full_ok[f"{year}:{name}"] = got is not None and exp is not None and abs(got - exp) < 1e-9

    if best_r10 is None:
        verdict = "No Recall@10."
        gate = "n/a"
    elif best_r10 < 2 * BASELINE_R10[2021]:
        verdict = (
            f"STOP: best 2021 Recall@10 is {best_r10:.1%} ({best_name}), below doubling "
            f"of 5.7% (11.4%). Reranking is not earning itself."
        )
        gate = "below_doubling_stop"
    elif best_r10 <= 0.17:
        verdict = (
            f"Best 2021 Recall@10 is {best_r10:.1%} ({best_name}). Doubled 5.7% but did "
            f"not triple to above 17%. Report it; do not treat this as a finished first page."
        )
        gate = "doubled_not_tripled"
    else:
        verdict = (
            f"Best 2021 Recall@10 is {best_r10:.1%} ({best_name}), above 17%. "
            f"Reranking moved eligible trials into the top 10."
        )
        gate = "cleared_triple"

    if not all(full_ok.values()):
        verdict = (
            "BUG: recall at full shortlist depth moved after reranking. "
            "Reordering cannot change that number. " + verdict
        )
        gate = "full_depth_moved"

    results = {
        "thresholds_commit": THRESHOLDS_COMMIT,
        "years_run": list(YEARS),
        "year_2023": "not_run",
        "chunk_max_ran": have_chunk,
        "llm_usd": llm.get("usd"),
        "llm_model": llm.get("model"),
        "best_arm_2021_r10": best_name,
        "best_2021_r10": best_r10,
        "full_depth_unchanged": all(full_ok.values()),
        "full_depth_checks": full_ok,
        "gate": gate,
        "verdict": verdict,
        "years": years_out,
    }
    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    write_report(results)
    print(verdict, flush=True)
    print(f"wrote {OUT} and {REPORT}", flush=True)
    if gate in {"below_doubling_stop", "full_depth_moved"}:
        raise SystemExit(1)


def write_report(results: dict) -> None:
    lines = [
        "# TREC reranking the shortlist (2021/2022 only)",
        "",
        f"Gates committed in `{THRESHOLDS_COMMIT}` before any rerank score.",
        "2023 was not run. Reranking reorders; it discards nothing.",
        "Shortlist is keyword hybrid (BM25 + MedCPT, RRF), top 6% of the judged pool.",
        "Document text starts as the same 512-token `[title, body]` truncation as retrieval.",
        "MedCPT-CE judges whether a PubMed article answers a search query, not eligibility.",
        "MS MARCO MiniLM is web search. The cheap model scores topical relevance.",
        "Polarity and conditional rules stay the reader's job. The system does not say a patient qualifies.",
        "The 0.81 NDCG figure in the literature is on 2023 and is not a comparison here.",
        "",
        "## Eligible recall",
        "",
        "| Year | Arm | @10 | @20 | @50 | @100 | @200 | Full shortlist |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for year in YEARS:
        arms = results["years"][str(year)]["arms"]
        for name, pack in arms.items():
            er = pack["eligible_recall"]
            lines.append(
                f"| {year} | {name} | {pct(er.get('10'))} | {pct(er.get('20'))} | "
                f"{pct(er.get('50'))} | {pct(er.get('100'))} | {pct(er.get('200'))} | "
                f"{pct(pack.get('recall_at_full'))} |"
            )
    lines += [
        "",
        "## NDCG@10 and precision@10",
        "",
        "| Year | Arm | NDCG@10 | P@10 eligible | P@10 relevant |",
        "|---|---|---:|---:|---:|",
    ]
    for year in YEARS:
        for name, pack in results["years"][str(year)]["arms"].items():
            lines.append(
                f"| {year} | {name} | {pct(pack.get('ndcg10'))} | "
                f"{pct(pack.get('p10_eligible'))} | {pct(pack.get('p10_relevant'))} |"
            )
    lines += [
        "",
        "## Gates",
        "",
        f"| Check | Result |",
        f"|---|---|",
        f"| Best 2021 Recall@10 | {pct(results['best_2021_r10'])} ({results['best_arm_2021_r10']}) |",
        f"| Full-shortlist recall unchanged | {results['full_depth_unchanged']} |",
        f"| Gate | {results['gate']} |",
        "",
        results["verdict"],
        "",
        f"Chunk-and-max ran: {results['chunk_max_ran']}.",
        f"Language-model arm: {results.get('llm_model')} on 2021 top 200, ${results.get('llm_usd')}.",
        "",
        "Per-arm JSON is in `data/trec/trec_rerank_results.json`.",
        "No overall accuracy.",
        "",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
