"""Held-out 2022 numbers for the three 1e-5 seeds. No GPU.

Does not pick a winner. Mean and spread are the headline.
2023 is not used. The system does not say a patient qualifies.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_lora_ci import by_patient, per_patient, pooled  # noqa: E402
from trec_lora_common import (  # noqa: E402
    ADAPTER_SCORES,
    BASE_SCORES,
    EVAL_PAIRS_PATH,
    SEED_A,
    SEED_RUNS,
    adapter_scores_for,
    pct,
    train_log_for,
)
from trec_lora_eval import load, rows_for  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "data" / "trec" / "trec_lora_seeds.json"
BASE_POOLED = 0.7492162043245275


def collapsed(seed: int) -> bool:
    path = train_log_for(seed)
    if not path.exists():
        return False
    rec = json.loads(path.read_text(encoding="utf-8"))
    if rec.get("stopped"):
        return True
    for probe in rec.get("probes") or []:
        if probe.get("collapsed"):
            return True
    return False


def one(seed: int, base_g: dict, ada_rows: list[dict]) -> dict:
    ada_g = by_patient(ada_rows)
    tids = sorted(set(base_g) & set(ada_g), key=lambda x: int(x))
    point = pooled([ada_g[t] for t in tids])
    base_pp = per_patient(base_g)
    ada_pp = per_patient(ada_g)
    both = sorted(set(base_pp) & set(ada_pp), key=lambda x: int(x))
    diffs = [ada_pp[t] - base_pp[t] for t in both]
    return {
        "seed": seed,
        "n_patients": len(tids),
        "pooled": point,
        "paired_mean_diff": (sum(diffs) / len(diffs)) if diffs else None,
        "n_adapter_higher": sum(1 for d in diffs if d > 0),
        "n_base_higher": sum(1 for d in diffs if d < 0),
        "n_tie": sum(1 for d in diffs if d == 0),
        "gain_vs_untrained_pooled": None if point is None else point - BASE_POOLED,
        "collapsed": collapsed(seed),
        "original_run": seed == SEED_A,
    }


def main() -> None:
    pairs = load(EVAL_PAIRS_PATH)
    block = pairs["test_2022"]
    base_rows = rows_for(block, load(BASE_SCORES).get("scores") or {}, "2022")
    base_g = by_patient(base_rows)
    runs = []
    for seed in SEED_RUNS:
        path = adapter_scores_for(seed)
        if not path.exists():
            if seed == SEED_A and ADAPTER_SCORES.exists():
                path = ADAPTER_SCORES
            else:
                print(f"missing scores for seed {seed}: {path}", flush=True)
                continue
        rec = one(seed, base_g, rows_for(block, load(path).get("scores") or {}, "2022"))
        rec["scores"] = str(path)
        runs.append(rec)
        print(
            f"seed {seed} pooled {pct(rec['pooled'])}  "
            f"gain {pct(rec['gain_vs_untrained_pooled'])}  "
            f"collapsed={rec['collapsed']}",
            flush=True,
        )
    alive = [r for r in runs if r.get("pooled") is not None and not r.get("collapsed")]
    use = alive if alive else [r for r in runs if r.get("pooled") is not None]
    xs = [float(r["pooled"]) for r in use]
    report = {
        "note": (
            "Three repetitions of one configuration. 2022 was scored once per "
            "seed at the end and was not used to choose a seed. Headline is "
            "the mean of non-collapsed seeds, with the spread stated. Do not "
            "quote the best run."
        ),
        "untrained_pooled": BASE_POOLED,
        "runs": runs,
        "n_reported": len(use),
        "n_collapsed": sum(1 for r in runs if r.get("collapsed")),
        "mean_pooled": (sum(xs) / len(xs)) if xs else None,
        "min_pooled": min(xs) if xs else None,
        "max_pooled": max(xs) if xs else None,
        "spread": (max(xs) - min(xs)) if xs else None,
        "mean_gain_vs_untrained": (
            (sum(float(r["gain_vs_untrained_pooled"]) for r in use) / len(use)) if use else None
        ),
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        f"mean {pct(report['mean_pooled'])}  "
        f"range {pct(report['min_pooled'])}–{pct(report['max_pooled'])}  "
        f"spread {pct(report['spread'])}",
        flush=True,
    )
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
