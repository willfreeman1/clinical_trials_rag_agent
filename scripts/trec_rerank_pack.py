"""Build the GPU pack from shortlists + judged docs. No secrets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_hybrid_common import SNAPSHOT, YEAR_SNAP, load_docs  # noqa: E402
from trec_rerank_common import DATA, SHORTLIST, YEARS  # noqa: E402

PACK = DATA / "rerank_pack.json"


def main() -> None:
    short = json.loads(SHORTLIST.read_text(encoding="utf-8"))
    docs_out = {}
    years_out = {}
    for year in YEARS:
        snap = YEAR_SNAP[year]
        docs = load_docs(SNAPSHOT[snap]["docs"])
        y = short["years"][str(year)]
        topics = {}
        for tid, trow in y["topics"].items():
            topics[tid] = {
                "shortlist": trow["shortlist"],
                "keyword_query": trow["keyword_query"],
                "raw_query": trow["raw_query"],
            }
            for nct in trow["shortlist"]:
                if nct in docs_out:
                    continue
                row = docs.get(nct) or {}
                docs_out[nct] = {
                    "title": row.get("title") or "",
                    "text": row.get("text") or "",
                }
        years_out[str(year)] = {"topics": topics}
    PACK.write_text(
        json.dumps({"docs": docs_out, "years": years_out}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"wrote {PACK} docs {len(docs_out)} bytes {PACK.stat().st_size}", flush=True)


if __name__ == "__main__":
    main()
