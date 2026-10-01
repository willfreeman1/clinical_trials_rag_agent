"""Pack all 125 2021/2022 shortlists for Qwen scoring. No secrets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_hybrid_common import SNAPSHOT, YEAR_SNAP, load_docs  # noqa: E402
from trec_score_common import (  # noqa: E402
    PACK,
    SAMPLE_TOPICS,
    YEARS,
    load_shortlist,
)

ELIG_LENS: list[int] = []


def main() -> None:
    short = load_shortlist()
    docs_out: dict[str, dict] = {}
    years_out: dict[str, dict] = {}
    n_topics = 0
    n_pairs = 0
    for year in YEARS:
        docs = load_docs(SNAPSHOT[YEAR_SNAP[year]]["docs"])
        y = str(year)
        topics = {}
        for tid, trow in short["years"][y]["topics"].items():
            topics[tid] = {
                "shortlist": trow["shortlist"],
                "raw_query": trow["raw_query"],
            }
            n_topics += 1
            n_pairs += len(trow["shortlist"])
            for nct in trow["shortlist"]:
                if nct in docs_out:
                    continue
                row = docs.get(nct) or {}
                elig = row.get("eligibility") or ""
                ELIG_LENS.append(len(elig))
                docs_out[nct] = {
                    "title": row.get("title") or "",
                    "conditions": row.get("conditions") or [],
                    "eligibility": elig,
                    "text": row.get("text") or "",
                }
        years_out[y] = {"topics": topics}
    ELIG_LENS.sort()

    def pct(p: float) -> int:
        if not ELIG_LENS:
            return 0
        i = min(len(ELIG_LENS) - 1, int(round((len(ELIG_LENS) - 1) * p)))
        return ELIG_LENS[i]

    payload = {
        "thresholds_commit": "114cce7",
        "n_topics": n_topics,
        "n_pairs": n_pairs,
        "n_docs": len(docs_out),
        "sample_topics": SAMPLE_TOPICS,
        "elig_chars": {
            "n": len(ELIG_LENS),
            "p50": pct(0.50),
            "p90": pct(0.90),
            "p99": pct(0.99),
            "max": ELIG_LENS[-1] if ELIG_LENS else 0,
        },
        "docs": docs_out,
        "years": years_out,
    }
    PACK.parent.mkdir(parents=True, exist_ok=True)
    PACK.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    stats = payload["elig_chars"]
    print(
        f"wrote {PACK} topics {n_topics} pairs {n_pairs} docs {len(docs_out)} "
        f"bytes {PACK.stat().st_size} elig_p50 {stats['p50']} p90 {stats['p90']} "
        f"p99 {stats['p99']} max {stats['max']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
