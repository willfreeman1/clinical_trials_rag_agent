"""Compare eligibility prompt v2 vs stored v1 on the same 30 patients.

Gates: 4424157. Not a matched model comparison. Ask whether true
positives (label 2) rose on the first page.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_score_common import (  # noqa: E402
    DATA,
    FULL_DEPTH,
    QWEN_SCORES,
    SAMPLE_TOPICS,
    YEARS,
    load_qrels,
    load_shortlist,
    mean,
)
from trec_score_eval import order_by, pct, summarize, topic_metrics  # noqa: E402

V2_SCORES = DATA / "score_qwen_elig_v2.json"
REPORT = Path(__file__).resolve().parents[1] / "docs" / "trec_elig_v2.md"
RESULTS = DATA / "trec_elig_v2_results.json"
THRESHOLDS_COMMIT = "4424157"
V1_P20 = {"2021": 0.487, "2022": 0.580}


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def v1_cont(raw: dict) -> dict[str, dict[str, dict[str, float]]]:
    block = (raw.get("arms") or {}).get("elig_full") or {}
    out: dict[str, dict[str, dict[str, float]]] = {}
    for year, topics in block.items():
        yout = out.setdefault(str(year), {})
        for tid, scores in topics.items():
            dest = {}
            for nct, rec in scores.items():
                if isinstance(rec, list) and len(rec) >= 2:
                    dest[nct] = float(rec[1])
                elif isinstance(rec, dict):
                    dest[nct] = float(rec.get("c") or rec.get("cont") or 0)
            yout[str(tid)] = dest
    return out


def v2_maps(raw: dict) -> dict[str, dict[str, dict[str, dict]]]:
    out: dict[str, dict[str, dict[str, dict]]] = {}
    for year, topics in (raw.get("scores") or {}).items():
        yout = out.setdefault(str(year), {})
        for tid, scores in topics.items():
            yout[str(tid)] = scores
    return out


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


def wilson(k: int, n: int) -> tuple[float, float] | None:
    if n <= 0:
        return None
    z = 1.96
    p = k / n
    den = 1 + z * z / n
    centre = p + z * z / (2 * n)
    adj = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - adj) / den, (centre + adj) / den


def class_stats(v2: dict, labels: dict[str, int]) -> dict:
    words = {"eligible": 0, "ineligible": 0, "unsure": 0}
    judged = {0: [], 1: [], 2: []}
    word_by_label = {0: dict(words), 1: dict(words), 2: dict(words)}
    for nct, rec in v2.items():
        word = (rec.get("word") or "unsure").lower()
        if word not in words:
            word = "unsure"
        words[word] += 1
        lab = labels.get(nct)
        if lab in word_by_label:
            word_by_label[lab][word] += 1
            judged[lab].append(float(rec.get("p_eligible") or 0))
    n12 = sum(word_by_label[1].values()) + sum(word_by_label[2].values())
    unsure_12 = word_by_label[1]["unsure"] + word_by_label[2]["unsure"]
    n2 = sum(word_by_label[2].values())
    n1 = sum(word_by_label[1].values())
    return {
        "word_counts": words,
        "word_by_label": word_by_label,
        "tpr_eligible_on_2": (word_by_label[2]["eligible"] / n2) if n2 else None,
        "fpr_eligible_on_1": (word_by_label[1]["eligible"] / n1) if n1 else None,
        "unsure_share_1_2": (unsure_12 / n12) if n12 else None,
        "auroc_1v2": auroc(judged[2], judged[1]),
        "n_judged_2": n2,
        "n_judged_1": n1,
        "n_judged_0": sum(word_by_label[0].values()),
    }


def main() -> None:
    short = load_shortlist()
    v1_raw = load_json(QWEN_SCORES)
    v2_raw = load_json(V2_SCORES)
    if not v2_raw:
        raise SystemExit(f"missing {V2_SCORES}")
    v1 = v1_cont(v1_raw)
    v2 = v2_maps(v2_raw)
    results = {
        "thresholds_commit": THRESHOLDS_COMMIT,
        "gpu": v2_raw.get("gpu"),
        "seconds": v2_raw.get("seconds"),
        "n_scored": v2_raw.get("n_scored"),
        "parse_fail": v2_raw.get("parse_fail"),
        "years": {},
        "class": {},
        "gate": {},
    }
    class_all = []
    for year in YEARS:
        y = str(year)
        labels_all = load_qrels(year)
        topics = short["years"][y]["topics"]
        sample_ids = list(SAMPLE_TOPICS[y])
        rows = {"v1_cont": [], "v2_p_eligible": [], "baseline": []}
        year_class = []
        for tid in sample_ids:
            trow = topics.get(tid) or {}
            base = trow.get("shortlist") or []
            labels = labels_all.get(tid) or {}
            if not any(v == 2 for v in labels.values()):
                continue
            s1 = (v1.get(y) or {}).get(tid) or {}
            s2 = (v2.get(y) or {}).get(tid) or {}
            rows["baseline"].append(topic_metrics(base, labels, base))
            if s1:
                rows["v1_cont"].append(
                    topic_metrics(order_by(base, lambda n, m=s1: float(m.get(n, -1))), labels, base)
                )
            if s2:
                rows["v2_p_eligible"].append(
                    topic_metrics(
                        order_by(base, lambda n, m=s2: float((m.get(n) or {}).get("p_eligible") or 0)),
                        labels,
                        base,
                    )
                )
                year_class.append(class_stats(s2, labels))
        results["years"][y] = {
            tag: summarize(rs, FULL_DEPTH[year]) for tag, rs in rows.items() if rs
        }
        if year_class:
            results["class"][y] = {
                "tpr_eligible_on_2": mean([c["tpr_eligible_on_2"] for c in year_class if c["tpr_eligible_on_2"] is not None]),
                "fpr_eligible_on_1": mean([c["fpr_eligible_on_1"] for c in year_class if c["fpr_eligible_on_1"] is not None]),
                "unsure_share_1_2": mean([c["unsure_share_1_2"] for c in year_class if c["unsure_share_1_2"] is not None]),
                "auroc_1v2": mean([c["auroc_1v2"] for c in year_class if c["auroc_1v2"] is not None]),
                "word_counts": {
                    w: sum(c["word_counts"][w] for c in year_class)
                    for w in ("eligible", "ineligible", "unsure")
                },
                "n_judged_2": sum(c["n_judged_2"] for c in year_class),
                "n_judged_1": sum(c["n_judged_1"] for c in year_class),
                "word_eligible_on_2": sum(c["word_by_label"][2]["eligible"] for c in year_class),
                "word_eligible_on_1": sum(c["word_by_label"][1]["eligible"] for c in year_class),
                "word_unsure_on_12": sum(
                    c["word_by_label"][1]["unsure"] + c["word_by_label"][2]["unsure"]
                    for c in year_class
                ),
            }
            class_all.extend(year_class)

    y21 = results["years"].get("2021") or {}
    y22 = results["years"].get("2022") or {}
    p21 = (y21.get("v2_p_eligible") or {}).get("precision@20")
    p22 = (y22.get("v2_p_eligible") or {}).get("precision@20")
    t21 = (y21.get("v2_p_eligible") or {}).get("ten_in_20")
    t21_n = (y21.get("v2_p_eligible") or {}).get("n") or 0
    t21_v1 = (y21.get("v1_cont") or {}).get("ten_in_20")
    replace = (
        p21 is not None
        and p22 is not None
        and p21 >= 0.507
        and p22 >= V1_P20["2022"] - 0.02
    )
    no_replace = (
        p21 is not None
        and p21 <= V1_P20["2021"]
        and t21 is not None
        and t21_v1 is not None
        and t21 <= t21_v1
    )
    unsure = None
    auroc_all = None
    if class_all:
        n12 = sum(c["n_judged_1"] + c["n_judged_2"] for c in class_all)
        u12 = sum(
            c["word_by_label"][1]["unsure"] + c["word_by_label"][2]["unsure"]
            for c in class_all
        )
        unsure = (u12 / n12) if n12 else None
        auroc_all = mean([c["auroc_1v2"] for c in class_all if c["auroc_1v2"] is not None])
    if replace:
        decision = "keep v2 as the eligibility prompt"
    elif no_replace:
        decision = "do not replace v1 on this evidence"
    else:
        decision = "split — report; do not replace v1"
    results["gate"] = {
        "p20_2021": p21,
        "p20_2022": p22,
        "ten_in_20_2021": t21,
        "ten_in_20_2021_n": t21_n,
        "ten_in_20_2021_v1": t21_v1,
        "unsure_share_1_2": unsure,
        "auroc_1v2": auroc_all,
        "replace": replace,
        "no_replace": no_replace,
        "decision": decision,
        "dumping": bool(unsure is not None and unsure > 0.50),
        "loud_1v2": bool(auroc_all is not None and auroc_all >= 0.80),
    }
    RESULTS.write_text(json.dumps(results, indent=2), encoding="utf-8")
    REPORT.write_text(render(results), encoding="utf-8")
    print(f"wrote {RESULTS} {REPORT}", flush=True)
    print(decision, flush=True)


def render(results: dict) -> str:
    gate = results.get("gate") or {}
    lines = [
        "# Eligibility prompt v2 on the same 30 patients",
        "",
        f"Gates committed in `{THRESHOLDS_COMMIT}` before any v2 score.",
        "Same shortlist, same 30 patients (seed **20261001**). Prompt and",
        "scoring both changed, so this is not a matched model comparison.",
        "The question is whether true positives (human label 2) rose on the page.",
        "The system does not say a patient qualifies.",
        "",
        f"GPU: {results.get('gpu') or '—'}. Seconds: {results.get('seconds')}. "
        f"Scored: {results.get('n_scored')}.",
        "",
        f"**Decision:** {gate.get('decision')}",
        "",
    ]
    if gate.get("dumping"):
        lines.append("Unsure is more than half of judged disease-relevant pairs. Still dumping.")
        lines.append("")
    if gate.get("loud_1v2"):
        lines.append(f"1-vs-2 AUROC on P(eligible) is {gate.get('auroc_1v2'):.3f} (≥ 0.80).")
        lines.append("")

    depths_show = (10, 20, 50, 100, 200, 500)
    for year in YEARS:
        y = str(year)
        year_out = results["years"].get(y) or {}
        if not year_out:
            continue
        n = (year_out.get("baseline") or {}).get("n", 0)
        lines.extend(
            [
                f"## {year} (n={n})",
                "",
                "| Arm | " + " | ".join(f"@{d}" for d in depths_show) + " | P@10 | P@20 | 10-in-20 |",
                "|" + "---|" * (len(depths_show) + 4),
            ]
        )
        for tag in ("baseline", "v1_cont", "v2_p_eligible"):
            rec = year_out.get(tag) or {}
            if not rec:
                continue
            cells = [pct(rec.get(f"recall@{d}")) for d in depths_show]
            ten = rec.get("ten_in_20", 0)
            nn = rec.get("n", 0)
            extra = ""
            if tag == "v2_p_eligible" and year == 2021:
                ci = wilson(int(ten or 0), int(nn or 0))
                if ci:
                    extra = f" (Wilson {100 * ci[0]:.0f}–{100 * ci[1]:.0f}%)"
            lines.append(
                f"| `{tag}` | "
                + " | ".join(cells)
                + f" | {pct(rec.get('precision@10'))} | {pct(rec.get('precision@20'))} "
                + f"| {ten}/{nn}{extra} |"
            )
        lines.extend(
            [
                "",
                "| Arm | Read 20 | Read 200 | Read 500 |",
                "|---|---:|---:|---:|",
            ]
        )
        for tag in ("baseline", "v1_cont", "v2_p_eligible"):
            rec = year_out.get(tag) or {}
            if not rec:
                continue
            cells = []
            for d in (20, 200, 500):
                mult = rec.get(f"eq_mult@{d}")
                raw = rec.get(f"eq@{d}")
                cells.append("—" if mult is None else f"{mult:.2f}x ({raw:.0f})")
            lines.append(f"| `{tag}` | " + " | ".join(cells) + " |")
        cls = (results.get("class") or {}).get(y) or {}
        if cls:
            lines.extend(
                [
                    "",
                    f"- Word mix: {cls.get('word_counts')}",
                    f"- Word 'eligible' on label 2: {cls.get('word_eligible_on_2')}/{cls.get('n_judged_2')} "
                    f"(macro TPR {pct(cls.get('tpr_eligible_on_2'))})",
                    f"- Word 'eligible' on label 1: {cls.get('word_eligible_on_1')}/{cls.get('n_judged_1')} "
                    f"(macro {pct(cls.get('fpr_eligible_on_1'))})",
                    f"- Unsure among judged 1+2: {pct(cls.get('unsure_share_1_2'))}",
                    f"- P(eligible) AUROC label 1 vs 2: {cls.get('auroc_1v2'):.3f}"
                    if cls.get("auroc_1v2") is not None
                    else "- P(eligible) AUROC label 1 vs 2: —",
                    "",
                ]
            )
        else:
            lines.append("")
    lines.extend(
        [
            "The replace-gate is 2021 P@20 ≥ 50.7% with 2022 not more than 2 points worse than 58.0%.",
            "Depth 200 is reported, not the replace-gate.",
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
