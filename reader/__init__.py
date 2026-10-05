"""Rule-by-rule eligibility reader.

For one patient note and one trial, split the criteria into rules,
judge each one, verify the quote, and combine the verdicts. The
system does not say a patient qualifies. A human still has to read
the criteria.
"""

from reader.aggregate import aggregate, score_any_hard_fail, score_compatible, score_net
from reader.judge import read_trial
from reader.schema import Rule, RuleJudgement, TrialRead
from reader.split_rules import split_rules
from reader.verify_quote import bucket_quote, verify_judgement

__all__ = [
    "Rule",
    "RuleJudgement",
    "TrialRead",
    "aggregate",
    "bucket_quote",
    "read_trial",
    "score_any_hard_fail",
    "score_compatible",
    "score_net",
    "split_rules",
    "verify_judgement",
]
