"""Build discarded/kept sets for the six Step 8 patients, then draw the sample.

No API calls. Seed and patient ids are in step8_design.json, committed before
this ran.
"""

from __future__ import annotations

import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from step2_ceiling import (  # noqa: E402
    load_markers,
    load_step5b,
    load_yes_no,
    marker_out,
    stage_out,
    yes_no_out,
)
from step3c_closed_names import FACT_TO_NAME  # noqa: E402
from step3d_match import (  # noqa: E402
    FACTS,
    listed_facts,
    load_assigned,
    retrieve,
)
from step3d_reassign import canonical_name  # noqa: E402
from step8_common import DESIGN, DATA, ROOT  # noqa: E402
from therapy_containment import load_child_to_parent  # noqa: E402

OUT_SETS = DATA / "step8_sets.json"
OUT_SAMPLE = DATA / "step8_sample.json"
PARSE = DATA / "step4_parse.json"
VAGUE_PARSE = DATA / "step3d_vague_parse.json"
PATIENTS = DATA / "fake_patients_draw.json"
PATIENTS_MD = DATA / "fake_patients.md"
VAGUE_MD = ROOT / "fake_patients_vague.md"


def load_blockquotes(path: Path, pattern: str) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    found: dict[str, list[str]] = {}
    current = None
    rx = re.compile(pattern)
    for line in text.splitlines():
        header = rx.match(line)
        if header:
            current = header.group(1)
            found[current] = []
            continue
        if current is None:
            continue
        if line.startswith("## "):
            current = None
            continue
        if line.startswith(">"):
            found[current].append(line[1:].strip())
    return {pid: " ".join(parts) for pid, parts in found.items() if parts}


def v01_gold() -> dict:
    return {
        "id": "V01",
        "age": 68,
        "sex": "female",
        "disease_stage": "IV",
        "histology": "adenocarcinoma",
        "driver_mutation": "no driver mutation identified",
        "ecog": "1",
        "prior_immunotherapy": False,
        "prior_platinum_chemo": False,
        "prior_lines_of_therapy": "1",
        "brain_metastases": False,
        "brain_mets_treated_stable": None,
        "creatinine_clearance": 80,
        "autoimmune_disease": False,
        "interstitial_lung_disease": False,
        "hepatitis_b": False,
        "hepatitis_c": False,
        "hiv": False,
        "recent_myocardial_infarction": False,
        "major_surgery_within_4_weeks": False,
        "pleural_effusion": False,
    }


def oracle_out(p: dict, nct: str, yes_no: dict, markers: dict, extra: dict) -> dict[str, bool]:
    return {
        "prior_immunotherapy": yes_no_out(
            yes_no[nct].get("prior_immunotherapy_classification", ""), bool(p["prior_immunotherapy"]), False
        ),
        "brain_metastases": yes_no_out(
            yes_no[nct].get("brain_metastases_classification", ""), bool(p["brain_metastases"]), False
        ),
        "prior_platinum_chemo": yes_no_out(
            extra[nct].get("prior_platinum_chemo_classification", ""), bool(p["prior_platinum_chemo"]), False
        ),
        "autoimmune_disease": yes_no_out(
            extra[nct].get("autoimmune_disease_classification", ""), bool(p["autoimmune_disease"]), False
        ),
        "driver_mutation": marker_out(p["driver_mutation"], markers[nct], False),
        "disease_stage": stage_out(p["disease_stage"], extra[nct], False),
    }


def main() -> None:
    yes_no = load_yes_no()
    markers = load_markers()
    extra = load_step5b()
    universe = sorted(set(yes_no) & set(markers) & set(extra))
    edges = load_child_to_parent()
    assigned = load_assigned()
    trial_names: dict[str, set[str]] = defaultdict(set)
    for row in assigned:
        trial_names[row["nct_id"]].add(canonical_name(row.get("assigned_name") or ""))

    draw = {p["id"]: p for p in json.loads(PATIENTS.read_text(encoding="utf-8"))["patients"]}
    draw["V01"] = v01_gold()
    parse = {row["patient_id"]: row for row in json.loads(PARSE.read_text(encoding="utf-8"))["patients"]}
    vague = {row["patient_id"]: row for row in json.loads(VAGUE_PARSE.read_text(encoding="utf-8"))["patients"]}
    parse["V01"] = vague["V01"]

    descriptions = load_blockquotes(PATIENTS_MD, r"^## (P\d+)\s*$")
    descriptions.update(load_blockquotes(VAGUE_MD, r"^## (V\d+)\s*$"))

    sets = {}
    for pid in DESIGN["patients"]:
        p = draw[pid]
        traits = (parse[pid].get("answer") or {}).get("traits") or []
        listed = listed_facts(traits)
        found = {}
        for fact in FACTS:
            if fact not in listed:
                found[fact] = set()
            else:
                found[fact] = retrieve(listed[fact], trial_names, False, edges)
        discarded: set[str] = set()
        for nct in universe:
            facts_out = oracle_out(p, nct, yes_no, markers, extra)
            for fact in FACTS:
                if facts_out[fact] and nct in found[fact]:
                    discarded.add(nct)
        kept = [nct for nct in universe if nct not in discarded]
        sets[pid] = {
            "n_universe": len(universe),
            "n_discarded": len(discarded),
            "n_kept": len(kept),
            "discarded": sorted(discarded),
            "kept": kept,
            "listed_facts": listed,
            "description": descriptions[pid],
            "gold": {k: p[k] for k in p},
        }
        print(
            f"{pid} discarded={len(discarded)} kept={len(kept)} "
            f"listed={list(listed)}",
            flush=True,
        )

    rng = random.Random(DESIGN["seed"])
    sample = {
        "seed": DESIGN["seed"],
        "models": [DESIGN["expensive_model"], DESIGN["cheap_model"]],
        "patients": {},
    }
    for pid in DESIGN["patients"]:
        discarded = list(sets[pid]["discarded"])
        kept = list(sets[pid]["kept"])
        rng.shuffle(discarded)
        rng.shuffle(kept)
        n_disc = min(DESIGN["n_discarded"], len(discarded))
        n_kept = min(DESIGN["n_kept"], len(kept))
        disc_s = discarded[:n_disc]
        kept_s = kept[:n_kept]
        cons_disc, cons_kept = [], []
        if pid == DESIGN["consistency_patient"]:
            cons_disc = disc_s[: DESIGN["consistency_n_discarded"]]
            cons_kept = kept_s[: DESIGN["consistency_n_kept"]]
        sample["patients"][pid] = {
            "n_discarded_available": len(sets[pid]["discarded"]),
            "n_kept_available": len(sets[pid]["kept"]),
            "discarded": disc_s,
            "kept": kept_s,
            "consistency_discarded": cons_disc,
            "consistency_kept": cons_kept,
            "short_of_100_discarded": n_disc < DESIGN["n_discarded"],
            "description": sets[pid]["description"],
            "listed_facts": sets[pid]["listed_facts"],
        }
        print(
            f"{pid} sample discarded={len(disc_s)} kept={len(kept_s)} "
            f"short={n_disc < DESIGN['n_discarded']}",
            flush=True,
        )

    # Drop bulky discarded/kept full lists from the sets file? Keep them — scoring
    # needs key_excludes. Full discarded lists are ~few hundred ids.
    slim = {}
    for pid, row in sets.items():
        slim[pid] = {
            "n_universe": row["n_universe"],
            "n_discarded": row["n_discarded"],
            "n_kept": row["n_kept"],
            "listed_facts": row["listed_facts"],
            "description": row["description"],
            "gold": row["gold"],
        }
    OUT_SETS.write_text(json.dumps(slim, indent=2), encoding="utf-8")
    OUT_SAMPLE.write_text(json.dumps(sample, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_SETS}")
    print(f"Wrote {OUT_SAMPLE}")


if __name__ == "__main__":
    main()
