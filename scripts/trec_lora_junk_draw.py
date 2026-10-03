"""Draw judged-0 and unjudged shortlist trials for the junk-sort check.

The 0.85 figure was 2-vs-0 AUROC on every judged-0 trial on the
2022 shortlist (13,062 zeros, 3,614 joinable) using the logistic
on stored scores (0.846). Topical slice on that same set is 0.883.
This draw samples from that judged-0 pool, plus a smaller unjudged
sample. No API calls. 2023 is not used.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_lora_common import JUNK_PAIRS_PATH, load_splits  # noqa: E402
from trec_score_common import load_qrels, load_shortlist  # noqa: E402

PAIR_SEED = 20261005
N_JUDGED0 = 100
N_UNJUDGED = 50


def take(xs: list[str], k: int, rng: random.Random) -> list[str]:
    if len(xs) <= k:
        return list(xs)
    return rng.sample(xs, k)


def main() -> None:
    splits = load_splits()
    short = load_shortlist()
    labels = load_qrels(2022)
    rng = random.Random(PAIR_SEED)
    topics = {}
    n0 = n_unj = 0
    for tid in splits["test_2022"]:
        base = (short["years"]["2022"]["topics"].get(tid) or {}).get("shortlist") or []
        labs = labels.get(tid) or {}
        judged0 = [nct for nct in base if labs.get(nct) == 0]
        unj = [nct for nct in base if nct not in labs]
        rows = [[nct, 0] for nct in take(judged0, N_JUDGED0, rng)]
        rows += [[nct, 9] for nct in take(unj, N_UNJUDGED, rng)]
        topics[tid] = rows
        n0 += sum(1 for _n, lab in rows if lab == 0)
        n_unj += sum(1 for _n, lab in rows if lab == 9)
    payload = {
        "pair_seed": PAIR_SEED,
        "note": (
            "Judged-0 sample is from the same shortlist pool that produced "
            "the 0.85 logistic 2-vs-0 figure (all judged 0 on the 2022 "
            "shortlist). Label 9 is unjudged-for-this-patient, a convention, "
            "not a human verdict."
        ),
        "n_judged0_cap": N_JUDGED0,
        "n_unjudged_cap": N_UNJUDGED,
        "n_judged0": n0,
        "n_unjudged": n_unj,
        "n": n0 + n_unj,
        "test_2022": {"topics": topics},
        "dev_2021": {"topics": {}},
    }
    JUNK_PAIRS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {JUNK_PAIRS_PATH} judged0={n0} unjudged={n_unj} n={n0 + n_unj}", flush=True)


if __name__ == "__main__":
    main()
