"""Write a committed table of every MLflow run.

Reads the local file store (mlruns/). Does not rescore. Does not
need data/trec/. Regenerates docs/trec_mlflow_runs.csv so the
numbers stay in the repository after the store is gitignored.

The history is retrofitted. Live tracking starts with the reader.
The system does not say a patient qualifies.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORE = f"file:{(ROOT / 'mlruns').as_posix()}"
OUT = ROOT / "docs" / "trec_mlflow_runs.csv"

# Columns the brief asked for, in that order, then every metric
# that appears on any run, then the two honesty tags.
CONFIG_COLS = [
    "experiment",
    "run_name",
    "model",
    "prompt",
    "learning_rate",
    "adapter_size",
    "seed",
    "cutoff_depth",
    "year",
    "n_patients",
    "other_params",
]
TRAIL_COLS = ["threshold_commit", "retrofitted"]

# Param names that fold into the config columns above.
CONSUMED = {
    "model",
    "prompt",
    "lr",
    "lora_r",
    "lora_alpha",
    "adapter",
    "seed",
    "cutoff",
    "depth",
    "shortlist_depth",
    "cascade_cutoffs",
    "year",
    "years",
    "n_patients",
    "n_test_patients",
    "patients",
    "patients_2021",
    "patients_2022",
}


def _first(params: dict[str, str], *keys: str) -> str:
    for k in keys:
        if params.get(k):
            return params[k]
    return ""


def _adapter_size(params: dict[str, str]) -> str:
    r = params.get("lora_r")
    a = params.get("lora_alpha")
    if r and a:
        return f"r={r} alpha={a}"
    if r:
        return f"r={r}"
    return params.get("adapter", "")


def _cutoff(params: dict[str, str]) -> str:
    cutoff = _first(params, "cutoff", "depth")
    short = params.get("shortlist_depth", "")
    cascade = params.get("cascade_cutoffs", "")
    parts = [p for p in (cutoff, f"shortlist={short}" if short else "", f"cascade={cascade}" if cascade else "") if p]
    return "; ".join(parts)


def _n_patients(params: dict[str, str]) -> str:
    n = _first(params, "n_patients", "n_test_patients", "patients")
    if n:
        return n
    p21 = params.get("patients_2021", "")
    p22 = params.get("patients_2022", "")
    if p21 or p22:
        return f"2021={p21}; 2022={p22}".strip("; ")
    return ""


def _other(params: dict[str, str]) -> str:
    leftover = {k: v for k, v in sorted(params.items()) if k not in CONSUMED and v}
    return "; ".join(f"{k}={v}" for k, v in leftover.items())


def _metric_cell(v: float) -> str:
    if v is None:
        return ""
    text = f"{v:.6f}".rstrip("0").rstrip(".")
    return text


def main() -> None:
    import mlflow
    from mlflow.tracking import MlflowClient

    store = Path(ROOT / "mlruns")
    if not store.exists():
        sys.stderr.write(
            "No mlruns/ store. On this machine: python scripts/mlflow_backfill.py\n"
            "A fresh clone cannot rebuild the store (data/trec/ is not in git).\n"
            "The committed table is docs/trec_mlflow_runs.csv.\n"
        )
        sys.exit(1)

    mlflow.set_tracking_uri(STORE)
    client = MlflowClient(tracking_uri=STORE)

    rows: list[dict[str, str]] = []
    metric_keys: set[str] = set()
    for exp in sorted(client.search_experiments(), key=lambda e: e.name):
        if exp.name == "Default":
            continue
        for run in client.search_runs(exp.experiment_id, order_by=["start_time ASC"]):
            params = {k: str(v) for k, v in run.data.params.items()}
            metrics = run.data.metrics
            metric_keys.update(metrics)
            tags = run.data.tags
            rows.append(
                {
                    "experiment": exp.name,
                    "run_name": tags.get("mlflow.runName", run.info.run_id),
                    "model": params.get("model", ""),
                    "prompt": params.get("prompt", ""),
                    "learning_rate": params.get("lr", ""),
                    "adapter_size": _adapter_size(params),
                    "seed": params.get("seed", ""),
                    "cutoff_depth": _cutoff(params),
                    "year": _first(params, "year", "years"),
                    "n_patients": _n_patients(params),
                    "other_params": _other(params),
                    "threshold_commit": tags.get("threshold_commit", ""),
                    "retrofitted": tags.get("retrofitted", ""),
                    **{k: _metric_cell(v) for k, v in metrics.items()},
                }
            )

    metric_cols = sorted(metric_keys)
    fieldnames = CONFIG_COLS + metric_cols + TRAIL_COLS
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})
    print(f"wrote {OUT.relative_to(ROOT)} ({len(rows)} runs, {len(metric_cols)} metrics)", flush=True)


if __name__ == "__main__":
    main()
