"""2x2 eval: GPT-5.4 and Qwen, v1 and TREC prompt, judged 1 vs 2 only.

Precision at 20 is not computable. The system does not say a patient qualifies.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_frontier_elig_common import (  # noqa: E402
    GPT_SCORES,
    QWEN_NEW_SCORES,
    REPORT,
    pair_rows,
)
from trec_score_common import QWEN_SCORES  # noqa: E402

PAIRS_COMMIT = "99f795c"
RESULTS = Path(__file__).resolve().parents[1] / "data" / "trec" / "frontier_elig_results.json"


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def auroc(pos: list[float], neg: list[float]) -> float | None:
    if not pos or not neg:
        return None
    better = 0.0
    for p in pos:
        for n in neg:
            if p > n:
                better += 1
            elif p == n:
                better += 0.5
    return better / (len(pos) * len(neg))


def qwen_v1_maps(raw: dict) -> dict[str, dict[str, dict[str, tuple[int, float]]]]:
    block = (raw.get("arms") or {}).get("elig_full") or {}
    out: dict[str, dict[str, dict[str, tuple[int, float]]]] = {}
    for year, topics in block.items():
        yout = out.setdefault(str(year), {})
        for tid, scores in topics.items():
            dest = {}
            for nct, rec in scores.items():
                if isinstance(rec, list) and len(rec) >= 2:
                    dest[nct] = (int(rec[0]), float(rec[1]))
                elif isinstance(rec, dict):
                    dest[nct] = (
                        int(rec.get("d") or rec.get("digit") or 0),
                        float(rec.get("c") or rec.get("cont") or 0),
                    )
            yout[str(tid)] = dest
    return out


def metrics(rows: list[tuple[int, int | None, float | None]]) -> dict:
    # gold, pred_label 1/2/0/None, score higher=more eligible
    pos = [s for g, _p, s in rows if g == 2 and s is not None]
    neg = [s for g, _p, s in rows if g == 1 and s is not None]
    n1 = sum(1 for g, _p, _s in rows if g == 1)
    n2 = sum(1 for g, _p, _s in rows if g == 2)
    pred2_on_1 = sum(1 for g, p, _s in rows if g == 1 and p == 2)
    pred1_on_2 = sum(1 for g, p, _s in rows if g == 2 and p == 1)
    pred0 = sum(1 for _g, p, _s in rows if p == 0)
    both = [(g, p) for g, p, _s in rows if p in (1, 2)]
    acc = None
    if both:
        # balanced accuracy
        t1 = [1 for g, p in both if g == 1 and p == 1]
        t2 = [1 for g, p in both if g == 2 and p == 2]
        n1b = sum(1 for g, _p in both if g == 1)
        n2b = sum(1 for g, _p in both if g == 2)
        a1 = (len(t1) / n1b) if n1b else None
        a2 = (len(t2) / n2b) if n2b else None
        if a1 is not None and a2 is not None:
            acc = (a1 + a2) / 2
    # calibration: high vs low p_eligible correctness of "thinks eligible" (score>=0.5)
    highs = [(g, s) for g, _p, s in rows if s is not None and s >= 0.75]
    lows = [(g, s) for g, _p, s in rows if s is not None and s <= 0.25]
    def rate_right_eligible(xs):
        if not xs:
            return None
        # if score high, gold should be 2; if low, gold should be 1
        return None
    high_ok = (sum(1 for g, _s in highs if g == 2) / len(highs)) if highs else None
    low_ok = (sum(1 for g, _s in lows if g == 1) / len(lows)) if lows else None
    return {
        "n": len(rows),
        "n1": n1,
        "n2": n2,
        "auroc": auroc(pos, neg),
        "balanced_acc": acc,
        "said_eligible_on_excluded": pred2_on_1,
        "said_excluded_on_eligible": pred1_on_2,
        "said_not_relevant": pred0,
        "high_p_share_actually_eligible": high_ok,
        "low_p_share_actually_excluded": low_ok,
        "n_high_p": len(highs),
        "n_low_p": len(lows),
        "n_with_score": len(pos) + len(neg),
    }


def spot_wrong(rows: list[dict], limit: int = 8) -> list[dict]:
    out = []
    for rec in rows:
        if rec.get("gold") == 2 and rec.get("pred") == 1:
            out.append(rec)
        if len(out) >= limit:
            break
    return out


def main() -> None:
    pairs = pair_rows()
    gpt = load(GPT_SCORES)
    qwen_new = load(QWEN_NEW_SCORES)
    qwen_v1 = qwen_v1_maps(load(QWEN_SCORES))
    cells = {
        "gpt_v1": [],
        "gpt_trec": [],
        "qwen_v1": [],
        "qwen_trec": [],
    }
    spots = {k: [] for k in cells}
    for row in pairs:
        y, tid, nct, gold = row["year"], row["topic"], row["nct"], row["label"]
        gv1 = ((gpt.get("arms") or {}).get("v1") or {}).get(y, {}).get(tid, {}).get(nct) or {}
        gt = ((gpt.get("arms") or {}).get("trec") or {}).get(y, {}).get(tid, {}).get(nct) or {}
        qv = (qwen_v1.get(y) or {}).get(tid, {}).get(nct)
        qn = ((qwen_new.get("scores") or {}).get(y) or {}).get(tid, {}).get(nct) or {}

        if gv1.get("digit") is not None or gv1.get("cont") is not None:
            digit = gv1.get("digit")
            pred = {0: 1, 1: 1, 2: 2, 3: 2}.get(digit)
            score = gv1.get("cont")
            if score is None and digit is not None:
                score = float(digit)
            cells["gpt_v1"].append((gold, pred, score))
            if gold == 2 and pred == 1:
                spots["gpt_v1"].append({"year": y, "topic": tid, "nct": nct, "digit": digit})

        if gt.get("label") is not None or gt.get("p_eligible") is not None:
            pred = gt.get("label")
            if pred not in (0, 1, 2):
                pred = None
            cells["gpt_trec"].append((gold, pred, gt.get("p_eligible")))
            if gold == 2 and pred == 1:
                spots["gpt_trec"].append(
                    {"year": y, "topic": tid, "nct": nct, "p": gt.get("p_eligible"), "text": (gt.get("text") or "")[:200]}
                )

        if qv is not None:
            digit, cont = qv
            pred = {0: 1, 1: 1, 2: 2, 3: 2}.get(digit)
            cells["qwen_v1"].append((gold, pred, cont))
            if gold == 2 and pred == 1:
                spots["qwen_v1"].append({"year": y, "topic": tid, "nct": nct, "digit": digit, "cont": cont})

        if qn.get("label") is not None or qn.get("p_eligible") is not None:
            pred = qn.get("label")
            score = qn.get("p_eligible")
            toks = qn.get("p_tokens") or []
            if score is None and len(toks) == 3:
                score = float(toks[2])
            cells["qwen_trec"].append((gold, pred if pred in (0, 1, 2) else None, score))
            if gold == 2 and pred == 1:
                spots["qwen_trec"].append(
                    {"year": y, "topic": tid, "nct": nct, "p": score, "text": (qn.get("text") or "")[:200]}
                )

    summary = {name: metrics(rows) for name, rows in cells.items()}
    results = {
        "pairs_commit": PAIRS_COMMIT,
        "gpt_usd": gpt.get("usd"),
        "gpt_tokens": {"in": gpt.get("input_tokens"), "out": gpt.get("output_tokens")},
        "qwen_gpu": qwen_new.get("gpu"),
        "qwen_seconds": qwen_new.get("seconds"),
        "cells": summary,
        "spot_excluded_on_eligible": {k: v[:6] for k, v in spots.items()},
    }
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(results, indent=2), encoding="utf-8")
    REPORT.write_text(render(results), encoding="utf-8")
    print(f"wrote {RESULTS} {REPORT}", flush=True)


def pct(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{100 * x:.1f}%"


def num(x: float | None) -> str:
    if x is None:
        return "—"
    return f"{x:.3f}"


def render(results: dict) -> str:
    c = results.get("cells") or {}
    lines = [
        "# Frontier-model baseline on eligibility judging",
        "",
        f"Pair list and prompts committed in `{PAIRS_COMMIT}` before any new score.",
        "Same 30 patients (seed **20261001**). Up to 7 joinable and 7 excluded",
        "trials per patient (pair seed **20261002**). **411 judged pairs**",
        "(201 excluded / 210 joinable). 2023 was not touched.",
        "",
        "This is not a first-page ranking. **Precision at 20 is not computable**",
        "here. Do not compare these numbers to the earlier P@20 tables.",
        "",
        "AUROC is on label 1 vs 2. The score is higher when the model thinks",
        "the patient looks eligible. Balanced accuracy averages the two",
        "class hit rates so the slightly uneven 201/210 split does not tilt it.",
        "",
        "The system does not say a patient qualifies.",
        "",
        f"GPT-5.4 cost: ${results.get('gpt_usd')}. "
        f"Qwen GPU: {results.get('qwen_gpu') or '—'} "
        f"({results.get('qwen_seconds')}s).",
        "",
        "## 2 × 2",
        "",
        "| | v1 prompt (0–3, unsure→2) | TREC-label prompt |",
        "|---|---|---|",
    ]
    def cell(name: str) -> str:
        rec = c.get(name) or {}
        return (
            f"AUROC {num(rec.get('auroc'))}; "
            f"balanced acc {pct(rec.get('balanced_acc'))}; "
            f"said excluded on joinable {rec.get('said_excluded_on_eligible')}/"
            f"{rec.get('n2')}; "
            f"said eligible on excluded {rec.get('said_eligible_on_excluded')}/"
            f"{rec.get('n1')}"
        )
    lines.append(f"| **GPT-5.4** | {cell('gpt_v1')} | {cell('gpt_trec')} |")
    lines.append(f"| **Qwen2.5-7B** | {cell('qwen_v1')} | {cell('qwen_trec')} |")
    lines.extend(["", "## Detail", ""])
    for name, title in (
        ("gpt_v1", "GPT-5.4 × v1"),
        ("gpt_trec", "GPT-5.4 × TREC prompt"),
        ("qwen_v1", "Qwen × v1 (stored scores)"),
        ("qwen_trec", "Qwen × TREC prompt"),
    ):
        rec = c.get(name) or {}
        lines.extend(
            [
                f"### {title}",
                "",
                f"- n = {rec.get('n')} (excluded {rec.get('n1')}, joinable {rec.get('n2')})",
                f"- AUROC 1 vs 2: {num(rec.get('auroc'))}",
                f"- Balanced accuracy: {pct(rec.get('balanced_acc'))}",
                f"- Said excluded on a joinable pair: {rec.get('said_excluded_on_eligible')}/{rec.get('n2')}",
                f"- Said eligible on an excluded pair: {rec.get('said_eligible_on_excluded')}/{rec.get('n1')}",
                f"- Said not relevant (0) on these 1/2 pairs: {rec.get('said_not_relevant')}",
                f"- Among high p_eligible (≥0.75), share that were joinable: {pct(rec.get('high_p_share_actually_eligible'))} (n={rec.get('n_high_p')})",
                f"- Among low p_eligible (≤0.25), share that were excluded: {pct(rec.get('low_p_share_actually_excluded'))} (n={rec.get('n_low_p')})",
                "",
            ]
        )
    lines.extend(
        [
            "## Does confidence mean anything?",
            "",
            "If the number is working, high scores should mostly be human-joinable",
            "and low scores should mostly be human-excluded. Compare the two",
            "share rows above.",
            "",
            "## Fine-tune?",
            "",
            _gap_answer(c),
            "",
        ]
    )
    return "\n".join(lines)


def _gap_answer(cells: dict) -> str:
    q = (cells.get("qwen_v1") or {}).get("auroc")
    g = (cells.get("gpt_trec") or {}).get("auroc") or (cells.get("gpt_v1") or {}).get("auroc")
    if q is None or g is None:
        return "Not enough scores yet to answer."
    gap = g - q
    if gap >= 0.08:
        return (
            f"Yes, there is a gap worth a fine-tune look. GPT AUROC {g:.3f} vs "
            f"Qwen {q:.3f} (difference {gap:.3f}). If we fine-tune later, use the "
            f"human TREC labels, not GPT's answers."
        )
    if gap <= 0.03:
        return (
            f"No. GPT AUROC {g:.3f} vs Qwen {q:.3f} (difference {gap:.3f}). "
            f"The frontier model is not far enough ahead to justify a fine-tune "
            f"aimed at closing a model-size gap. The task itself looks hard."
        )
    return (
        f"The gap is modest: GPT AUROC {g:.3f} vs Qwen {q:.3f} "
        f"(difference {gap:.3f}). That is not a loud yes or no. Report it; "
        f"do not start a fine-tune from this number alone."
    )


if __name__ == "__main__":
    main()
