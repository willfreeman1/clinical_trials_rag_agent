"""One patient note through search, fusion, ranking, split, read, verify.

In replay mode the model replies are stored. Search, fusion, ranking,
rule splitting, quote checks, and combination still run.
The system does not say a patient qualifies.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from reader.aggregate import aggregate
from reader.judge import read_trial
from reader.split_rules import split_rules
from service.backend import ReplayComplete, ReplayMiss
from service.search import BM25, rrf, vector_search, vector_search_pg


DISCLAIMER = (
    "This system does not say a patient qualifies. It returns ranked "
    "candidates and the criterion text a person must check."
)

LABEL_NAME = {2: "joinable", 1: "excluded", 0: "irrelevant"}


@dataclass
class TrialRec:
    nct_id: str
    title: str
    conditions: list[str]
    eligibility: str
    summary: str
    overall_status: str
    phase: str
    location: str
    embedding: list[float]
    splitter_mode: str = ""


@dataclass
class PatientRec:
    patient_id: str
    note: str
    keywords: list[str]
    summary: str
    query_embedding: list[float]


class Catalog:
    def __init__(
        self,
        trials: list[TrialRec],
        patients: list[PatientRec],
        qrels: dict[tuple[str, str], int],
        scores: dict[tuple[str, str], float],
        reads: dict[tuple[str, str], str],
    ) -> None:
        self.trials = {t.nct_id: t for t in trials}
        self.patients = {p.patient_id: p for p in patients}
        self.qrels = qrels
        self.scores = scores
        self.reads = reads
        docs = [
            (
                t.nct_id,
                " ".join(
                    [
                        t.title,
                        " ".join(t.conditions),
                        t.eligibility,
                        t.summary,
                    ]
                ),
            )
            for t in trials
        ]
        self.bm25 = BM25(docs)
        self.emb_ids = [t.nct_id for t in trials]
        self.emb_mat = [t.embedding for t in trials]


def resolve_patient(catalog: Catalog, patient_id: str | None, note: str | None) -> PatientRec:
    if patient_id and patient_id in catalog.patients:
        return catalog.patients[patient_id]
    if note:
        want = " ".join(note.split())
        for p in catalog.patients.values():
            if " ".join(p.note.split()) == want:
                return p
    raise KeyError("unknown patient; replay mode only serves the three seed notes")


def match_patient(
    catalog: Catalog,
    patient: PatientRec,
    complete,
    model_mode: str,
    depth: int = 10,
    vector_backend: str = "memory",
    database_url: str | None = None,
) -> dict:
    t0 = time.perf_counter()
    timings: dict[str, float] = {}

    s0 = time.perf_counter()
    rankings = [catalog.bm25.query(kw, k=40) for kw in patient.keywords if kw.strip()]
    if not rankings:
        rankings = [catalog.bm25.query(patient.note, k=40)]
    active_vector_backend = "none"
    if patient.query_embedding:
        if vector_backend == "pgvector":
            if not database_url:
                raise RuntimeError("VECTOR_BACKEND=pgvector requires DATABASE_URL")
            rankings.append(vector_search_pg(patient.query_embedding, database_url, k=40))
            active_vector_backend = "pgvector"
        else:
            rankings.append(vector_search(patient.query_embedding, catalog.emb_ids, catalog.emb_mat, k=40))
            active_vector_backend = "memory"
    fused = rrf(rankings)
    timings["search_ms"] = round((time.perf_counter() - s0) * 1000, 1)

    s1 = time.perf_counter()
    def rank_key(item: tuple[str, float]) -> tuple[float, float]:
        nct, rrf_s = item
        topical = catalog.scores.get((patient.patient_id, nct))
        # Stored topical score first when we have it; fusion score breaks ties.
        return (topical if topical is not None else -1.0, rrf_s)

    ordered = sorted(fused, key=rank_key, reverse=True)
    timings["rank_ms"] = round((time.perf_counter() - s1) * 1000, 1)

    s2 = time.perf_counter()
    results = []
    for nct, rrf_s in ordered[:depth]:
        trial = catalog.trials[nct]
        rules = split_rules(trial.eligibility)
        read = None
        read_error = None
        try:
            fn = complete
            if isinstance(complete, ReplayComplete):
                fn = complete.bind(patient.patient_id, nct)
            read = read_trial(
                patient.patient_id,
                nct,
                patient.note,
                trial.title,
                trial.eligibility,
                fn,
            )
        except ReplayMiss:
            read_error = "no stored reader reply for this pair"
            read = None
        except Exception as exc:
            read_error = str(exc)
            read = None
        gold = catalog.qrels.get((patient.patient_id, nct))
        agg = read.aggregates if read else aggregate([], rules)
        split_by_id = {rule.rule_id: rule for rule in rules}
        results.append(
            {
                "nct_id": nct,
                "title": trial.title,
                "conditions": trial.conditions,
                "overall_status": trial.overall_status,
                "phase": trial.phase,
                "location": trial.location,
                "splitter_mode": trial.splitter_mode or None,
                "n_rules": len(rules),
                "rrf": round(rrf_s, 6),
                "topical_score": catalog.scores.get((patient.patient_id, nct)),
                "expert_verdict": LABEL_NAME.get(gold) if gold is not None else None,
                "expert_label": gold,
                "criteria": [
                    {
                        "rule_id": rule.rule_id,
                        "section": rule.section,
                        "text": rule.text,
                    }
                    for rule in rules
                ],
                "reader": None
                if read is None
                else {
                    "schema_ok": read.schema_ok,
                    "compatible_unless_contradicted": agg.get("compatible_unless_contradicted"),
                    "any_hard_fail": agg.get("any_hard_fail"),
                    "score_compatible": agg.get("score_compatible"),
                    "rules": [
                        {
                            "rule_id": r.rule_id,
                            "section": split_by_id[r.rule_id].section if r.rule_id in split_by_id else "unsplit",
                            "text": split_by_id[r.rule_id].text if r.rule_id in split_by_id else "",
                            "verdict": r.verdict,
                            "explanation": r.explanation,
                            "quote": r.quote,
                            "quote_source": r.quote_source,
                            "quote_bucket": r.quote_bucket,
                            "quote_flagged": r.quote_flagged,
                        }
                        for r in read.rules
                    ],
                },
                "reader_error": read_error,
            }
        )
    timings["read_ms"] = round((time.perf_counter() - s2) * 1000, 1)
    timings["total_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return {
        "patient_id": patient.patient_id,
        "model_mode": model_mode,
        "vector_backend": active_vector_backend,
        "disclaimer": DISCLAIMER,
        "n_retrieved": len(fused),
        "results": results,
        "timings": timings,
    }
