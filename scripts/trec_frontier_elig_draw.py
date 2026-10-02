"""Draw the judged 1-vs-2 sample. Run once before any score. No API calls."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_frontier_elig_common import (  # noqa: E402
    CAP,
    PAIR_SEED,
    PAIRS_PATH,
    PATIENT_SEED,
    SAMPLE_TOPICS,
    YEARS,
    load_qrels,
    load_shortlist,
)
from trec_score_common import PACK  # noqa: E402


def main() -> None:
    if not PACK.exists():
        raise SystemExit(f"missing {PACK}")
    short = load_shortlist()
    rng = random.Random(PAIR_SEED)
    years = {}
    n1 = n2 = 0
    for year in YEARS:
        y = str(year)
        labels_all = load_qrels(year)
        topics = {}
        for tid in SAMPLE_TOPICS[y]:
            base = (short["years"][y]["topics"].get(tid) or {}).get("shortlist") or []
            labs = labels_all.get(tid) or {}
            by = {1: [], 2: []}
            for nct in base:
                lab = labs.get(nct)
                if lab in by:
                    by[lab].append(nct)
            picked = []
            for lab in (1, 2):
                pool = list(by[lab])
                if len(pool) > CAP:
                    pool = sorted(rng.sample(pool, CAP))
                else:
                    pool = sorted(pool)
                for nct in pool:
                    picked.append([nct, lab])
                    if lab == 1:
                        n1 += 1
                    else:
                        n2 += 1
            topics[tid] = picked
        years[y] = topics
    payload = {
        "patient_seed": PATIENT_SEED,
        "pair_seed": PAIR_SEED,
        "cap_per_label": CAP,
        "n_label_1": n1,
        "n_label_2": n2,
        "n_pairs": n1 + n2,
        "years": years,
        "notes": [
            "Judged label 1 and 2 only. 2023 not touched.",
            "Prompts are in trec_frontier_elig_common.py. No scores yet.",
            "The system does not say a patient qualifies.",
        ],
    }
    PAIRS_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {PAIRS_PATH} n1={n1} n2={n2} n={n1 + n2}", flush=True)


if __name__ == "__main__":
    main()
