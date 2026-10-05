"""Evaluate the pre-registered 2021 cutoff-25 replication. No GPU.

Primary measure: paired P@10, cascade-at-25 minus topical slice.
Patients are resampled, not pairs. Other cutoffs are not scored.
2023 is not used. The system does not say a patient qualifies.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_lora_common import RANK_2021_CONFIG, RANK_2021_RESULTS, RANK_2021_SCORES  # noqa: E402
from trec_lora_eval import load, score_of  # noqa: E402
from trec_lora_rank_eval import cascade  # noqa: E402
from trec_lora_rank_finish import (  # noqa: E402
    BOOT_SEED,
    N_BOOT,
    boot_paired_diff,
    official_row,
    percentile,
)
from trec_score_common import QWEN_SCORES, load_qrels, load_shortlist, mean  # noqa: E402
from trec_score_eval import order_by, qwen_maps, topic_metrics  # noqa: E402

ED_NS = (20, 200, 500)


def elig_2021(path: Path) -> dict[str, dict[str, tuple[int, float]]]:
    raw = load(path)
    block = ((raw.get("scores") or {}).get("2021") or {})
    out = {}
    for tid, scores in block.items():
        dest = {}
        for nct, rec in scores.items():
            sc = score_of(rec)
            if sc is None:
                continue
            digit = int(rec[0]) if isinstance(rec, list) and rec else 0
            dest[str(nct)] = (digit, float(sc))
        out[str(tid)] = dest
    return out


def ed_from_rows(rows: list[dict]) -> dict:
    out = {"n": len(rows), "ten_in_20": sum(1 for r in rows if r["ten_in_20"])}
    for d in ED_NS:
        out[f"eq_mult@{d}"] = mean([r["eq_mult"].get(d) for r in rows if r["eq_mult"].get(d) is not None])
        out[f"eq@{d}"] = mean([r["eq"].get(d) for r in rows if r["eq"].get(d) is not None])
        out[f"precision@{d}"] = mean([r["precision"].get(d) for r in rows if d in r["precision"]])
    out["precision@10"] = mean([r["precision"].get(10) for r in rows if 10 in r["precision"]])
    return out


def boot_mean(vals: list[float], rng: random.Random) -> dict:
    n = len(vals)
    draws = []
    for _ in range(N_BOOT):
        draws.append(sum(vals[rng.randrange(n)] for _ in range(n)) / n)
    return {
        "n_boot": N_BOOT,
        "seed": BOOT_SEED,
        "mean": sum(draws) / len(draws),
        "lo": percentile(draws, 0.025),
        "hi": percentile(draws, 0.975),
        "point": sum(vals) / n if n else None,
        "median": percentile(vals, 0.5),
        "n_patients": n,
    }


def summarize_official(rows: list[dict], rng: random.Random) -> dict:
    out = {"n": len(rows)}
    for key in ("ndcg@10", "ndcg@10_bin", "p@10", "rprec", "mrr"):
        vals = [r[key] for r in rows if r.get(key) is not None]
        boot = boot_mean(vals, rng)
        out[key] = {
            "mean": boot["point"],
            "lo": boot["lo"],
            "hi": boot["hi"],
            "median": boot["median"],
            "n": boot["n_patients"],
        }
    return out


def main() -> None:
    cfg = json.loads(RANK_2021_CONFIG.read_text(encoding="utf-8"))
    if int(cfg["cutoff"]) != 25:
        raise SystemExit("refusing to evaluate a cutoff other than the locked 25")
    if not RANK_2021_SCORES.exists():
        raise SystemExit(f"missing {RANK_2021_SCORES}")
    short = load_shortlist()
    labels_all = load_qrels(2021)
    topics = short["years"]["2021"]["topics"]
    sl = qwen_maps(load(QWEN_SCORES), "topical_title_cond_slice").get("2021") or {}
    elig = elig_2021(RANK_2021_SCORES)
    ready = []
    for tid in cfg["patients"]:
        base = (topics.get(tid) or {}).get("shortlist") or []
        if len(base) < 10 or len(elig.get(tid) or {}) < len(base):
            continue
        ready.append(tid)
    if len(ready) != 75:
        raise SystemExit(f"expected 75 full 2021 adapter shortlists, got {len(ready)}")

    tm: dict[str, list] = {}
    off: dict[str, list] = {}
    p10: dict[str, list[float]] = {}
    for tid in ready:
        base = topics[tid]["shortlist"]
        labels = labels_all.get(tid) or {}
        tsc = sl.get(tid) or {}
        esc = elig[tid]
        orders = {
            "baseline_fused": base,
            "topical_slice_cont": order_by(base, lambda n, s=tsc: float(s[n][1]) if n in s else -1.0),
            "cascade_top25": cascade(base, tsc, esc, 25),
        }
        for tag, order in orders.items():
            tm.setdefault(tag, []).append(topic_metrics(order, labels, base))
            row = official_row(order, labels)
            off.setdefault(tag, []).append(row)
            p10.setdefault(tag, []).append(row["p@10"])

    rng = random.Random(BOOT_SEED)
    primary = boot_paired_diff(p10["cascade_top25"], p10["topical_slice_cont"], rng)
    if primary["lo"] > 0:
        verdict = "replicates"
        verdict_text = cfg["interpretation"]["interval_excludes_zero_positive"]
    elif primary["hi"] < 0:
        verdict = "reverses"
        verdict_text = cfg["interpretation"]["interval_excludes_zero_negative"]
    else:
        verdict = "includes_zero"
        verdict_text = cfg["interpretation"]["interval_includes_zero"]

    rng_o = random.Random(BOOT_SEED)
    report = {
        "note": cfg["note"],
        "adapter_seed": cfg["adapter_seed"],
        "cutoff": 25,
        "n_patients": len(ready),
        "primary": {
            "metric": "p@10",
            "contrast": "cascade_top25 minus topical_slice_cont",
            **primary,
            "verdict": verdict,
            "verdict_text": verdict_text,
        },
        "secondary_official": {tag: summarize_official(off[tag], rng_o) for tag in off},
        "secondary_paired": {
            "cascade25_minus_topical_ndcg": boot_paired_diff(
                [r["ndcg@10"] for r in off["cascade_top25"]],
                [r["ndcg@10"] for r in off["topical_slice_cont"]],
                random.Random(BOOT_SEED),
            ),
            "cascade25_minus_topical_ndcg_bin": boot_paired_diff(
                [r["ndcg@10_bin"] for r in off["cascade_top25"]],
                [r["ndcg@10_bin"] for r in off["topical_slice_cont"]],
                random.Random(BOOT_SEED),
            ),
        },
        "equivalent_depth": {tag: ed_from_rows(tm[tag]) for tag in tm},
        "boot_seed": BOOT_SEED,
        "n_boot": N_BOOT,
    }
    RANK_2021_RESULTS.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {RANK_2021_RESULTS}", flush=True)
    print("PRIMARY P@10", primary, flush=True)
    print("VERDICT", verdict, flush=True)
    for tag, rec in report["equivalent_depth"].items():
        print(
            f"  {tag}: P@10 {rec['precision@10']:.3f} P@20 {rec['precision@20']:.3f} "
            f"ED20 {rec['eq_mult@20']:.2f} ED200 {rec['eq_mult@200']:.2f} "
            f"10in20 {rec['ten_in_20']}/{rec['n']}",
            flush=True,
        )


if __name__ == "__main__":
    main()
