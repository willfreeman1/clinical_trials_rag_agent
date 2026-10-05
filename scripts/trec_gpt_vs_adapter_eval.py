"""Score GPT-5.4 against the three adapter seeds on the locked 2022 pairs.

Patient bootstrap, not pair bootstrap. No overall accuracy.
The system does not say a patient qualifies.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_gpt_vs_adapter_common import (  # noqa: E402
    BOOT_SEED,
    GPT_SCORES,
    N_BOOT,
    PAIRS,
    REPORT,
    RESULTS,
    pair_rows,
)
from trec_lora_ci import boot_pooled, by_patient, percentile, pooled  # noqa: E402
from trec_lora_common import adapter_scores_for, pct  # noqa: E402
from trec_lora_eval import load, rows_for, score_of  # noqa: E402

SEEDS = (20261003, 20261006, 20261007)
ADAPTER_MEAN = 0.779


def gpt_score(rec: dict) -> float | None:
    if rec.get("error"):
        return None
    if rec.get("cont") is not None:
        return float(rec["cont"])
    if rec.get("digit") is not None:
        return float(rec["digit"])
    return None


def gpt_rows(pairs: dict, scores: dict) -> list[dict]:
    block = (scores.get("scores") or {}).get("2022") or {}
    out = []
    for row in pair_rows(pairs):
        rec = (block.get(row["topic"]) or {}).get(row["nct"]) or {}
        out.append(
            {
                "tid": row["topic"],
                "nct": row["nct"],
                "label": row["label"],
                "score": gpt_score(rec),
                "digit": rec.get("digit"),
                "reused": bool(rec.get("reused")),
            }
        )
    return out


def interval(rows: list[dict], rng: random.Random) -> dict:
    groups = by_patient(rows)
    tids = sorted(groups, key=lambda x: int(x))
    point = pooled([groups[t] for t in tids])
    boot = boot_pooled(tids, groups, rng)
    usable = [
        t
        for t, g in groups.items()
        if any(x["label"] == 2 for x in g) and any(x["label"] == 1 for x in g)
    ]
    return {
        "n1": sum(1 for r in rows if r["label"] == 1 and r.get("score") is not None),
        "n2": sum(1 for r in rows if r["label"] == 2 and r.get("score") is not None),
        "n_missing": sum(1 for r in rows if r.get("score") is None),
        "n_patients": len(tids),
        "n_patients_both": len(usable),
        "pooled": None if point is None else round(point, 4),
        "lo": round(percentile(boot, 0.025), 4) if boot else None,
        "hi": round(percentile(boot, 0.975), 4) if boot else None,
    }


def log_mlflow(rec: dict) -> None:
    try:
        import mlflow
        from mlflow.tracking import MlflowClient
    except ImportError:
        print("mlflow not installed; skipped live log", flush=True)
        return
    store = ROOT / "mlruns"
    if not store.exists():
        print("no mlruns/; skipped live log", flush=True)
        return
    mlflow.set_tracking_uri(f"file:{store.as_posix()}")
    mlflow.set_experiment("trec_eligibility")
    gpt = rec.get("gpt") or {}
    with mlflow.start_run(run_name="gpt54_vs_adapter_2022"):
        mlflow.set_tags(
            {
                "retrofitted": "false",
                "live_from": "gpt_vs_adapter",
                "threshold_commit": rec.get("threshold_commit") or "",
            }
        )
        mlflow.log_params(
            {
                "model": "gpt-5.4",
                "year": "2022",
                "prompt": "v1_ELIG_SYSTEM_DIGIT",
                "n_pairs": str(rec.get("n_pairs")),
            }
        )

        def put(name: str, value: object) -> None:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                mlflow.log_metric(name, float(value))

        put("auroc_gpt", gpt.get("pooled"))
        put("auroc_gpt_lo", gpt.get("lo"))
        put("auroc_gpt_hi", gpt.get("hi"))
        put("adapter_mean_reference", ADAPTER_MEAN)
        put("usd", rec.get("usd"))
        put("reused", rec.get("reused"))
        MlflowClient().set_terminated(mlflow.active_run().info.run_id)


def main() -> None:
    if not GPT_SCORES.exists():
        raise SystemExit(f"missing {GPT_SCORES}")
    pairs = json.loads(PAIRS.read_text(encoding="utf-8"))
    raw = json.loads(GPT_SCORES.read_text(encoding="utf-8"))
    g_rows = gpt_rows(pairs, raw)
    gpt = interval(g_rows, random.Random(BOOT_SEED))
    seeds = {}
    block = {"topics": pairs["topics"]}
    for seed in SEEDS:
        path = adapter_scores_for(seed)
        scores = load(path).get("scores") or {}
        rows = rows_for(block, scores, "2022")
        seeds[str(seed)] = interval(rows, random.Random(BOOT_SEED))
    rec = {
        "n_pairs": len(g_rows),
        "usd": raw.get("usd"),
        "reused": raw.get("reused"),
        "errors": raw.get("errors"),
        "logprobs_ok": raw.get("logprobs_ok"),
        "gpt": gpt,
        "adapter_seeds": seeds,
        "adapter_mean_reference": ADAPTER_MEAN,
        "untrained_qwen_reference": 0.749,
        "frontier_411_reference": 0.828,
        "no_overall_accuracy": True,
        "no_p_at_10": True,
        "threshold_commit": "6f7bc99",
    }
    RESULTS.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    log_mlflow(rec)
    print(json.dumps(rec, indent=2), flush=True)
    print(f"wrote {RESULTS}", flush=True)
    print(
        f"GPT {pct(gpt.get('pooled'))}  {pct(gpt.get('lo'))}–{pct(gpt.get('hi'))}  "
        f"vs adapter mean {ADAPTER_MEAN}",
        flush=True,
    )


if __name__ == "__main__":
    main()
