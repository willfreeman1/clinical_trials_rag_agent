"""Two ways to turn per-rule verdicts into one trial-level call.

Polarity is in reader.schema. Neither rule says the patient
qualifies. Both produce a label a coordinator can disagree with,
and a number that can be ranked against the 0.779 scorer.

any_hard_fail: one failed inclusion, or one firing exclusion, and
the trial is excluded. Joinable only when every inclusion is met,
no exclusion fires, and nothing is unsettled.

net_balance: the same hard exclusion fire still excludes. Otherwise
the share of settled inclusions that were met is the score. Below
half is excluded; half or more with leftover unknowns is uncertain;
half or more with none unknown is joinable.

If the two rules disagree on the headline, that is the finding.

The system does not say a patient qualifies.
"""

from __future__ import annotations

from reader.schema import Rule, RuleJudgement

HARD_FAIL_EXCLUSION = "met"
HARD_FAIL_INCLUSION = "not_met"


def _section(rule_by_id: dict[str, Rule], row: RuleJudgement) -> str:
    rule = rule_by_id.get(row.rule_id)
    return rule.section if rule else "unsplit"


def _counts(rows: list[RuleJudgement], rule_by_id: dict[str, Rule]) -> dict[str, int]:
    n = {
        "inc_met": 0,
        "inc_not": 0,
        "inc_nei": 0,
        "exc_met": 0,
        "exc_not": 0,
        "exc_nei": 0,
        "u_met": 0,
        "u_not": 0,
        "u_nei": 0,
        "n": len(rows),
    }
    for row in rows:
        sec = _section(rule_by_id, row)
        key = {"inclusion": "inc", "exclusion": "exc"}.get(sec, "u")
        if row.verdict == "met":
            n[f"{key}_met"] += 1
        elif row.verdict == "not_met":
            n[f"{key}_not"] += 1
        else:
            n[f"{key}_nei"] += 1
    return n


def any_hard_fail_label(c: dict[str, int]) -> str:
    if c["exc_met"] or c["inc_not"] or c["u_not"]:
        return "excluded"
    if c["inc_nei"] or c["exc_nei"] or c["u_nei"]:
        return "uncertain"
    return "joinable"


def net_balance_label(c: dict[str, int]) -> str:
    if c["exc_met"]:
        return "excluded"
    settled = c["inc_met"] + c["inc_not"] + c["u_met"] + c["u_not"]
    met = c["inc_met"] + c["u_met"]
    share = met / settled if settled else 0.0
    if share < 0.5 and settled:
        return "excluded"
    if c["inc_nei"] or c["exc_nei"] or c["u_nei"]:
        return "uncertain"
    return "joinable"


def score_any_hard_fail(c: dict[str, int]) -> float:
    """Higher means more joinable. Hard fail is zero."""
    if c["exc_met"] or c["inc_not"] or c["u_not"]:
        return 0.0
    n = max(c["n"], 1)
    nei = c["inc_nei"] + c["exc_nei"] + c["u_nei"]
    return 1.0 - 0.5 * (nei / n)


def score_net(c: dict[str, int]) -> float:
    """(met inclusions − failed inclusions − firing exclusions) / n, shifted to 0–1."""
    n = max(c["n"], 1)
    raw = (c["inc_met"] + c["u_met"]) - (c["inc_not"] + c["u_not"]) - c["exc_met"]
    return (raw / n + 1.0) / 2.0


def aggregate(rows: list[RuleJudgement], rules: list[Rule]) -> dict:
    rule_by_id = {r.rule_id: r for r in rules}
    c = _counts(rows, rule_by_id)
    return {
        "counts": c,
        "any_hard_fail": any_hard_fail_label(c),
        "net_balance": net_balance_label(c),
        "score_any_hard_fail": round(score_any_hard_fail(c), 6),
        "score_net": round(score_net(c), 6),
    }
