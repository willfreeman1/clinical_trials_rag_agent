"""Step 3c: exact-name matching on the closed list, then the gated ceiling.

No word index, no embeddings. A trial is retrieved for a fact when any of
its assigned names equals that fact's name. The patient query is the name
only — never the value — so a marker of `none` still finds every trial
assigned `tumour genetic marker`.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from step2_ceiling import load_markers, load_step5b, load_yes_no  # noqa: E402
from step3b_match import gated_ceiling, has_rule  # noqa: E402
from step3c_closed_names import FACT_TO_NAME, canonical_name  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ASSIGNED = ROOT / "data" / "step3c_closed_names.jsonl"
PARSE = ROOT / "data" / "step4_parse.json"
PATIENTS = ROOT / "data" / "fake_patients_draw.json"
CEILING = ROOT / "data" / "step2_ceiling.json"
OUT = ROOT / "data" / "step3c_match_report.json"

FACTS = [
    "prior_immunotherapy",
    "brain_metastases",
    "driver_mutation",
    "prior_platinum_chemo",
    "autoimmune_disease",
    "disease_stage",
]


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


def load_patient_facts() -> dict[str, set[str]]:
    """patient_id -> facts they actually listed in the Step 4 parse."""
    parse = json.loads(PARSE.read_text(encoding="utf-8"))
    by_pid: dict[str, set[str]] = {}
    for row in parse["patients"]:
        pid = row["patient_id"]
        facts: set[str] = set()
        for t in (row.get("answer") or {}).get("traits") or []:
            name = canonical_name(t.get("name") or "")
            for fact, closed in FACT_TO_NAME.items():
                if name == closed:
                    facts.add(fact)
        by_pid[pid] = facts
    return by_pid


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
        recall = tp / (tp + fn) if (tp + fn) else None
        fpr = fp / (fp + tn) if (fp + tn) else None
        out[fact] = {
            "recall": None if recall is None else round(recall, 4),
            "wrongly_picked_up": None if fpr is None else round(fpr, 4),
            "tp": tp,
            "fn": fn,
            "fp": fp,
            "tn": tn,
        }
        if recall is not None:
            recalls.append(recall)
        if fpr is not None:
            fprs.append(fpr)
    out["mean_recall"] = round(sum(recalls) / len(recalls), 4) if recalls else None
    out["mean_wrongly_picked_up"] = round(sum(fprs) / len(fprs), 4) if fprs else None
    return out


def main() -> None:
    rows = load_assigned()
    yes_no = load_yes_no()
    markers = load_markers()
    extra = load_step5b()
    patients = json.loads(PATIENTS.read_text(encoding="utf-8"))["patients"]
    patient_facts = load_patient_facts()
    ids = set(yes_no) & set(markers) & set(extra)
    universe = sorted(ids)

    truth: dict[str, set[str]] = {f: set() for f in FACTS}
    for nct in universe:
        for fact in FACTS:
            if has_rule(nct, fact, yes_no, markers, extra):
                truth[fact].add(nct)

    # Per-trial assigned names. Exact equality only — no shared token bag.
    trial_names: dict[str, set[str]] = defaultdict(set)
    confusion = Counter()
    for row in rows:
        name = canonical_name(row.get("assigned_name") or "")
        trial_names[row["nct_id"]].add(name)
        source = FACT_TO_NAME.get(row.get("fact"), "unknown")
        confusion[(source, name)] += 1

    found_global: dict[str, set[str]] = {f: set() for f in FACTS}
    for nct in universe:
        names = trial_names.get(nct, set())
        for fact, closed in FACT_TO_NAME.items():
            if closed in names:
                found_global[fact].add(nct)

    # Retrieval is the same for every patient who listed the fact.
    found_by_patient: dict[str, dict[str, set[str]]] = {}
    for p in patients:
        pid = p["id"]
        listed = patient_facts.get(pid, set())
        found_by_patient[pid] = {f: (found_global[f] if f in listed else set()) for f in FACTS}

    per_patient = []
    for p in patients:
        pid = p["id"]
        listed = patient_facts.get(pid, set())
        usable_facts = [f for f in FACTS if f in listed]
        per_patient.append(rates(found_by_patient[pid], truth, universe, usable_facts))

    summary = {"by_fact": {}, "mean_recall": None, "mean_wrongly_picked_up": None}
    recs, fprs = [], []
    for fact in FACTS:
        usable = [
            r for p, r in zip(patients, per_patient)
            if fact in patient_facts.get(p["id"], set()) and fact in r
        ]
        fact_recs = [r[fact]["recall"] for r in usable if r[fact]["recall"] is not None]
        fact_fprs = [r[fact]["wrongly_picked_up"] for r in usable if r[fact]["wrongly_picked_up"] is not None]
        summary["by_fact"][fact] = {
            "recall": round(sum(fact_recs) / len(fact_recs), 4) if fact_recs else None,
            "wrongly_picked_up": round(sum(fact_fprs) / len(fact_fprs), 4) if fact_fprs else None,
            "n_patients_with_trait": len(usable),
        }
        if fact_recs:
            recs.append(sum(fact_recs) / len(fact_recs))
        if fact_fprs:
            fprs.append(sum(fact_fprs) / len(fact_fprs))
    summary["mean_recall"] = round(sum(recs) / len(recs), 4) if recs else None
    summary["mean_wrongly_picked_up"] = round(sum(fprs) / len(fprs), 4) if fprs else None

    quote_coverage = {}
    quoted: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        quoted[row["fact"]].add(row["nct_id"])
    for fact in FACTS:
        have = len(truth[fact] & quoted[fact])
        total = len(truth[fact])
        quote_coverage[fact] = {
            "rule_trials": total,
            "rule_trials_with_quote": have,
            "coverage": round(have / total, 4) if total else None,
        }

    agree = sum(1 for row in rows if canonical_name(row.get("assigned_name") or "") == FACT_TO_NAME.get(row.get("fact")))
    assignment = {
        "n_quotes": len(rows),
        "agree_with_source": agree,
        "accuracy": round(agree / len(rows), 4) if rows else None,
        "n_other": sum(1 for row in rows if canonical_name(row.get("assigned_name") or "") == "other"),
        "confusion": [
            {"source": src, "assigned": assigned, "n": n}
            for (src, assigned), n in sorted(confusion.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        "quote_coverage": quote_coverage,
    }

    gated = gated_ceiling(patients, yes_no, markers, extra, found_by_patient, FACTS)

    # Same matcher, but every patient queries the five always-on facts.
    # Isolates matching from Step 4 misses. Not the official number.
    always = [f for f in FACTS if f != "autoimmune_disease"]
    found_complete: dict[str, dict[str, set[str]]] = {}
    for p in patients:
        listed = set(always)
        if p.get("autoimmune_disease"):
            listed.add("autoimmune_disease")
        found_complete[p["id"]] = {f: (found_global[f] if f in listed else set()) for f in FACTS}
    gated_if_complete_parse = gated_ceiling(patients, yes_no, markers, extra, found_complete, FACTS)

    oracle_union = None
    if CEILING.exists():
        oracle_union = json.loads(CEILING.read_text(encoding="utf-8")).get("union_mean")

    report = {
        "method": "exact_name_equality",
        "n_assigned_quotes": len(rows),
        "n_trials": len(universe),
        "n_patients": len(patients),
        "arm": summary,
        "assignment": assignment,
        "gates": {
            "recall_rethink_below": 0.60,
            "recall_not_bottleneck_above": 0.85,
            "wrongly_picked_up_max": 0.20,
            "recall": summary["mean_recall"],
            "wrongly_picked_up": summary["mean_wrongly_picked_up"],
            "recall_band": (
                "below_60" if (summary["mean_recall"] or 0) < 0.60
                else "above_85" if summary["mean_recall"] > 0.85
                else "60_to_85"
            ),
            "wrongly_picked_up_cleared": (summary["mean_wrongly_picked_up"] or 1) <= 0.20,
        },
        "matching_gated_ceiling": gated,
        "matching_gated_if_every_fact_queried": gated_if_complete_parse,
        "perfect_oracle_union_mean": oracle_union,
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    print(f"{'fact':<24}{'recall':>10}{'wrong':>10}")
    for fact, row in summary["by_fact"].items():
        rec = "n/a" if row["recall"] is None else f"{row['recall']:.1%}"
        wrn = "n/a" if row["wrongly_picked_up"] is None else f"{row['wrongly_picked_up']:.1%}"
        print(f"{fact:<24}{rec:>10}{wrn:>10}")
    print(f"{'mean':<24}{summary['mean_recall']:.1%}{summary['mean_wrongly_picked_up']:>10.1%}")
    print()
    print(f"assignment accuracy     : {assignment['accuracy']:.1%}  "
          f"({assignment['agree_with_source']} of {assignment['n_quotes']}; "
          f"{assignment['n_other']} other)")
    print(f"matching-gated union    : {gated['union_mean']:.1%}  "
          f"(range {gated['union_range'][0]:.1%} to {gated['union_range'][1]:.1%})")
    print(f"  if every fact queried : {gated_if_complete_parse['union_mean']:.1%}")
    print(f"perfect-oracle union    : {oracle_union}")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
