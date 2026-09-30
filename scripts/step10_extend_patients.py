"""Extend the 20 invented patients with fields the canonical questions need.

Existing values are not changed. New fields only. Seed 202609303, committed
in questions_design.json before this file was written.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN = json.loads((ROOT / "questions_design.json").read_text(encoding="utf-8"))
DRAW = ROOT / "data" / "fake_patients_draw.json"
OUT = ROOT / "data" / "fake_patients_questions.json"


def never_weeks() -> dict:
    return {"value": None, "status": "never"}


def weeks(n: int) -> dict:
    return {"value": n, "status": "known"}


def months(n: int) -> dict:
    return {"value": n, "status": "known"}


def never_months() -> dict:
    return {"value": None, "status": "never"}


def extend_one(rng, p: dict) -> dict:
    row = dict(p)
    has_brain = bool(p["brain_metastases"])
    treated_stable = p.get("brain_mets_treated_stable")
    has_auto = bool(p["autoimmune_disease"])
    has_immuno = bool(p["prior_immunotherapy"])
    has_plat = bool(p["prior_platinum_chemo"])
    stage = (p.get("disease_stage") or "").upper()

    if not has_brain:
        row["brain_treatment"] = "not_applicable"
        row["brain_stable_weeks"] = never_weeks()
        row["brain_symptoms"] = "none"
        row["brain_steroids"] = "none"
        row["leptomeningeal"] = "none"
    elif treated_stable is True:
        row["brain_treatment"] = "treated"
        # Stable by construction; duration is the missing number.
        row["brain_stable_weeks"] = weeks(rng.choice([8, 12, 16, 24, 32, 52]))
        row["brain_symptoms"] = "none"
        row["brain_steroids"] = rng.choice(["none", "none", "stable_physiologic"])
        row["leptomeningeal"] = "none" if rng.random() < 0.9 else "present"
    else:
        # Existing flag is untreated/unstable. Do not flip it to treated+stable.
        if rng.random() < 0.6:
            row["brain_treatment"] = "untreated"
            row["brain_stable_weeks"] = weeks(0)
            row["brain_symptoms"] = rng.choice(["present", "progressive", "none"])
            row["brain_steroids"] = rng.choice(["none", "increasing"])
        else:
            row["brain_treatment"] = "treated"
            row["brain_stable_weeks"] = weeks(rng.choice([0, 1, 2]))
            row["brain_symptoms"] = rng.choice(["present", "none"])
            row["brain_steroids"] = rng.choice(["increasing", "stable_physiologic"])
        row["leptomeningeal"] = "none" if rng.random() < 0.8 else "present"

    if not has_auto:
        row["autoimmune_activity"] = "never"
        row["autoimmune_systemic_months"] = never_months()
    else:
        row["autoimmune_activity"] = rng.choice(["active", "inactive"])
        if row["autoimmune_activity"] == "active":
            row["autoimmune_systemic_months"] = months(rng.choice([0, 1, 3, 6, 12]))
        else:
            row["autoimmune_systemic_months"] = months(rng.choice([18, 24, 36, 48]))

    if has_immuno:
        row["immuno_washout_weeks"] = weeks(rng.choice([1, 2, 3, 4, 6, 8, 12, 26]))
    else:
        row["immuno_washout_weeks"] = never_weeks()

    if has_plat or has_immuno or int(p.get("prior_lines_of_therapy") or 0) >= 1:
        row["systemic_washout_weeks"] = weeks(rng.choice([1, 2, 3, 4, 6, 8, 12, 26]))
    else:
        row["systemic_washout_weeks"] = never_weeks()

    # Stage IV is not a curative-local candidate. Earlier stages may be.
    if stage in {"IV", "4"}:
        row["amenable_to_curative_therapy"] = "no"
    else:
        row["amenable_to_curative_therapy"] = rng.choice(["yes", "no", "no"])

    return row


def main() -> None:
    import random

    seed = DESIGN["seed"]
    rng = random.Random(seed)
    src = json.loads(DRAW.read_text(encoding="utf-8"))
    patients = [extend_one(rng, p) for p in src["patients"]]
    new_fields = sorted(
        set(patients[0]) - set(src["patients"][0])
    )
    out = {
        "seed": seed,
        "source_draw_seed": src.get("seed"),
        "n": len(patients),
        "existing_fields_unchanged": True,
        "new_fields": new_fields,
        "patients": patients,
        "dont_know_policy": "Missing or null values make the simulated coordinator return don't know, which keeps the trial.",
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"seed={seed} patients={len(patients)} new_fields={new_fields}")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
