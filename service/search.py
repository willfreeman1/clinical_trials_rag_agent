"""Lexical search, vector search, and reciprocal rank fusion.

These run for real in replay mode. They do not call a model.
The system does not say a patient qualifies.
"""

from __future__ import annotations

import math
import re
from importlib import import_module
from collections import defaultdict

TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return TOKEN.findall((text or "").lower())


class BM25:
    def __init__(self, docs: list[tuple[str, str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.ids = [nct for nct, _ in docs]
        tokenized = [tokenize(text) for _, text in docs]
        self.doc_len = [len(toks) or 1 for toks in tokenized]
        self.avgdl = sum(self.doc_len) / max(len(self.doc_len), 1)
        df: dict[str, int] = defaultdict(int)
        self.tf: list[dict[str, int]] = []
        for toks in tokenized:
            counts: dict[str, int] = defaultdict(int)
            for t in toks:
                counts[t] += 1
            self.tf.append(counts)
            for t in counts:
                df[t] += 1
        n = max(len(docs), 1)
        self.idf = {t: math.log((n - c + 0.5) / (c + 0.5) + 1.0) for t, c in df.items()}

    def query(self, text: str, k: int = 50) -> list[tuple[str, float]]:
        q = tokenize(text)
        if not q:
            return []
        scores: dict[str, float] = {}
        for i, nct in enumerate(self.ids):
            s = 0.0
            dl = self.doc_len[i]
            freq = self.tf[i]
            for t in q:
                if t not in freq:
                    continue
                tf = freq[t]
                idf = self.idf.get(t, 0.0)
                s += idf * (tf * (self.k1 + 1)) / (tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
            if s:
                scores[nct] = s
        return sorted(scores.items(), key=lambda kv: -kv[1])[:k]


def cosine(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a)) or 1.0
    db = math.sqrt(sum(y * y for y in b)) or 1.0
    return num / (da * db)


def vector_search(
    query: list[float],
    ids: list[str],
    matrix: list[list[float]],
    k: int = 50,
) -> list[tuple[str, float]]:
    scored = [(nct, cosine(query, row)) for nct, row in zip(ids, matrix)]
    scored.sort(key=lambda kv: -kv[1])
    return scored[:k]


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.7f}" for v in values) + "]"


def vector_search_pg(
    query: list[float],
    database_url: str,
    k: int = 50,
) -> list[tuple[str, float]]:
    """Return nearest trials using pgvector cosine distance."""
    psycopg = import_module("psycopg")

    if not query:
        return []
    vec = _vector_literal(query)
    sql = """
        SELECT nct_id, embedding <=> %s::vector AS dist
        FROM trials
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector ASC
        LIMIT %s
    """
    with psycopg.connect(database_url, connect_timeout=5) as conn:
        rows = conn.execute(sql, (vec, vec, k)).fetchall()
    # Convert distance (lower is better) to a bounded similarity for RRF tie clarity.
    return [(str(nct), 1.0 / (1.0 + float(dist))) for nct, dist in rows]


def rrf(rankings: list[list[tuple[str, float]]], k: int = 60) -> list[tuple[str, float]]:
    fused: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, (nct, _s) in enumerate(ranking, start=1):
            fused[nct] += 1.0 / (k + rank)
    return sorted(fused.items(), key=lambda kv: -kv[1])
