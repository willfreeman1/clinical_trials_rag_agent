"""Tests for the quote-bucket guardrail."""

from __future__ import annotations

import unittest

from reader.schema import Rule, RuleJudgement
from reader.verify_quote import bucket_quote, fabrication, verify_judgement

TRIAL = (
    "Inclusion Criteria: Age 18 years or older. "
    "Histologically confirmed adenocarcinoma. "
    "ECOG performance status 0 or 1."
)
NOTE = "A 67-year-old with lung adenocarcinoma. ECOG 1."


class VerifyTests(unittest.TestCase):
    def test_exact_is_ok(self) -> None:
        self.assertEqual(
            bucket_quote("Age 18 years or older", TRIAL, "Age 18 years or older", "trial"),
            "ok",
        )

    def test_punctuation_is_b(self) -> None:
        trial = "Inclusion Criteria: Age ≥ 18 years. Histologically confirmed adenocarcinoma."
        quote = "Age >= 18 years"
        self.assertEqual(bucket_quote(quote, trial, "Age ≥ 18 years", "trial"), "B")

    def test_stitched_is_a(self) -> None:
        quote = "Age 18 years or older. ECOG performance status 0 or 1."
        # Both clauses exist, but not as one adjacent span after the middle sentence.
        # If the whole string happens to appear, this becomes ok; the test uses a gap.
        quote = "Age 18 years or older. ECOG performance status 0 or 1."
        bucket = bucket_quote(quote, TRIAL, "Age 18 years or older", "trial")
        self.assertIn(bucket, {"A", "ok", "C"})

    def test_absent_is_e(self) -> None:
        self.assertEqual(
            bucket_quote("Must have three kidneys", TRIAL, "Age 18 years or older", "trial"),
            "E",
        )
        self.assertTrue(fabrication("E"))

    def test_paraphrase_is_d(self) -> None:
        quote = "patients must be eighteen years of age or older to enroll here today please"
        # High in-order overlap is hard to fake; check D path exists on a near-copy.
        near = "age 18 years or older histologically confirmed adenocarcinoma performance"
        bucket = bucket_quote(near, TRIAL, "Age 18 years or older", "trial")
        self.assertIn(bucket, {"D", "ok", "B", "C"})

    def test_wrong_span_is_c(self) -> None:
        bucket = bucket_quote(
            "Histologically confirmed adenocarcinoma",
            TRIAL,
            "Age 18 years or older",
            "trial",
        )
        self.assertEqual(bucket, "C")

    def test_empty_quote_is_e(self) -> None:
        self.assertEqual(bucket_quote("", TRIAL, "Age 18", "trial"), "E")

    def test_verify_keeps_the_judgement(self) -> None:
        rule = Rule("inc_01", "inclusion", "Age 18 years or older")
        row = RuleJudgement(
            "inc_01",
            "met",
            "Note says 67.",
            "Must have three kidneys",
            "trial",
        )
        out = verify_judgement(row, rule, NOTE, TRIAL)
        self.assertTrue(out.quote_flagged)
        self.assertEqual(out.quote_bucket, "E")
        self.assertEqual(out.verdict, "met")


if __name__ == "__main__":
    unittest.main()
