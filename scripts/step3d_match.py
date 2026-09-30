"""Step 3d: directional containment matching, then the gated ceiling.

Neither side is rewritten. Containment is consulted only at comparison time.
Embeddings are not used. Thresholds in THRESHOLDS.md, committed before this ran.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from step2_ceiling import load_markers, load_step5b, load_yes_no, yes_no_out  # noqa: E402
from step3b_match import gated_ceiling, has_rule  # noqa: E402
from step3c_closed_names import FACT_TO_NAME  # noqa: E402
from step3d_reassign import canonical_name  # noqa: E402
from therapy_containment import (  # noqa: E402
    CANT_TELL,
    MATCH,
    _self_check,
    comparison,
    load_child_to_parent,
)

ROOT = Path(__file__).resolve().parents[1]
ASSIGNED = ROOT / "data" / "step3d_closed_names.jsonl"
PARSE = ROOT / "data" / "step4_parse.json"
VAGUE_PARSE = ROOT / "data" / "step3d_vague_parse.json"
PATIENTS = ROOT / "data" / "fake_patients_draw.json"
CEILING = ROOT / "data" / "step2_ceiling.json"
BASELINE = ROOT / "data" / "step3c_match_report.json"
OUT = ROOT / "data" / "step3d_match_report.json"

FACTS = [
    "prior_immunotherapy",
    "brain_metastases",
    "driver_mutation",
    "prior_platinum_chemo",
    "autoimmune_disease",
    "disease_stage",
]

BASELINE_RECALL = {
    "prior_immunotherapy": 0.8144,
    "brain_metastases": 0.9387,
    "driver_mutation": 0.9986,
    "prior_platinum_chemo": 0.3718,
    "autoimmune_disease": 0.9935,
    "disease_stage": 0.9328,
}

PLATINUM_NAME = "previous platinum chemotherapy"


def wilson(successes: int, total: int, z: float = 1.96) -> dict | None:
    if total == 0:
        return None
    p = successes / total
    z2 = z * z
    denom = 1 + z2 / total
    center = (p + z2 / (2 * total)) / denom
    margin = z * math.sqrt((p * (1 - p) + z2 / (4 * total)) / total) / denom
    out = {
        "point": round(p, 4),
        "low": round(max(0.0, center - margin), 4),
        "high": round(min(1.0, center + margin), 4),
        "n": total,
        "k": successes,
    }
    if total < 200:
        return out
    return {"point": round(p, 4), "n": total, "k": successes, "wilson_omitted_n_ge_200": True}


def load_assigned() -> list[dict]:
    seen: dict[str, dict] = {}
    with ASSIGNED.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("assigned_name"):
                seen[row["id"]] = row
    return list(seen.values())


def listed_facts(traits: list[dict]) -> dict[str, str]:
    """fact -> the closed name the patient actually stated."""
    out: dict[str, str] = {}
    for t in traits:
        name = canonical_name(t.get("name") or "")
        for fact, closed in FACT_TO_NAME.items():
            if name == closed:
                out[fact] = name
    return out


def all_canonical_names(traits: list[dict]) -> list[str]:
    names = []
    for t in traits:
        name = canonical_name(t.get("name") or "")
        if name and name not in names:
            names.append(name)
    return names


def trial_hits(query_name: str, trial_names: set[str], allow_cant_tell: bool, edges: dict[str, str]) -> bool:
    for trial_name in trial_names:
        result = comparison(query_name, trial_name, edges)
        if result == MATCH:
            return True
        if allow_cant_tell and result == CANT_TELL:
            return True
    return False


def retrieve(
    query_name: str,
    trial_names_by_nct: dict[str, set[str]],
    allow_cant_tell: bool,
    edges: dict[str, str],
) -> set[str]:
    return {
        nct
        for nct, names in trial_names_by_nct.items()
        if trial_hits(query_name, names, allow_cant_tell, edges)
    }


def rates(found: dict[str, set[str]], truth: dict[str, set[str]], universe: list[str], facts: list[str]) -> dict:
    out = {}
    recalls, fprs = [], []
    for fact in facts:
        tp = fp = fn = tn = 0
        for nct in universe:
            is_rule = nct in truth[fact]
            is_hit = nct in found[fact]
            if is_rule and is_hit:
                tp += 1
            elif is_rule and not is_hit:
                fn += 1
            elif not is_rule and is_hit:
                fp += 1
            else:
                tn += 1
        n_pos = tp + fn
        n_neg = fp + tn
        recall = tp / n_pos if n_pos else None
        fpr = fp / n_neg if n_neg else None
        out[fact] = {
            "recall": None if recall is None else round(recall, 4),
            "wrongly_picked_up": None if fpr is None else round(fpr, 4),
            "tp": tp,
            "fn": fn,
            "fp": fp,
            "tn": tn,
            "recall_ci": None if recall is None else wilson(tp, n_pos),
            "wrongly_picked_up_ci": None if fpr is None else wilson(fp, n_neg),
        }
        if recall is not None:
            recalls.append(recall)
        if fpr is not None:
            fprs.append(fpr)
    out["mean_recall"] = round(sum(recalls) / len(recalls), 4) if recalls else None
    out["mean_wrongly_picked_up"] = round(sum(fprs) / len(fprs), 4) if fprs else None
    return out


def original_20_have_vague_history(parse: dict) -> dict:
    """The original 20 named drugs. Confirm none parsed at the vague levels only."""
    vague_only = []
    for row in parse["patients"]:
        pid = row["patient_id"]
        names = all_canonical_names((row.get("answer") or {}).get("traits") or [])
        listed = listed_facts((row.get("answer") or {}).get("traits") or [])
        has_specific = "prior_platinum_chemo" in listed or "prior_immunotherapy" in listed
        has_vague = any(
            n in {
                "previous chemotherapy (any kind)",
                "previous systemic anticancer treatment (any kind)",
            }
            for n in names
        )
        if has_vague and not has_specific:
            vague_only.append({"id": pid, "names": names})
    return {
        "n_original_with_vague_history_only": len(vague_only),
        "ids": [r["id"] for r in vague_only],
        "note": (
            "None of the original 20 is a vague-history case. They name specific "
            "drugs or classes. Case 3 is tested on V01–V05, not on P01–P20."
            if not vague_only
            else "Unexpected: at least one of the original 20 parsed as vague-only."
        ),
    }


def main() -> None:
    _self_check()
    edges = load_child_to_parent()
    rows = load_assigned()
    yes_no = load_yes_no()
    markers = load_markers()
    extra = load_step5b()
    patients = json.loads(PATIENTS.read_text(encoding="utf-8"))["patients"]
    parse = json.loads(PARSE.read_text(encoding="utf-8"))
    vague = json.loads(VAGUE_PARSE.read_text(encoding="utf-8"))
    ids = set(yes_no) & set(markers) & set(extra)
    universe = sorted(ids)

    truth: dict[str, set[str]] = {f: set() for f in FACTS}
    for nct in universe:
        for fact in FACTS:
            if has_rule(nct, fact, yes_no, markers, extra):
                truth[fact].add(nct)

    trial_names: dict[str, set[str]] = defaultdict(set)
    confusion = Counter()
    for row in rows:
        name = canonical_name(row.get("assigned_name") or "")
        trial_names[row["nct_id"]].add(name)
        source = FACT_TO_NAME.get(row.get("fact"), "unknown")
        confusion[(source, name)] += 1

    platinum_named = {nct for nct, names in trial_names.items() if PLATINUM_NAME in names}

    parse_by_id = {row["patient_id"]: row for row in parse["patients"]}
    patient_listed: dict[str, dict[str, str]] = {}
    found_by_patient: dict[str, dict[str, set[str]]] = {}
    found_symmetric: dict[str, dict[str, set[str]]] = {}
    for p in patients:
        pid = p["id"]
        traits = (parse_by_id[pid].get("answer") or {}).get("traits") or []
        listed = listed_facts(traits)
        patient_listed[pid] = listed
        found_by_patient[pid] = {}
        found_symmetric[pid] = {}
        for fact in FACTS:
            if fact not in listed:
                found_by_patient[pid][fact] = set()
                found_symmetric[pid][fact] = set()
                continue
            query = listed[fact]
            found_by_patient[pid][fact] = retrieve(query, trial_names, False, edges)
            found_symmetric[pid][fact] = retrieve(query, trial_names, True, edges)

    per_patient = []
    for p in patients:
        pid = p["id"]
        usable = [f for f in FACTS if f in patient_listed[pid]]
        per_patient.append(rates(found_by_patient[pid], truth, universe, usable))

    summary = {"by_fact": {}, "mean_recall": None, "mean_wrongly_picked_up": None}
    recs, fprs = [], []
    for fact in FACTS:
        usable = [
            r for p, r in zip(patients, per_patient)
            if fact in patient_listed.get(p["id"], {}) and fact in r
        ]
        fact_recs = [r[fact]["recall"] for r in usable if r[fact]["recall"] is not None]
        fact_fprs = [r[fact]["wrongly_picked_up"] for r in usable if r[fact]["wrongly_picked_up"] is not None]
        # Trial-level counts are the same for every patient who listed the fact.
        sample = next((r[fact] for r in usable), None)
        summary["by_fact"][fact] = {
            "recall": round(sum(fact_recs) / len(fact_recs), 4) if fact_recs else None,
            "wrongly_picked_up": round(sum(fact_fprs) / len(fact_fprs), 4) if fact_fprs else None,
            "n_patients_with_trait": len(usable),
            "baseline_recall": BASELINE_RECALL[fact],
            "recall_delta": (
                round(sum(fact_recs) / len(fact_recs) - BASELINE_RECALL[fact], 4)
                if fact_recs else None
            ),
            "recall_ci": None if sample is None else sample.get("recall_ci"),
            "wrongly_picked_up_ci": None if sample is None else sample.get("wrongly_picked_up_ci"),
            "tp": None if sample is None else sample["tp"],
            "fn": None if sample is None else sample["fn"],
            "fp": None if sample is None else sample["fp"],
            "tn": None if sample is None else sample["tn"],
        }
        if fact_recs:
            recs.append(sum(fact_recs) / len(fact_recs))
        if fact_fprs:
            fprs.append(sum(fact_fprs) / len(fact_fprs))
    summary["mean_recall"] = round(sum(recs) / len(recs), 4) if recs else None
    summary["mean_wrongly_picked_up"] = round(sum(fprs) / len(fprs), 4) if fprs else None

    quoted: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        quoted[row["fact"]].add(row["nct_id"])
    quote_coverage = {}
    for fact in FACTS:
        have = len(truth[fact] & quoted[fact])
        total = len(truth[fact])
        quote_coverage[fact] = {
            "rule_trials": total,
            "rule_trials_with_quote": have,
            "coverage": round(have / total, 4) if total else None,
        }

    assignment = {
        "n_quotes": len(rows),
        "n_reassigned": sum(1 for r in rows if r.get("reassigned")),
        "assigned_counts": dict(Counter(canonical_name(r.get("assigned_name") or "") for r in rows)),
        "n_other": sum(1 for r in rows if canonical_name(r.get("assigned_name") or "") == "other"),
        "confusion": [
            {"source": src, "assigned": assigned, "n": n}
            for (src, assigned), n in sorted(confusion.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        "quote_coverage": quote_coverage,
    }

    gated = gated_ceiling(patients, yes_no, markers, extra, found_by_patient, FACTS)
    always = [f for f in FACTS if f != "autoimmune_disease"]
    found_complete: dict[str, dict[str, set[str]]] = {}
    for p in patients:
        listed = set(always)
        if p.get("autoimmune_disease"):
            listed.add("autoimmune_disease")
        found_complete[p["id"]] = {}
        for fact in FACTS:
            if fact not in listed:
                found_complete[p["id"]][fact] = set()
            else:
                query = FACT_TO_NAME[fact]
                found_complete[p["id"]][fact] = retrieve(query, trial_names, False, edges)
    gated_if_complete_parse = gated_ceiling(patients, yes_no, markers, extra, found_complete, FACTS)

    oracle_union = None
    if CEILING.exists():
        oracle_union = json.loads(CEILING.read_text(encoding="utf-8")).get("union_mean")

    # Safety-valve price: trials a both-directions comparison would narrow
    # that directional containment keeps.
    extra_pairs = []
    extra_by_patient = []
    for p in patients:
        pid = p["id"]
        extra_trials: set[str] = set()
        for fact in FACTS:
            if fact not in patient_listed[pid]:
                continue
            directional = found_by_patient[pid][fact]
            symmetric = found_symmetric[pid][fact]
            only_sym = symmetric - directional
            if fact == "prior_immunotherapy":
                oracle = {
                    t for t in universe
                    if yes_no_out(yes_no[t].get("prior_immunotherapy_classification", ""), bool(p["prior_immunotherapy"]), False)
                }
            elif fact == "prior_platinum_chemo":
                oracle = {
                    t for t in universe
                    if yes_no_out(extra[t].get("prior_platinum_chemo_classification", ""), bool(p["prior_platinum_chemo"]), False)
                }
            elif fact == "autoimmune_disease":
                oracle = {
                    t for t in universe
                    if yes_no_out(extra[t].get("autoimmune_disease_classification", ""), bool(p["autoimmune_disease"]), False)
                }
            else:
                continue
            kept_that_symmetric_would_drop = only_sym & oracle
            extra_trials |= kept_that_symmetric_would_drop
            for nct in kept_that_symmetric_would_drop:
                extra_pairs.append({"patient_id": pid, "nct_id": nct, "fact": fact})
        extra_by_patient.append({"id": pid, "n_trials_kept_as_cant_tell": len(extra_trials)})
    safety_original = {
        "n_patient_trial_pairs_kept_as_cant_tell": len(extra_pairs),
        "mean_trials_kept_per_patient": round(
            sum(r["n_trials_kept_as_cant_tell"] for r in extra_by_patient) / len(extra_by_patient), 4
        ),
        "patients": extra_by_patient,
        "note": (
            "Original 20 name specific drugs, so the patient side is the narrower "
            "level. Case 3 (patient broader than the rule) barely arises here."
        ),
    }

    vague_rows = []
    vague_wrong_pairs = []
    vague_cant_tell_pairs = []
    for row in vague["patients"]:
        pid = row["patient_id"]
        traits = (row.get("answer") or {}).get("traits") or []
        names = all_canonical_names(traits)
        retrieved_platinum = set()
        cant_tell_platinum = set()
        for query in names:
            for nct in platinum_named:
                result = comparison(query, PLATINUM_NAME, edges)
                if result == MATCH:
                    retrieved_platinum.add(nct)
                    vague_wrong_pairs.append({"patient_id": pid, "nct_id": nct, "query": query})
                elif result == CANT_TELL:
                    cant_tell_platinum.add(nct)
                    vague_cant_tell_pairs.append({"patient_id": pid, "nct_id": nct, "query": query})
        n_plat = len(platinum_named)
        vague_rows.append({
            "id": pid,
            "canonical_names": names,
            "expected_therapy_name": row.get("expected_therapy_name"),
            "safety_valve_parse_ok": row.get("safety_valve_parse_ok"),
            "n_platinum_named_trials": n_plat,
            "n_wrongly_retrieved_platinum_named": len(retrieved_platinum),
            "n_cant_tell_platinum_named": len(cant_tell_platinum),
            "wrongly_picked_up": round(len(retrieved_platinum) / n_plat, 4) if n_plat else None,
        })

    n_vague = len(vague_rows)
    n_wrong = sum(r["n_wrongly_retrieved_platinum_named"] for r in vague_rows)
    n_plat = len(platinum_named)
    vague_denom = n_vague * n_plat
    safety_vague = {
        "n_patients": n_vague,
        "n_platinum_named_trials": n_plat,
        "wrongly_picked_up_any_patient": round(n_wrong / vague_denom, 4) if vague_denom else None,
        "wrongly_picked_up_ci": wilson(n_wrong, vague_denom) if vague_denom else None,
        "n_wrong_patient_trial_pairs": n_wrong,
        "n_cant_tell_patient_trial_pairs": sum(r["n_cant_tell_platinum_named"] for r in vague_rows),
        "mean_platinum_named_trials_kept_as_cant_tell": round(
            sum(r["n_cant_tell_platinum_named"] for r in vague_rows) / n_vague, 4
        ) if n_vague else None,
        "patients": vague_rows,
        "gate_cleared": n_wrong == 0,
    }

    original_vague_check = original_20_have_vague_history(parse)

    other_recall_ok = True
    other_drops = {}
    for fact, row in summary["by_fact"].items():
        if fact == "prior_platinum_chemo":
            continue
        delta = row["recall_delta"]
        other_drops[fact] = delta
        if delta is not None and delta < -0.03:
            other_recall_ok = False

    platinum_recall = summary["by_fact"]["prior_platinum_chemo"]["recall"]
    fpr_ok = all(
        (row["wrongly_picked_up"] or 0) < 0.20
        for row in summary["by_fact"].values()
    )
    union_delta = None if gated["union_mean"] is None else round(gated["union_mean"] - 0.406, 4)

    gates = {
        "platinum_recall_min": 0.70,
        "other_recall_max_drop": 0.03,
        "wrongly_picked_up_max": 0.20,
        "vague_wrongly_picked_up_max": 0.0,
        "six_fact_union_must_rise_from": 0.406,
        "platinum_recall": platinum_recall,
        "platinum_recall_cleared": (platinum_recall or 0) >= 0.70,
        "other_recall_deltas": other_drops,
        "other_recall_cleared": other_recall_ok,
        "wrongly_picked_up": summary["mean_wrongly_picked_up"],
        "wrongly_picked_up_cleared": fpr_ok,
        "vague_wrongly_picked_up_cleared": safety_vague["gate_cleared"],
        "six_fact_union": gated["union_mean"],
        "six_fact_union_delta": union_delta,
        "six_fact_union_rose": union_delta is not None and union_delta > 0,
        "stop_if_union_fell": union_delta is not None and union_delta < 0,
    }

    report = {
        "method": "directional_containment_on_closed_names",
        "n_assigned_quotes": len(rows),
        "n_trials": len(universe),
        "n_patients": len(patients),
        "arm": summary,
        "assignment": assignment,
        "gates": gates,
        "matching_gated_ceiling": gated,
        "matching_gated_if_every_fact_queried": gated_if_complete_parse,
        "perfect_oracle_union_mean": oracle_union,
        "original_20_vague_history_check": original_vague_check,
        "safety_valve_price_original_20": safety_original,
        "safety_valve_vague_patients": safety_vague,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print()
    print(f"{'fact':<24}{'recall':>10}{'delta':>10}{'wrong':>10}")
    for fact, row in summary["by_fact"].items():
        rec = "n/a" if row["recall"] is None else f"{row['recall']:.1%}"
        delta = "n/a" if row["recall_delta"] is None else f"{row['recall_delta']:+.1%}"
        wrn = "n/a" if row["wrongly_picked_up"] is None else f"{row['wrongly_picked_up']:.1%}"
        print(f"{fact:<24}{rec:>10}{delta:>10}{wrn:>10}")
    print(f"{'mean':<24}{summary['mean_recall']:.1%}{'':>10}{summary['mean_wrongly_picked_up']:.1%}")
    print()
    print(f"matching-gated union    : {gated['union_mean']:.1%}  (was 40.6%, delta {union_delta})")
    print(f"  if every fact queried : {gated_if_complete_parse['union_mean']:.1%}")
    print(f"perfect-oracle union    : {oracle_union}")
    print(f"platinum recall gate    : {platinum_recall:.1%}  cleared={gates['platinum_recall_cleared']}")
    print(f"other-fact recall gate  : cleared={other_recall_ok}")
    print(f"wrongly-picked-up gate  : cleared={fpr_ok}")
    print(f"vague platinum FPR      : {n_wrong} pairs  cleared={safety_vague['gate_cleared']}")
    print(
        "original 20 vague-only  : "
        f"{original_vague_check['n_original_with_vague_history_only']}  "
        f"{original_vague_check['note']}"
    )
    print(
        "can't-tell kept (orig)  : "
        f"{safety_original['n_patient_trial_pairs_kept_as_cant_tell']} pairs, "
        f"mean {safety_original['mean_trials_kept_per_patient']:.2f} trials/patient"
    )
    print(
        "can't-tell kept (vague) : "
        f"{safety_vague['n_cant_tell_patient_trial_pairs']} pairs, "
        f"mean {safety_vague['mean_platinum_named_trials_kept_as_cant_tell']} platinum-named trials/patient"
    )
    if gates["stop_if_union_fell"]:
        print("STOP: six-fact narrowing fell from 40.6%.")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
