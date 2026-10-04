"""Tests for schema validation and retries."""

from __future__ import annotations

import json
import unittest

from reader.judge import read_trial
from reader.schema import SchemaError, parse_model_rules


EXPECTED = {"inc_01", "exc_01"}


class SchemaTests(unittest.TestCase):
    def test_happy(self) -> None:
        rows = parse_model_rules(
            {
                "rules": [
                    {
                        "rule_id": "inc_01",
                        "verdict": "met",
                        "explanation": "Age 67.",
                        "quote": "67-year-old",
                        "quote_source": "patient",
                    },
                    {
                        "rule_id": "exc_01",
                        "verdict": "not_met",
                        "explanation": "No pregnancy mentioned.",
                        "quote": "Exclusion: pregnant",
                        "quote_source": "trial",
                    },
                ]
            },
            EXPECTED,
        )
        self.assertEqual(len(rows), 2)

    def test_rejects_unknown_rule(self) -> None:
        with self.assertRaises(SchemaError):
            parse_model_rules(
                {
                    "rules": [
                        {
                            "rule_id": "inc_99",
                            "verdict": "met",
                            "explanation": "x",
                            "quote": "y",
                            "quote_source": "patient",
                        }
                    ]
                },
                EXPECTED,
            )

    def test_met_requires_quote(self) -> None:
        with self.assertRaises(SchemaError):
            parse_model_rules(
                {
                    "rules": [
                        {
                            "rule_id": "inc_01",
                            "verdict": "met",
                            "explanation": "x",
                            "quote": "",
                            "quote_source": "patient",
                        }
                    ]
                },
                {"inc_01"},
            )

    def test_retry_then_ok(self) -> None:
        replies = [
            "not json",
            json.dumps(
                {
                    "rules": [
                        {
                            "rule_id": "inc_01",
                            "verdict": "met",
                            "explanation": "Note says 67.",
                            "quote": "67-year-old",
                            "quote_source": "patient",
                        }
                    ]
                }
            ),
        ]

        def complete(_system: str, _user: str) -> str:
            if not replies:
                raise AssertionError("complete called too many times")
            return replies.pop(0)

        result = read_trial(
            "1",
            "NCT0",
            "A 67-year-old with lung cancer.",
            "A trial",
            "Inclusion Criteria\n- Age 18 years or older\nExclusion Criteria\n- Pregnant patients must not enroll\n",
            complete,
        )
        self.assertTrue(result.schema_ok)
        self.assertEqual(result.retries, 1)
        self.assertEqual(result.rules[0].verdict, "met")

    def test_omitted_rule_filled_nei(self) -> None:
        def complete(_system: str, _user: str) -> str:
            return json.dumps(
                {
                    "rules": [
                        {
                            "rule_id": "inc_01",
                            "verdict": "met",
                            "explanation": "Note says 67.",
                            "quote": "67-year-old",
                            "quote_source": "patient",
                        }
                    ]
                }
            )

        result = read_trial(
            "1",
            "NCT0",
            "A 67-year-old with lung cancer.",
            "A trial",
            "Inclusion Criteria\n- Age 18 years or older\nExclusion Criteria\n- Pregnant patients must not enroll\n",
            complete,
        )
        self.assertIn("exc_01", result.missing_rule_ids)
        missing = [r for r in result.rules if r.rule_id == "exc_01"][0]
        self.assertEqual(missing.verdict, "not_enough_information")


if __name__ == "__main__":
    unittest.main()
