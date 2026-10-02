"""Pack sample (or all 2021/2022) shortlists for the GPU cheap pass. No secrets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_cheap_common import (  # noqa: E402
    PACK,
    YEARS,
    first_keyword,
    load_keywords,
    load_sample,
    load_shortlist,
    summary_query,
)
from trec_hybrid_common import SNAPSHOT, YEAR_SNAP, load_docs  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    short = load_shortlist()
    keywords = load_keywords()
    wanted = None if args.full else load_sample()["years"]
    docs_out = {}
    years_out = {}
    n_topics = 0
    for year in YEARS:
        y = str(year)
        docs = load_docs(SNAPSHOT[YEAR_SNAP[year]]["docs"])
        year_kw = keywords.get(y, {})
        tids = list(short["years"][y]["topics"]) if args.full else wanted[y]
        topics = {}
        for tid in tids:
            trow = short["years"][y]["topics"][tid]
            kw_row = year_kw.get(tid) or {}
            topics[tid] = {
                "shortlist": trow["shortlist"],
                "summary": summary_query(kw_row),
                "first_keyword": first_keyword(kw_row),
            }
            n_topics += 1
            for nct in trow["shortlist"]:
                if nct in docs_out:
                    continue
                row = docs.get(nct) or {}
                docs_out[nct] = {
                    "title": row.get("title") or "",
                    "conditions": row.get("conditions") or [],
                    "eligibility": row.get("eligibility") or "",
                    "text": row.get("text") or "",
                }
        years_out[y] = {"topics": topics}
    dest = PACK
    if args.full:
        dest = PACK.with_name("cheap_pass_pack_full.json")
    dest.write_text(
        json.dumps(
            {
                "sample_only": not args.full,
                "n_topics": n_topics,
                "n_docs": len(docs_out),
                "docs": docs_out,
                "years": years_out,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"wrote {dest} topics {n_topics} docs {len(docs_out)} bytes {dest.stat().st_size}", flush=True)


if __name__ == "__main__":
    main()
