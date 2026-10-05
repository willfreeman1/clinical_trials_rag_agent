"""Finish the ranker analysis from stored scores. No GPU.

Paired patient-resampled intervals, equivalent depth, cascade
cutoff sweep, and TREC-official metrics. 2023 is not used.
The system does not say a patient qualifies.
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_lora_common import (  # noqa: E402
    RANK_CONFIG,
    RANK_SCORES,
    SEED_RUNS,
    adapter_scores_for,
)
from trec_lora_eval import load, score_of  # noqa: E402
from trec_score_common import (  # noqa: E402
    CE_SCORES,
    DATA,
    MINI_SCORES,
    QWEN_SCORES,
    SAMPLE_TOPICS,
    load_qrels,
    load_shortlist,
    mean,
)
from trec_score_eval import mini_map, order_by, qwen_maps, topic_metrics  # noqa: E402

BOOT_SEED = 20261009
N_BOOT = 5000
CUTOFFS = (25, 50, 100, 200, 300, 500)
ED_NS = (20, 200, 500)
RANK_HOURS = 3.71
RANK_USD = 6.65
RANK_PAIRS_N = 79750
OUT = DATA / "trec_lora_rank_finish.json"


def percentile(xs: list[float], q: float) -> float:
    ys = sorted(xs)
    if not ys:
        raise SystemExit("empty bootstrap")
    i = min(len(ys) - 1, max(0, int(q * (len(ys) - 1))))
    return ys[i]


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


def boot_paired_diff(a: list[float], b: list[float], rng: random.Random) -> dict:
    if len(a) != len(b):
        raise SystemExit("paired lists differ")
    n = len(a)
    deltas = [a[i] - b[i] for i in range(n)]
    draws = []
    for _ in range(N_BOOT):
        idx = [rng.randrange(n) for _ in range(n)]
        draws.append(sum(deltas[i] for i in idx) / n)
    point = sum(deltas) / n
    lo = percentile(draws, 0.025)
    hi = percentile(draws, 0.975)
    return {
        "n_boot": N_BOOT,
        "seed": BOOT_SEED,
        "point": point,
        "lo": lo,
        "hi": hi,
        "zero_inside": lo <= 0.0 <= hi,
        "a_higher": sum(1 for i in range(n) if a[i] > b[i]),
        "b_higher": sum(1 for i in range(n) if b[i] > a[i]),
        "tie": sum(1 for i in range(n) if a[i] == b[i]),
        "n_patients": n,
    }


def graded(nct: str, labels: dict[str, int]) -> int:
    return int(labels.get(nct, 0))


def dcg10(order: list[str], labels: dict[str, int]) -> float:
    s = 0.0
    for i, nct in enumerate(order[:10], 1):
        s += graded(nct, labels) / math.log2(i + 1)
    return s


def idcg10(labels: dict[str, int]) -> float:
    gains = sorted((int(v) for v in labels.values()), reverse=True)[:10]
    s = 0.0
    for i, g in enumerate(gains, 1):
        s += g / math.log2(i + 1)
    return s


def binary_gain(nct: str, labels: dict[str, int]) -> int:
    return 1 if labels.get(nct) == 2 else 0


def dcg10_bin(order: list[str], labels: dict[str, int]) -> float:
    s = 0.0
    for i, nct in enumerate(order[:10], 1):
        s += binary_gain(nct, labels) / math.log2(i + 1)
    return s


def idcg10_bin(labels: dict[str, int]) -> float:
    n_elig = sum(1 for v in labels.values() if v == 2)
    s = 0.0
    for i in range(1, min(10, n_elig) + 1):
        s += 1.0 / math.log2(i + 1)
    return s


def official_row(order: list[str], labels: dict[str, int]) -> dict:
    ideal = idcg10(labels)
    ndcg = (dcg10(order, labels) / ideal) if ideal else 0.0
    ideal_b = idcg10_bin(labels)
    ndcg_b = (dcg10_bin(order, labels) / ideal_b) if ideal_b else 0.0
    p10 = sum(1 for nct in order[:10] if labels.get(nct) == 2) / 10.0
    r_count = sum(1 for v in labels.values() if v == 2)
    rprec = (
        sum(1 for nct in order[:r_count] if labels.get(nct) == 2) / r_count
        if r_count
        else None
    )
    mrr = 0.0
    for i, nct in enumerate(order, 1):
        if labels.get(nct) == 2:
            mrr = 1.0 / i
            break
    return {"ndcg@10": ndcg, "ndcg@10_bin": ndcg_b, "p@10": p10, "rprec": rprec, "mrr": mrr}


def summarize_official(rows: list[dict], rng: random.Random) -> dict:
    out = {"n": len(rows)}
    for key in ("ndcg@10", "ndcg@10_bin", "p@10", "rprec", "mrr"):
        vals = [r[key] for r in rows if r.get(key) is not None]
        boot = boot_mean(vals, rng)
        out[key] = {
            "mean": boot["point"],
            "mean_boot": boot["mean"],
            "lo": boot["lo"],
            "hi": boot["hi"],
            "median": boot["median"],
            "n": boot["n_patients"],
        }
    return out


def slice_year(qwen: dict, year: str) -> dict[str, dict[str, tuple[int, float]]]:
    return qwen_maps(qwen, "topical_title_cond_slice").get(year) or {}


def elig_full(path: Path) -> dict[str, dict[str, tuple[int, float]]]:
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
            dest[str(nct)] = (digit, float(sc))
        out[str(tid)] = dest
    return out


def cascade(base: list[str], topical: dict, elig: dict, n: int) -> list[str]:
    top_order = order_by(base, lambda nct, s=topical: float(s[nct][1]) if nct in s else -1.0)
    head, tail = top_order[:n], top_order[n:]
    head_re = order_by(head, lambda nct, s=elig: float(s[nct][1]) if nct in s else -1.0)
    return head_re + tail


def cutoff_cost(n: int) -> dict:
    pairs = 50 * n
    scale = pairs / RANK_PAIRS_N
    return {
        "cutoff": n,
        "pairs": pairs,
        "hours": round(RANK_HOURS * scale, 3),
        "usd": round(RANK_USD * scale, 2),
        "usd_per_patient": round(RANK_USD * scale / 50.0, 3),
    }


def main() -> None:
    cfg = json.loads(RANK_CONFIG.read_text(encoding="utf-8"))
    short = load_shortlist()
    qwen = load(QWEN_SCORES)
    mini = mini_map(load(MINI_SCORES))
    ce = load(CE_SCORES)
    ce_med = ((ce.get("truncate") or {}).get("medcpt_ce") or {})
    elig = elig_full(RANK_SCORES)
    sl = slice_year(qwen, "2022")
    want = list(cfg["patients"])
    labels_2022 = load_qrels(2022)
    topics_2022 = short["years"]["2022"]["topics"]
    ready = []
    for tid in want:
        base = (topics_2022.get(tid) or {}).get("shortlist") or []
        if len(base) < 10 or len(elig.get(tid) or {}) < len(base):
            continue
        ready.append(tid)
    if len(ready) != 50:
        raise SystemExit(f"expected 50 full adapter shortlists, got {len(ready)}")

    per: dict[str, list] = {}
    per_official: dict[str, list] = {}
    per_p10: dict[str, list[float]] = {}
    eq_rows: dict[str, list] = {}

    def add_arm(tag: str, tid: str, order: list[str], labels: dict, base: list[str]) -> None:
        tm = topic_metrics(order, labels, base)
        per.setdefault(tag, []).append(tm)
        eq_rows.setdefault(tag, []).append(tm)
        off = official_row(order, labels)
        per_official.setdefault(tag, []).append(off)
        per_p10.setdefault(tag, []).append(off["p@10"])

    for tid in ready:
        base = topics_2022[tid]["shortlist"]
        labels = labels_2022.get(tid) or {}
        tsc = sl.get(tid) or {}
        esc = elig[tid]
        orders = {
            "baseline_fused": base,
            "topical_slice_cont": order_by(base, lambda n, s=tsc: float(s[n][1]) if n in s else -1.0),
            "topical_slice_digit": order_by(base, lambda n, s=tsc: float(s[n][0]) if n in s else -1.0),
            "elig_lora_cont": order_by(base, lambda n, s=esc: float(s[n][1]) if n in s else -1.0),
            "elig_lora_digit": order_by(base, lambda n, s=esc: float(s[n][0]) if n in s else -1.0),
        }
        for n in CUTOFFS:
            orders[f"cascade_top{n}"] = cascade(base, tsc, esc, n)
        for tag, order in orders.items():
            add_arm(tag, tid, order, labels, base)

    rng = random.Random(BOOT_SEED)
    paired = {
        "adapter_minus_topical_p10": boot_paired_diff(
            per_p10["elig_lora_cont"], per_p10["topical_slice_cont"], rng
        ),
    }
    for n in CUTOFFS:
        paired[f"cascade{n}_minus_topical_p10"] = boot_paired_diff(
            per_p10[f"cascade_top{n}"], per_p10["topical_slice_cont"], rng
        )
    rng_n = random.Random(BOOT_SEED)
    paired["adapter_minus_topical_ndcg"] = boot_paired_diff(
        [r["ndcg@10"] for r in per_official["elig_lora_cont"]],
        [r["ndcg@10"] for r in per_official["topical_slice_cont"]],
        rng_n,
    )
    for n in (25, 100):
        paired[f"cascade{n}_minus_topical_ndcg"] = boot_paired_diff(
            [r["ndcg@10"] for r in per_official[f"cascade_top{n}"]],
            [r["ndcg@10"] for r in per_official["topical_slice_cont"]],
            rng_n,
        )
    paired["adapter_minus_topical_ndcg_bin"] = boot_paired_diff(
        [r["ndcg@10_bin"] for r in per_official["elig_lora_cont"]],
        [r["ndcg@10_bin"] for r in per_official["topical_slice_cont"]],
        rng_n,
    )
    for n in (25, 100):
        paired[f"cascade{n}_minus_topical_ndcg_bin"] = boot_paired_diff(
            [r["ndcg@10_bin"] for r in per_official[f"cascade_top{n}"]],
            [r["ndcg@10_bin"] for r in per_official["topical_slice_cont"]],
            rng_n,
        )
    unjudged_top10 = {}
    for tag in ("baseline_fused", "topical_slice_cont", "cascade_top25", "cascade_top100"):
        xs = []
        for tid in ready:
            base = topics_2022[tid]["shortlist"]
            labels = labels_2022.get(tid) or {}
            tsc = sl.get(tid) or {}
            if tag == "baseline_fused":
                order = base
            elif tag == "topical_slice_cont":
                order = order_by(base, lambda n, s=tsc: float(s[n][1]) if n in s else -1.0)
            elif tag == "cascade_top25":
                order = cascade(base, tsc, elig[tid], 25)
            else:
                order = cascade(base, tsc, elig[tid], 100)
            xs.append(sum(1 for nct in order[:10] if nct not in labels))
        unjudged_top10[tag] = {
            "mean": sum(xs) / len(xs),
            "patients_with_any": sum(1 for x in xs if x),
            "total_slots": sum(xs),
            "n": len(xs),
        }

    def ed_from_rows(rows: list[dict]) -> dict:
        out = {}
        for d in ED_NS:
            out[f"eq_mult@{d}"] = mean([r["eq_mult"].get(d) for r in rows if r["eq_mult"].get(d) is not None])
            out[f"eq@{d}"] = mean([r["eq"].get(d) for r in rows if r["eq"].get(d) is not None])
            out[f"precision@{d}"] = mean([r["precision"].get(d) for r in rows if d in r["precision"]])
        out["precision@10"] = mean([r["precision"].get(10) for r in rows if 10 in r["precision"]])
        out["ten_in_20"] = sum(1 for r in rows if r["ten_in_20"])
        out["n"] = len(rows)
        return out

    def ed_summary(tag: str) -> dict:
        return ed_from_rows(eq_rows[tag])

    sweep = []
    for n in CUTOFFS:
        rec = ed_summary(f"cascade_top{n}")
        rec.update(cutoff_cost(n))
        sweep.append(rec)

    # Official metrics for every full-shortlist arm we have.
    official = {"2022": {}, "2021": {}}
    rng_o = random.Random(BOOT_SEED)
    for tag in (
        "baseline_fused",
        "topical_slice_digit",
        "topical_slice_cont",
        "elig_lora_cont",
        "elig_lora_digit",
        "cascade_top25",
        "cascade_top100",
    ):
        official["2022"][tag] = summarize_official(per_official[tag], rng_o)

    # Both-year arms from stored full-shortlist scores.
    qwen_title = qwen_maps(qwen, "topical_title_cond")
    qwen_slice = qwen_maps(qwen, "topical_title_cond_slice")
    qwen_elig = qwen_maps(qwen, "elig_full")
    both_year_rows: dict[str, dict[str, list]] = {"2021": {}, "2022": {}}
    both_year_eq: dict[str, dict[str, list]] = {"2021": {}, "2022": {}}
    for year in (2021, 2022):
        y = str(year)
        labels_all = load_qrels(year)
        topics = short["years"][y]["topics"]
        for tid, trow in topics.items():
            base = trow["shortlist"]
            labels = labels_all.get(tid) or {}
            if not any(v == 2 for v in labels.values()):
                continue
            cands = {"baseline_fused": base}
            mini_topic = (mini.get(y) or {}).get(tid) or {}
            if len(mini_topic) >= 10:
                cands["mini_full"] = order_by(base, lambda n, m=mini_topic: float(m.get(n, -1)))
            tsc = (qwen_slice.get(y) or {}).get(tid) or {}
            if len(tsc) >= 10:
                cands["topical_slice_digit"] = order_by(base, lambda n, s=tsc: float(s[n][0]) if n in s else -1.0)
                cands["topical_slice_cont"] = order_by(base, lambda n, s=tsc: float(s[n][1]) if n in s else -1.0)
            ttc = (qwen_title.get(y) or {}).get(tid) or {}
            if len(ttc) >= 10:
                cands["topical_title_cond_digit"] = order_by(base, lambda n, s=ttc: float(s[n][0]) if n in s else -1.0)
                cands["topical_title_cond_cont"] = order_by(base, lambda n, s=ttc: float(s[n][1]) if n in s else -1.0)
            esc = (qwen_elig.get(y) or {}).get(tid) or {}
            if len(esc) >= 10:
                cands["untrained_elig_cont"] = order_by(base, lambda n, s=esc: float(s[n][1]) if n in s else -1.0)
                cands["untrained_elig_digit"] = order_by(base, lambda n, s=esc: float(s[n][0]) if n in s else -1.0)
            for qn in ("raw", "keywords"):
                sc = ((ce_med.get(qn) or {}).get(y) or {}).get(tid)
                if sc:
                    cands[f"medcpt_ce_{qn}"] = order_by(base, lambda n, s=sc: float(s.get(n, -1e9)))
            if y == "2022" and tid in elig and len(elig[tid]) >= len(base):
                cands["elig_lora_cont"] = order_by(
                    base, lambda n, s=elig[tid]: float(s[n][1]) if n in s else -1.0
                )
                cands["cascade_top25"] = cascade(base, tsc, elig[tid], 25)
                cands["cascade_top100"] = cascade(base, tsc, elig[tid], 100)
            for tag, order in cands.items():
                both_year_rows[y].setdefault(tag, []).append(official_row(order, labels))
                both_year_eq[y].setdefault(tag, []).append(topic_metrics(order, labels, base))

    for year in ("2021", "2022"):
        for tag, rows in both_year_rows[year].items():
            official[year][tag] = summarize_official(rows, random.Random(BOOT_SEED))

    seed_note = []
    for seed in SEED_RUNS:
        path = adapter_scores_for(seed)
        if not path.exists():
            seed_note.append({"seed": seed, "path": str(path), "full_shortlist": False, "reason": "missing"})
            continue
        raw = load(path)
        block = ((raw.get("scores") or {}).get("2022") or {})
        ns = [len(v) for v in block.values() if isinstance(v, dict)]
        mean_n = (sum(ns) / len(ns)) if ns else 0
        seed_note.append(
            {
                "seed": seed,
                "patients": len(block),
                "mean_pairs": mean_n,
                "full_shortlist": mean_n >= 1500,
                "reason": (
                    "full 2022 shortlist is score_qwen_elig_lora_rank.json for seed 20261007 only"
                    if mean_n < 1500
                    else "full shortlist"
                ),
            }
        )

    sample_ids = set(SAMPLE_TOPICS["2022"])
    sample15_rows: dict[str, list] = {}
    qwen_elig_2022 = qwen_elig.get("2022") or {}
    for tid in ready:
        if tid not in sample_ids:
            continue
        base = topics_2022[tid]["shortlist"]
        labels = labels_2022.get(tid) or {}
        tsc = sl.get(tid) or {}
        esc = elig[tid]
        usc = qwen_elig_2022.get(tid) or {}
        orders15 = {
            "baseline_fused": base,
            "topical_slice_cont": order_by(base, lambda n, s=tsc: float(s[n][1]) if n in s else -1.0),
            "elig_lora_cont": order_by(base, lambda n, s=esc: float(s[n][1]) if n in s else -1.0),
            "cascade_top25": cascade(base, tsc, esc, 25),
            "cascade_top100": cascade(base, tsc, esc, 100),
        }
        if len(usc) >= 10:
            orders15["untrained_elig_cont"] = order_by(
                base, lambda n, s=usc: float(s[n][1]) if n in s else -1.0
            )
        for tag, order in orders15.items():
            sample15_rows.setdefault(tag, []).append(topic_metrics(order, labels, base))
    sample15 = {tag: ed_from_rows(rows) for tag, rows in sample15_rows.items()}

    eq_table = {tag: ed_summary(tag) for tag in eq_rows}
    eq_both = {
        year: {tag: ed_from_rows(rows) for tag, rows in both_year_eq[year].items()}
        for year in ("2021", "2022")
    }
    rec = {
        "note": (
            "No GPU. TREC-official: NDCG@10 graded 2/1/0; P@10, RPrec and MRR "
            "binary (eligible only). Unjudged is 0. Patients resampled, not pairs. "
            "The system does not say a patient qualifies."
        ),
        "boot_seed": BOOT_SEED,
        "n_boot": N_BOOT,
        "n_2022": 50,
        "paired": paired,
        "unjudged_in_top10_this_topic": unjudged_top10,
        "equivalent_depth": eq_table,
        "equivalent_depth_both_years": eq_both,
        "cascade_sweep": sweep,
        "cutoff_rate": {
            "hours": RANK_HOURS,
            "usd": RANK_USD,
            "pairs": RANK_PAIRS_N,
            "usd_per_pair": RANK_USD / RANK_PAIRS_N,
        },
        "official": official,
        "official_rules": {
            "ndcg@10": "graded: eligible=2, excluded=1, not relevant/unjudged=0; IDCG from all qrels for the topic",
            "ndcg@10_bin": "binary NDCG@10: eligible=1, excluded and not relevant/unjudged=0; IDCG from eligible qrels only",
            "p@10": "binary: eligible is relevant; excluded merged with not relevant",
            "rprec": "binary: precision at R, R = number of eligible qrels for the topic",
            "mrr": "binary: 1 / rank of first eligible; 0 if none",
        },
        "seeds_cannot_rank": seed_note,
        "headline_arm_both_years": "topical_slice_cont",
        "headline_why": (
            "Only arm that is a current default-path score, exists on all 75+50 "
            "patients, and is not a different model per year."
        ),
        "sample15_2022": sample15,
        "sample15_note": (
            "Same 15 2022 patients as the untrained elig_full sample in Run 2. "
            "Use this row to compare untrained 1.86× at depth 200 with fine-tuned arms."
        ),
    }
    OUT.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    print(f"wrote {OUT}", flush=True)
    print("paired cascade-topical P@10", paired["cascade100_minus_topical_p10"], flush=True)
    print("paired adapter-topical P@10", paired["adapter_minus_topical_p10"], flush=True)
    print("paired adapter-topical NDCG", paired["adapter_minus_topical_ndcg"], flush=True)
    print("paired adapter-topical NDCGbin", paired["adapter_minus_topical_ndcg_bin"], flush=True)
    print("paired cascade25-topical NDCGbin", paired["cascade25_minus_topical_ndcg_bin"], flush=True)
    for row in sweep:
        print(
            f"  cut {row['cutoff']}: P@10 {row['precision@10']:.3f} P@20 {row.get('precision@20'):.3f} "
            f"ED@20 {row['eq_mult@20']:.2f} ED@200 {row['eq_mult@200']:.2f} "
            f"${row['usd']} {row['hours']}h",
            flush=True,
        )
    for year in ("2021", "2022"):
        print(f"official {year}", flush=True)
        for tag, rec_o in official[year].items():
            p = rec_o["p@10"]
            n = rec_o["ndcg@10"]
            nb = rec_o["ndcg@10_bin"]
            print(
                f"  {tag}: n={rec_o['n']} NDCG {n['mean']:.4f} [{n['lo']:.4f},{n['hi']:.4f}] "
                f"NDCGb {nb['mean']:.4f} [{nb['lo']:.4f},{nb['hi']:.4f}] "
                f"P@10 {p['mean']:.4f} [{p['lo']:.4f},{p['hi']:.4f}] medP {p['median']:.4f} "
                f"RPrec {rec_o['rprec']['mean']:.4f} MRR {rec_o['mrr']['mean']:.4f}",
                flush=True,
            )


if __name__ == "__main__":
    main()
