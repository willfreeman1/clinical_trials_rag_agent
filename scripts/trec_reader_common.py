"""Paths and constants for the TREC rule-by-rule reader.

Design is locked in trec_reader_config.json before any score exists.
No pass/fail threshold. 2022 only. Top 25 of the topical slice.
The system does not say a patient qualifies.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
DATA = ROOT / "data" / "trec"

CONFIG = HERE / "trec_reader_config.json"
PAIRS = HERE / "trec_reader_pairs.json"
PROBE_PAIRS = HERE / "trec_reader_probe_pairs.json"
READS = DATA / "trec_reader_reads.jsonl"
PROBE_READS = DATA / "trec_reader_probe_reads.jsonl"
RESULTS = DATA / "trec_reader_results.json"
WILL_SAMPLE = ROOT / "docs" / "trec_reader_will_check.md"
REPORT = ROOT / "docs" / "trec_reader.md"

YEAR = 2022
CUTOFF = 25
ARM = "topical_title_cond_slice"
MODEL = "Qwen/Qwen2.5-7B-Instruct"
FABRICATION_REFERENCE = 0.05
