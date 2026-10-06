"""Observability wiring tests with no external collector required."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from service.backend import ReplayComplete
from service.load_seed import load_catalog
from service.observability import NoopObs, obs_from_env
from service.pipeline import match_patient

SEED = Path(__file__).resolve().parents[1] / "demo" / "seed"


class _Span:
    def __init__(self, bucket: list[tuple[str, dict]]) -> None:
        self.bucket = bucket

    def start_span(self, name: str, input=None, metadata=None):  # noqa: ANN001
        self.bucket.append((f"start:{name}", metadata or {}))
        return _Span(self.bucket)

    def event(self, name: str, metadata=None):  # noqa: ANN001
        self.bucket.append((f"event:{name}", metadata or {}))

    def end(self, output=None, metadata=None):  # noqa: ANN001
        self.bucket.append(("end", {"output": output, "metadata": metadata or {}}))


class ObsConfigTests(unittest.TestCase):
    def test_obs_defaults_to_noop(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            obs = obs_from_env()
        self.assertIsInstance(obs, NoopObs)
        self.assertFalse(obs.enabled)

    def test_obs_enabled_without_keys_is_noop(self) -> None:
        with patch.dict(os.environ, {"LANGFUSE_ENABLED": "true"}, clear=True):
            obs = obs_from_env()
        self.assertIsInstance(obs, NoopObs)
        self.assertIn("missing", obs.reason)


@unittest.skipUnless((SEED / "embeddings.npz").exists(), "demo seed not built")
class ObsPipelineTests(unittest.TestCase):
    def test_pipeline_emits_observability_events(self) -> None:
        catalog = load_catalog(SEED)
        patient = catalog.patients["1"]
        complete = ReplayComplete(catalog.reads)
        events: list[tuple[str, dict]] = []
        root = _Span(events)
        out = match_patient(catalog, patient, complete, "replay", depth=5, obs=root)
        self.assertGreaterEqual(len(out["results"]), 1)
        names = [name for name, _ in events]
        self.assertIn("event:search_completed", names)
        self.assertIn("event:rank_completed", names)
        self.assertIn("event:quote_verification", names)


if __name__ == "__main__":
    unittest.main()
