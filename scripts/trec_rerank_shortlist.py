"""Rebuild keyword-hybrid shortlists for 2021/2022. Same first stage as 91.6%/91.4%.

RETRIEVE_N=1000 per keyword, BM25 + MedCPT, RRF. Top 6% kept. No 2023.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_hybrid_common import (  # noqa: E402
    RETRIEVE_N,
    SNAPSHOT,
    YEAR_SNAP,
    load_docs,
    load_topics,
    pool_ids,
    qrels_by_topic,
    recall_at,
)
from trec_hybrid_eval import (  # noqa: E402
    QUERY_ENC,
    bm25_rank,
    build_bm25,
    dense_rank,
    encode_queries,
    fuse,
    topic_queries,
)
from trec_rerank_common import (  # noqa: E402
    DATA,
    FULL_DEPTH,
    SHORTLIST,
    YEARS,
    keyword_query,
    load_keywords,
)

THRESHOLDS_COMMIT = "44878a7"


def eval_year(year: int, keywords: dict, q_model, q_tok) -> dict:
    snap = YEAR_SNAP[year]
    meta = SNAPSHOT[snap]
    docs = load_docs(meta["docs"])
    ncts = [nct for nct in pool_ids(year) if nct in docs]
    ncts_set = set(ncts)
    qrels = qrels_by_topic(year)
    topics = load_topics(year)
    year_kw = keywords.get(str(year), {})
    depth = FULL_DEPTH[year]
    print(f"year {year} collection {len(ncts)} shortlist {depth}", flush=True)

    bm25 = build_bm25(ncts, docs)
    idx_dir = DATA / f"index_{snap}"
    medcpt_all = np.load(idx_dir / "medcpt.npy")
    chunk_all = json.loads((idx_dir / "chunk_nct.json").read_text(encoding="utf-8"))
    chunk_vecs = []
    chunk_nct = []
    for vec, nct in zip(medcpt_all, chunk_all):
        if nct in ncts_set:
            chunk_vecs.append(vec)
            chunk_nct.append(nct)
    chunk_vecs = np.asarray(chunk_vecs)

    topics_out = {}
    recalls = []
    judged = [tid for tid in topics if qrels.get(tid)]
    for tid in judged:
        labels = qrels[tid]
        eligible = {n for n, r in labels.items() if r == 2 and n in ncts_set}
        kw_row = year_kw.get(tid) or {}
        kw_queries = topic_queries(topics[tid], kw_row, "kw")
        q_kw = encode_queries(kw_queries, q_model, q_tok)
        bm = bm25_rank(bm25, ncts, kw_queries, RETRIEVE_N)
        med = dense_rank(q_kw, chunk_vecs, ncts, chunk_nct, RETRIEVE_N)
        ranked = fuse(bm + med)[:depth]
        rec = recall_at(ranked, eligible, depth)
        recalls.append(rec)
        topics_out[tid] = {
            "shortlist": ranked,
            "keyword_query": keyword_query(kw_row),
            "raw_query": topics[tid],
            "n_eligible": len(eligible),
            "recall_at_full": rec,
        }
        print(f"  {year} topic {tid} rec@full={rec:.3f} n={len(ranked)}", flush=True)

    mean_full = sum(r for r in recalls if r is not None) / max(1, len([r for r in recalls if r is not None]))
    return {
        "n_collection": len(ncts),
        "shortlist_depth": depth,
        "n_topics": len(topics_out),
        "mean_recall_at_full": mean_full,
        "topics": topics_out,
    }


def main() -> None:
    keywords = load_keywords()
    print(f"loading {QUERY_ENC}", flush=True)
    q_tok = AutoTokenizer.from_pretrained(QUERY_ENC)
    q_model = AutoModel.from_pretrained(QUERY_ENC)
    q_model.eval()
    pack = {
        "thresholds_commit": THRESHOLDS_COMMIT,
        "first_stage": "kw_hybrid",
        "retrieve_n": RETRIEVE_N,
        "years": {},
    }
    with torch.no_grad():
        for year in YEARS:
            pack["years"][str(year)] = eval_year(year, keywords, q_model, q_tok)
    SHORTLIST.write_text(json.dumps(pack), encoding="utf-8")
    for year in YEARS:
        y = pack["years"][str(year)]
        print(f"{year} mean recall at {y['shortlist_depth']}: {y['mean_recall_at_full']:.4f}", flush=True)
    print(f"wrote {SHORTLIST}", flush=True)


if __name__ == "__main__":
    main()
