"""Score cheap-pass candidates against committed gates. 2021/2022 only."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_cheap_common import (  # noqa: E402
    GPU_SCORES,
    LEXICAL_SCORES,
    MINI_SCORES,
    RECALL_SHIP,
    RECALL_STOP,
    REPORT,
    RESULTS,
    RETENTION_MAX,
    RETRIEVAL_ELIGIBLE,
    YEARS,
    gate_label,
    keep_from_ce_logit,
    keep_from_decision,
    load_sample,
    load_shortlist,
    mean,
    pct,
    pooled_from_topics,
    topic_counts,
    wilson,
)
from trec_hybrid_common import qrels_by_topic  # noqa: E402

LAMBDA_A10_USD_PER_HOUR = 0.75


def kept_from_lexical(payload: dict, year: str, tid: str) -> set[str]:
    bucket = ((payload.get("decisions") or {}).get(year) or {}).get(tid) or {}
    return {nct for nct, rec in bucket.items() if rec.get("keep")}


def kept_from_ce(payload: dict, doc: str, year: str, tid: str) -> set[str]:
    bucket = (((payload.get("ce") or {}).get(doc) or {}).get(year) or {}).get(tid) or {}
    return {nct for nct, logit in bucket.items() if keep_from_ce_logit(logit)}


def kept_from_qwen(payload: dict, doc: str, year: str, tid: str) -> set[str]:
    bucket = (((payload.get("qwen") or {}).get(doc) or {}).get(year) or {}).get(tid) or {}
    return {nct for nct, word in bucket.items() if keep_from_decision(word)}


def kept_from_mini(payload: dict, doc: str, year: str, tid: str) -> set[str]:
    bucket = (((payload.get("decisions") or {}).get(doc) or {}).get(year) or {}).get(tid) or {}
    return {nct for nct, word in bucket.items() if keep_from_decision(word)}


def eval_arm(name: str, doc: str, getter, sample, short, qrels, extra: dict) -> dict:
    rows = []
    missing = 0
    for year in YEARS:
        y = str(year)
        labels_year = qrels[year]
        for tid in sample["years"][y]:
            trow = short["years"][y]["topics"][tid]
            shortlist = trow["shortlist"]
            kept = getter(y, tid)
            scored = extra.get("scored_n")
            if scored is not None and len(kept) == 0 and scored == 0:
                missing += 1
            rows.append(
                {
                    "year": year,
                    "topic": tid,
                    **topic_counts(shortlist, labels_year.get(tid, {}), kept),
                }
            )
    pooled = pooled_from_topics(rows)
    n_topics = pooled["n_topics"]
    high_recall_topics = sum(1 for r in rows if r["recall"] is not None and r["recall"] >= RECALL_SHIP)
    e2e = {}
    for year in YEARS:
        year_rows = [r for r in rows if r["year"] == year]
        elig = mean([r["eligible_recall"] for r in year_rows if r["eligible_recall"] is not None])
        if elig is None:
            e2e[str(year)] = None
        else:
            e2e[str(year)] = round(RETRIEVAL_ELIGIBLE[year] * elig, 4)
    usd = extra.get("usd")
    seconds = extra.get("seconds")
    per_patient_usd = None if usd is None else round(usd / max(n_topics, 1), 4)
    per_patient_sec = None if seconds is None else round(seconds / max(n_topics, 1), 2)
    return {
        "name": name,
        "doc": doc,
        **pooled,
        "topics_ge_90": high_recall_topics,
        "topics_ge_90_wilson": wilson(high_recall_topics, n_topics),
        "e2e_eligible_recall": e2e,
        "usd": usd,
        "seconds": seconds,
        "usd_per_patient": per_patient_usd,
        "seconds_per_patient": per_patient_sec,
        "gpu_hours": extra.get("gpu_hours"),
        "gpu_usd": extra.get("gpu_usd"),
        **{k: v for k, v in extra.items() if k not in {"usd", "seconds", "gpu_hours", "gpu_usd", "scored_n"}},
        "topics": rows,
    }


def pick_winner(arms: list[dict]) -> dict | None:
    cleared = [a for a in arms if a.get("gate") == "clears"]
    if not cleared:
        return None
    def key(a: dict):
        ret = a.get("retention_micro")
        cost = a.get("usd_per_patient")
        if cost is None:
            cost = a.get("gpu_usd_per_patient")
        if cost is None:
            cost = 0.0
        return (ret if ret is not None else 9, cost, a["name"])
    cleared.sort(key=key)
    return {
        "name": cleared[0]["name"],
        "doc": cleared[0]["doc"],
        "retention_micro": cleared[0]["retention_micro"],
        "recall_micro": cleared[0]["recall_micro"],
        "reason": "clears both bars; lowest retention, then lowest cost",
    }


def gpu_cost(seconds: float | None) -> tuple[float | None, float | None]:
    if not seconds:
        return None, None
    hours = seconds / 3600
    return round(hours, 4), round(hours * LAMBDA_A10_USD_PER_HOUR, 4)


def write_report(results: dict) -> None:
    lines = [
        "# Cheap topical pass on the shortlist (2021/2022 only)",
        "",
        "Gates committed in `THRESHOLDS.md` before any keep/drop score.",
        "30-patient sample, seed 20261001. 2023 was not run. This is not the reader.",
        "",
        "Question: could this trial conceivably be about this patient's problem?",
        "Uncertainty keeps the trial.",
        "",
        "## Gates",
        "",
        f"- Disease-relevant recall ≥ {RECALL_SHIP:.0%} to ship; below {RECALL_STOP:.0%} the candidate is rejected.",
        f"- Retention ≤ {RETENTION_MAX:.0%} of the shortlist.",
        "- Winner: among those that clear both, lowest retention, then lowest cost.",
        "",
        "## Sample result",
        "",
        "| Candidate | Doc text | Disease-relevant recall | Eligible recall | Retention | Gate | $/patient | sec/patient |",
        "|---|---|---:|---:|---:|---|---:|---:|",
    ]
    for arm in results["arms"]:
        usd = arm.get("usd_per_patient")
        if usd is None and arm.get("gpu_usd_per_patient") is not None:
            usd = arm["gpu_usd_per_patient"]
        sec = arm.get("seconds_per_patient")
        lines.append(
            "| {name} | {doc} | {rec} | {elig} | {ret} | {gate} | {usd} | {sec} |".format(
                name=arm["name"],
                doc=arm["doc"],
                rec=pct(arm.get("recall_micro")),
                elig=pct(arm.get("eligible_recall_micro")),
                ret=pct(arm.get("retention_micro")),
                gate=arm.get("gate"),
                usd="n/a" if usd is None else f"{usd:.4f}",
                sec="n/a" if sec is None else f"{sec:.1f}",
            )
        )
    winner = results.get("winner")
    lines += [
        "",
        "## Winner",
        "",
        "None. No candidate cleared both bars. Full scale was not run."
        if not winner
        else f"**{winner['name']}** on `{winner['doc']}`. Recall {pct(winner.get('recall_micro'))}, retention {pct(winner.get('retention_micro'))}. {winner.get('reason')}",
        "",
        "End-to-end eligible recall is retrieval 91.6%/91.4% times this pass's eligible recall.",
        "No overall accuracy. The system does not say a patient qualifies.",
        "",
        "Per-patient JSON: `data/trec/cheap_pass_results.json`.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    sample = load_sample()
    short = load_shortlist()
    qrels = {year: qrels_by_topic(year) for year in YEARS}
    arms = []

    if LEXICAL_SCORES.exists():
        lex = json.loads(LEXICAL_SCORES.read_text(encoding="utf-8"))
        arms.append(
            eval_arm(
                "lexical_first_keyword",
                "title_cond",
                lambda y, tid, payload=lex: kept_from_lexical(payload, y, tid),
                sample,
                short,
                qrels,
                {"usd": 0.0, "seconds": lex.get("seconds"), "gpu_hours": 0.0, "gpu_usd": 0.0},
            )
        )

    gpu = None
    if GPU_SCORES.exists():
        gpu = json.loads(GPU_SCORES.read_text(encoding="utf-8"))
        ce_secs = gpu.get("seconds") or {}
        for doc in ("title_cond", "title_cond_slice", "title_body_512"):
            if doc not in (gpu.get("ce") or {}):
                continue
            sec = ce_secs.get(f"ce_{doc}")
            hours, usd = gpu_cost(sec)
            n_topics = 30
            arms.append(
                eval_arm(
                    "medcpt_ce",
                    doc,
                    lambda y, tid, d=doc: kept_from_ce(gpu, d, y, tid),
                    sample,
                    short,
                    qrels,
                    {
                        "seconds": sec,
                        "gpu_hours": hours,
                        "gpu_usd": usd,
                        "gpu_usd_per_patient": None if usd is None else round(usd / n_topics, 4),
                        "keep_rule": "logit>0",
                    },
                )
            )
        for doc in ("title_cond", "title_cond_slice"):
            if doc not in (gpu.get("qwen") or {}):
                continue
            sec = ce_secs.get(f"qwen_{doc}")
            hours, usd = gpu_cost(sec)
            arms.append(
                eval_arm(
                    "qwen2.5_7b",
                    doc,
                    lambda y, tid, d=doc: kept_from_qwen(gpu, d, y, tid),
                    sample,
                    short,
                    qrels,
                    {
                        "seconds": sec,
                        "gpu_hours": hours,
                        "gpu_usd": usd,
                        "gpu_usd_per_patient": None if usd is None else round(usd / 30, 4),
                    },
                )
            )

    if MINI_SCORES.exists():
        mini = json.loads(MINI_SCORES.read_text(encoding="utf-8"))
        n_docs = len(mini.get("decisions") or {})
        total_usd = mini.get("usd")
        total_sec = mini.get("seconds")
        for doc in ("title_cond", "title_cond_slice"):
            if doc not in (mini.get("decisions") or {}):
                continue
            share = 1 / max(n_docs, 1)
            arms.append(
                eval_arm(
                    "gpt-4o-mini",
                    doc,
                    lambda y, tid, d=doc: kept_from_mini(mini, d, y, tid),
                    sample,
                    short,
                    qrels,
                    {
                        "usd": None if total_usd is None else round(total_usd * share, 4),
                        "seconds": None if total_sec is None else round(total_sec * share, 1),
                    },
                )
            )

    winner = pick_winner(arms)
    results = {
        "n_topics": 30,
        "seed": 20261001,
        "recall_ship": RECALL_SHIP,
        "recall_stop": RECALL_STOP,
        "retention_max": RETENTION_MAX,
        "winner": winner,
        "run_full": bool(winner),
        "arms": [{k: v for k, v in a.items() if k != "topics"} | {"n_topic_rows": len(a.get("topics") or [])} for a in arms],
        "topic_rows": {f"{a['name']}|{a['doc']}": a["topics"] for a in arms},
    }
    RESULTS.write_text(json.dumps(results, indent=2), encoding="utf-8")
    write_report(results)
    print(json.dumps({"winner": winner, "gates": [(a["name"], a["doc"], a["gate"], a.get("recall_micro"), a.get("retention_micro")) for a in arms]}, indent=2))
    print(f"wrote {REPORT}", flush=True)


if __name__ == "__main__":
    main()
