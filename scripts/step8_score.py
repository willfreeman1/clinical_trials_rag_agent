"""Score Step 8 reads. No API. Four verifiable measurements, no overall accuracy."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from step2_ceiling import load_markers, load_step5b, load_yes_no  # noqa: E402
from step3c_closed_names import FACT_TO_NAME  # noqa: E402
from step8_common import (  # noqa: E402
    CHEAP,
    DATA,
    DESIGN,
    EXPENSIVE,
    FACT_TO_KEY,
    canonical_fact,
    cost_usd,
    load_trials,
    quote_status,
    topic_ok,
    wilson,
)
from step8_sample import oracle_out, v01_gold  # noqa: E402

READS = DATA / "step8_reads.jsonl"
SAMPLE = DATA / "step8_sample.json"
SETS = DATA / "step8_sets.json"
PATIENTS = DATA / "fake_patients_draw.json"
OUT = DATA / "step8_report.json"
WILL = ROOT = Path(__file__).resolve().parents[1]
WILL_PATH = WILL / "docs" / "step8_will_check.md"


def load_reads() -> list[dict]:
    rows = []
    with READS.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def gold_by_id() -> dict[str, dict]:
    gold = {p["id"]: p for p in json.loads(PATIENTS.read_text(encoding="utf-8"))["patients"]}
    gold["V01"] = v01_gold()
    return gold


def key_excluding_facts(p: dict, nct: str, yes_no, markers, extra) -> list[str]:
    flags = oracle_out(p, nct, yes_no, markers, extra)
    return [f for f, on in flags.items() if on]


def load_best() -> dict[tuple, dict]:
    """Keep the last successful answer per (model, patient, nct, pass)."""
    best = {}
    for row in load_reads():
        key = (row["model"], row["patient_id"], row["nct_id"], row.get("pass", 1))
        best[key] = row
    return best


def overall_of(row: dict) -> str | None:
    answer = row.get("answer") or {}
    return answer.get("overall")


def rules_of(row: dict) -> list[dict]:
    return list((row.get("answer") or {}).get("rules") or [])


def main() -> None:
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    sets = json.loads(SETS.read_text(encoding="utf-8"))
    trials = load_trials()
    yes_no = load_yes_no()
    markers = load_markers()
    extra = load_step5b()
    gold = gold_by_id()
    best = load_best()

    by_model = {}
    will_pool = []

    for model in (EXPENSIVE, CHEAP):
        lost = []
        quotes = Counter()
        topic = Counter()
        nei = Counter()
        nei_n = Counter()
        agree_rows = []
        extra_excl = []
        elapsed = []
        tokens_in = tokens_out = 0
        n_fail = 0
        overall_counts = Counter()
        per_patient_lost = {}

        for pid, prow in sample["patients"].items():
            p = gold[pid]
            lost_k = lost_n = 0
            for stratum, ids in (("discarded", prow["discarded"]), ("kept", prow["kept"])):
                for nct in ids:
                    row = best.get((model, pid, nct, 1))
                    if not row or not row.get("answer"):
                        n_fail += 1
                        continue
                    elapsed.append(row.get("elapsed_s") or 0)
                    usage = row.get("usage") or {}
                    tokens_in += usage.get("input_tokens") or 0
                    tokens_out += usage.get("output_tokens") or 0
                    overall = overall_of(row)
                    overall_counts[overall] += 1
                    text = trials[nct]["eligibility_criteria"]
                    for rule in rules_of(row):
                        verdict = (rule.get("verdict") or "").strip()
                        fact = canonical_fact(rule.get("fact") or "")
                        quote = rule.get("quote") or ""
                        if verdict == "not_enough_information":
                            nei[fact] += 1
                            nei_n[fact] += 1
                            continue
                        if verdict in ("excludes_this_patient", "does_not_exclude"):
                            nei_n[fact] += 1
                            status = quote_status(quote, text)
                            quotes[status] += 1
                            top = topic_ok(fact, quote)
                            if top is True:
                                topic["on_topic"] += 1
                            elif top is False:
                                topic["off_topic"] += 1
                            else:
                                topic["open_fact"] += 1
                    if stratum == "discarded":
                        lost_n += 1
                        if overall == "candidate_needs_human_check":
                            lost_k += 1
                            lost.append({"patient_id": pid, "nct_id": nct, "overall": overall})
                    key_facts = key_excluding_facts(p, nct, yes_no, markers, extra)
                    if key_facts:
                        reader_excl = overall in ("definitely_excluded", "never_eligible")
                        reader_facts = set()
                        for rule in rules_of(row):
                            if (rule.get("verdict") or "") != "excludes_this_patient":
                                continue
                            mapped = FACT_TO_KEY.get(canonical_fact(rule.get("fact") or ""))
                            if mapped:
                                reader_facts.add(mapped)
                        same = bool(set(key_facts) & reader_facts)
                        agree_rows.append({
                            "patient_id": pid,
                            "nct_id": nct,
                            "stratum": stratum,
                            "key_facts": key_facts,
                            "reader_excluded": reader_excl,
                            "same_rule": same,
                        })
                    if stratum == "kept" and not key_facts and overall == "definitely_excluded":
                        extra_excl.append({
                            "patient_id": pid,
                            "nct_id": nct,
                            "model": model,
                            "rules": [
                                r for r in rules_of(row)
                                if (r.get("verdict") or "") == "excludes_this_patient"
                            ],
                            "brief_title": row.get("brief_title"),
                        })
            per_patient_lost[pid] = {
                "k": lost_k,
                "n": lost_n,
                "rate": round(lost_k / lost_n, 4) if lost_n else None,
                "ci": wilson(lost_k, lost_n) if lost_n else None,
            }

        judged_quotes = quotes["exact"] + quotes["normalized"] + quotes["missing"] + quotes["empty"]
        missing = quotes["missing"] + quotes["empty"]
        agree_n = len(agree_rows)
        agree_k = sum(1 for r in agree_rows if r["reader_excluded"])
        same_k = sum(1 for r in agree_rows if r["reader_excluded"] and r["same_rule"])
        lost_k = sum(1 for r in lost)
        lost_n = sum(r["n"] for r in per_patient_lost.values())

        nei_rate = {}
        for fact, n in sorted(nei_n.items(), key=lambda kv: -kv[1]):
            nei_rate[fact] = {
                "not_enough_information": nei[fact],
                "n_rules": n,
                "rate": round(nei[fact] / n, 4) if n else None,
            }

        by_model[model] = {
            "n_failed_reads": n_fail,
            "overall_counts": dict(overall_counts),
            "measurement_1_lost_joinable": {
                "k": lost_k,
                "n": lost_n,
                "rate": round(lost_k / lost_n, 4) if lost_n else None,
                "ci": wilson(lost_k, lost_n) if lost_n else None,
                "per_patient": per_patient_lost,
                "gate_unsafe_above": 0.10,
                "cleared": (lost_k / lost_n if lost_n else 1) <= 0.10,
            },
            "measurement_2_fabrication": {
                "quote_status": dict(quotes),
                "missing_or_empty": missing,
                "n_judged_quotes": judged_quotes,
                "rate": round(missing / judged_quotes, 4) if judged_quotes else None,
                "ci": wilson(missing, judged_quotes) if judged_quotes else None,
                "topic": dict(topic),
                "gate_fail_above": 0.05,
                "cleared": (missing / judged_quotes if judged_quotes else 1) <= 0.05,
            },
            "measurement_3_key_exclusions": {
                "n": agree_n,
                "reader_also_excludes": agree_k,
                "rate": round(agree_k / agree_n, 4) if agree_n else None,
                "ci": wilson(agree_k, agree_n) if agree_n else None,
                "same_rule_given_exclusion": {
                    "k": same_k,
                    "n": agree_k,
                    "rate": round(same_k / agree_k, 4) if agree_k else None,
                },
                "gate_fail_below": 0.85,
                "cleared": (agree_k / agree_n if agree_n else 0) >= 0.85,
            },
            "measurement_4_extra_exclusions": {
                "n": len(extra_excl),
                "note": "kept trials the six-fact key does not exclude and the reader does",
            },
            "not_enough_information_by_fact": nei_rate,
            "cost": {
                "input_tokens": tokens_in,
                "output_tokens": tokens_out,
                "estimated_usd": round(cost_usd(model, tokens_in, tokens_out), 4),
                "n_reads_pass1": sum(r["n"] for r in per_patient_lost.values())
                + sum(len(sample["patients"][pid]["kept"]) for pid in sample["patients"]),
                "mean_elapsed_s": round(sum(elapsed) / len(elapsed), 3) if elapsed else None,
            },
        }
        if model == EXPENSIVE:
            will_pool = extra_excl

    # Consistency: P01 pass 1 vs pass 2, both models.
    consistency = {}
    pid = DESIGN["consistency_patient"]
    cons_ids = (
        [("discarded", n) for n in sample["patients"][pid]["consistency_discarded"]]
        + [("kept", n) for n in sample["patients"][pid]["consistency_kept"]]
    )
    for model in (EXPENSIVE, CHEAP):
        changed = 0
        n = 0
        pairs = []
        for stratum, nct in cons_ids:
            a = best.get((model, pid, nct, 1))
            b = best.get((model, pid, nct, 2))
            if not a or not b or not a.get("answer") or not b.get("answer"):
                continue
            n += 1
            oa, ob = overall_of(a), overall_of(b)
            flip = oa != ob
            if flip:
                changed += 1
            pairs.append({"nct_id": nct, "stratum": stratum, "pass1": oa, "pass2": ob, "changed": flip})
        consistency[model] = {
            "n": n,
            "changed": changed,
            "rate": round(changed / n, 4) if n else None,
            "ci": wilson(changed, n) if n else None,
            "pairs": pairs,
        }

    rng_n = min(20, len(will_pool))
    # Stable sample of 20 extra exclusions for Will, from expensive model.
    import random

    rng = random.Random(DESIGN["seed"])
    will_sample = list(will_pool)
    rng.shuffle(will_sample)
    will_sample = will_sample[:rng_n]

    m1_exp = by_model[EXPENSIVE]["measurement_1_lost_joinable"]
    m1_cheap = by_model[CHEAP]["measurement_1_lost_joinable"]
    gap = None
    if m1_exp["rate"] is not None and m1_cheap["rate"] is not None:
        gap = round(m1_cheap["rate"] - m1_exp["rate"], 4)

    report = {
        "models": [EXPENSIVE, CHEAP],
        "n_patients": len(sample["patients"]),
        "by_model": by_model,
        "measurement_1_gap_cheap_minus_expensive": gap,
        "consistency": consistency,
        "gates": {
            "lost_joinable_unsafe": not m1_exp["cleared"],
            "withdraw_44pct": not m1_exp["cleared"],
            "fabrication_headline": not by_model[EXPENSIVE]["measurement_2_fabrication"]["cleared"],
            "key_agreement_investigate": not by_model[EXPENSIVE]["measurement_3_key_exclusions"]["cleared"],
            "cheap_vs_expensive_no_gate": True,
            "gap": gap,
        },
        "will_check_n": len(will_sample),
        "human_interrater_context": "Doctors agreed with each other 64–70% on per-rule eligibility in published work. Do not treat 90% as a human ceiling.",
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Step 8 — Will check: 20 extra exclusions the six-fact key missed",
        "",
        "Reading comprehension only. For each row: does the quoted sentence plainly",
        "say what the model claims? Not a medical judgment. Mark agree / disagree /",
        "cannot tell from the quote.",
        "",
        f"Drawn with seed {DESIGN['seed']} from the expensive model (`{EXPENSIVE}`).",
        f"{len(will_sample)} of {len(will_pool)} extra exclusions on kept trials.",
        "",
    ]
    for i, row in enumerate(will_sample, 1):
        lines.append(f"## {i}. {row['patient_id']} / {row['nct_id']}")
        lines.append("")
        if row.get("brief_title"):
            lines.append(f"_{row['brief_title']}_")
            lines.append("")
        for rule in row.get("rules") or []:
            lines.append(f"- fact: `{rule.get('fact')}`")
            lines.append(f"- claim: {rule.get('verdict')}")
            lines.append(f"- quote: {rule.get('quote')}")
            lines.append(f"- reasoning: {rule.get('reasoning')}")
            lines.append("")
        lines.append("Will: agree / disagree / cannot tell")
        lines.append("")
    WILL_PATH.write_text("\n".join(lines), encoding="utf-8")

    print()
    for model, block in by_model.items():
        m1 = block["measurement_1_lost_joinable"]
        m2 = block["measurement_2_fabrication"]
        m3 = block["measurement_3_key_exclusions"]
        print(model)
        print(f"  lost joinable     {m1['rate']}  ({m1['k']}/{m1['n']})  cleared={m1['cleared']}")
        print(f"  missing quotes    {m2['rate']}  ({m2['missing_or_empty']}/{m2['n_judged_quotes']})  cleared={m2['cleared']}")
        print(f"  key exclusions    {m3['rate']}  ({m3['reader_also_excludes']}/{m3['n']})  cleared={m3['cleared']}")
        print(f"  extra exclusions  {block['measurement_4_extra_exclusions']['n']}")
        print(f"  usd               {block['cost']['estimated_usd']}  mean_s={block['cost']['mean_elapsed_s']}")
    print(f"gap cheap-expensive measurement 1: {gap}")
    print(f"Wrote {OUT}")
    print(f"Wrote {WILL_PATH}")


if __name__ == "__main__":
    main()
