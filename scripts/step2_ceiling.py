"""Spike 2, Step 2: what is the best a perfect cheap step could ever do?

Assumes a flawless filter and builds nothing. Uses the answer key as a perfect
oracle to count how many of the 1,308 trials could be thrown out for each
invented patient, and takes the union across traits so trials thrown out by more
than one trait are not double-counted.

Only two traits are labelled today, so this is a partial run: it reports per-trait
elimination, the two-trait union, and the overlap between them. Thresholds are in
THRESHOLDS.md, committed before this ran.

No API calls. No cost.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANSWER_KEY = ROOT / "data" / "answer_key.jsonl"
PATIENTS = ROOT / "data" / "fake_patients_draw.json"
OUT = ROOT / "data" / "step2_ceiling.json"

# Which patient field pairs with which answer-key field.
TRAITS = {
    "prior_immunotherapy": "prior_immunotherapy_classification",
    "brain_metastases": "brain_metastases_classification",
}

# A trial can only be thrown out when a rule settles the matter definitely.
DEFINITE_BAR = "barred"
DEFINITE_REQUIRE = "required"
CONDITIONAL_BAR = "barred_with_exception"


def load_key() -> dict[str, dict[str, str]]:
    """nct_id -> {answer-key field: verdict} for the rows that have an answer."""
    key: dict[str, dict[str, str]] = {}
    with ANSWER_KEY.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if not row.get("answer"):
                continue
            key[row["nct_id"]] = row["answer"]
    return key


def thrown_out(verdict: str, patient_has: bool, optimistic: bool) -> bool:
    """Would a perfect filter throw this trial out for this patient?

    Pessimistic: only definite rules can decide, so conditional refusals keep the
    trial. Optimistic: conditional refusals are treated as though the extra detail
    were available and went against the patient.
    """
    if patient_has:
        if verdict == DEFINITE_BAR:
            return True
        if optimistic and verdict == CONDITIONAL_BAR:
            return True
        return False
    return verdict == DEFINITE_REQUIRE


def main() -> None:
    key = load_key()
    patients = json.loads(PATIENTS.read_text(encoding="utf-8"))["patients"]
    trial_ids = sorted(key)
    n_trials = len(trial_ids)

    # How much of the corpus is unreachable: has a rule, but states it conditionally.
    unreachable = {
        field: sum(1 for t in trial_ids if key[t].get(field) == CONDITIONAL_BAR)
        for field in TRAITS.values()
    }

    rows = []
    for p in patients:
        row: dict = {"id": p["id"], "per_trait": {}, "per_trait_optimistic": {}}
        union: set[str] = set()
        union_opt: set[str] = set()
        for pfield, kfield in TRAITS.items():
            has = bool(p[pfield])
            out = {t for t in trial_ids if thrown_out(key[t].get(kfield, ""), has, False)}
            out_opt = {t for t in trial_ids if thrown_out(key[t].get(kfield, ""), has, True)}
            row["per_trait"][pfield] = {"patient_has": has, "thrown_out": len(out),
                                       "share": round(len(out) / n_trials, 4)}
            row["per_trait_optimistic"][pfield] = {"thrown_out": len(out_opt),
                                                   "share": round(len(out_opt) / n_trials, 4)}
            union |= out
            union_opt |= out_opt
        summed = sum(v["thrown_out"] for v in row["per_trait"].values())
        row["union"] = len(union)
        row["union_share"] = round(len(union) / n_trials, 4)
        row["summed_if_no_overlap"] = summed
        row["overlap"] = summed - len(union)
        row["union_optimistic"] = len(union_opt)
        row["union_optimistic_share"] = round(len(union_opt) / n_trials, 4)
        rows.append(row)

    # Mean per-trait share across every (patient, trait) pair — the number the
    # committed threshold is read from.
    shares = [v["share"] for r in rows for v in r["per_trait"].values()]
    mean_per_trait = sum(shares) / len(shares)
    unions = [r["union_share"] for r in rows]
    unions_opt = [r["union_optimistic_share"] for r in rows]

    def project(x: float, n: int = 6) -> float:
        """Share thrown out if n traits each removed x, independently."""
        return 1 - (1 - x) ** n

    report = {
        "n_trials": n_trials,
        "n_patients": len(rows),
        "traits_measured": list(TRAITS),
        "unreachable_conditional_bars": unreachable,
        "mean_per_trait_share": round(mean_per_trait, 4),
        "per_trait_share_range": [round(min(shares), 4), round(max(shares), 4)],
        "two_trait_union_mean": round(sum(unions) / len(unions), 4),
        "two_trait_union_range": [round(min(unions), 4), round(max(unions), 4)],
        "two_trait_union_optimistic_mean": round(sum(unions_opt) / len(unions_opt), 4),
        "total_overlap_across_patients": sum(r["overlap"] for r in rows),
        "projection_to_six_traits_if_independent": round(project(mean_per_trait), 4),
        "thresholds": {"floor_40pct_needs_per_trait": 0.082,
                       "target_70pct_needs_per_trait": 0.182},
        "patients": rows,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"{n_trials} trials, {len(rows)} patients, traits: {', '.join(TRAITS)}\n")
    print("Unreachable — has a rule but states it conditionally:")
    for field, count in unreachable.items():
        print(f"  {field:45} {count:5} of {n_trials}  ({count/n_trials:.1%})")
    print()
    print(f"{'patient':8}{'immuno':>9}{'brain':>9}{'union':>9}{'overlap':>9}{'optimistic':>12}")
    for r in rows:
        i = r["per_trait"]["prior_immunotherapy"]
        b = r["per_trait"]["brain_metastases"]
        print(f"{r['id']:8}{i['share']:>9.1%}{b['share']:>9.1%}"
              f"{r['union_share']:>9.1%}{r['overlap']:>9}{r['union_optimistic_share']:>12.1%}")
    print()
    print(f"mean per-trait share      : {mean_per_trait:.1%}  "
          f"(range {min(shares):.1%} to {max(shares):.1%})")
    print(f"two-trait union, mean     : {sum(unions)/len(unions):.1%}  "
          f"(range {min(unions):.1%} to {max(unions):.1%})")
    print(f"  same, optimistic        : {sum(unions_opt)/len(unions_opt):.1%}")
    print(f"total overlap             : {sum(r['overlap'] for r in rows)} "
          f"trial-slots double-counted across {len(rows)} patients")
    print()
    print("THRESHOLD: floor 40% needs 8.2% per trait; target 70% needs 18.2% per trait")
    print(f"projection to six independent traits at {mean_per_trait:.1%} each: "
          f"{project(mean_per_trait):.1%}  (an UPPER bound — overlap makes the real figure lower)")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
