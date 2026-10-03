"""Patient-resampled intervals for the 1-vs-2 AUROC. No GPU.

Resamples patients, not pairs: pairs from one note are not independent.
2023 is not used. The system does not say a patient qualifies.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_lora_common import (  # noqa: E402
    ADAPTER_SCORES,
    BASE_SCORES,
    EVAL_PAIRS_PATH,
    auroc,
    load_splits,
    pct,
)
from trec_lora_eval import load, rows_for, score_of  # noqa: E402

BOOT_SEED = 20261004
N_BOOT = 5000
OUT = Path(__file__).resolve().parents[1] / "data" / "trec" / "trec_lora_ci.json"


def by_patient(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("score") is None or r["label"] not in (1, 2):
            continue
        out.setdefault(r["tid"], []).append(r)
    return out


def pooled(groups: list[list[dict]]) -> float | None:
    pos = [r["score"] for g in groups for r in g if r["label"] == 2]
    neg = [r["score"] for g in groups for r in g if r["label"] == 1]
    return auroc(pos, neg)


def per_patient(groups_map: dict[str, list[dict]]) -> dict[str, float]:
    out = {}
    for tid, rows in groups_map.items():
        pos = [r["score"] for r in rows if r["label"] == 2]
        neg = [r["score"] for r in rows if r["label"] == 1]
        val = auroc(pos, neg)
        if val is not None:
            out[tid] = val
    return out


def percentile(xs: list[float], q: float) -> float:
    ys = sorted(xs)
    if not ys:
        raise SystemExit("empty bootstrap")
    i = min(len(ys) - 1, max(0, int(q * (len(ys) - 1))))
    return ys[i]


def boot_pooled(tids: list[str], groups: dict[str, list[dict]], rng: random.Random) -> list[float]:
    vals = []
    for _ in range(N_BOOT):
        draw = [rng.choice(tids) for _ in tids]
        val = pooled([groups[t] for t in draw])
        if val is not None:
            vals.append(val)
    return vals


def main() -> None:
    pairs = load(EVAL_PAIRS_PATH)
    block = pairs["test_2022"]
    base_rows = rows_for(block, load(BASE_SCORES).get("scores") or {}, "2022")
    ada_rows = rows_for(block, load(ADAPTER_SCORES).get("scores") or {}, "2022")
    base_g = by_patient(base_rows)
    ada_g = by_patient(ada_rows)
    tids = sorted(set(base_g) & set(ada_g), key=lambda x: int(x))
    if len(tids) != 50:
        raise SystemExit(f"expected 50 test patients, got {len(tids)}")

    base_point = pooled([base_g[t] for t in tids])
    ada_point = pooled([ada_g[t] for t in tids])
    base_pp = per_patient(base_g)
    ada_pp = per_patient(ada_g)
    both = sorted(set(base_pp) & set(ada_pp), key=lambda x: int(x))
    diffs = [ada_pp[t] - base_pp[t] for t in both]
    n_ada_win = sum(1 for d in diffs if d > 0)
    n_base_win = sum(1 for d in diffs if d < 0)
    n_tie = sum(1 for d in diffs if d == 0)

    rng_a = random.Random(BOOT_SEED)
    rng_b = random.Random(BOOT_SEED)
    rng_d = random.Random(BOOT_SEED)
    ada_boot = boot_pooled(tids, ada_g, rng_a)
    base_boot = boot_pooled(tids, base_g, rng_b)
    diff_boot = []
    for _ in range(N_BOOT):
        draw = [rng_d.choice(tids) for _ in tids]
        a = pooled([ada_g[t] for t in draw])
        b = pooled([base_g[t] for t in draw])
        if a is not None and b is not None:
            diff_boot.append(a - b)
    mean_diff_boot = []
    rng_m = random.Random(BOOT_SEED)
    for _ in range(N_BOOT):
        draw = [rng_m.choice(both) for _ in both]
        mean_diff_boot.append(sum(ada_pp[t] - base_pp[t] for t in draw) / len(draw))

    def ci(xs: list[float]) -> dict:
        return {
            "n": len(xs),
            "mean": sum(xs) / len(xs),
            "lo": percentile(xs, 0.025),
            "hi": percentile(xs, 0.975),
        }

    ada_ci = ci(ada_boot)
    base_ci = ci(base_boot)
    gap_ci = ci(diff_boot)
    paired_ci = ci(mean_diff_boot)
    base_inside = ada_ci["lo"] <= (base_point or 0) <= ada_ci["hi"]
    zero_inside = gap_ci["lo"] <= 0 <= gap_ci["hi"]

    report = {
        "boot_seed": BOOT_SEED,
        "n_boot": N_BOOT,
        "n_patients": len(tids),
        "note": (
            "Patients resampled with replacement. All judged 1 and 2 for a "
            "drawn patient are kept together. 95% percentile interval."
        ),
        "adapter_pooled": ada_point,
        "base_pooled": base_point,
        "adapter_ci": ada_ci,
        "base_ci": base_ci,
        "pooled_diff_ci": gap_ci,
        "paired_per_patient": {
            "n": len(both),
            "mean_diff": sum(diffs) / len(diffs),
            "n_adapter_higher": n_ada_win,
            "n_base_higher": n_base_win,
            "n_tie": n_tie,
            "ci": paired_ci,
        },
        "base_point_inside_adapter_ci": base_inside,
        "zero_inside_pooled_diff_ci": zero_inside,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        f"adapter pooled {pct(ada_point)}  "
        f"95% patient bootstrap {pct(ada_ci['lo'])}–{pct(ada_ci['hi'])}",
        flush=True,
    )
    print(
        f"base pooled    {pct(base_point)}  "
        f"95% patient bootstrap {pct(base_ci['lo'])}–{pct(base_ci['hi'])}",
        flush=True,
    )
    print(
        f"adapter minus base (same patient draws) "
        f"{pct(gap_ci['mean'])}  95% {pct(gap_ci['lo'])}–{pct(gap_ci['hi'])}",
        flush=True,
    )
    print(
        f"0.749 inside adapter interval? {base_inside}  "
        f"zero inside difference interval? {zero_inside}",
        flush=True,
    )
    print(
        f"per-patient AUROC: adapter higher {n_ada_win}/{len(both)}, "
        f"base higher {n_base_win}/{len(both)}, tie {n_tie}; "
        f"mean diff {pct(sum(diffs)/len(diffs))}  "
        f"95% {pct(paired_ci['lo'])}–{pct(paired_ci['hi'])}",
        flush=True,
    )
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
