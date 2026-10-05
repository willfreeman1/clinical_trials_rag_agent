"""Write a committed table of the tracked MLflow runs.

Long format: one row per run-and-metric. Interval bounds sit in
lo / hi on the same row rather than as extra columns. Config that
distinguishes the run rides along so a spreadsheet stays dense.

These twelve runs are the ones that produced reported results, not
every experiment the project ran.

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

FIELDNAMES = [
    "experiment",
    "run_name",
    "metric",
    "value",
    "lo",
    "hi",
    "config",
    "threshold_commit",
    "retrofitted",
]

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
    parts = [
        p
        for p in (
            cutoff,
            f"shortlist={short}" if short else "",
            f"cascade={cascade}" if cascade else "",
        )
        if p
    ]
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


def _config(params: dict[str, str]) -> str:
    parts: list[str] = []
    named = [
        ("model", params.get("model", "")),
        ("prompt", params.get("prompt", "")),
        ("lr", params.get("lr", "")),
        ("adapter", _adapter_size(params)),
        ("seed", params.get("seed", "")),
        ("cutoff", _cutoff(params)),
        ("year", _first(params, "year", "years")),
        ("patients", _n_patients(params)),
    ]
    for key, val in named:
        if val:
            parts.append(f"{key}={val}")
    leftover = {k: v for k, v in sorted(params.items()) if k not in CONSUMED and v}
    parts.extend(f"{k}={v}" for k, v in leftover.items())
    return "; ".join(parts)


def _num(v: float | None) -> str:
    if v is None:
        return ""
    return f"{v:.6f}".rstrip("0").rstrip(".")


def _fold_metrics(metrics: dict[str, float]) -> list[tuple[str, float, float | None, float | None]]:
    names = set(metrics)
    rows: list[tuple[str, float, float | None, float | None]] = []
    for name in sorted(names):
        if name.endswith("_lo") or name.endswith("_hi"):
            if name[:-3] in names:
                continue
        lo = metrics.get(f"{name}_lo")
        hi = metrics.get(f"{name}_hi")
        rows.append((name, metrics[name], lo, hi))
    return rows


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
    for exp in sorted(client.search_experiments(), key=lambda e: e.name):
        if exp.name == "Default":
            continue
        for run in client.search_runs(exp.experiment_id, order_by=["start_time ASC"]):
            params = {k: str(v) for k, v in run.data.params.items()}
            tags = run.data.tags
            shared = {
                "experiment": exp.name,
                "run_name": tags.get("mlflow.runName", run.info.run_id),
                "config": _config(params),
                "threshold_commit": tags.get("threshold_commit", ""),
                "retrofitted": tags.get("retrofitted", ""),
            }
            for name, value, lo, hi in _fold_metrics(run.data.metrics):
                rows.append(
                    {
                        **shared,
                        "metric": name,
                        "value": _num(value),
                        "lo": _num(lo),
                        "hi": _num(hi),
                    }
                )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    n_runs = len({(r["experiment"], r["run_name"]) for r in rows})
    print(
        f"wrote {OUT.relative_to(ROOT)} ({len(rows)} metric rows, {n_runs} runs)",
        flush=True,
    )


if __name__ == "__main__":
    main()
