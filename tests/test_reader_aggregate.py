"""Tests for the three aggregation rules."""

from __future__ import annotations

import unittest

from reader.aggregate import aggregate
from reader.schema import Rule, RuleJudgement


def row(rid: str, verdict: str) -> RuleJudgement:
    return RuleJudgement(rid, verdict, "x", "quote", "trial", quote_bucket="ok", quote_flagged=False)


class AggregateTests(unittest.TestCase):
    def test_all_met_is_joinable_on_both(self) -> None:
        rules = [
            Rule("inc_01", "inclusion", "Age 18"),
            Rule("exc_01", "exclusion", "Pregnant"),
        ]
        rows = [row("inc_01", "met"), row("exc_01", "not_met")]
        out = aggregate(rows, rules)
        self.assertEqual(out["any_hard_fail"], "joinable")
        self.assertEqual(out["net_balance"], "joinable")
        self.assertEqual(out["compatible_unless_contradicted"], "compatible")
        self.assertGreater(out["score_any_hard_fail"], 0.9)
        self.assertGreater(out["score_net"], 0.5)
        self.assertGreater(out["score_compatible"], 0.5)

    def test_exclusion_fire_excludes_both(self) -> None:
        rules = [
            Rule("inc_01", "inclusion", "Age 18"),
            Rule("exc_01", "exclusion", "Prior immunotherapy"),
        ]
        rows = [row("inc_01", "met"), row("exc_01", "met")]
        out = aggregate(rows, rules)
        self.assertEqual(out["any_hard_fail"], "excluded")
        self.assertEqual(out["net_balance"], "excluded")
        self.assertEqual(out["compatible_unless_contradicted"], "excluded")
        self.assertEqual(out["score_any_hard_fail"], 0.0)
        self.assertLess(out["score_compatible"], 0.1)

    def test_failed_inclusion_excludes_hard_fail(self) -> None:
        rules = [Rule("inc_01", "inclusion", "Must have EGFR")]
        rows = [row("inc_01", "not_met")]
        out = aggregate(rows, rules)
        self.assertEqual(out["any_hard_fail"], "excluded")
        self.assertEqual(out["net_balance"], "excluded")

    def test_nei_is_uncertain_when_nothing_fails(self) -> None:
        rules = [
            Rule("inc_01", "inclusion", "Age 18"),
            Rule("inc_02", "inclusion", "Creatinine clearance >= 60"),
        ]
        rows = [row("inc_01", "met"), row("inc_02", "not_enough_information")]
        out = aggregate(rows, rules)
        self.assertEqual(out["any_hard_fail"], "uncertain")
        self.assertEqual(out["net_balance"], "uncertain")
        self.assertEqual(out["compatible_unless_contradicted"], "compatible")
        self.assertGreater(out["score_compatible"], 0.5)

    def test_all_nei_is_compatible_and_neutral(self) -> None:
        rules = [Rule("inc_01", "inclusion", "Age 18"), Rule("exc_01", "exclusion", "X")]
        rows = [
            row("inc_01", "not_enough_information"),
            row("exc_01", "not_enough_information"),
        ]
        out = aggregate(rows, rules)
        self.assertEqual(out["compatible_unless_contradicted"], "compatible")
        self.assertAlmostEqual(out["score_compatible"], 0.5)

    def test_unsplit_not_met_is_a_contradiction(self) -> None:
        rules = [Rule("u_01", "unsplit", "Must not be pregnant")]
        rows = [row("u_01", "not_met")]
        out = aggregate(rows, rules)
        self.assertEqual(out["any_hard_fail"], "excluded")
        self.assertEqual(out["compatible_unless_contradicted"], "excluded")

    def test_majority_inclusions_fail_excludes_net_only(self) -> None:
        rules = [
            Rule("inc_01", "inclusion", "A"),
            Rule("inc_02", "inclusion", "B"),
            Rule("inc_03", "inclusion", "C"),
            Rule("exc_01", "exclusion", "X"),
        ]
        rows = [
            row("inc_01", "not_met"),
            row("inc_02", "not_met"),
            row("inc_03", "met"),
            row("exc_01", "not_met"),
        ]
        out = aggregate(rows, rules)
        self.assertEqual(out["any_hard_fail"], "excluded")
        self.assertEqual(out["net_balance"], "excluded")


if __name__ == "__main__":
    unittest.main()
