"""Tests for schema validation and retries."""

from __future__ import annotations

import json
import unittest

from reader.judge import read_trial
from reader.prompt import retry_message
from reader.schema import SchemaError, list_schema_problems, parse_model_rules


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

    def test_not_met_requires_quote(self) -> None:
        with self.assertRaises(SchemaError) as ctx:
            parse_model_rules(
                {
                    "rules": [
                        {
                            "rule_id": "inc_01",
                            "verdict": "not_met",
                            "explanation": "Note never mentions an adnexal mass.",
                            "quote": "",
                            "quote_source": "trial",
                        }
                    ]
                },
                {"inc_01"},
            )
        self.assertIn("needs a quote", str(ctx.exception))

    def test_lists_every_schema_problem(self) -> None:
        problems = list_schema_problems(
            {
                "rules": [
                    {
                        "rule_id": "inc_01",
                        "verdict": "not_met",
                        "explanation": "Silent note.",
                        "quote": "",
                        "quote_source": "trial",
                    },
                    {
                        "rule_id": "exc_99",
                        "verdict": "met",
                        "explanation": "x",
                        "quote": "y",
                        "quote_source": "",
                    },
                ]
            },
            EXPECTED,
        )
        self.assertTrue(any("needs a quote" in p for p in problems))
        self.assertTrue(any("quote_source" in p for p in problems))

    def test_retry_does_not_paste_previous_json(self) -> None:
        previous = '{"rules": [{"rule_id": "inc_01", "verdict": "not_met", "quote": ""}]}'
        text = retry_message("rules[0] inc_01 needs a quote", previous)
        self.assertNotIn(previous, text)
        self.assertIn("needs a quote", text)
        self.assertIn("not_enough_information", text)

    def test_one_repair_then_give_up(self) -> None:
        calls = []

        def complete(_system: str, user: str) -> str:
            calls.append(user)
            return "not json"

        result = read_trial(
            "1",
            "NCT0",
            "A 67-year-old with lung cancer.",
            "A trial",
            "Inclusion Criteria\n- Age 18 years or older\nExclusion Criteria\n- Pregnant patients must not enroll\n",
            complete,
        )
        self.assertFalse(result.schema_ok)
        self.assertEqual(result.retries, 1)
        self.assertEqual(len(calls), 2)
        self.assertNotIn("not json", calls[1])
        self.assertIn("does not parse", result.schema_error)

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
