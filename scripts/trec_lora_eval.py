"""Evaluate a v1 eligibility score file on the frozen 1-vs-2 pair lists."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_lora_common import (  # noqa: E402
    BASE_RESULTS,
    EVAL_PAIRS_PATH,
    auroc,
    load_splits,
    pct,
    split_auroc,
)
from trec_score_common import QWEN_SCORES, load_qrels, load_shortlist  # noqa: E402


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def score_of(rec) -> float | None:
    if isinstance(rec, list) and len(rec) >= 2:
        return float(rec[1])
    if isinstance(rec, dict):
        if rec.get("c") is not None:
            return float(rec["c"])
        if rec.get("cont") is not None:
            return float(rec["cont"])
    return None


def digit_of(rec) -> int | None:
    if isinstance(rec, list) and rec:
        return int(rec[0])
    if isinstance(rec, dict) and rec.get("d") is not None:
        return int(rec["d"])
    return None


def rows_for(block: dict, scores: dict, year: str) -> list[dict]:
    out = []
    ysc = scores.get(year) or {}
    for tid, pairs in (block.get("topics") or {}).items():
        tsc = ysc.get(tid) or {}
        for nct, lab in pairs:
            rec = tsc.get(nct)
            out.append(
                {
                    "tid": tid,
                    "nct": nct,
                    "label": int(lab),
                    "score": score_of(rec),
                    "digit": digit_of(rec),
                }
            )
    return out


def balanced(rows: list[dict]) -> float | None:
    t1 = t2 = n1 = n2 = 0
    for r in rows:
        if r.get("digit") is None or r["label"] not in (1, 2):
            continue
        pred2 = r["digit"] >= 2
        if r["label"] == 1:
            n1 += 1
            if not pred2:
                t1 += 1
        else:
            n2 += 1
            if pred2:
                t2 += 1
    if not n1 or not n2:
        return None
    return 0.5 * (t1 / n1 + t2 / n2)


def slice_rows(year: int, tids: list[str]) -> list[dict]:
    qwen = load(QWEN_SCORES)
    arm = ((qwen.get("arms") or {}).get("topical_title_cond_slice") or {}).get(str(year)) or {}
    labels = load_qrels(year)
    short = load_shortlist()
    topics = short["years"][str(year)]["topics"]
    out = []
    for tid in tids:
        sl = (arm.get(tid) or {})
        labs = labels.get(tid) or {}
        base = (topics.get(tid) or {}).get("shortlist") or []
        for nct in base:
            lab = labs.get(nct)
            if lab not in (1, 2) or nct not in sl:
                continue
            rec = sl[nct]
            out.append(
                {
                    "tid": tid,
                    "nct": nct,
                    "label": lab,
                    "score": score_of(rec),
                    "digit": digit_of(rec),
                }
            )
    return out


def summarize(name: str, rows: list[dict]) -> dict:
    scored = [r for r in rows if r.get("score") is not None]
    rec = split_auroc(scored, "score")
    rec["n_missing"] = len(rows) - len(scored)
    rec["balanced_acc"] = balanced(rows)
    return rec


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("usage: trec_lora_eval.py SCORE.json [label]")
    path = Path(sys.argv[1])
    label = sys.argv[2] if len(sys.argv) > 2 else path.stem
    pairs = load(EVAL_PAIRS_PATH)
    raw = load(path)
    scores = raw.get("scores") or raw.get("arms", {}).get("elig_full") or {}
    splits = {
        "dev": (pairs["dev_2021"], "2021"),
        "test": (pairs["test_2022"], "2022"),
    }
    report = {"source": str(path), "label": label, "gpu": raw.get("gpu"), "n_scored": raw.get("n_scored")}
    lines = [f"{label}  file={path.name}"]
    for name, (block, year) in splits.items():
        rows = rows_for(block, scores, year)
        rec = summarize(name, rows)
        report[name] = rec
        lines.append(
            f"  {name}: n1={rec.get('n1')} n2={rec.get('n2')} missing={rec.get('n_missing')} "
            f"pooled {pct(rec.get('pooled'))} macro {pct(rec.get('macro'))} "
            f"bal-acc {pct(rec.get('balanced_acc'))}"
        )
    splits_ids = load_splits()
    slice_test = summarize("slice_test", slice_rows(2022, splits_ids["test_2022"]))
    slice_dev = summarize("slice_dev", slice_rows(2021, splits_ids["dev_2021"]))
    report["topical_slice_dev"] = slice_dev
    report["topical_slice_test"] = slice_test
    lines.append(
        f"  topical slice on same pairs: dev {pct(slice_dev.get('pooled'))} "
        f"test {pct(slice_test.get('pooled'))}"
    )
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else BASE_RESULTS
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\n".join(lines), flush=True)
    print(f"wrote {out}", flush=True)


if __name__ == "__main__":
    main()
