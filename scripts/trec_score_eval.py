"""Evaluate topical vs eligibility scoring. Gates committed in 114cce7.

Equivalent depth uses the baseline's own equivalent depth as calibration.
Continuous score is not credited for a depth-200/500 win.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_score_common import (  # noqa: E402
    CE_SCORES,
    DEPTHS,
    FULL_DEPTH,
    MINI_SCORES,
    OLD_MINI,
    QWEN_SCORES,
    REPORT,
    RESULTS,
    RETRIEVAL_ELIGIBLE,
    SAMPLE_TOPICS,
    THRESHOLDS_COMMIT,
    YEARS,
    curve,
    depth_for,
    load_qrels,
    load_shortlist,
    mean,
)

PAGE_N = 20
READER_N = 200


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def qwen_maps(raw: dict, arm: str) -> dict[str, dict[str, dict[str, tuple[int, float]]]]:
    block = (raw.get("arms") or {}).get(arm) or {}
    out: dict[str, dict[str, dict[str, tuple[int, float]]]] = {}
    for year, topics in block.items():
        yout = out.setdefault(str(year), {})
        for tid, scores in topics.items():
            dest = {}
            for nct, rec in scores.items():
                if isinstance(rec, list) and len(rec) >= 2:
                    dest[nct] = (int(rec[0]), float(rec[1]))
                elif isinstance(rec, dict):
                    dest[nct] = (int(rec.get("d") or rec.get("digit") or 0), float(rec.get("c") or rec.get("cont") or 0))
            yout[str(tid)] = dest
    return out


def mini_map(raw: dict) -> dict[str, dict[str, dict[str, int]]]:
    scores = raw.get("scores") or {}
    # New file is years -> topics. Old file is topics only (2021).
    if scores and any(k in ("2021", "2022") for k in scores):
        return {y: {str(t): {n: int(v) for n, v in bucket.items()} for t, bucket in year.items()} for y, year in scores.items()}
    return {"2021": {str(t): {n: int(v) for n, v in bucket.items()} for t, bucket in scores.items()}}


def order_by(
    shortlist: list[str],
    key_fn,
) -> list[str]:
    rank = {nct: i for i, nct in enumerate(shortlist)}

    def sort_key(nct: str):
        score = key_fn(nct)
        return (-score, rank[nct])

    return sorted(shortlist, key=sort_key)


def topic_metrics(order: list[str], labels: dict[str, int], baseline: list[str]) -> dict:
    eligible = {n for n, r in labels.items() if r == 2}
    n_eligible = len(eligible)
    bc = curve(baseline, labels)
    cc = curve(order, labels)
    rec = {}
    prec = {}
    eq = {}
    eq_mult = {}
    hits = {}
    for d in DEPTHS + (len(baseline),):
        depth = min(d, len(order), len(cc) - 1)
        got = cc[depth]
        hits[d] = got
        rec[d] = got / n_eligible if n_eligible else None
        prec[d] = got / depth if depth else 0.0
        target = got
        arm_eq = depth_for(bc, target)
        base_hits = bc[min(depth, len(bc) - 1)]
        base_eq = depth_for(bc, base_hits)
        eq[d] = arm_eq
        eq_mult[d] = (arm_eq / base_eq) if base_eq else None
    ten_in_20 = hits.get(20, 0) >= 10
    return {
        "n_eligible": n_eligible,
        "recall": rec,
        "precision": prec,
        "hits": hits,
        "eq": eq,
        "eq_mult": eq_mult,
        "ten_in_20": ten_in_20,
        "full_recall": rec.get(len(baseline)),
    }


def summarize(rows: list[dict], full_depth: int) -> dict:
    if not rows:
        return {}
    out = {"n": len(rows)}
    for d in DEPTHS + (full_depth,):
        recs = [r["recall"].get(d) for r in rows if r["recall"].get(d) is not None]
        precs = [r["precision"].get(d) for r in rows if d in r["precision"]]
        eqs = [r["eq"].get(d) for r in rows if r["eq"].get(d) is not None]
        mults = [r["eq_mult"].get(d) for r in rows if r["eq_mult"].get(d) is not None]
        hits = [r["hits"].get(d) for r in rows if r["hits"].get(d) is not None]
        out[f"recall@{d}"] = mean(recs)
        out[f"precision@{d}"] = mean(precs)
        out[f"hits@{d}"] = mean(hits)
        out[f"eq@{d}"] = mean(eqs)
        out[f"eq_mult@{d}"] = mean(mults)
    out["ten_in_20"] = sum(1 for r in rows if r["ten_in_20"])
    out["full_recall"] = mean([r["full_recall"] for r in rows if r["full_recall"] is not None])
    return out


def pct(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{100 * x:.1f}%"


def num(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "—"
    return f"{x:.{digits}f}"


def main() -> None:
    short = load_shortlist()
    qwen_raw = load_json(QWEN_SCORES)
    mini_raw = load_json(MINI_SCORES)
    if not mini_raw and OLD_MINI.exists():
        mini_raw = load_json(OLD_MINI)
    ce_raw = load_json(CE_SCORES)
    mini_scores = mini_map(mini_raw)
    qwen_arms = {
        "qwen_topical_title_cond": qwen_maps(qwen_raw, "topical_title_cond"),
        "qwen_topical_slice": qwen_maps(qwen_raw, "topical_title_cond_slice"),
        "qwen_elig_full": qwen_maps(qwen_raw, "elig_full"),
    }
    ce_med = ((ce_raw.get("truncate") or {}).get("medcpt_ce") or {})
    results = {
        "thresholds_commit": THRESHOLDS_COMMIT,
        "qwen_seconds": qwen_raw.get("seconds") or {},
        "qwen_notes": qwen_raw.get("notes") or [],
        "qwen_gpu": qwen_raw.get("gpu"),
        "qwen_elapsed_sec": qwen_raw.get("elapsed_sec"),
        "sample_elig": qwen_raw.get("sample_elig"),
        "mini_usd": mini_raw.get("usd"),
        "mini_seconds": mini_raw.get("seconds"),
        "years": {},
        "sample": {},
    }

    for year in YEARS:
        y = str(year)
        labels_all = load_qrels(year)
        topics = short["years"][y]["topics"]
        sample_ids = set(SAMPLE_TOPICS[y])
        year_rows: dict[str, list] = {}
        sample_rows: dict[str, list] = {}
        for tid, trow in topics.items():
            base = trow["shortlist"]
            labels = labels_all.get(tid) or {}
            if not any(v == 2 for v in labels.values()):
                continue
            cands: dict[str, list[str]] = {"baseline": base}

            mini_topic = (mini_scores.get(y) or {}).get(tid) or {}
            if mini_topic:
                cands["mini_full"] = order_by(base, lambda n, m=mini_topic: float(m.get(n, -1)))

            for tag, mapped in qwen_arms.items():
                topic_sc = (mapped.get(y) or {}).get(tid) or {}
                if len(topic_sc) < 10:
                    continue
                cands[f"{tag}_digit"] = order_by(base, lambda n, s=topic_sc: float(s[n][0]) if n in s else -1.0)
                cands[f"{tag}_cont"] = order_by(base, lambda n, s=topic_sc: float(s[n][1]) if n in s else -1.0)

            for qn in ("raw", "keywords"):
                sc = ((ce_med.get(qn) or {}).get(y) or {}).get(tid)
                if sc:
                    cands[f"medcpt_ce_{qn}"] = order_by(base, lambda n, s=sc: float(s.get(n, -1e9)))

            for tag, order in cands.items():
                row = topic_metrics(order, labels, base)
                if not tag.startswith("qwen_elig"):
                    year_rows.setdefault(tag, []).append(row)
                if tid in sample_ids:
                    sample_rows.setdefault(tag, []).append(row)

        results["years"][y] = {
            tag: summarize(rows, FULL_DEPTH[year]) for tag, rows in year_rows.items()
        }
        results["sample"][y] = {
            tag: summarize(rows, FULL_DEPTH[year]) for tag, rows in sample_rows.items()
        }

    RESULTS.write_text(json.dumps(results, indent=2), encoding="utf-8")
    REPORT.write_text(render(results), encoding="utf-8")
    print(f"wrote {RESULTS} {REPORT}", flush=True)


def _tables(year: int, n: int, year_out: dict, depths_show: tuple, full_bar: float) -> list[str]:
    lines = [
        f"### {year} (n={n})",
        "",
        "#### Eligible recall (label 2)",
        "",
        "| Arm | " + " | ".join(f"@{d}" for d in depths_show) + " | P@10 | P@20 | 10-in-20 |",
        "|" + "---|" * (len(depths_show) + 4),
    ]
    for tag in sorted(year_out, key=_arm_sort):
        rec = year_out[tag]
        cells = [pct(rec.get(f"recall@{d}")) for d in depths_show]
        lines.append(
            f"| `{tag}` | "
            + " | ".join(cells)
            + f" | {pct(rec.get('precision@10'))} | {pct(rec.get('precision@20'))} "
            + f"| {rec.get('ten_in_20', 0)}/{rec.get('n', 0)} |"
        )
    lines.extend(
        [
            "",
            "#### Equivalent depth (multiple of baseline's own)",
            "",
            "| Arm | Read 20 | Read 200 | Read 500 |",
            "|---|---:|---:|---:|",
        ]
    )
    for tag in sorted(year_out, key=_arm_sort):
        rec = year_out[tag]
        cells = []
        for d in (20, 200, 500):
            mult = rec.get(f"eq_mult@{d}")
            raw = rec.get(f"eq@{d}")
            if mult is None:
                cells.append("—")
            else:
                cells.append(f"{mult:.2f}x ({raw:.0f})")
        lines.append(f"| `{tag}` | " + " | ".join(cells) + " |")
    full = year_out.get("baseline", {}).get("full_recall")
    lines.extend(
        [
            "",
            f"Full-shortlist eligible recall (must stay {100 * full_bar:.1f}%): {pct(full)}.",
            "",
        ]
    )
    return lines


def render(results: dict) -> str:
    lines = [
        "# Does a reordering stage earn its place? (2021/2022 only)",
        "",
        f"Gates committed in `{THRESHOLDS_COMMIT}` before any 0–3 score.",
        "2023 was not touched. The shortlist was not cut. Nothing discarded.",
        "Equivalent depth is a multiple of the **baseline's own equivalent depth**",
        "at the same N. The baseline row is calibration, not a result.",
        "A continuous score is judged at depths 10 and 20. It does not get",
        "credit for a depth-200 or depth-500 win.",
        "",
        f"Qwen GPU: {results.get('qwen_gpu') or '—'}. "
        f"Elapsed {results.get('qwen_elapsed_sec')}s. Mini: ${results.get('mini_usd')}.",
        "",
    ]
    if results.get("qwen_notes"):
        lines.append("Notes: " + "; ".join(str(n) for n in results["qwen_notes"]))
        lines.append("")

    depths_show = (10, 20, 50, 100, 200, 500)
    lines.append("## Run 1 — all 125 patients (topical scoring)")
    lines.append("")
    lines.append("Eligibility is not in these tables. That arm was cut to a sample.")
    lines.append("")
    for year in YEARS:
        y = str(year)
        year_out = results["years"].get(y) or {}
        if not year_out:
            continue
        n = (year_out.get("baseline") or {}).get("n", 0)
        lines.extend(_tables(year, n, year_out, depths_show, RETRIEVAL_ELIGIBLE[year]))

    lines.append("## Run 2 vs Run 1 — matched 30-patient sample")
    lines.append("")
    lines.append("Same seed **20261001** as the cheap-pass sample. 15 patients per year.")
    lines.append("This is the only fair Run 1 vs Run 2 comparison.")
    lines.append("")
    for year in YEARS:
        y = str(year)
        year_out = results["sample"].get(y) or {}
        if not year_out:
            continue
        n = (year_out.get("baseline") or {}).get("n", 0)
        lines.extend(_tables(year, n, year_out, depths_show, RETRIEVAL_ELIGIBLE[year]))

    lines.extend(
        [
            "## Cost",
            "",
            f"- Qwen seconds: {json.dumps(results.get('qwen_seconds') or {})}",
            f"- Mini: ${results.get('mini_usd')} in {results.get('mini_seconds')}s",
            "",
            "The system does not say a patient qualifies.",
            "",
        ]
    )
    return "\n".join(lines)


def _arm_sort(tag: str) -> tuple:
    order = {
        "baseline": 0,
        "mini_full": 1,
        "qwen_topical_title_cond_digit": 2,
        "qwen_topical_title_cond_cont": 3,
        "qwen_topical_slice_digit": 4,
        "qwen_topical_slice_cont": 5,
        "qwen_elig_full_digit": 6,
        "qwen_elig_full_cont": 7,
        "medcpt_ce_raw": 8,
        "medcpt_ce_keywords": 9,
    }
    return (order.get(tag, 50), tag)


if __name__ == "__main__":
    main()
