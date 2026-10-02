"""Hybrid retrieval + ablations. Gates committed in 613635e.

Per keyword: BM25 and MedCPT, then reciprocal rank fusion.
No trial text to an LLM. No reader, reranker, or ranking stage.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from rank_bm25 import BM25Okapi
from transformers import AutoModel, AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_hybrid_common import (  # noqa: E402
    DATA,
    DEPTHS,
    REPORT,
    RETRIEVE_N,
    RRF_K,
    SNAPSHOT,
    THRESHOLDS_COMMIT,
    YEAR_SNAP,
    YEARS,
    load_docs,
    load_topics,
    mean_ignore_none,
    pool_ids,
    qrels_by_topic,
    recall_at,
    rrf,
    tokenize,
)

QUERY_ENC = "ncbi/MedCPT-Query-Encoder"
OUT = DATA / "trec_hybrid_results.json"


def load_keywords() -> dict:
    return json.loads((DATA / "keywords.json").read_text(encoding="utf-8"))


def build_bm25(ncts: list[str], docs: dict[str, dict]) -> BM25Okapi:
    corpus = []
    for nct in ncts:
        row = docs[nct]
        title = tokenize(row.get("title") or "")
        cond = tokenize(" ".join(row.get("conditions") or []))
        body = tokenize(row.get("text") or "")
        corpus.append(title * 3 + cond * 2 + body)
    return BM25Okapi(corpus)


@torch.no_grad()
def encode_queries(texts: list[str], model, tokenizer) -> np.ndarray:
    if not texts:
        return np.zeros((0, 768), dtype=np.float32)
    enc = tokenizer(
        texts,
        truncation=True,
        padding=True,
        return_tensors="pt",
        max_length=256,
    )
    return model(**enc).last_hidden_state[:, 0, :].cpu().numpy()


def dense_rank(
    query_vecs: np.ndarray,
    doc_vecs: np.ndarray,
    ncts: list[str],
    chunk_nct: list[str] | None,
    topn: int,
) -> list[list[str]]:
    if query_vecs.size == 0:
        return [[] for _ in range(0)]
    q = query_vecs / (np.linalg.norm(query_vecs, axis=1, keepdims=True) + 1e-12)
    d = doc_vecs / (np.linalg.norm(doc_vecs, axis=1, keepdims=True) + 1e-12)
    sims = q @ d.T
    rankings = []
    one_each = chunk_nct is not None and len(chunk_nct) == len(set(chunk_nct))
    for row in sims:
        if chunk_nct is not None and not one_each:
            best: dict[str, float] = {}
            for score, nct in zip(row, chunk_nct):
                prev = best.get(nct)
                if prev is None or score > prev:
                    best[nct] = float(score)
            ordered = sorted(best.items(), key=lambda kv: -kv[1])[:topn]
            rankings.append([nct for nct, _ in ordered])
        elif chunk_nct is not None and one_each:
            idx = np.argpartition(-row, min(topn, len(row) - 1))[:topn]
            idx = idx[np.argsort(-row[idx])]
            rankings.append([chunk_nct[i] for i in idx])
        else:
            idx = np.argpartition(-row, min(topn, len(row) - 1))[:topn]
            idx = idx[np.argsort(-row[idx])]
            rankings.append([ncts[i] for i in idx])
    return rankings


def bm25_rank(bm25: BM25Okapi, ncts: list[str], queries: list[str], topn: int) -> list[list[str]]:
    out = []
    for q in queries:
        toks = tokenize(q)
        if not toks:
            out.append([])
            continue
        scores = bm25.get_scores(toks)
        idx = np.argpartition(-scores, min(topn, len(scores) - 1))[:topn]
        idx = idx[np.argsort(-scores[idx])]
        out.append([ncts[i] for i in idx])
    return out


def fuse(lists: list[list[str]]) -> list[str]:
    return rrf([x for x in lists if x], k=RRF_K)


def topic_queries(note: str, kw_row: dict, mode: str) -> list[str]:
    if mode == "raw":
        return [note]
    kws = [k for k in (kw_row or {}).get("keywords") or [] if k]
    return kws or [note]


def eval_year(
    year: int,
    keywords: dict,
    q_model,
    q_tok,
) -> dict:
    snap = YEAR_SNAP[year]
    meta = SNAPSHOT[snap]
    docs = load_docs(meta["docs"])
    ncts = [nct for nct in pool_ids(year) if nct in docs]
    ncts_set = set(ncts)
    qrels = qrels_by_topic(year)
    topics = load_topics(year)
    year_kw = keywords.get(str(year), {})
    print(f"year {year} collection {len(ncts)} topics {len(topics)}", flush=True)

    bm25 = build_bm25(ncts, docs)
    idx_dir = DATA / f"index_{snap}"
    all_ncts = json.loads((idx_dir / "nctids.json").read_text(encoding="utf-8"))
    keep = [i for i, n in enumerate(all_ncts) if n in ncts_set]
    nct_pos = {n: i for i, n in enumerate(ncts)}

    medcpt_all = np.load(idx_dir / "medcpt.npy")
    chunk_all = json.loads((idx_dir / "chunk_nct.json").read_text(encoding="utf-8"))
    chunk_vecs = []
    chunk_nct = []
    for vec, nct in zip(medcpt_all, chunk_all):
        if nct in ncts_set:
            chunk_vecs.append(vec)
            chunk_nct.append(nct)
    chunk_vecs = np.asarray(chunk_vecs)
    openai_all = np.load(idx_dir / "openai.npy")
    openai_vecs = np.stack([openai_all[all_ncts.index(n)] for n in ncts]) if keep else openai_all
    # all_ncts.index in a loop is O(n^2). Fix:
    pos_all = {n: i for i, n in enumerate(all_ncts)}
    openai_vecs = np.stack([openai_all[pos_all[n]] for n in ncts])

    systems = (
        "kw_bm25",
        "kw_medcpt",
        "kw_openai",
        "kw_hybrid",
        "kw_hybrid_openai",
        "raw_hybrid",
    )
    per_topic = {name: {} for name in systems}
    eligible_recalls = {name: defaultdict(list) for name in systems}
    relevant_recalls = {name: defaultdict(list) for name in systems}
    pct6 = max(1, int(round(0.06 * len(ncts))))
    depths = list(DEPTHS) + [pct6]
    depth_labels = {d: str(d) for d in DEPTHS}
    depth_labels[pct6] = "pct6"

    for tid, note in topics.items():
        labels = qrels.get(tid, {})
        if not labels:
            continue
        eligible = {n for n, r in labels.items() if r == 2 and n in ncts_set}
        relevant = {n for n, r in labels.items() if r >= 1 and n in ncts_set}
        kw_queries = topic_queries(note, year_kw.get(tid), "kw")
        raw_queries = topic_queries(note, year_kw.get(tid), "raw")

        bm25_kw = bm25_rank(bm25, ncts, kw_queries, RETRIEVE_N)
        bm25_raw = bm25_rank(bm25, ncts, raw_queries, RETRIEVE_N)
        q_kw = encode_queries(kw_queries, q_model, q_tok)
        q_raw = encode_queries(raw_queries, q_model, q_tok)
        med_kw = dense_rank(q_kw, chunk_vecs, ncts, chunk_nct, RETRIEVE_N)
        med_raw = dense_rank(q_raw, chunk_vecs, ncts, chunk_nct, RETRIEVE_N)
        # OpenAI query embeddings are filled later if needed — use MedCPT query
        # encoder only for MedCPT. OpenAI queries: embed keywords via stored
        # function? We embed query texts with the same OpenAI model at eval.
        # That is done in a batch below if missing. For now compute per topic
        # via a small cache on disk? Simpler: encode OpenAI queries in this
        # loop through a caller-supplied cache.
        rankings = {
            "kw_bm25": fuse(bm25_kw),
            "kw_medcpt": fuse(med_kw),
            "kw_hybrid": fuse(bm25_kw + med_kw),
            "raw_hybrid": fuse(bm25_raw + med_raw),
        }
        # openai filled by caller after we have query vectors
        per_topic["_kw_queries"] = per_topic.get("_kw_queries", {})
        per_topic["_kw_queries"][tid] = kw_queries
        for name, ranked in rankings.items():
            per_topic[name][tid] = ranked[: max(depths)]
            for d in depths:
                eligible_recalls[name][d].append(recall_at(ranked, eligible, d))
                relevant_recalls[name][d].append(recall_at(ranked, relevant, d))
        print(f"  {year} topic {tid} kw={len(kw_queries)}", flush=True)

    judged = [t for t in topics if qrels.get(t)]
    return {
        "n_collection": len(ncts),
        "pct6": pct6,
        "n_topics": len(judged),
        "systems_partial": {n: per_topic[n] for n in rankings},
        "eligible_recalls": {n: {str(k): v for k, v in eligible_recalls[n].items()} for n in rankings},
        "relevant_recalls": {n: {str(k): v for k, v in relevant_recalls[n].items()} for n in rankings},
        "kw_queries": {tid: topic_queries(topics[tid], year_kw.get(tid), "kw") for tid in topics},
        "ncts": ncts,
        "openai_vecs": openai_vecs,
        "bm25": bm25,
        "docs_ncts": ncts,
        "chunk_vecs": chunk_vecs,
        "chunk_nct": chunk_nct,
        "qrels": qrels,
        "topics": topics,
        "year_kw": year_kw,
        "depth_labels": depth_labels,
        "depths": depths,
    }


def openai_query_vecs(queries: list[str], cache: dict[str, np.ndarray], api_key: str) -> np.ndarray:
    import urllib.request

    missing = [q for q in queries if q not in cache]
    for i in range(0, len(missing), 64):
        batch = missing[i : i + 64] or [" "]
        payload = {"model": "text-embedding-3-small", "input": [q[:8000] or " " for q in batch]}
        req = urllib.request.Request(
            "https://api.openai.com/v1/embeddings",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = json.loads(resp.read().decode())
        by_i = {row["index"]: np.asarray(row["embedding"], dtype=np.float32) for row in body["data"]}
        for j, q in enumerate(batch):
            cache[q] = by_i[j]
    return np.stack([cache[q] for q in queries]) if queries else np.zeros((0, 1536), dtype=np.float32)


def finish_openai(year_pack: dict, api_key: str, cache: dict) -> None:
    ncts = year_pack["ncts"]
    openai_vecs = year_pack["openai_vecs"]
    bm25 = year_pack["bm25"]
    qrels = year_pack["qrels"]
    topics = year_pack["topics"]
    year_kw = year_pack["year_kw"]
    depths = year_pack["depths"]
    ncts_set = set(ncts)
    for name in ("kw_openai", "kw_hybrid_openai"):
        year_pack["eligible_recalls"][name] = defaultdict(list)
        year_pack["relevant_recalls"][name] = defaultdict(list)
        year_pack["systems_partial"][name] = {}
    for tid, note in topics.items():
        labels = qrels.get(tid, {})
        if not labels:
            continue
        eligible = {n for n, r in labels.items() if r == 2 and n in ncts_set}
        relevant = {n for n, r in labels.items() if r >= 1 and n in ncts_set}
        kw_queries = year_pack["kw_queries"][tid]
        qv = openai_query_vecs(kw_queries, cache, api_key)
        oai = dense_rank(qv, openai_vecs, ncts, None, RETRIEVE_N)
        bm = bm25_rank(bm25, ncts, kw_queries, RETRIEVE_N)
        rankings = {"kw_openai": fuse(oai), "kw_hybrid_openai": fuse(bm + oai)}
        for name, ranked in rankings.items():
            year_pack["systems_partial"][name][tid] = ranked[: max(depths)]
            for d in depths:
                year_pack["eligible_recalls"][name][str(d)].append(recall_at(ranked, eligible, d))
                year_pack["relevant_recalls"][name][str(d)].append(recall_at(ranked, relevant, d))


def summarise(year_pack: dict) -> dict:
    out = {
        "n_collection": year_pack["n_collection"],
        "pct6": year_pack["pct6"],
        "n_topics": year_pack["n_topics"],
        "systems": {},
    }
    for name, by_depth in year_pack["eligible_recalls"].items():
        out["systems"][name] = {"eligible": {}, "relevant": {}}
        for d, vals in by_depth.items():
            out["systems"][name]["eligible"][d] = mean_ignore_none(vals)
        for d, vals in year_pack["relevant_recalls"][name].items():
            out["systems"][name]["relevant"][d] = mean_ignore_none(vals)
    return out


def write_report(results: dict) -> None:
    lines = [
        "# TREC hybrid retrieval (stages 1–2 only)",
        "",
        f"Gates committed in `{THRESHOLDS_COMMIT}` before keywords, encoding, or recall.",
        "Judged pool is the collection. No trial text to an LLM. No reader, reranker, or ranking stage.",
        "Six-name narrowing was not used.",
        "",
        "2021 and 2022 use the **27 April 2021** ClinicalTrials.gov dump.",
        "2023 uses the **8 May 2023** dump (confirmed on trec-cds.org; not the 2021 dump).",
        "",
        "MedCPT was trained on PubMed search logs and is out of domain here. TrialGPT used it anyway.",
        "Each trial is one `[title, body]` pair truncated to 512 tokens — the same as TrialGPT.",
        "A typical trial is 3,581 characters, so the tail of eligibility is dropped.",
        "Chunking (2.7 windows/trial) was started and abandoned on CPU (~5 hours per snapshot).",
        "The cross-encoder was downloaded and not run.",
        "",
        "## Collection",
        "",
        "| Year | Snapshot | Topics | Judged trials (collection) | 6% depth |",
        "|---|---|---:|---:|---:|",
    ]
    for year in YEARS:
        y = results["years"][str(year)]
        lines.append(
            f"| {year} | {results['snapshots'][str(year)]} | {y['n_topics']} | {y['n_collection']} | {y['pct6']} |"
        )
    lines += [
        "",
        "## Recall of eligible trials (label 2), keywords + hybrid",
        "",
        "| Year | @10 | @20 | @50 | @100 | @200 | @500 | @6% |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    def pct(x):
        return "n/a" if x is None else f"{x:.1%}"

    for year in YEARS:
        s = results["years"][str(year)]["systems"]["kw_hybrid"]["eligible"]
        p6 = results["years"][str(year)]["pct6"]
        lines.append(
            "| {year} | {a} | {b} | {c} | {d} | {e} | {f} | {g} |".format(
                year=year,
                a=pct(s.get("10")),
                b=pct(s.get("20")),
                c=pct(s.get("50")),
                d=pct(s.get("100")),
                e=pct(s.get("200")),
                f=pct(s.get("500")),
                g=pct(s.get(str(p6))),
            )
        )
    lines += [
        "",
        "## Reproduction checks and gate",
        "",
        f"| Check | Result |",
        f"|---|---|",
        f"| Hybrid beats BM25 and MedCPT | {results['checks']['hybrid_beats_singles']} |",
        f"| Keywords beat raw note | {results['checks']['keywords_beat_raw']} |",
        f"| Eligible recall @ 6% of collection | {results['checks']['eligible_at_6pct']} |",
        "",
        results["checks"]["verdict"],
        "",
        "## Ablations (eligible recall @ 6%)",
        "",
        "| Year | Raw hybrid | KW BM25 | KW MedCPT | KW OpenAI 3-small | KW hybrid | KW hybrid+OpenAI |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for year in YEARS:
        y = results["years"][str(year)]
        p6 = str(y["pct6"])
        syss = y["systems"]

        def g(name):
            return pct(syss.get(name, {}).get("eligible", {}).get(p6))

        lines.append(
            f"| {year} | {g('raw_hybrid')} | {g('kw_bm25')} | {g('kw_medcpt')} | {g('kw_openai')} | {g('kw_hybrid')} | {g('kw_hybrid_openai')} |"
        )
    lines += [
        "",
        "Relevant (labels 1+2) at the same depths is in `data/trec/trec_hybrid_results.json`.",
        "No six-name vocabulary. Steps 6 and 7 not started.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    keywords = load_keywords()
    print("load MedCPT query encoder", flush=True)
    q_tok = AutoTokenizer.from_pretrained(QUERY_ENC)
    q_model = AutoModel.from_pretrained(QUERY_ENC)
    q_model.eval()
    from mini_pilot import load_key

    api_key = load_key()
    oai_cache: dict[str, np.ndarray] = {}
    cache_path = DATA / "openai_query_cache.npz"
    if cache_path.exists():
        blob = np.load(cache_path, allow_pickle=True)
        keys = list(blob["keys"])
        vecs = blob["vecs"]
        oai_cache = {k: vecs[i] for i, k in enumerate(keys)}

    packs = {}
    summaries = {}
    for year in YEARS:
        pack = eval_year(year, keywords, q_model, q_tok)
        finish_openai(pack, api_key, oai_cache)
        summaries[str(year)] = summarise(pack)
        del pack["openai_vecs"], pack["bm25"], pack["chunk_vecs"]
        if oai_cache:
            np.savez(
                cache_path,
                keys=np.array(list(oai_cache.keys()), dtype=object),
                vecs=np.stack(list(oai_cache.values())),
            )

    def eligible6(year: int, system: str) -> float | None:
        y = summaries[str(year)]
        return y["systems"][system]["eligible"].get(str(y["pct6"]))

    hybrid_ok = all(
        (eligible6(y, "kw_hybrid") or 0) > (eligible6(y, "kw_bm25") or 0)
        and (eligible6(y, "kw_hybrid") or 0) > (eligible6(y, "kw_medcpt") or 0)
        for y in YEARS
    )
    kw_ok = all(
        (eligible6(y, "kw_hybrid") or 0) > (eligible6(y, "raw_hybrid") or 0) for y in YEARS
    )
    at6 = {y: eligible6(y, "kw_hybrid") for y in YEARS}
    min6 = min(v for v in at6.values() if v is not None)
    if min6 >= 0.85:
        verdict = "Gate cleared: eligible recall at 6% of collection is in the published league (≥85%)."
        gate = "cleared_85"
    elif min6 >= 0.70:
        verdict = "Between 70% and 85% at 6% of collection. Report the number; not the published 90%."
        gate = "between_70_85"
    else:
        verdict = "STOP: eligible recall at 6% of collection is below 70%. Diagnose before going on."
        gate = "below_70_stop"

    results = {
        "thresholds_commit": THRESHOLDS_COMMIT,
        "collection": "judged_pool",
        "snapshots": {str(y): SNAPSHOT[YEAR_SNAP[y]]["date"] for y in YEARS},
        "rrf_k": RRF_K,
        "chunking": {
            "method": "truncate_512",
            "why": "same as TrialGPT; one [title, body] pair, 512 tokens. Typical trial is 3581 characters so eligibility tail is dropped. Chunking was 2.7 windows/trial and ~5 hours/snapshot on CPU.",
        },
        "medcpt_ood": True,
        "cross_encoder_unused": True,
        "years": summaries,
        "checks": {
            "hybrid_beats_singles": hybrid_ok,
            "keywords_beat_raw": kw_ok,
            "eligible_at_6pct": {str(y): at6[y] for y in YEARS},
            "gate": gate,
            "verdict": verdict,
        },
    }
    OUT.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    write_report(results)
    print(json.dumps(results["checks"], indent=2))
    print("Wrote", OUT)
    print("Wrote", REPORT)
    if not hybrid_ok:
        raise SystemExit("reproduction check failed: hybrid did not beat both singles")
    if not kw_ok:
        raise SystemExit("reproduction check failed: keywords did not beat the raw note")
    if gate == "below_70_stop":
        raise SystemExit("gate failed: eligible recall at 6% below 70%")


if __name__ == "__main__":
    main()
