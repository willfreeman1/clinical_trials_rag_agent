"""Load demo/seed into memory, and into Postgres when a URL is set."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import numpy as np

from service.pipeline import Catalog, PatientRec, TrialRec

ROOT = Path(__file__).resolve().parents[1]
SEED = Path(os.environ.get("SEED_DIR") or ROOT / "demo" / "seed")


def _jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_catalog(seed: Path = SEED) -> Catalog:
    trials_raw = _jsonl(seed / "trials.jsonl")
    patients_raw = json.loads((seed / "patients.json").read_text(encoding="utf-8"))
    emb = np.load(seed / "embeddings.npz", allow_pickle=True)
    nct_ids = [str(x) for x in emb["nct_ids"].tolist()]
    trial_mat = emb["trial"].astype(float).tolist()
    by_nct = {nct: vec for nct, vec in zip(nct_ids, trial_mat)}
    p_ids = [str(x) for x in emb["patient_ids"].tolist()]
    q_mat = emb["query"].astype(float).tolist()
    by_pid = {pid: vec for pid, vec in zip(p_ids, q_mat)}

    trials = [
        TrialRec(
            nct_id=r["nct_id"],
            title=r.get("title") or "",
            conditions=list(r.get("conditions") or []),
            eligibility=r.get("eligibility") or "",
            summary=r.get("summary") or "",
            overall_status=r.get("overall_status") or "",
            phase=r.get("phase") or "",
            location=r.get("location") or "",
            embedding=by_nct.get(r["nct_id"]) or [],
            splitter_mode=r.get("splitter_mode") or "",
        )
        for r in trials_raw
    ]
    patients = [
        PatientRec(
            patient_id=r["patient_id"],
            note=r.get("note") or "",
            keywords=list(r.get("keywords") or []),
            summary=r.get("summary") or "",
            query_embedding=by_pid.get(r["patient_id"]) or [],
        )
        for r in patients_raw
    ]
    qrels = {(r["patient_id"], r["nct_id"]): int(r["label"]) for r in _jsonl(seed / "qrels.jsonl")}
    scores = {
        (r["patient_id"], r["nct_id"]): float(r["topical"]) for r in _jsonl(seed / "scores.jsonl")
    }
    reads = {
        (r["patient_id"], r["nct_id"]): r["raw_model_output"] for r in _jsonl(seed / "reads.jsonl")
    }
    return Catalog(trials, patients, qrels, scores, reads)


def wait_db(url: str, tries: int = 30, delay: float = 2.0):
    import psycopg

    last = None
    for _ in range(tries):
        try:
            conn = psycopg.connect(url, connect_timeout=3)
            conn.execute("SELECT 1")
            return conn
        except Exception as exc:
            last = exc
            time.sleep(delay)
    raise RuntimeError(f"database not ready: {last}")


def ensure_schema(conn) -> None:
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trials (
            nct_id TEXT PRIMARY KEY,
            title TEXT,
            conditions TEXT[],
            eligibility TEXT,
            summary TEXT,
            overall_status TEXT,
            phase TEXT,
            location TEXT,
            splitter_mode TEXT,
            embedding vector(1536)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS patients (
            patient_id TEXT PRIMARY KEY,
            note TEXT,
            keywords TEXT[],
            summary TEXT,
            year INT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS qrels (
            patient_id TEXT,
            nct_id TEXT,
            label INT,
            PRIMARY KEY (patient_id, nct_id)
        )
        """
    )
    conn.commit()


def seed_postgres(conn, catalog: Catalog) -> None:
    n = conn.execute("SELECT COUNT(*) FROM trials").fetchone()[0]
    if n:
        return
    for t in catalog.trials.values():
        vec = t.embedding
        conn.execute(
            """
            INSERT INTO trials (
                nct_id, title, conditions, eligibility, summary,
                overall_status, phase, location, splitter_mode, embedding
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector
            )
            """,
            (
                t.nct_id,
                t.title,
                t.conditions,
                t.eligibility,
                t.summary,
                t.overall_status,
                t.phase,
                t.location,
                t.splitter_mode,
                "[" + ",".join(f"{x:.7f}" for x in vec) + "]" if vec else None,
            ),
        )
    for p in catalog.patients.values():
        conn.execute(
            """
            INSERT INTO patients (patient_id, note, keywords, summary, year)
            VALUES (%s, %s, %s, %s, 2022)
            """,
            (p.patient_id, p.note, p.keywords, p.summary),
        )
    for (pid, nct), lab in catalog.qrels.items():
        conn.execute(
            "INSERT INTO qrels (patient_id, nct_id, label) VALUES (%s, %s, %s)",
            (pid, nct, lab),
        )
    conn.commit()
