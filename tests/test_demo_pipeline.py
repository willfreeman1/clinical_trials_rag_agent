"""Replay pipeline on the committed seed. No GPU."""

from __future__ import annotations

import unittest
from pathlib import Path

from service.backend import ReplayComplete, mode_from_env
from service.load_seed import load_catalog
from service.pipeline import match_patient

SEED = Path(__file__).resolve().parents[1] / "demo" / "seed"


@unittest.skipUnless((SEED / "embeddings.npz").exists(), "demo seed not built")
class PipelineTests(unittest.TestCase):
    def test_replay_mode_is_the_default(self) -> None:
        self.assertEqual(mode_from_env(), "replay")

    def test_seed_patient_returns_ranked_trials_and_names_the_mode(self) -> None:
        catalog = load_catalog(SEED)
        patient = catalog.patients["1"]
        complete = ReplayComplete(catalog.reads)
        out = match_patient(catalog, patient, complete, "replay", depth=8)
        self.assertEqual(out["model_mode"], "replay")
        self.assertIn("does not say a patient qualifies", out["disclaimer"])
        self.assertGreaterEqual(len(out["results"]), 3)
        labels = {r.get("expert_verdict") for r in out["results"]}
        self.assertTrue(labels & {"joinable", "excluded", "irrelevant"})
        read_ok = [r for r in out["results"] if r.get("reader")]
        self.assertTrue(read_ok)
        quote_rows = [rule for r in read_ok for rule in r["reader"]["rules"] if rule.get("quote")]
        if quote_rows:
            self.assertIn(quote_rows[0]["quote_bucket"], ("ok", "A", "B", "C", "D", "E"))
        first = out["results"][0]
        self.assertTrue(first.get("criteria"))
        self.assertTrue(first["criteria"][0].get("text"))
        self.assertIn(first["criteria"][0]["section"], ("inclusion", "exclusion", "unsplit"))
        if first.get("reader"):
            self.assertTrue(first["reader"]["rules"][0].get("text"))


if __name__ == "__main__":
    unittest.main()
