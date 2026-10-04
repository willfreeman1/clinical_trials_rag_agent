"""Tests for splitting eligibility prose into rules."""

from __future__ import annotations

import unittest

from reader.split_rules import split_rules

BULLETS = """
Inclusion Criteria

          -  no history of spontaneous puberty

          -  clinical hypogonadism

          -  infantile testes (< 3 ml)

        Exclusion Criteria

          -  Prior therapy with gonadotropins (FSH, hCG, or GnRH)
          -  Pregnant patients
"""

PROSE = """
INCLUSION CRITERIA:
        Males or females who are greater than or equal to 14 years old with
        clinical findings of HH as outlined above will be included.

EXCLUSION CRITERIA:
        Because HH represents a rare condition, patients with other diagnoses
        will not be enrolled.
"""


class SplitTests(unittest.TestCase):
    def test_bullets_keep_section(self) -> None:
        rules = split_rules(BULLETS)
        inc = [r for r in rules if r.section == "inclusion"]
        exc = [r for r in rules if r.section == "exclusion"]
        self.assertGreaterEqual(len(inc), 3)
        self.assertGreaterEqual(len(exc), 2)
        self.assertTrue(any("spontaneous puberty" in r.text for r in inc))
        self.assertTrue(any("gonadotropins" in r.text for r in exc))
        self.assertTrue(all(r.rule_id.startswith("inc_") for r in inc))
        self.assertTrue(all(r.rule_id.startswith("exc_") for r in exc))

    def test_prose_without_bullets(self) -> None:
        rules = split_rules(PROSE)
        self.assertGreaterEqual(len(rules), 2)
        self.assertEqual(rules[0].section, "inclusion")
        self.assertEqual(rules[-1].section, "exclusion")

    def test_empty(self) -> None:
        self.assertEqual(split_rules(""), [])
        self.assertEqual(split_rules("   "), [])

    def test_no_header_is_unsplit(self) -> None:
        rules = split_rules("- Age 18 years or older\n- Written informed consent")
        self.assertEqual(len(rules), 2)
        self.assertTrue(all(r.section == "unsplit" for r in rules))


if __name__ == "__main__":
    unittest.main()
