"""CE logit sweep. Not the gate. Committed keep is logit > 0."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_cheap_common import (  # noqa: E402
    GPU_SCORES,
    YEARS,
    load_sample,
    load_shortlist,
    pooled_from_topics,
    topic_counts,
)
from trec_hybrid_common import qrels_by_topic  # noqa: E402

THS = [
    -14,
    -13.5,
    -13,
    -12.5,
    -12,
    -11.5,
    -11,
    -10.5,
    -10,
    -8,
    -6,
    -4,
    -2,
    0,
]


def main() -> None:
    sample = load_sample()
    short = load_shortlist()
    qrels = {year: qrels_by_topic(year) for year in YEARS}
    gpu = json.loads(GPU_SCORES.read_text(encoding="utf-8"))
    for doc, scores in (gpu.get("ce") or {}).items():
        vals = [float(v) for year in scores.values() for topic in year.values() for v in topic.values()]
        if not vals:
            continue
        vals_s = sorted(vals)
        n = len(vals_s)
        print(doc, "n", n)
        print(
            " min",
            round(vals_s[0], 3),
            "p10",
            round(vals_s[n // 10], 3),
            "p50",
            round(vals_s[n // 2], 3),
            "p90",
            round(vals_s[9 * n // 10], 3),
            "max",
            round(vals_s[-1], 3),
            "gt0",
            round(sum(1 for v in vals if v > 0) / n, 4),
        )
        print(" thr  recall  elig   retent  both")
        for thr in THS:
            rows = []
            for year in YEARS:
                y = str(year)
                labels = qrels[year]
                bucket_y = scores.get(y) or {}
                for tid in sample["years"][y]:
                    sl = short["years"][y]["topics"][tid]["shortlist"]
                    bucket = bucket_y.get(tid) or {}
                    kept = {nct for nct, v in bucket.items() if float(v) > thr}
                    rows.append(topic_counts(sl, labels.get(tid, {}), kept))
            pooled = pooled_from_topics(rows)
            rec = pooled["recall_micro"] or 0.0
            elig = pooled["eligible_recall_micro"] or 0.0
            ret = pooled["retention_micro"] or 0.0
            both = rec >= 0.90 and ret <= 0.50
            print(
                f" {thr:5} {rec:6.3f} {elig:6.3f} {ret:6.3f}  {'YES' if both else 'no'}"
            )


if __name__ == "__main__":
    main()
