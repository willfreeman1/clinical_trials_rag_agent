"""Recompute precision, ceilings, and the 10-in-20 bar from stored rankings.

No new retrieval, GPU, or API. 2021/2022 only. 2023 is not read.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_cheap_common import (  # noqa: E402
    GPU_SCORES,
    LEXICAL_SCORES,
    MINI_SCORES,
    keep_from_ce_logit,
    keep_from_decision,
    load_sample,
)
from trec_cheap_eval import (  # noqa: E402
    kept_from_ce,
    kept_from_lexical,
    kept_from_mini,
    kept_from_qwen,
)
from trec_hybrid_common import qrels_by_topic  # noqa: E402
from trec_rerank_common import (  # noqa: E402
    CE_SCORES,
    DATA,
    LLM_DEPTH,
    LLM_SCORES,
    SHORTLIST,
    YEARS,
    rerank,
    stitch_prefix,
    wilson,
)
from trec_rerank_eval import ce_map  # noqa: E402

DEPTHS = (10, 20, 50)
OUT = DATA / "trec_precision.json"
REPORT = Path(__file__).resolve().parents[1] / "docs" / "trec_precision.md"
FIX = DATA / "trec_shortlist_fix.json"

CE_ARMS = (
    ("medcpt_ce_keywords", "truncate", "medcpt_ce", "keywords"),
    ("medcpt_ce_raw", "truncate", "medcpt_ce", "raw"),
    ("msmarco_ce_keywords", "truncate", "msmarco_ce", "keywords"),
    ("msmarco_ce_raw", "truncate", "msmarco_ce", "raw"),
)


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def wilson_s(w: dict | None) -> str:
    if not w:
        return "n/a"
    if "low" in w:
        return f"{w['point']:.1%} [{w['low']:.1%}, {w['high']:.1%}] (n={w['n']})"
    return f"{w['point']:.1%} (n={w['n']})"


def mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def quantiles(xs: list[float]) -> dict:
    if not xs:
        return {}
    s = sorted(xs)
    n = len(s)

    def at(p: float) -> float:
        if n == 1:
            return s[0]
        i = p * (n - 1)
        lo = int(i)
        hi = min(lo + 1, n - 1)
        frac = i - lo
        return s[lo] * (1 - frac) + s[hi] * frac

    return {
        "n": n,
        "min": s[0],
        "p10": at(0.10),
        "p25": at(0.25),
        "median": statistics.median(s),
        "p75": at(0.75),
        "p90": at(0.90),
        "max": s[-1],
        "mean": sum(s) / n,
    }


def hits(ranked: list[str], wanted: set[str], depth: int) -> int:
    return sum(1 for n in ranked[:depth] if n in wanted)


def topic_row(ranked: list[str], eligible: set[str], relevant: set[str]) -> dict:
    n_elig = len(eligible)
    n_rel = len(relevant)
    out: dict = {
        "n_eligible": n_elig,
        "n_relevant": n_rel,
        "n_ranked": len(ranked),
    }
    for d in DEPTHS:
        h2 = hits(ranked, eligible, d)
        h1 = hits(ranked, relevant, d)
        p_ceil = min(1.0, n_elig / d) if d else None
        r_ceil = min(1.0, d / n_elig) if n_elig else None
        p = h2 / d if d else None
        out[f"elig_hits_{d}"] = h2
        out[f"rel_hits_{d}"] = h1
        out[f"p{d}_elig"] = p
        out[f"p{d}_rel"] = h1 / d if d else None
        out[f"p{d}_ceil"] = p_ceil
        out[f"r{d}_ceil"] = r_ceil
        out[f"p{d}_of_ceil"] = (p / p_ceil) if p_ceil else None
        out[f"r{d}"] = (h2 / n_elig) if n_elig else None
    out["hit10_in20"] = hits(ranked, eligible, 20) >= 10
    out["possible10_in20"] = n_elig >= 10
    return out


def agg_rows(rows: list[dict]) -> dict:
    n = len(rows)
    possible = sum(1 for r in rows if r["possible10_in20"])
    meet = sum(1 for r in rows if r["hit10_in20"])
    meet_possible = sum(1 for r in rows if r["hit10_in20"] and r["possible10_in20"])
    out: dict = {
        "n_topics": n,
        "eligible_dist": quantiles([r["n_eligible"] for r in rows]),
        "relevant_dist": quantiles([r["n_relevant"] for r in rows]),
        "bar20": {
            "meet": meet,
            "possible": possible,
            "impossible": n - possible,
            "meet_among_possible": (meet_possible / possible) if possible else None,
            "meet_wilson": wilson(meet, n),
            "possible_wilson": wilson(possible, n),
        },
    }
    for d in DEPTHS:
        out[f"mean_elig_hits_{d}"] = mean([r[f"elig_hits_{d}"] for r in rows])
        out[f"mean_rel_hits_{d}"] = mean([r[f"rel_hits_{d}"] for r in rows])
        out[f"macro_p{d}_elig"] = mean([r[f"p{d}_elig"] for r in rows])
        out[f"macro_p{d}_rel"] = mean([r[f"p{d}_rel"] for r in rows])
        out[f"macro_p{d}_ceil"] = mean(
            [r[f"p{d}_ceil"] for r in rows if r[f"p{d}_ceil"] is not None]
        )
        out[f"macro_r{d}"] = mean([r[f"r{d}"] for r in rows if r[f"r{d}"] is not None])
        out[f"macro_r{d}_ceil"] = mean(
            [r[f"r{d}_ceil"] for r in rows if r[f"r{d}_ceil"] is not None]
        )
        of_ceil = [r[f"p{d}_of_ceil"] for r in rows if r[f"p{d}_of_ceil"] is not None]
        out[f"macro_p{d}_of_ceil"] = mean(of_ceil)
    return out


def load_kept_maps() -> dict[str, dict]:
    sample = load_sample()
    out = {}
    if LEXICAL_SCORES.exists():
        lex = json.loads(LEXICAL_SCORES.read_text(encoding="utf-8"))
        out["lexical_title_cond"] = {
            (y, tid): kept_from_lexical(lex, y, tid)
            for y in ("2021", "2022")
            for tid in sample["years"][y]
        }
    if GPU_SCORES.exists():
        gpu = json.loads(GPU_SCORES.read_text(encoding="utf-8"))
        for doc in ("title_cond", "title_cond_slice", "title_body_512"):
            if doc in (gpu.get("ce") or {}):
                out[f"ce_{doc}"] = {
                    (y, tid): kept_from_ce(gpu, doc, y, tid)
                    for y in ("2021", "2022")
                    for tid in sample["years"][y]
                }
            if doc in (gpu.get("qwen") or {}):
                out[f"qwen_{doc}"] = {
                    (y, tid): kept_from_qwen(gpu, doc, y, tid)
                    for y in ("2021", "2022")
                    for tid in sample["years"][y]
                }
    if MINI_SCORES.exists():
        mini = json.loads(MINI_SCORES.read_text(encoding="utf-8"))
        for doc in ("title_cond", "title_cond_slice"):
            if doc in (mini.get("decisions") or {}):
                out[f"mini_{doc}"] = {
                    (y, tid): kept_from_mini(mini, doc, y, tid)
                    for y in ("2021", "2022")
                    for tid in sample["years"][y]
                }
    return out, sample


def main() -> None:
    short = json.loads(SHORTLIST.read_text(encoding="utf-8"))
    ce = json.loads(CE_SCORES.read_text(encoding="utf-8")) if CE_SCORES.exists() else {}
    llm = json.loads(LLM_SCORES.read_text(encoding="utf-8")) if LLM_SCORES.exists() else {}
    llm_scores = llm.get("scores") or {}
    kept_maps, sample = load_kept_maps()
    sample_ids = {
        (y, tid) for y in ("2021", "2022") for tid in sample["years"][y]
    }

    year_rows: dict[str, dict[str, list[dict]]] = {}
    gold: dict[str, dict] = {}
    for year in YEARS:
        y = str(year)
        qrels = qrels_by_topic(year)
        topics = short["years"][y]["topics"]
        arms: dict[str, list[dict]] = {
            "kw_hybrid": [],
            "medcpt_ce_keywords": [],
            "medcpt_ce_raw": [],
            "msmarco_ce_keywords": [],
            "msmarco_ce_raw": [],
        }
        if year == 2021:
            arms["llm_raw_top200"] = []
        gold_rows = []
        for tid, trow in topics.items():
            labels = qrels.get(tid, {})
            eligible = {n for n, r in labels.items() if r == 2}
            relevant = {n for n, r in labels.items() if r >= 1}
            shortlist = trow["shortlist"]
            gold_rows.append(
                {
                    "year": year,
                    "topic": tid,
                    "n_eligible": len(eligible),
                    "n_relevant": len(relevant),
                    "n_elig_in_short": sum(1 for n in shortlist if n in eligible),
                    "possible10_in20": len(eligible) >= 10,
                    "possible10_in20_retrieved": sum(1 for n in shortlist if n in eligible)
                    >= 10,
                }
            )
            ranks = {"kw_hybrid": shortlist}
            for name, mode, model, qname in CE_ARMS:
                scores = ce_map(ce, mode, model, qname, y, tid)
                ranks[name] = rerank(shortlist, scores) if scores else list(shortlist)
            if year == 2021:
                prefix = rerank(
                    shortlist[:LLM_DEPTH],
                    {k: float(v) for k, v in (llm_scores.get(tid) or {}).items()},
                )
                ranks["llm_raw_top200"] = stitch_prefix(shortlist, prefix)
            for name, ranked in ranks.items():
                row = topic_row(ranked, eligible, relevant)
                row["year"] = year
                row["topic"] = tid
                arms[name].append(row)
            if (y, tid) in sample_ids:
                hrow = topic_row(shortlist, eligible, relevant)
                hrow["year"] = year
                hrow["topic"] = tid
                arms.setdefault("cheap_hybrid_sample", []).append(hrow)
                for kname, kmap in kept_maps.items():
                    kept = kmap.get((y, tid)) or set()
                    filtered = [n for n in shortlist if n in kept]
                    frow = topic_row(filtered, eligible, relevant)
                    frow["year"] = year
                    frow["topic"] = tid
                    arms.setdefault(f"cheap_{kname}", []).append(frow)
        year_rows[y] = arms
        gold[y] = {
            "n_topics": len(gold_rows),
            "eligible": quantiles([r["n_eligible"] for r in gold_rows]),
            "relevant": quantiles([r["n_relevant"] for r in gold_rows]),
            "elig_in_short": quantiles([r["n_elig_in_short"] for r in gold_rows]),
            "possible10_in20": sum(1 for r in gold_rows if r["possible10_in20"]),
            "possible10_in20_retrieved": sum(
                1 for r in gold_rows if r["possible10_in20_retrieved"]
            ),
            "n_elig_lt_10": sum(1 for r in gold_rows if r["n_eligible"] < 10),
            "n_elig_lt_20": sum(1 for r in gold_rows if r["n_eligible"] < 20),
            "topics": gold_rows,
        }

    pooled_arms: dict[str, list[dict]] = {}
    for y, arms in year_rows.items():
        for name, rows in arms.items():
            pooled_arms.setdefault(name, []).extend(rows)

    results = {
        "note": "Recompute from stored shortlists and scores. No new runs. 2023 omitted.",
        "aggregation": "macro_mean_of_per_patient_precision",
        "why_macro": (
            "Each patient is one screening job. Micro-averaging would let "
            "patients with 200 eligible trials dominate the mean."
        ),
        "gold": gold,
        "years": {y: {name: agg_rows(rows) for name, rows in arms.items()} for y, arms in year_rows.items()},
        "pooled_125": {name: agg_rows(rows) for name, rows in pooled_arms.items()},
        "fusion_stored_p10_only": {},
    }
    if FIX.exists():
        fix = json.loads(FIX.read_text(encoding="utf-8"))
        stored = {}
        for y, pack in (fix.get("years") or {}).items():
            stored[y] = {
                name: {
                    "p10_eligible": arm.get("p10_eligible"),
                    "eligible_recall": arm.get("eligible_recall"),
                }
                for name, arm in (pack.get("arms") or {}).items()
            }
        results["fusion_stored_p10_only"] = stored
        results["fusion_note"] = (
            "Weighted-fusion / section arms did not persist per-patient ranked "
            "lists. P@20, P@50, and the 10-in-20 bar cannot be reconstructed "
            "without re-running fusion. Stored P@10 and recall@k are copied here."
        )

    slim = json.loads(json.dumps(results))
    for y in slim.get("gold") or {}:
        slim["gold"][y].pop("topics", None)
    OUT.write_text(json.dumps(slim, indent=2), encoding="utf-8")
    write_report(results)
    print(f"wrote {OUT} and {REPORT}", flush=True)


def qfmt(q: dict) -> str:
    if not q:
        return "n/a"
    return (
        f"mean {q['mean']:.1f}, median {q['median']:.1f}, "
        f"min {q['min']:.0f}, p10 {q['p10']:.1f}, p25 {q['p25']:.1f}, "
        f"p75 {q['p75']:.1f}, p90 {q['p90']:.1f}, max {q['max']:.0f}"
    )


def bar_line(agg: dict) -> str:
    b = agg["bar20"]
    share = b["meet"] / agg["n_topics"] if agg["n_topics"] else 0
    poss = b["meet_among_possible"]
    return (
        f"{b['meet']}/{agg['n_topics']} ({share:.1%}) meet ≥10 eligible in top 20; "
        f"possible for {b['possible']}/{agg['n_topics']}; "
        f"of those possible, {pct(poss)} meet it"
    )


def write_report(results: dict) -> None:
    g21 = results["gold"]["2021"]
    g22 = results["gold"]["2022"]
    y21 = results["years"]["2021"]
    y22 = results["years"]["2022"]
    pooled = results["pooled_125"]
    rank_names = [
        "kw_hybrid",
        "llm_raw_top200",
        "medcpt_ce_keywords",
        "medcpt_ce_raw",
        "msmarco_ce_keywords",
        "msmarco_ce_raw",
    ]
    cheap_names = [
        "cheap_hybrid_sample",
        "cheap_lexical_title_cond",
        "cheap_ce_title_cond",
        "cheap_ce_title_cond_slice",
        "cheap_ce_title_body_512",
        "cheap_qwen_title_cond",
        "cheap_qwen_title_cond_slice",
        "cheap_mini_title_cond",
        "cheap_mini_title_cond_slice",
    ]
    lines = [
        "# Precision, ceilings, and the 10-in-20 bar (2021/2022 only)",
        "",
        "Recomputed from stored shortlists and scores. No new retrieval, GPU, or API run.",
        "2023 was not touched. Original gates in `THRESHOLDS.md` are not edited.",
        "",
        "Aggregation is the **macro mean of per-patient precision**: each patient is one",
        "screening job. Micro-averaging would let patients with 200 eligible trials",
        "dominate. The number that matches the product requirement is not that mean;",
        "it is a **count of patients** with at least 10 eligible trials in the top 20.",
        "",
        "## Eligible trials per patient (the distribution, not the mean)",
        "",
        "Label 2 in the judged pool. This is independent of any ranker.",
        "",
        f"- **2021** (n=75): {qfmt(g21['eligible'])}",
        f"- **2022** (n=50): {qfmt(g22['eligible'])}",
        "",
        f"2021 patients with fewer than 10 eligible trials: **{g21['n_elig_lt_10']}/75**. "
        f"Fewer than 20: **{g21['n_elig_lt_20']}/75**.",
        f"2022: **{g22['n_elig_lt_10']}/50** under 10, **{g22['n_elig_lt_20']}/50** under 20.",
        "",
        f"Will's bar (≥10 eligible in a top 20) is even possible for "
        f"**{g21['possible10_in20']}/75** patients in 2021 and "
        f"**{g22['possible10_in20']}/50** in 2022. The rest do not have 10 gold",
        "eligible trials at all. Retrieval then leaves "
        f"**{g21['possible10_in20_retrieved']}/75** (2021) and "
        f"**{g22['possible10_in20_retrieved']}/50** (2022) with at least 10 eligible",
        "inside the 6% shortlist — the most a reranker of that shortlist can show.",
        "",
        f"Disease-relevant (labels 1+2) 2021: {qfmt(g21['relevant'])}.",
        f"2022: {qfmt(g22['relevant'])}.",
        "",
        "The mean of 76 would have been a reasonable headline for 2021. It still hides",
        "the tails. Do not convert a mean recall into a count by multiplying by 76.",
        "That is how “9.0% recall@10 ≈ 7 of 10” was obtained, and it is not what",
        "macro-recall times mean-n equals. **Mean eligible hits in the top 10 is",
        "already on disk as P@10 × 10.** For keyword hybrid that is 2.9 of 10, not 7.",
        "",
        "## Ceilings, per patient then averaged",
        "",
        "Recall ceiling at depth k is min(1, k / n_eligible). Precision ceiling is",
        "min(1, n_eligible / k). Average after, not before.",
        "",
        "| Year | Depth | Mean recall ceiling | Mean precision ceiling | Naive 10-or-20 / mean-n |",
        "|---|---:|---:|---:|---:|",
    ]
    for year, g, ypack in (("2021", g21, y21), ("2022", g22, y22)):
        base = ypack["kw_hybrid"]
        nmean = g["eligible"]["mean"]
        for d in DEPTHS:
            naive = min(1.0, d / nmean)
            lines.append(
                f"| {year} | {d} | {pct(base[f'macro_r{d}_ceil'])} | "
                f"{pct(base[f'macro_p{d}_ceil'])} | {pct(naive)} |"
            )
    lines += [
        "",
        "2021 recall@10 ceiling is **not** 13%. 13% is 10/76. The mean of per-patient",
        "ceilings is higher because 1/n is convex and because some patients have few",
        "eligible trials (ceiling 100%). The triple-recall gate of 17% sits **below**",
        "the real 2021 recall@10 ceiling — so that gate was not physically impossible.",
        "It was still the wrong target: it asked for a share of a long tail, not for",
        "what a coordinator sees on the first page.",
        "",
        "Precision@20 ceiling is below 100% because some patients have fewer than 20",
        "eligible trials. Will's 50% of 20 is 10 eligible shown. Against the mean",
        "precision ceiling, 50% absolute is a large fraction of achievable — compute",
        "the row, do not assume 100%.",
        "",
        "## Ranking configurations (full 2021 / 2022)",
        "",
        "Counts are mean eligible (label 2) or disease-relevant (1+2) in the top N.",
        "Share is macro P@N. “Of ceiling” is mean(P / P_ceiling) per patient.",
        "",
        "### 2021 (75 patients)",
        "",
        "| Arm | elig@10 | P@10 | of ceil | elig@20 | P@20 | of ceil | elig@50 | P@50 | rel@10 | rel@20 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    def table_row(name: str, agg: dict) -> str:
        return (
            f"| {name} | {agg['mean_elig_hits_10']:.2f} | {pct(agg['macro_p10_elig'])} | "
            f"{pct(agg['macro_p10_of_ceil'])} | {agg['mean_elig_hits_20']:.2f} | "
            f"{pct(agg['macro_p20_elig'])} | {pct(agg['macro_p20_of_ceil'])} | "
            f"{agg['mean_elig_hits_50']:.2f} | {pct(agg['macro_p50_elig'])} | "
            f"{agg['mean_rel_hits_10']:.2f} | {agg['mean_rel_hits_20']:.2f} |"
        )

    for name in rank_names:
        if name in y21:
            lines.append(table_row(name, y21[name]))
    lines += [
        "",
        "### 2022 (50 patients)",
        "",
        "| Arm | elig@10 | P@10 | of ceil | elig@20 | P@20 | of ceil | elig@50 | P@50 | rel@10 | rel@20 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in rank_names:
        if name in y22:
            lines.append(table_row(name, y22[name]))
    lines += [
        "",
        "## The product bar: ≥10 eligible in the top 20",
        "",
        "2021 is the 75-patient set the requirement was stated on. 2022 is the other",
        "admission-note year. Cheap-pass arms were only scored on the 30-patient sample;",
        "they are in a later section, not mixed into 75.",
        "",
        "| Year | Arm | Patients with ≥10 eligible in top 20 | Possible (n_elig ≥ 10) | Of those possible |",
        "|---|---|---:|---:|---:|",
    ]
    for year, ypack, n in (("2021", y21, 75), ("2022", y22, 50)):
        for name in rank_names:
            if name not in ypack:
                continue
            b = ypack[name]["bar20"]
            lines.append(
                f"| {year} | {name} | {b['meet']}/{n} | {b['possible']}/{n} | "
                f"{pct(b['meet_among_possible'])} |"
            )
    lines += [
        "",
        "Wilson 95% on 2021 keyword-hybrid meet rate: "
        + wilson_s(y21["kw_hybrid"]["bar20"]["meet_wilson"])
        + ".",
        "Best 2021 rerank (`llm_raw_top200`): "
        + wilson_s((y21.get("llm_raw_top200") or {}).get("bar20", {}).get("meet_wilson"))
        + ".",
        "",
        "## Weighted fusion and section ranking",
        "",
        results.get("fusion_note") or "Fusion lists were not stored.",
        "",
        "Stored P@10 eligible (already computed at the time; not a new run):",
        "",
        "| Year | Arm | P@10 eligible | Recall@10 | Recall@20 |",
        "|---|---|---:|---:|---:|",
    ]
    stored = results.get("fusion_stored_p10_only") or {}
    for y in ("2021", "2022"):
        for name, arm in (stored.get(y) or {}).items():
            er = arm.get("eligible_recall") or {}
            lines.append(
                f"| {y} | {name} | {pct(arm.get('p10_eligible'))} | "
                f"{pct(er.get('10'))} | {pct(er.get('20'))} |"
            )
    lines += [
        "",
        "P@10 barely moves. Baseline 2021 is 28.5%; best official (`idf_section`) is",
        "28.4%. The +3-point **recall** gate was a different unit from the first page.",
        "The 10-in-20 bar cannot be scored for these arms without re-running fusion.",
        "",
        "## Cheap pass (30-patient sample only)",
        "",
        "These arms **filter** the hybrid shortlist, then the remaining trials keep",
        "hybrid order. Top 20 after a filter is “the first 20 survivors,” not a new",
        "ranker. Sample seed 20261001, 15+15.",
        "",
        "| Arm | n | elig@10 | P@10 | elig@20 | P@20 | ≥10 in top 20 | possible |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in cheap_names:
        if name not in pooled:
            continue
        agg = pooled[name]
        b = agg["bar20"]
        lines.append(
            f"| {name} | {agg['n_topics']} | {agg['mean_elig_hits_10']:.2f} | "
            f"{pct(agg['macro_p10_elig'])} | {agg['mean_elig_hits_20']:.2f} | "
            f"{pct(agg['macro_p20_elig'])} | {b['meet']}/{agg['n_topics']} | "
            f"{b['possible']}/{agg['n_topics']} |"
        )
    hy_s = pooled.get("cheap_hybrid_sample") or {}
    llm = y21.get("llm_raw_top200") or {}
    hy = y21["kw_hybrid"]
    lines += [
        "",
        "If a cheap pass only drops the tail, the first page does not move. If it drops",
        "junk that sat in the top 20, P@20 rises. Retention and first-page quality are",
        "different questions — that is why a 50% keep rule was the wrong gate for this",
        "product bar.",
        "",
        "## Is precision the right lens?",
        "",
        "For “of 20 shown, 10 eligible,” **yes**, and the honest form is the patient",
        "count, not mean P@20. Mean precision still hides patients with 5 eligible",
        "trials (who can never hit 10 in 20) and patients with 200 (who pull the mean).",
        "",
        "Recall@k is the wrong gate when k is far below n_eligible. It is still the",
        "right gate for the first stage at 6% of the collection, where the list is",
        "long enough to hold almost every eligible trial. Do not use one number for",
        "both jobs.",
        "",
        "Disease-relevant hits (labels 1+2) are reported because an excluded trial",
        "is still a coordinator glance. They are not the product bar. Will asked for",
        "eligible.",
        "",
        "## Which conclusions change",
        "",
        "Three different mistakes. They do not share a verdict.",
        "",
        "### 1. Reranking — wrong gate, not an automatic pass",
        "",
        f"2021 mean recall@10 ceiling is {pct(hy['macro_r10_ceil'])}, so 17% was",
        "achievable in principle. It was still the wrong target. The conversion",
        "“9.0% of a 13% ceiling ≈ 7 of 10” is false. Keyword hybrid puts",
        f"**{hy['mean_elig_hits_10']:.1f} eligible in the top 10** (P@10 {pct(hy['macro_p10_elig'])},",
        f"{pct(hy['macro_p10_of_ceil'])} of the precision ceiling). Best rerank",
        f"(`llm_raw_top200`) puts **{llm.get('mean_elig_hits_10', 0):.1f} in 10**",
        f"(P@10 {pct(llm.get('macro_p10_elig'))}, {pct(llm.get('macro_p10_of_ceil'))} of ceiling)",
        f"and **{llm.get('mean_elig_hits_20', 0):.1f} in 20**.",
        "",
        f"Product bar, 2021, 75 patients: hybrid {hy['bar20']['meet']}/75 have ≥10",
        f"eligible in the top 20 (possible for {hy['bar20']['possible']}/75).",
        f"Best rerank: {llm.get('bar20', {}).get('meet')}/75",
        f"(of possible, {pct((llm.get('bar20') or {}).get('meet_among_possible'))}).",
        "That is a lift, not a pass on “at least 10 of 20 for a coordinator.”",
        "The 17% recall stop should be retired as misspecified. The product stop",
        "**does not flip**. MS MARCO still hurts the first page.",
        "",
        "### 2. Weighted fusion + section ranking — still a genuine fail on the first page",
        "",
        f"The +3-point recall@10 gate was achievable (ceiling {pct(hy['macro_r10_ceil'])},",
        "target 8.7%). Stored P@10 does not move (28.5% baseline → 28.4% best official).",
        "A coordinator reading ten sees the same list. Real fail, different kind:",
        "the method did not change the page. 10-in-20 was not persisted; unchanged",
        "P@10 is enough to say it would not have cleared Will's bar.",
        "",
        "### 3. Cheap pass — 50% retention was arbitrary; the first page is mixed",
        "",
        "Retention is a reader-cost sketch, not a product number. On the 30-patient",
        "sample, unfiltered hybrid already has "
        + (
            f"{hy_s.get('bar20', {}).get('meet')}/{hy_s.get('n_topics')} "
            "with ≥10 eligible in top 20"
            if hy_s
            else "n/a"
        )
        + ". Filters that drop eligible trials from the head can lower that count;",
        "filters that only drop the tail leave it alone. The 90%/50% joint window",
        "is still a true statement about **how much remains for the reader**. It is",
        "not the 10-in-20 statement. Do not promote a cheap pass from this table",
        "without looking at whether the first 20 got better or worse.",
        "",
        "JSON: `data/trec/trec_precision.json`. No overall accuracy.",
        "The system does not say a patient qualifies.",
        "",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
