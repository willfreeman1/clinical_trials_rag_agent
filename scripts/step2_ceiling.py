"""Spike 2, Step 2: what is the best a perfect cheap step could ever do?

Assumes a flawless filter and builds nothing. Uses the answer key as a perfect
oracle to count how many of the 1,308 trials could be thrown out for each
invented patient, and takes the union across traits so trials thrown out by more
than one trait are not double-counted.

Re-run after Step 5a: three traits (immunotherapy, brain, genetic marker).
Thresholds are in THRESHOLDS.md, committed before the original run; the 8.2%
and 18.2% gates still decide.

No API calls. No cost.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANSWER_KEY = ROOT / "data" / "answer_key.jsonl"
MARKERS = ROOT / "data" / "answer_key_markers.jsonl"
PATIENTS = ROOT / "data" / "fake_patients_draw.json"
OUT = ROOT / "data" / "step2_ceiling.json"

DEFINITE_BAR = "barred"
DEFINITE_REQUIRE = "required"
CONDITIONAL_BAR = "barred_with_exception"

NONE_MARKERS = {
    "no driver mutation identified",
    "none",
    "wild type",
    "none identified",
}
GENE = re.compile(
    r"\b(egfr|alk|kras|ros1|braf|met|ret|ntrk[0-9]?|her2|erbb2|nrg1|fgfr[0-9]?|pik3ca)\b",
    re.IGNORECASE,
)
WILDTYPE_REFUSAL = re.compile(r"wild[\s-]?type|no mut|negativ|unmutat", re.IGNORECASE)


def load_yes_no() -> dict[str, dict]:
    key: dict[str, dict] = {}
    with ANSWER_KEY.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("answer"):
                key[row["nct_id"]] = row["answer"]
    return key


def load_markers() -> dict[str, dict]:
    key: dict[str, dict] = {}
    if not MARKERS.exists():
        return key
    with MARKERS.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("answer"):
                key[row["nct_id"]] = row["answer"]
    return key


def genes(text: str) -> set[str]:
    return {m.lower() for m in GENE.findall(text or "")}


def as_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value).strip()]


def in_marker_list(patient: str, items: list[str]) -> bool:
    p = (patient or "").lower().strip()
    p_genes = genes(p)
    for item in items:
        n = item.lower()
        if p in n or n in p:
            return True
        i_genes = genes(n)
        if p_genes and i_genes and p_genes & i_genes:
            return True
    return False


def generic_only(items: list[str]) -> bool:
    return bool(items) and not any(genes(i) for i in items)


def yes_no_out(verdict: str, patient_has: bool, optimistic: bool) -> bool:
    if patient_has:
        if verdict == DEFINITE_BAR:
            return True
        if optimistic and verdict == CONDITIONAL_BAR:
            return True
        return False
    return verdict == DEFINITE_REQUIRE


def marker_out(patient_value: str, answer: dict, optimistic: bool) -> bool:
    """List-shaped trait. A condition keeps the trial unless optimistic."""
    required = as_list(answer.get("required_markers"))
    refused = as_list(answer.get("refused_markers"))
    condition = (answer.get("genetic_marker_condition") or "").strip()
    if condition and not optimistic:
        return False

    value = (patient_value or "").strip()
    has_none = value.lower() in NONE_MARKERS or value.lower().startswith("no driver")

    if required:
        if has_none:
            return True
        if generic_only(required):
            return False
        if not in_marker_list(value, required):
            return True

    if refused:
        if has_none:
            return any(WILDTYPE_REFUSAL.search(i) for i in refused)
        if in_marker_list(value, refused):
            return True
    return False


def project(x: float, n: int = 6) -> float:
    return 1 - (1 - x) ** n


def main() -> None:
    yes_no = load_yes_no()
    markers = load_markers()
    patients = json.loads(PATIENTS.read_text(encoding="utf-8"))["patients"]
    trial_ids = sorted(set(yes_no) & set(markers) if markers else set(yes_no))
    n_trials = len(trial_ids)

    unreachable = {
        "prior_immunotherapy_classification": sum(
            1 for t in trial_ids if yes_no[t].get("prior_immunotherapy_classification") == CONDITIONAL_BAR
        ),
        "brain_metastases_classification": sum(
            1 for t in trial_ids if yes_no[t].get("brain_metastases_classification") == CONDITIONAL_BAR
        ),
        "genetic_marker_condition": sum(
            1 for t in trial_ids if (markers.get(t, {}).get("genetic_marker_condition") or "").strip()
        ),
    }

    rows = []
    for p in patients:
        row: dict = {"id": p["id"], "driver_mutation": p["driver_mutation"], "per_trait": {}, "per_trait_optimistic": {}}
        union: set[str] = set()
        union_opt: set[str] = set()
        union_two: set[str] = set()

        for pfield, kfield in (
            ("prior_immunotherapy", "prior_immunotherapy_classification"),
            ("brain_metastases", "brain_metastases_classification"),
        ):
            has = bool(p[pfield])
            out = {t for t in trial_ids if yes_no_out(yes_no[t].get(kfield, ""), has, False)}
            out_opt = {t for t in trial_ids if yes_no_out(yes_no[t].get(kfield, ""), has, True)}
            row["per_trait"][pfield] = {"patient_has": has, "thrown_out": len(out), "share": round(len(out) / n_trials, 4)}
            row["per_trait_optimistic"][pfield] = {"thrown_out": len(out_opt), "share": round(len(out_opt) / n_trials, 4)}
            union |= out
            union_opt |= out_opt
            union_two |= out

        if markers:
            value = p["driver_mutation"]
            out = {t for t in trial_ids if marker_out(value, markers[t], False)}
            out_opt = {t for t in trial_ids if marker_out(value, markers[t], True)}
            row["per_trait"]["driver_mutation"] = {
                "patient_value": value,
                "thrown_out": len(out),
                "share": round(len(out) / n_trials, 4),
            }
            row["per_trait_optimistic"]["driver_mutation"] = {
                "thrown_out": len(out_opt),
                "share": round(len(out_opt) / n_trials, 4),
            }
            union |= out
            union_opt |= out_opt

        summed = sum(v["thrown_out"] for v in row["per_trait"].values())
        row["union"] = len(union)
        row["union_share"] = round(len(union) / n_trials, 4)
        row["two_trait_union"] = len(union_two)
        row["two_trait_union_share"] = round(len(union_two) / n_trials, 4)
        row["summed_if_no_overlap"] = summed
        row["overlap"] = summed - len(union)
        row["union_optimistic"] = len(union_opt)
        row["union_optimistic_share"] = round(len(union_opt) / n_trials, 4)
        rows.append(row)

    shares = [v["share"] for r in rows for v in r["per_trait"].values()]
    marker_shares = [r["per_trait"]["driver_mutation"]["share"] for r in rows] if markers else []
    mean_per_trait = sum(shares) / len(shares)
    unions = [r["union_share"] for r in rows]
    unions_opt = [r["union_optimistic_share"] for r in rows]
    two_unions = [r["two_trait_union_share"] for r in rows]

    report = {
        "n_trials": n_trials,
        "n_patients": len(rows),
        "traits_measured": list(rows[0]["per_trait"]),
        "unreachable": unreachable,
        "mean_per_trait_share": round(mean_per_trait, 4),
        "per_trait_share_range": [round(min(shares), 4), round(max(shares), 4)],
        "marker_mean_share": round(sum(marker_shares) / len(marker_shares), 4) if marker_shares else None,
        "marker_share_range": [round(min(marker_shares), 4), round(max(marker_shares), 4)] if marker_shares else None,
        "union_mean": round(sum(unions) / len(unions), 4),
        "union_range": [round(min(unions), 4), round(max(unions), 4)],
        "two_trait_union_mean": round(sum(two_unions) / len(two_unions), 4),
        "union_optimistic_mean": round(sum(unions_opt) / len(unions_opt), 4),
        "projection_to_six_traits_if_independent": round(project(mean_per_trait), 4),
        "thresholds": {"floor_40pct_needs_per_trait": 0.082, "target_70pct_needs_per_trait": 0.182},
        "patients": rows,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"{n_trials} trials, {len(rows)} patients, traits: {', '.join(report['traits_measured'])}\n")
    print("Unreachable / conditional:")
    for field, count in unreachable.items():
        print(f"  {field:45} {count:5} of {n_trials}  ({count / n_trials:.1%})")
    print()
    header = f"{'patient':8}{'immuno':>9}{'brain':>9}"
    if markers:
        header += f"{'marker':>9}"
    header += f"{'union':>9}{'2-trait':>9}{'optimistic':>12}"
    print(header)
    for r in rows:
        line = (
            f"{r['id']:8}"
            f"{r['per_trait']['prior_immunotherapy']['share']:>9.1%}"
            f"{r['per_trait']['brain_metastases']['share']:>9.1%}"
        )
        if markers:
            line += f"{r['per_trait']['driver_mutation']['share']:>9.1%}"
        line += (
            f"{r['union_share']:>9.1%}"
            f"{r['two_trait_union_share']:>9.1%}"
            f"{r['union_optimistic_share']:>12.1%}"
        )
        print(line)
    print()
    print(f"mean per-trait share      : {mean_per_trait:.1%}  (range {min(shares):.1%} to {max(shares):.1%})")
    if marker_shares:
        print(f"  of which marker trait   : {sum(marker_shares)/len(marker_shares):.1%}  "
              f"(range {min(marker_shares):.1%} to {max(marker_shares):.1%})")
    print(f"union, mean              : {sum(unions)/len(unions):.1%}  (range {min(unions):.1%} to {max(unions):.1%})")
    print(f"  two-trait union, mean   : {sum(two_unions)/len(two_unions):.1%}")
    print(f"  optimistic union, mean  : {sum(unions_opt)/len(unions_opt):.1%}")
    print()
    print("THRESHOLD: floor 40% needs 8.2% per trait; target 70% needs 18.2% per trait")
    print(f"projection to six independent traits at {mean_per_trait:.1%} each: {project(mean_per_trait):.1%}")
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
