"""Draw the 30-patient cheap-pass sample. No scores. Seed 20261001."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_rerank_common import SHORTLIST, YEARS  # noqa: E402

SEED = 20261001
PER_YEAR = 15
OUT = Path(__file__).resolve().parents[1] / "data" / "trec" / "cheap_pass_sample.json"


def main() -> None:
    short = json.loads(SHORTLIST.read_text(encoding="utf-8"))
    rng = random.Random(SEED)
    years = {}
    for year in YEARS:
        tids = sorted(short["years"][str(year)]["topics"])
        picked = sorted(rng.sample(tids, PER_YEAR))
        years[str(year)] = picked
        print(year, picked, flush=True)
    OUT.write_text(
        json.dumps(
            {
                "seed": SEED,
                "per_year": PER_YEAR,
                "years": years,
                "note": "Drawn before any cheap-pass score. 2021 and 2022 only.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
