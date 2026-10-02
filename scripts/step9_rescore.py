"""Re-score ceiling, matching-gated narrowing, and lost-joinable after the key fixes.

Writes *_after_fix.json. Leaves the previous JSON reports in place.
Does not regenerate the Will extra-exclusion sheet.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import step2_ceiling  # noqa: E402
import step3d_match  # noqa: E402
from step2_ceiling import load_markers, load_step5b, load_yes_no  # noqa: E402
from step3d_match import FACTS, listed_facts, load_assigned, retrieve  # noqa: E402
from step3d_reassign import canonical_name  # noqa: E402
from step8_common import DESIGN, DATA, ROOT, wilson  # noqa: E402
from step8_sample import oracle_out  # noqa: E402
from step8_score import gold_by_id, load_best, overall_of  # noqa: E402
from therapy_containment import load_child_to_parent  # noqa: E402

OLD_CEILING = DATA / "step2_ceiling.json"
NEW_CEILING = DATA / "step2_ceiling_after_fix.json"
OLD_MATCH = DATA / "step3d_match_report.json"
NEW_MATCH = DATA / "step3d_match_report_after_fix.json"
OLD_STEP8 = DATA / "step8_report.json"
NEW_STEP8 = DATA / "step8_report_after_fix.json"
SAMPLE = DATA / "step8_sample.json"
PARSE = DATA / "step4_parse.json"
VAGUE_PARSE = DATA / "step3d_vague_parse.json"
PATIENTS = DATA / "fake_patients_draw.json"
COMPARE = DATA / "step9_after_fix.json"
REPORT = ROOT / "docs" / "step9_after_fix.md"


def matching_discarded(pid: str, p: dict, yes_no, markers, extra, listed, found, universe) -> set[str]:
    discarded = set()
    for nct in universe:
        facts_out = oracle_out(p, nct, yes_no, markers, extra)
        for fact in FACTS:
            if facts_out[fact] and nct in found[fact]:
                discarded.add(nct)
    return discarded


def score_lost_joinable() -> dict:
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    yes_no = load_yes_no()
    markers = load_markers()
    extra = load_step5b()
    universe = sorted(set(yes_no) & set(markers) & set(extra))
    gold = gold_by_id()
    best = load_best()
    edges = load_child_to_parent()
    assigned = load_assigned()
    trial_names: dict[str, set[str]] = defaultdict(set)
    for row in assigned:
        trial_names[row["nct_id"]].add(canonical_name(row.get("assigned_name") or ""))
    parse = {row["patient_id"]: row for row in json.loads(PARSE.read_text(encoding="utf-8"))["patients"]}
    vague = {row["patient_id"]: row for row in json.loads(VAGUE_PARSE.read_text(encoding="utf-8"))["patients"]}
    parse["V01"] = vague["V01"]

    expensive = DESIGN["expensive_model"]
    cheap = DESIGN["cheap_model"]
    by_model = {}
    set_shift = {}
    for pid in DESIGN["patients"]:
        p = gold[pid]
        traits = (parse[pid].get("answer") or {}).get("traits") or []
        listed = listed_facts(traits)
        found = {}
        for fact in FACTS:
            found[fact] = set() if fact not in listed else retrieve(listed[fact], trial_names, False, edges)
        new_disc = matching_discarded(pid, p, yes_no, markers, extra, listed, found, universe)
        old_disc = set(sample["patients"][pid]["discarded"])
        old_kept = set(sample["patients"][pid]["kept"])
        sampled = old_disc | old_kept
        set_shift[pid] = {
            "old_sample_discarded": len(old_disc),
            "old_sample_kept": len(old_kept),
            "new_matching_discarded_in_universe": len(new_disc),
            "sampled_still_discarded": len(sampled & new_disc),
            "sampled_now_kept": len(old_disc - new_disc),
            "sampled_now_discarded": len(old_kept & new_disc),
        }

        for model in (expensive, cheap):
            by_model.setdefault(model, {"k": 0, "n": 0, "per_patient": {}, "lost_rows": []})
            k = n = 0
            for nct in sampled:
                if nct not in new_disc:
                    continue
                row = best.get((model, pid, nct, 1))
                if not row or not row.get("answer"):
                    continue
                n += 1
                if overall_of(row) == "candidate_needs_human_check":
                    k += 1
                    by_model[model]["lost_rows"].append({"patient_id": pid, "nct_id": nct})
            by_model[model]["k"] += k
            by_model[model]["n"] += n
            by_model[model]["per_patient"][pid] = {
                "k": k,
                "n": n,
                "rate": round(k / n, 4) if n else None,
                "ci": wilson(k, n) if n else None,
            }

    out = {"set_shift": set_shift, "by_model": {}}
    for model, row in by_model.items():
        rate = row["k"] / row["n"] if row["n"] else None
        out["by_model"][model] = {
            "k": row["k"],
            "n": row["n"],
            "rate": round(rate, 4) if rate is not None else None,
            "ci": wilson(row["k"], row["n"]) if row["n"] else None,
            "gate_unsafe_above": 0.10,
            "cleared": (rate if rate is not None else 1) <= 0.10,
            "per_patient": row["per_patient"],
            "n_lost_rows": len(row["lost_rows"]),
        }
    return out


def pct(x) -> str:
    if x is None:
        return "n/a"
    return f"{x:.1%}"


def main() -> None:
    old_ceiling = json.loads(OLD_CEILING.read_text(encoding="utf-8"))
    old_match = json.loads(OLD_MATCH.read_text(encoding="utf-8"))
    old_step8 = json.loads(OLD_STEP8.read_text(encoding="utf-8"))

    print("scoring ceiling...", flush=True)
    step2_ceiling.OUT = NEW_CEILING
    step2_ceiling.main()

    print("scoring matching-gated...", flush=True)
    step3d_match.OUT = NEW_MATCH
    step3d_match.CEILING = NEW_CEILING
    step3d_match.main()

    print("scoring lost-joinable against corrected key...", flush=True)
    lost = score_lost_joinable()
    NEW_STEP8.write_text(json.dumps({
        "note": (
            "Lost-joinable re-scored against the corrected key using existing Step 8 "
            "reads. Sampled trials that the new matching-gated filter still discards. "
            "Does not regenerate the Will extra-exclusion sheet."
        ),
        "measurement_1_lost_joinable": lost,
    }, indent=2), encoding="utf-8")

    new_ceiling = json.loads(NEW_CEILING.read_text(encoding="utf-8"))
    new_match = json.loads(NEW_MATCH.read_text(encoding="utf-8"))
    expensive = DESIGN["expensive_model"]
    old_lost = old_step8["by_model"][expensive]["measurement_1_lost_joinable"]
    new_lost = lost["by_model"][expensive]

    compare = {
        "old": {
            "ceiling_union_mean": old_ceiling["union_mean"],
            "ceiling_optimistic_mean": old_ceiling.get("union_optimistic_mean"),
            "matching_gated_union_mean": old_match["matching_gated_ceiling"]["union_mean"],
            "matching_gated_if_every_fact_queried": old_match["matching_gated_if_every_fact_queried"]["union_mean"],
            "lost_joinable": {"rate": old_lost["rate"], "k": old_lost["k"], "n": old_lost["n"]},
        },
        "new": {
            "ceiling_union_mean": new_ceiling["union_mean"],
            "ceiling_optimistic_mean": new_ceiling.get("union_optimistic_mean"),
            "matching_gated_union_mean": new_match["matching_gated_ceiling"]["union_mean"],
            "matching_gated_if_every_fact_queried": new_match["matching_gated_if_every_fact_queried"]["union_mean"],
            "lost_joinable": {
                "rate": new_lost["rate"],
                "k": new_lost["k"],
                "n": new_lost["n"],
                "cleared": new_lost["cleared"],
            },
        },
        "deltas": {
            "ceiling": round(new_ceiling["union_mean"] - old_ceiling["union_mean"], 4),
            "matching_gated": round(
                new_match["matching_gated_ceiling"]["union_mean"]
                - old_match["matching_gated_ceiling"]["union_mean"],
                4,
            ),
            "lost_joinable": None
            if old_lost["rate"] is None or new_lost["rate"] is None
            else round(new_lost["rate"] - old_lost["rate"], 4),
        },
        "withdraw_narrowing": not new_lost["cleared"],
        "lost_joinable_detail": lost,
    }
    COMPARE.write_text(json.dumps(compare, indent=2), encoding="utf-8")

    o, n = compare["old"], compare["new"]
    lost_delta = compare["deltas"]["lost_joinable"]
    lost_delta_s = "n/a" if lost_delta is None else f"{lost_delta:+.1%}"
    lines = [
        "# Step 9 — numbers after the remaining-list fixes",
        "",
        "Previous reports stay on disk. This page is the side-by-side.",
        "The 12 title-inferred stage labels were cleared, 70 crossing slots",
        "were re-labelled, and a narrowing word on a bar became",
        "`barred_with_exception` (keeps the trial).",
        "",
        "A smaller headline that discards fewer joinable trials is the better",
        "system, not a regression.",
        "",
        "| | Before | After | Change | Why |",
        "|---|---:|---:|---:|---|",
        f"| Ceiling (perfect finder) | {pct(o['ceiling_union_mean'])} | {pct(n['ceiling_union_mean'])} | "
        f"{compare['deltas']['ceiling']:+.1%} | Twelve false stage requirements dropped; "
        "qualified bars no longer discard. |",
        f"| Matching-gated narrowing | {pct(o['matching_gated_union_mean'])} | {pct(n['matching_gated_union_mean'])} | "
        f"{compare['deltas']['matching_gated']:+.1%} | Same key changes, still gated on matching. |",
        f"| Lost-joinable (gpt-5.4, discarded stratum) | {pct(o['lost_joinable']['rate'])} "
        f"({o['lost_joinable']['k']}/{o['lost_joinable']['n']}) | {pct(n['lost_joinable']['rate'])} "
        f"({n['lost_joinable']['k']}/{n['lost_joinable']['n']}) | {lost_delta_s} | "
        "Existing reads, scored against the corrected matching-gated discarded set. |",
        f"| Ceiling if conditionals could be settled | {pct(o['ceiling_optimistic_mean'])} | "
        f"{pct(n['ceiling_optimistic_mean'])} | | Qualifier pass moves rows into this bucket. |",
        "",
        f"10% lost-joinable gate: **{'cleared' if n['lost_joinable']['cleared'] else 'BREACHED — withdraw the narrowing figure'}**.",
        "",
        "Old files: `data/step2_ceiling.json`, `data/step3d_match_report.json`, `data/step8_report.json`.",
        "New files: `data/step2_ceiling_after_fix.json`, `data/step3d_match_report_after_fix.json`, `data/step8_report_after_fix.json`.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({k: compare[k] for k in compare if k != "lost_joinable_detail"}, indent=2))
    print("Wrote", COMPARE)
    print("Wrote", REPORT)


if __name__ == "__main__":
    main()
