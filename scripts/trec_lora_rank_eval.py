"""Compare adapter eligibility vs topical slice on the 2022 shortlist.

Equivalent depth is a multiple of the baseline's own equivalent
depth at the same N. Patients are resampled, not pairs.
2023 is not used. The system does not say a patient qualifies.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_lora_common import RANK_CONFIG, RANK_RESULTS, RANK_SCORES, pct  # noqa: E402
from trec_lora_eval import load, score_of  # noqa: E402
from trec_score_common import DEPTHS, QWEN_SCORES, load_qrels, load_shortlist, mean  # noqa: E402
from trec_score_eval import order_by, topic_metrics  # noqa: E402

BOOT_SEED = 20261008
N_BOOT = 5000
ED_NS = (20, 200, 500)


def slice_map() -> dict[str, dict[str, tuple[int, float]]]:
    qwen = load(QWEN_SCORES)
    block = ((qwen.get("arms") or {}).get("topical_title_cond_slice") or {}).get("2022") or {}
    out = {}
    for tid, scores in block.items():
        dest = {}
        for nct, rec in scores.items():
            if isinstance(rec, list) and len(rec) >= 2:
                dest[nct] = (int(rec[0]), float(rec[1]))
        out[str(tid)] = dest
    return out


def elig_map(path: Path) -> dict[str, dict[str, tuple[int, float]]]:
    raw = load(path)
    block = ((raw.get("scores") or {}).get("2022") or {})
    out = {}
    for tid, scores in block.items():
        dest = {}
        for nct, rec in scores.items():
            sc = score_of(rec)
            if sc is None:
                continue
            digit = int(rec[0]) if isinstance(rec, list) and rec else 0
            dest[nct] = (digit, float(sc))
        out[str(tid)] = dest
    return out


def cascade(base: list[str], topical: dict, elig: dict, n: int) -> list[str]:
    top_order = order_by(base, lambda nct, s=topical: float(s[nct][1]) if nct in s else -1.0)
    head, tail = top_order[:n], top_order[n:]
    head_re = order_by(head, lambda nct, s=elig: float(s[nct][1]) if nct in s else -1.0)
    return head_re + tail


def summarize(rows: list[dict], full_n: int) -> dict:
    if not rows:
        return {}
    out = {"n": len(rows)}
    for d in DEPTHS + (full_n,):
        out[f"recall@{d}"] = mean([r["recall"].get(d) for r in rows if r["recall"].get(d) is not None])
        out[f"precision@{d}"] = mean([r["precision"].get(d) for r in rows if d in r["precision"]])
        out[f"eq@{d}"] = mean([r["eq"].get(d) for r in rows if r["eq"].get(d) is not None])
        out[f"eq_mult@{d}"] = mean([r["eq_mult"].get(d) for r in rows if r["eq_mult"].get(d) is not None])
    out["ten_in_20"] = sum(1 for r in rows if r["ten_in_20"])
    out["full_recall"] = mean([r["full_recall"] for r in rows if r["full_recall"] is not None])
    return out


def percentile(xs: list[float], q: float) -> float:
    ys = sorted(xs)
    i = min(len(ys) - 1, max(0, int(q * (len(ys) - 1))))
    return ys[i]


def boot_mean(rows: list[dict], key: str, rng: random.Random) -> dict:
    vals = []
    n = len(rows)
    for _ in range(N_BOOT):
        draw = [rows[rng.randrange(n)] for _ in range(n)]
        xs = [r["precision"][key] for r in draw if key in r["precision"]]
        if xs:
            vals.append(sum(xs) / len(xs))
    return {
        "n": len(vals),
        "mean": sum(vals) / len(vals),
        "lo": percentile(vals, 0.025),
        "hi": percentile(vals, 0.975),
    }


def main() -> None:
    cfg = json.loads(RANK_CONFIG.read_text(encoding="utf-8"))
    if not RANK_SCORES.exists():
        raise SystemExit(f"missing {RANK_SCORES}")
    short = load_shortlist()
    labels_all = load_qrels(2022)
    topics = short["years"]["2022"]["topics"]
    sl = slice_map()
    elig = elig_map(RANK_SCORES)
    want = set(cfg["patients"])
    ready = []
    for tid in cfg["patients"]:
        base = (topics.get(tid) or {}).get("shortlist") or []
        esc = elig.get(tid) or {}
        if len(base) < 10 or len(esc) < len(base):
            continue
        ready.append(tid)
    if not ready:
        raise SystemExit("no patient has a full adapter shortlist yet")
    cutoffs = list(cfg["cascade_cutoffs"])
    arm_rows: dict[str, list] = {}
    for tid in ready:
        base = topics[tid]["shortlist"]
        labels = labels_all.get(tid) or {}
        tsc = sl.get(tid) or {}
        esc = elig[tid]
        orders = {
            "baseline_fused": base,
            "topical_slice_cont": order_by(base, lambda n, s=tsc: float(s[n][1]) if n in s else -1.0),
            "elig_lora_cont": order_by(base, lambda n, s=esc: float(s[n][1]) if n in s else -1.0),
            "elig_lora_digit": order_by(base, lambda n, s=esc: float(s[n][0]) if n in s else -1.0),
        }
        for n in cutoffs:
            orders[f"cascade_top{n}"] = cascade(base, tsc, esc, n)
        for tag, order in orders.items():
            arm_rows.setdefault(tag, []).append(topic_metrics(order, labels, base))
    full_n = int(cfg["shortlist_depth"])
    arms = {tag: summarize(rows, full_n) for tag, rows in arm_rows.items()}
    rng = random.Random(BOOT_SEED)
    ci = {}
    for tag in ("topical_slice_cont", "elig_lora_cont"):
        if tag in arm_rows:
            ci[tag] = {
                "p10": boot_mean(arm_rows[tag], 10, rng),
                "p20": boot_mean(arm_rows[tag], 20, rng),
            }
    report = {
        "note": cfg["note"],
        "adapter_seed": cfg["adapter_seed"],
        "adapter_why": cfg["adapter_why"],
        "n_patients_ready": len(ready),
        "patients_ready": ready,
        "patients_planned": cfg["patients"],
        "n_planned": len(want),
        "arms": arms,
        "precision_ci": ci,
        "eq_note": (
            "Equivalent depth is a multiple of the baseline's own equivalent "
            "depth at the same N. The baseline row is calibration."
        ),
    }
    RANK_RESULTS.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"patients ready {len(ready)}/{len(want)}", flush=True)
    for tag in (
        "baseline_fused",
        "topical_slice_cont",
        "elig_lora_cont",
        "elig_lora_digit",
        *[f"cascade_top{n}" for n in cutoffs],
    ):
        rec = arms.get(tag) or {}
        print(
            f"  {tag}: P@10 {pct(rec.get('precision@10'))}  P@20 {pct(rec.get('precision@20'))}  "
            f"ED@20 {rec.get('eq_mult@20')}  ED@200 {rec.get('eq_mult@200')}  "
            f"10-in-20 {rec.get('ten_in_20')}/{rec.get('n')}  "
            f"full-recall {pct(rec.get('full_recall'))}",
            flush=True,
        )
    print(f"wrote {RANK_RESULTS}", flush=True)


if __name__ == "__main__":
    main()
