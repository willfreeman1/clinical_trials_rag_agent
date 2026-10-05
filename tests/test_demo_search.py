"""Fusion and lexical search, no database."""

from __future__ import annotations

import unittest

from service.search import BM25, rrf, tokenize


class SearchTests(unittest.TestCase):
    def test_tokenize(self) -> None:
        self.assertEqual(tokenize("EGFR-positive NSCLC"), ["egfr", "positive", "nsclc"])

    def test_bm25_puts_the_matching_trial_first(self) -> None:
        index = BM25(
            [
                ("NCT1", "atopic dermatitis eczema rash in a child"),
                ("NCT2", "knee osteoarthritis older adult"),
            ]
        )
        hits = index.query("child eczema rash")
        self.assertEqual(hits[0][0], "NCT1")

    def test_rrf_merges_two_lists(self) -> None:
        a = [("NCT1", 1.0), ("NCT2", 0.5)]
        b = [("NCT2", 1.0), ("NCT3", 0.2)]
        fused = rrf([a, b])
        ids = [n for n, _ in fused]
        self.assertIn("NCT2", ids)
        self.assertEqual(len(ids), 3)


if __name__ == "__main__":
    unittest.main()
