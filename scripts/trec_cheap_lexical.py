"""Lexical first-keyword filter on the cheap-pass sample. No model."""

from __future__ import annotations

import json
import time
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_cheap_common import (  # noqa: E402
    DATA,
    LEXICAL_SCORES,
    YEARS,
    first_keyword,
    load_keywords,
    load_sample,
    load_shortlist,
    loose_hit,
    title_cond_text,
)
from trec_hybrid_common import SNAPSHOT, YEAR_SNAP, load_docs  # noqa: E402


def texts_for_match(row: dict) -> list[str]:
    title = (row.get("title") or "").strip()
    conds = row.get("conditions") or []
    if isinstance(conds, str):
        conds = [conds] if conds.strip() else []
    out = []
    if title:
        out.append(title)
    out.extend(str(c).strip() for c in conds if str(c).strip())
    if not out:
        out.append(title_cond_text(row))
    return out


def main() -> None:
    started = time.time()
    sample = load_sample()
    short = load_shortlist()
    keywords = load_keywords()
    decisions = {}
    n_keep = 0
    n_all = 0
    for year in YEARS:
        y = str(year)
        docs = load_docs(SNAPSHOT[YEAR_SNAP[year]]["docs"])
        year_kw = keywords.get(y, {})
        topics = short["years"][y]["topics"]
        for tid in sample["years"][y]:
            trow = topics[tid]
            kw_row = year_kw.get(tid) or {}
            term = first_keyword(kw_row)
            bucket = decisions.setdefault(y, {}).setdefault(tid, {})
            for nct in trow["shortlist"]:
                row = docs.get(nct) or {}
                keep = loose_hit(term, texts_for_match(row))
                bucket[nct] = {"keep": keep, "term": term}
                n_all += 1
                n_keep += int(keep)
            print(f"{y} {tid} kept {sum(1 for v in bucket.values() if v['keep'])}/{len(bucket)}", flush=True)
    elapsed = time.time() - started
    payload = {
        "arm": "lexical_first_keyword",
        "doc": "title_cond",
        "seconds": round(elapsed, 3),
        "n_pairs": n_all,
        "n_keep": n_keep,
        "usd": 0.0,
        "decisions": decisions,
    }
    LEXICAL_SCORES.write_text(json.dumps(payload), encoding="utf-8")
    print(f"wrote {LEXICAL_SCORES} pairs {n_all} keep {n_keep} {elapsed:.1f}s", flush=True)


if __name__ == "__main__":
    main()
