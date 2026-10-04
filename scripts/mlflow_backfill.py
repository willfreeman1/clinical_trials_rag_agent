"""Retrofit TREC experiment history into a local MLflow store.

Reads numbers already on disk (data/trec/*.json when present, else
the committed tables in docs/). Does not rescore. Does not call a GPU.

The history is retrofitted. Live tracking starts with the reader.
The system does not say a patient qualifies.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_lora_common import (  # noqa: E402
    CI_RESULTS,
    RANK_2021_RESULTS,
    RANK_RESULTS,
    SEED_A,
    SEED_B,
    SEED_C,
    adapter_dir_for,
    adapter_scores_for,
)
from trec_score_common import DATA  # noqa: E402

TRACKING = ROOT / "mlruns"
STORE = f"file:{TRACKING.as_posix()}"


def epoch_ms(text: str) -> int:
    aware = datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return int(aware.timestamp() * 1000)


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def log_run(
    experiment: str,
    name: str,
    started: str,
    params: dict,
    metrics: dict,
    tags: dict,
    artifacts: list[Path],
) -> str:
    import mlflow
    from mlflow.entities import RunStatus
    from mlflow.tracking import MlflowClient

    mlflow.set_experiment(experiment)
    client = MlflowClient()
    exp = client.get_experiment_by_name(experiment)
    run = client.create_run(
        exp.experiment_id,
        start_time=epoch_ms(started),
        tags={
            "mlflow.runName": name,
            "retrofitted": "true",
            "live_from": "reader",
            **{k: str(v) for k, v in tags.items()},
        },
    )
    rid = run.info.run_id
    for k, v in params.items():
        if v is None:
            continue
        client.log_param(rid, k, str(v))
    end = epoch_ms(started) + 60_000
    for k, v in metrics.items():
        if v is None:
            continue
        client.log_metric(rid, k, float(v), timestamp=end)
    for path in artifacts:
        if path.exists():
            client.log_artifact(rid, str(path))
    client.set_terminated(rid, status=RunStatus.to_string(RunStatus.FINISHED), end_time=end)
    return rid


def maybe_ci() -> dict:
    return load_json(CI_RESULTS)


def maybe_rank() -> dict:
    return load_json(RANK_RESULTS)


def maybe_rank_2021() -> dict:
    return load_json(RANK_2021_RESULTS)


def register_adapters(client, runs_by_seed: dict[int, str]) -> None:
    names = {
        SEED_A: ("qwen-elig-lora-20261003", 0.793, "0.748", "0.834", False),
        SEED_B: ("qwen-elig-lora-20261006", 0.770, None, None, False),
        SEED_C: ("qwen-elig-lora-20261007", 0.773, None, None, True),
    }
    for seed, (reg_name, auroc, lo, hi, in_use) in names.items():
        run_id = runs_by_seed.get(seed)
        if not run_id:
            continue
        src = adapter_dir_for(seed)
        if src.exists():
            uri = f"runs:/{run_id}/adapter"
        else:
            uri = f"runs:/{run_id}"
        try:
            client.create_registered_model(
                reg_name,
                tags={
                    "seed": str(seed),
                    "auroc_2022": str(auroc),
                    "in_use": "true" if in_use else "false",
                    "retrofitted": "true",
                    "gate": "held-out 2022 1-vs-2 AUROC; quote mean 0.779 (0.770-0.793)",
                },
            )
        except Exception:
            pass
        mv = client.create_model_version(reg_name, uri, run_id=run_id)
        client.set_model_version_tag(reg_name, mv.version, "auroc_2022", str(auroc))
        client.set_model_version_tag(reg_name, mv.version, "seed", str(seed))
        if lo is not None:
            client.set_model_version_tag(reg_name, mv.version, "auroc_2022_lo", lo)
            client.set_model_version_tag(reg_name, mv.version, "auroc_2022_hi", hi)
        if in_use:
            client.set_registered_model_alias(reg_name, "in_use", mv.version)
            client.set_registered_model_tag(reg_name, "role", "ranking_adapter_in_use")
            client.set_registered_model_tag(
                reg_name,
                "why_this_seed",
                "median of three 1e-5 seeds, closest to the mean 0.779",
            )


def log_adapter_artifact(run_id: str, seed: int) -> None:
    import mlflow

    src = adapter_dir_for(seed)
    if not src.exists():
        return
    with mlflow.start_run(run_id=run_id):
        mlflow.log_artifacts(str(src), artifact_path="adapter")


def main() -> None:
    import mlflow
    from mlflow.tracking import MlflowClient

    if TRACKING.exists():
        shutil.rmtree(TRACKING)
    TRACKING.mkdir(parents=True)
    mlflow.set_tracking_uri(STORE)
    client = MlflowClient(tracking_uri=STORE)

    ci = maybe_ci()
    rank = maybe_rank()
    rank21 = maybe_rank_2021()
    finish = load_json(DATA / "trec_lora_rank_finish.json")
    docs = ROOT / "docs"

    log_run(
        "trec_retrieval",
        "keyword_hybrid_6pct",
        "2026-09-30 16:00:00",
        {
            "fusion": "RRF",
            "depth": "6pct",
            "years": "2021,2022,2023",
            "collection": "judged_pool",
        },
        {
            "eligible_recall_6pct_2021": 0.916,
            "eligible_recall_6pct_2022": 0.914,
            "eligible_recall_6pct_2023": 0.654,
        },
        {"threshold_commit": "613635e", "writeup": "docs/trec_hybrid_retrieval.md"},
        [docs / "trec_hybrid_retrieval.md"],
    )
    log_run(
        "trec_retrieval",
        "rerank_shortlist",
        "2026-09-30 22:00:00",
        {
            "shortlist": "keyword_hybrid_6pct",
            "ce": "medcpt_ce + msmarco",
            "llm": "gpt-4o-mini_top200_2021",
        },
        {
            "recall_at_10_2021_best": 0.090,
            "recall_at_10_2021_baseline": 0.057,
        },
        {"threshold_commit": "44878a7", "writeup": "docs/trec_rerank.md", "verdict": "below_doubling_stop"},
        [docs / "trec_rerank.md"],
    )
    log_run(
        "trec_scoring",
        "qwen_topical_slice",
        "2026-10-01 18:00:00",
        {
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "prompt": "topical_title_cond_slice",
            "score": "continuous_expected_digit",
            "patients_2021": 75,
            "patients_2022": 50,
        },
        {
            "p10_2021": 0.519,
            "p10_2021_lo": 0.468,
            "p10_2021_hi": 0.567,
            "ndcg10_graded_2021": 0.657,
            "ndcg10_graded_2021_lo": 0.617,
            "ndcg10_graded_2021_hi": 0.696,
            "p10_2022": 0.570,
            "p10_2022_lo": 0.498,
            "p10_2022_hi": 0.646,
            "ndcg10_graded_2022": 0.662,
            "ndcg10_graded_2022_lo": 0.585,
            "ndcg10_graded_2022_hi": 0.734,
            "auroc_1v2_2022": 0.682,
        },
        {"threshold_commit": "114cce7", "writeup": "docs/trec_score.md", "role": "current_default_ranker"},
        [docs / "trec_score.md", docs / "trec_lora_rank.md"],
    )
    log_run(
        "trec_scoring",
        "elig_prompt_v2",
        "2026-10-02 10:00:00",
        {"prompt": "v2_CHECK_then_eligible", "patients": "30_sample"},
        {"auroc_1v2": 0.60, "p20_2021_sample": 0.340, "p20_v1_same_sample": 0.487},
        {"threshold_commit": "4424157", "writeup": "docs/trec_elig_v2.md", "verdict": "do_not_replace_v1"},
        [docs / "trec_elig_v2.md"],
    )
    log_run(
        "trec_frontier",
        "gpt54_elig_411pairs",
        "2026-10-02 18:00:00",
        {
            "model": "gpt-5.4",
            "pairs": 411,
            "patients": 30,
            "prompt": "v1_and_trec_label",
        },
        {
            "auroc_v1": 0.828,
            "auroc_trec_prompt": 0.829,
            "p_elig_ge_0.75_joinable_rate": 0.85,
            "usd": 1.75,
        },
        {
            "threshold_commit": "99f795c",
            "writeup": "docs/trec_frontier_elig.md",
            "note": "Different and smaller sample than the 0.779 adapter figure. Not a gold standard.",
        },
        [docs / "trec_frontier_elig.md"],
    )

    adapter_runs: dict[int, str] = {}
    a_ci = (ci.get("adapter_ci") or {}) if ci else {}
    adapter_runs[SEED_A] = log_run(
        "trec_lora",
        "adapter_seed_20261003",
        "2026-10-02 21:30:00",
        {
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "adapter": "lora",
            "lora_r": 16,
            "lora_alpha": 32,
            "lr": 1e-5,
            "seed": SEED_A,
            "prompt": "v1_ELIG_SYSTEM_DIGIT",
            "score": "logit2_minus_logit1",
            "train_year": 2021,
            "test_year": 2022,
            "n_test_patients": 50,
        },
        {
            "auroc_2022": 0.793,
            "auroc_2022_lo": a_ci.get("lo", 0.748),
            "auroc_2022_hi": a_ci.get("hi", 0.834),
            "auroc_untrained_same_pairs": 0.749,
            "patients_adapter_higher": 43,
        },
        {
            "threshold_commit": "2f04bfa",
            "writeup": "docs/trec_lora_elig.md",
            "headline": "false",
            "note": "First working seed. Do not quote 0.793 as the result. Mean of three is 0.779.",
        },
        [docs / "trec_lora_elig.md", CI_RESULTS, adapter_scores_for(SEED_A)],
    )
    log_adapter_artifact(adapter_runs[SEED_A], SEED_A)

    adapter_runs[SEED_B] = log_run(
        "trec_lora",
        "adapter_seed_20261006",
        "2026-10-03 12:30:00",
        {
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "adapter": "lora",
            "lora_r": 16,
            "lora_alpha": 32,
            "lr": 1e-5,
            "seed": SEED_B,
            "prompt": "v1_ELIG_SYSTEM_DIGIT",
            "score": "logit2_minus_logit1",
            "train_year": 2021,
            "test_year": 2022,
            "n_test_patients": 50,
        },
        {"auroc_2022": 0.770, "auroc_untrained_same_pairs": 0.749, "patients_adapter_higher": 44},
        {
            "threshold_commit": "778721f",
            "writeup": "docs/trec_lora_elig.md",
            "headline": "false",
        },
        [docs / "trec_lora_elig.md", adapter_scores_for(SEED_B)],
    )
    log_adapter_artifact(adapter_runs[SEED_B], SEED_B)

    adapter_runs[SEED_C] = log_run(
        "trec_lora",
        "adapter_seed_20261007",
        "2026-10-03 13:00:00",
        {
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "adapter": "lora",
            "lora_r": 16,
            "lora_alpha": 32,
            "lr": 1e-5,
            "seed": SEED_C,
            "prompt": "v1_ELIG_SYSTEM_DIGIT",
            "score": "logit2_minus_logit1",
            "train_year": 2021,
            "test_year": 2022,
            "n_test_patients": 50,
        },
        {"auroc_2022": 0.773, "auroc_untrained_same_pairs": 0.749, "patients_adapter_higher": 43},
        {
            "threshold_commit": "778721f",
            "writeup": "docs/trec_lora_elig.md",
            "headline": "false",
            "in_use": "true",
            "why": "median seed, closest to mean 0.779",
        },
        [docs / "trec_lora_elig.md", adapter_scores_for(SEED_C)],
    )
    log_adapter_artifact(adapter_runs[SEED_C], SEED_C)

    log_run(
        "trec_lora",
        "three_seed_mean",
        "2026-10-03 13:30:00",
        {"seeds": "20261003,20261006,20261007", "lr": 1e-5, "lora_r": 16},
        {
            "auroc_2022_mean": 0.779,
            "auroc_2022_min": 0.770,
            "auroc_2022_max": 0.793,
            "spread": 0.023,
        },
        {
            "threshold_commit": "778721f",
            "writeup": "docs/trec_lora_elig.md",
            "quote": "0.779 (0.770-0.793)",
        },
        [docs / "trec_lora_elig.md"],
    )

    p_cas = (finish.get("paired") or {}).get("cascade25_minus_topical_p10") or {}
    log_run(
        "trec_ranking",
        "ranker_2022_sweep",
        "2026-10-03 18:00:00",
        {
            "adapter_seed": SEED_C,
            "year": 2022,
            "n_patients": 50,
            "shortlist_depth": 1595,
            "cascade_cutoffs": "25,50,100,200,300,500",
        },
        {
            "p10_topical": 0.570,
            "p10_topical_lo": 0.498,
            "p10_topical_hi": 0.646,
            "p10_adapter": 0.550,
            "p10_cascade100": 0.616,
            "p10_cascade25": 0.624,
            "cascade25_minus_topical_p10": p_cas.get("point", 0.054),
            "cascade25_minus_topical_p10_lo": p_cas.get("lo", 0.016),
            "cascade25_minus_topical_p10_hi": p_cas.get("hi", 0.092),
            "adapter_minus_topical_ndcg": -0.069,
            "adapter_minus_topical_ndcg_lo": -0.125,
            "adapter_minus_topical_ndcg_hi": -0.012,
            "adapter_minus_topical_ndcg_bin": -0.017,
            "usd": 6.65,
        },
        {
            "threshold_commit": "3b50e06",
            "writeup": "docs/trec_lora_rank.md",
            "note": "Cutoff 25 was a sweep finding on this year, not locked in advance.",
        },
        [docs / "trec_lora_rank.md", DATA / "trec_lora_rank_finish.json", RANK_RESULTS],
    )

    prim = (rank21.get("primary") or {}) if rank21 else {}
    log_run(
        "trec_ranking",
        "ranker_2021_cutoff25_prereg",
        "2026-10-04 06:00:00",
        {
            "adapter_seed": SEED_C,
            "year": 2021,
            "n_patients": 75,
            "cutoff": 25,
            "primary": "paired_p10_cascade25_minus_topical",
            "no_sweep": True,
        },
        {
            "p10_cascade25": 0.627,
            "p10_topical": 0.519,
            "primary_delta_p10": prim.get("point", 0.108),
            "primary_delta_p10_lo": prim.get("lo", 0.068),
            "primary_delta_p10_hi": prim.get("hi", 0.148),
            "cascade_higher": prim.get("a_higher", 47),
            "topical_higher": prim.get("b_higher", 13),
            "tie": prim.get("tie", 15),
            "usd": 12.40,
        },
        {
            "threshold_commit": "ed41185",
            "writeup": "docs/trec_lora_rank.md",
            "verdict": prim.get("verdict", "replicates"),
            "note": "60 of 75 patients were in the adapter train set. This tests the cutoff, not adapter generalisation.",
        },
        [docs / "trec_lora_rank.md", RANK_2021_RESULTS],
    )

    register_adapters(client, adapter_runs)
    print(f"tracking URI {STORE}", flush=True)
    print("experiments:", [e.name for e in client.search_experiments()], flush=True)
    for seed, rid in adapter_runs.items():
        print(f"  adapter seed {seed} run {rid}", flush=True)
    print("registered:", [m.name for m in client.search_registered_models()], flush=True)
    print("History is retrofitted. Live use starts with the reader.", flush=True)


if __name__ == "__main__":
    main()
