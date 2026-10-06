"""HTTP service for the seed demo.

Replay mode is the default and is named on every response.
The system does not say a patient qualifies.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from service.backend import complete_from_env, mode_from_env  # noqa: E402
from service.load_seed import ensure_schema, load_catalog, seed_postgres, wait_db  # noqa: E402
from service.pipeline import DISCLAIMER, match_patient, resolve_patient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("demo")

STATIC = Path(__file__).resolve().parent / "static"
app = Flask(__name__, static_folder=str(STATIC), static_url_path="/static")
CATALOG = None
COMPLETE = None
MODEL_MODE = "replay"
DB_OK = False
VECTOR_BACKEND = "memory"
DATABASE_URL = ""


def vector_backend_from_env() -> str:
    backend = (os.environ.get("VECTOR_BACKEND") or "memory").strip().lower()
    if backend not in {"memory", "pgvector"}:
        raise RuntimeError("VECTOR_BACKEND must be 'memory' or 'pgvector'")
    return backend


def boot() -> None:
    global CATALOG, COMPLETE, MODEL_MODE, DB_OK, VECTOR_BACKEND, DATABASE_URL
    CATALOG = load_catalog()
    MODEL_MODE, COMPLETE = complete_from_env(CATALOG.reads)
    VECTOR_BACKEND = vector_backend_from_env()
    DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip()
    if VECTOR_BACKEND == "pgvector" and not DATABASE_URL:
        raise RuntimeError("VECTOR_BACKEND=pgvector requires DATABASE_URL")
    if DATABASE_URL:
        conn = wait_db(DATABASE_URL)
        ensure_schema(conn)
        seed_postgres(conn, CATALOG)
        conn.close()
        DB_OK = True
    else:
        DB_OK = False
    if VECTOR_BACKEND == "pgvector" and not DB_OK:
        raise RuntimeError("VECTOR_BACKEND=pgvector requires an available database")
    log.info(
        "ready mode=%s vector_backend=%s patients=%s trials=%s db=%s",
        MODEL_MODE,
        VECTOR_BACKEND,
        len(CATALOG.patients),
        len(CATALOG.trials),
        DB_OK,
    )


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/health")
def health():
    return jsonify(
        {
            "ok": True,
            "model_mode": MODEL_MODE,
            "database": "up" if DB_OK else "memory_only",
            "vector_backend": VECTOR_BACKEND,
            "n_patients": len(CATALOG.patients) if CATALOG else 0,
            "n_trials": len(CATALOG.trials) if CATALOG else 0,
            "disclaimer": DISCLAIMER,
        }
    )


@app.get("/v1/patients")
def patients():
    if CATALOG is None:
        return jsonify({"error": "catalog not loaded", "model_mode": MODEL_MODE}), 503
    rows = []
    for p in CATALOG.patients.values():
        rows.append(
            {
                "patient_id": p.patient_id,
                "summary": p.summary,
                "note": p.note,
                "first_line": (p.note.split("\n")[0])[:160],
            }
        )
    return jsonify(
        {
            "model_mode": MODEL_MODE,
            "vector_backend": VECTOR_BACKEND,
            "patients": rows,
            "disclaimer": DISCLAIMER,
        }
    )


@app.post("/v1/match")
def match():
    t0 = time.perf_counter()
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "body must be a JSON object", "model_mode": MODEL_MODE}), 400
    pid = body.get("patient_id")
    note = body.get("note")
    if pid is not None and not isinstance(pid, str):
        return jsonify({"error": "patient_id must be a string", "model_mode": MODEL_MODE}), 400
    if note is not None and not isinstance(note, str):
        return jsonify({"error": "note must be a string", "model_mode": MODEL_MODE}), 400
    if not pid and not note:
        return jsonify({"error": "send patient_id or note", "model_mode": MODEL_MODE}), 400
    depth = body.get("depth", 10)
    if not isinstance(depth, int) or depth < 1 or depth > 25:
        return jsonify({"error": "depth must be an integer from 1 to 25", "model_mode": MODEL_MODE}), 400
    if CATALOG is None:
        return jsonify({"error": "catalog not loaded", "model_mode": MODEL_MODE}), 503
    try:
        patient = resolve_patient(CATALOG, pid, note)
    except KeyError as exc:
        return jsonify({"error": str(exc), "model_mode": MODEL_MODE}), 404
    try:
        payload = match_patient(
            CATALOG,
            patient,
            COMPLETE,
            MODEL_MODE,
            depth=depth,
            vector_backend=VECTOR_BACKEND,
            database_url=DATABASE_URL,
        )
    except Exception as exc:
        log.exception("match failed")
        return jsonify({"error": str(exc), "model_mode": MODEL_MODE}), 502
    payload["disclaimer"] = DISCLAIMER
    ms = round((time.perf_counter() - t0) * 1000, 1)
    log.info(
        "match patient=%s mode=%s n=%s total_ms=%s stages=%s",
        patient.patient_id,
        MODEL_MODE,
        len(payload.get("results") or []),
        ms,
        payload.get("timings"),
    )
    return jsonify(payload)


def main() -> None:
    boot()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT") or 8000), debug=False)


if __name__ == "__main__":
    main()
else:
    boot()
