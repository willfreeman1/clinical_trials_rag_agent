"""Draw 280 random fact-subsets. Seed 202609304. No API. Commit before generation."""

from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN = json.loads((ROOT / "sparse_design.json").read_text(encoding="utf-8"))
DRAW = ROOT / "data" / "fake_patients_draw.json"
OUT = ROOT / "sparse_configs.json"


def main() -> None:
    import random

    seed = DESIGN["seed"]
    rng = random.Random(seed)
    facts = list(DESIGN["facts"])
    patients = json.loads(DRAW.read_text(encoding="utf-8"))["patients"]
    ids = [p["id"] for p in patients]
    if len(ids) != 20:
        raise SystemExit(f"expected 20 patients, got {len(ids)}")

    configs = []
    n = 0
    for pid in ids:
        for k in range(7):
            drawn = []
            possible = list(combinations(facts, k))
            for d in range(2):
                if k in (0, 6) or len(possible) == 1:
                    subset = list(facts) if k == 6 else []
                else:
                    for _ in range(40):
                        cand = sorted(rng.sample(facts, k))
                        if cand not in drawn:
                            subset = cand
                            break
                    else:
                        subset = sorted(rng.sample(facts, k))
                drawn.append(subset)
                n += 1
                configs.append({
                    "id": f"{pid}|k{k}|d{d}",
                    "patient_id": pid,
                    "k": k,
                    "draw": d,
                    "include": subset,
                    "exclude": [f for f in facts if f not in subset],
                })

    if len(configs) != 280:
        raise SystemExit(f"expected 280 configs, got {len(configs)}")
    payload = {
        "seed": seed,
        "n": len(configs),
        "facts": facts,
        "checklist_order": DESIGN["checklist_order"],
        "configs": configs,
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"seed={seed} n={len(configs)} wrote {OUT}")


if __name__ == "__main__":
    main()
