"""Score the locked 2022 top-25 reader against TREC labels. No GPU.

Does not invent an overall accuracy. Uncertain is a third call, not
a wrong 1 or 2. Patient bootstrap, not pair bootstrap.
The system does not say a patient qualifies.
"""

from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_cheap_common import wilson  # noqa: E402
from trec_reader_common import (  # noqa: E402
    FABRICATION_REFERENCE,
    READS,
    RESULTS,
    WILL_SAMPLE,
)
from trec_score_common import PACK  # noqa: E402

BOOT_SEED = 20261004
N_BOOT = 5000
WILL_N = 80
WILL_SEED = 20261004
THRESHOLD_COMMIT = "89a2bf4"


def auroc(pos: list[float], neg: list[float]) -> float | None:
    if not pos or not neg:
        return None
    gt = 0
    eq = 0
    for p in pos:
        for n in neg:
            if p > n:
                gt += 1
            elif p == n:
                eq += 1
    return (gt + 0.5 * eq) / (len(pos) * len(neg))


def percentile(xs: list[float], q: float) -> float:
    ys = sorted(xs)
    i = min(len(ys) - 1, max(0, int(q * (len(ys) - 1))))
    return ys[i]


def boot_pooled(
    tids: list[str],
    groups: dict[str, list[dict]],
    key: str,
    rng: random.Random,
) -> list[float]:
    vals = []
    for _ in range(N_BOOT):
        draw = [rng.choice(tids) for _ in tids]
        pos = [r[key] for t in draw for r in groups[t] if r["label"] == 2]
        neg = [r[key] for t in draw for r in groups[t] if r["label"] == 1]
        val = auroc(pos, neg)
        if val is not None:
            vals.append(val)
    return vals


def load_reads(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def titles() -> dict[str, str]:
    if not PACK.exists():
        return {}
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    return {k: (v.get("title") or "") for k, v in (pack.get("docs") or {}).items()}


def cross(rows: list[dict], pred_key: str) -> dict:
    tab: dict[str, dict[str, int]] = {}
    for r in rows:
        pred = str((r.get("aggregates") or {}).get(pred_key) or "uncertain")
        lab = r.get("label")
        lab_s = "unjudged" if lab in (None, 9) else str(lab)
        tab.setdefault(pred, {})
        tab[pred][lab_s] = tab[pred].get(lab_s, 0) + 1
    return tab


def offered_quotes(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        coerced = set(r.get("coerced_rule_ids") or [])
        for rule in r.get("rules") or []:
            if rule.get("verdict") == "not_enough_information":
                continue
            if not str(rule.get("quote") or "").strip():
                continue
            item = dict(rule)
            item["patient_id"] = r.get("patient_id")
            item["nct_id"] = r.get("nct_id")
            item["label"] = r.get("label")
            item["was_coerced"] = rule.get("rule_id") in coerced
            out.append(item)
    return out


def write_will_sample(quotes: list[dict], name_of: dict[str, str]) -> None:
    rng = random.Random(WILL_SEED)
    by_b: dict[str, list[dict]] = {}
    for q in quotes:
        by_b.setdefault(q.get("quote_bucket") or "E", []).append(q)
    picked: list[dict] = []
    # Keep the rare buckets, then fill from ok/B.
    for bucket in ("E", "D", "C", "A", "B", "ok"):
        pool = list(by_b.get(bucket) or [])
        rng.shuffle(pool)
        take = min(len(pool), 12 if bucket in {"E", "D", "C", "A"} else 28)
        picked.extend(pool[:take])
    if len(picked) > WILL_N:
        rng.shuffle(picked)
        picked = picked[:WILL_N]
    elif len(picked) < WILL_N:
        rest = [q for q in quotes if q not in picked]
        rng.shuffle(rest)
        picked.extend(rest[: WILL_N - len(picked)])
    lines = [
        "# Reader Will-check: do the offered quotes say what the model claims?",
        "",
        "Reading only. For each row: does the quoted sentence plainly",
        "support the one-sentence explanation? Not a medical judgment.",
        "Not a decision that anyone qualifies.",
        "",
        f"Drawn with seed {WILL_SEED} from the 2022 top-25 reader.",
        f"{len(picked)} offered-quote rows (verdict met or not_met).",
        "Empty `not_enough_information` quotes are not in this sheet.",
        "",
        "Will: agree / disagree / cannot tell",
        "",
    ]
    for i, q in enumerate(picked, 1):
        title = name_of.get(q.get("nct_id") or "", "")
        lines.extend(
            [
                f"## {i}. patient {q.get('patient_id')} / {q.get('nct_id')}",
                "",
                f"_{title}_" if title else "",
                "",
                f"- rule: `{q.get('rule_id')}`",
                f"- verdict: `{q.get('verdict')}`",
                f"- quote_source: `{q.get('quote_source')}`",
                f"- explanation: {q.get('explanation')}",
                f"- quote: {q.get('quote')}",
                "",
                "Will: agree / disagree / cannot tell",
                "",
            ]
        )
    WILL_SAMPLE.write_text("\n".join(lines), encoding="utf-8")


def log_mlflow(rec: dict) -> None:
    try:
        import mlflow
        from mlflow.tracking import MlflowClient
    except ImportError:
        print("mlflow not installed; skipped live log", flush=True)
        return
    root = Path(__file__).resolve().parents[1]
    store = root / "mlruns"
    if not store.exists():
        print("no mlruns/; skipped live log", flush=True)
        return
    mlflow.set_tracking_uri(f"file:{store.as_posix()}")
    mlflow.set_experiment("trec_reader")
    aurocs = rec.get("auroc_1v2") or {}
    hard = (aurocs.get("any_hard_fail") or {})
    net = (aurocs.get("net_balance") or {})
    fab = rec.get("fabrication_offered") or {}
    with mlflow.start_run(run_name="reader_2022_top25"):
        mlflow.set_tags(
            {
                "retrofitted": "false",
                "live_from": "reader",
                "threshold_commit": THRESHOLD_COMMIT,
            }
        )
        mlflow.log_params(
            {
                "model": "Qwen/Qwen2.5-7B-Instruct",
                "year": "2022",
                "cutoff": "25",
                "n_patients": "50",
                "n_pairs": str(rec.get("n_pairs")),
                "aggregation": "any_hard_fail_and_net_balance",
            }
        )
        def put(name: str, value: object) -> None:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                mlflow.log_metric(name, float(value))

        put("valid_rate", rec.get("valid_rate"))
        put("generations_per_trial", rec.get("generations_per_trial"))
        put("usd", rec.get("usd"))
        put("hours", rec.get("hours"))
        put("coerced_rules", rec.get("coerced_rules"))
        put("auroc_any_hard_fail", hard.get("pooled"))
        put("auroc_any_hard_fail_lo", hard.get("lo"))
        put("auroc_any_hard_fail_hi", hard.get("hi"))
        put("auroc_net_balance", net.get("pooled"))
        put("auroc_net_balance_lo", net.get("lo"))
        put("auroc_net_balance_hi", net.get("hi"))
        put("offered_quotes", fab.get("n"))
        put("fabrication_d_plus_e", fab.get("d_plus_e_rate"))
        put("adapter_1v2_mean", 0.779)
        MlflowClient().set_terminated(mlflow.active_run().info.run_id)


def main() -> None:
    if not READS.exists():
        raise SystemExit(f"missing {READS}")
    rows = load_reads(READS)
    n = len(rows)
    schema_ok = sum(1 for r in rows if r.get("schema_ok"))
    gens = sum(int(r.get("retries") or 0) + 1 for r in rows)
    coerced = sum(len(r.get("coerced_rule_ids") or []) for r in rows)
    n_rules = sum(len(r.get("rules") or []) for r in rows)
    labels = Counter(r.get("label") for r in rows)
    hard_pred = Counter((r.get("aggregates") or {}).get("any_hard_fail") for r in rows)
    net_pred = Counter((r.get("aggregates") or {}).get("net_balance") for r in rows)
    quotes = offered_quotes(rows)
    buckets = Counter(q.get("quote_bucket") for q in quotes)
    d_e = buckets.get("D", 0) + buckets.get("E", 0)
    flagged = sum(1 for q in quotes if q.get("quote_flagged") or q.get("quote_bucket") != "ok")
    cost = {}
    cost_path = READS.parent / "trec_reader_full_cost.json"
    if cost_path.exists():
        cost = json.loads(cost_path.read_text(encoding="utf-8"))

    def pack_auroc(score_key: str) -> dict:
        groups: dict[str, list[dict]] = {}
        for r in rows:
            lab = r.get("label")
            if lab not in (1, 2):
                continue
            rec = {
                "label": lab,
                "any_hard_fail": (r.get("aggregates") or {}).get("score_any_hard_fail"),
                "net_balance": (r.get("aggregates") or {}).get("score_net"),
            }
            groups.setdefault(str(r.get("patient_id")), []).append(rec)
        usable = [t for t, g in groups.items() if any(x["label"] == 2 for x in g) and any(x["label"] == 1 for x in g)]
        pos = [x[score_key] for g in groups.values() for x in g if x["label"] == 2 and x.get(score_key) is not None]
        neg = [x[score_key] for g in groups.values() for x in g if x["label"] == 1 and x.get(score_key) is not None]
        pooled = auroc(pos, neg)
        tids = sorted(groups, key=lambda x: int(x))
        boot = boot_pooled(tids, groups, score_key, random.Random(BOOT_SEED))
        return {
            "n1": len(neg),
            "n2": len(pos),
            "n_patients": len(tids),
            "n_patients_both": len(usable),
            "pooled": None if pooled is None else round(pooled, 4),
            "lo": round(percentile(boot, 0.025), 4) if boot else None,
            "hi": round(percentile(boot, 0.975), 4) if boot else None,
        }

    rec = {
        "n_pairs": n,
        "schema_ok": schema_ok,
        "valid_rate": round(schema_ok / n, 4) if n else None,
        "generations": gens,
        "generations_per_trial": round(gens / n, 3) if n else None,
        "n_rules": n_rules,
        "coerced_rules": coerced,
        "labels": {str(k): v for k, v in labels.items()},
        "pred_any_hard_fail": dict(hard_pred),
        "pred_net_balance": dict(net_pred),
        "cross_any_hard_fail": cross(rows, "any_hard_fail"),
        "cross_net_balance": cross(rows, "net_balance"),
        "auroc_1v2": {
            "any_hard_fail": pack_auroc("any_hard_fail"),
            "net_balance": pack_auroc("net_balance"),
            "adapter_mean_reference": 0.779,
        },
        "fabrication_offered": {
            "n": len(quotes),
            "buckets": dict(buckets),
            "flagged": flagged,
            "flag_rate": round(flagged / len(quotes), 4) if quotes else None,
            "d_plus_e": d_e,
            "d_plus_e_rate": round(d_e / len(quotes), 4) if quotes else None,
            "d_plus_e_wilson": wilson(d_e, len(quotes)) if quotes else None,
            "reference_5pct": FABRICATION_REFERENCE,
            "earlier_1_3pct": 0.013,
        },
        "usd": cost.get("usd"),
        "hours": cost.get("hours"),
        "type": cost.get("type"),
        "no_overall_accuracy": True,
        "threshold_commit": THRESHOLD_COMMIT,
    }
    RESULTS.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    write_will_sample(quotes, titles())
    log_mlflow(rec)
    print(json.dumps(rec, indent=2), flush=True)
    print(f"wrote {RESULTS}", flush=True)
    print(f"wrote {WILL_SAMPLE}", flush=True)


if __name__ == "__main__":
    main()
