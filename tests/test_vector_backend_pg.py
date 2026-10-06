"""Integration test for pgvector retrieval path on the demo seed."""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from service.backend import ReplayComplete
from service.load_seed import ensure_schema, load_catalog, seed_postgres, wait_db
from service.pipeline import match_patient

SEED = Path(__file__).resolve().parents[1] / "demo" / "seed"


@unittest.skipUnless((SEED / "embeddings.npz").exists(), "demo seed not built")
class PgVectorBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.url = (os.environ.get("DATABASE_URL") or "").strip()
        if not cls.url:
            raise unittest.SkipTest("DATABASE_URL not set")
        cls.catalog = load_catalog(SEED)
        conn = wait_db(cls.url, tries=10, delay=1.0)
        ensure_schema(conn)
        seed_postgres(conn, cls.catalog)
        conn.close()

    def test_pgvector_backend_returns_ranked_results(self) -> None:
        patient = self.catalog.patients["1"]
        complete = ReplayComplete(self.catalog.reads)
        out = match_patient(
            self.catalog,
            patient,
            complete,
            "replay",
            depth=8,
            vector_backend="pgvector",
            database_url=self.url,
        )
        self.assertEqual(out["vector_backend"], "pgvector")
        self.assertGreaterEqual(len(out["results"]), 3)

    def test_pgvector_requires_database_url(self) -> None:
        patient = self.catalog.patients["1"]
        complete = ReplayComplete(self.catalog.reads)
        with self.assertRaises(RuntimeError):
            match_patient(
                self.catalog,
                patient,
                complete,
                "replay",
                depth=3,
                vector_backend="pgvector",
                database_url="",
            )


if __name__ == "__main__":
    unittest.main()
