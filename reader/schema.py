"""Fixed-shape records for one rule and one trial.

Verdict polarity, stated once:

- On an inclusion rule, met means the patient satisfies the
  requirement. not_met means they fail it.
- On an exclusion rule, met means the excluded condition is
  present, so this rule would keep the patient out. not_met
  means the excluded condition is absent.
- not_enough_information means the note does not settle it.

The system does not say a patient qualifies.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

VERDICTS = ("met", "not_met", "not_enough_information")
SECTIONS = ("inclusion", "exclusion", "unsplit")
QUOTE_SOURCES = ("patient", "trial")
# A stitched, B whitespace/punct, C wrong-span (in source, not this rule),
# D paraphrased, E absent. ok is a real span of the named source.
BUCKETS = ("ok", "A", "B", "C", "D", "E")
TRIAL_LABELS = ("joinable", "excluded", "uncertain")


class SchemaError(ValueError):
    pass


@dataclass(frozen=True)
class Rule:
    rule_id: str
    section: str
    text: str

    def __post_init__(self) -> None:
        if self.section not in SECTIONS:
            raise SchemaError(f"bad section {self.section!r}")
        if not self.rule_id or not self.text.strip():
            raise SchemaError("rule_id and text are required")


@dataclass
class RuleJudgement:
    rule_id: str
    verdict: str
    explanation: str
    quote: str
    quote_source: str
    quote_bucket: str = "E"
    quote_flagged: bool = True

    def __post_init__(self) -> None:
        if self.verdict not in VERDICTS:
            raise SchemaError(f"bad verdict {self.verdict!r}")
        if self.quote_source not in QUOTE_SOURCES:
            raise SchemaError(f"bad quote_source {self.quote_source!r}")
        if self.quote_bucket not in BUCKETS:
            raise SchemaError(f"bad quote_bucket {self.quote_bucket!r}")


@dataclass
class TrialRead:
    patient_id: str
    nct_id: str
    rules: list[RuleJudgement] = field(default_factory=list)
    raw_model_output: str = ""
    retries: int = 0
    schema_ok: bool = False
    missing_rule_ids: list[str] = field(default_factory=list)
    aggregates: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def parse_model_rules(payload: object, expected_ids: set[str]) -> list[dict]:
    """Accept only a JSON object with a rules array. Raise SchemaError."""
    if not isinstance(payload, dict):
        raise SchemaError("model output is not a JSON object")
    rules = payload.get("rules")
    if not isinstance(rules, list) or not rules:
        raise SchemaError("rules must be a non-empty array")
    out = []
    seen: set[str] = set()
    for i, row in enumerate(rules):
        if not isinstance(row, dict):
            raise SchemaError(f"rules[{i}] is not an object")
        rid = str(row.get("rule_id") or "").strip()
        verdict = str(row.get("verdict") or "").strip().lower().replace(" ", "_")
        if verdict in {"not_met", "notmet", "failed"}:
            verdict = "not_met"
        elif verdict in {"met", "satisfied"}:
            verdict = "met"
        elif verdict in {
            "not_enough_information",
            "not_enough_info",
            "unknown",
            "unsure",
            "nei",
        }:
            verdict = "not_enough_information"
        source = str(row.get("quote_source") or "").strip().lower()
        if source not in QUOTE_SOURCES:
            raise SchemaError(f"rules[{i}] quote_source must be patient or trial")
        if not rid:
            raise SchemaError(f"rules[{i}] missing rule_id")
        if rid not in expected_ids:
            raise SchemaError(f"rules[{i}] unexpected rule_id {rid!r}")
        if rid in seen:
            raise SchemaError(f"duplicate rule_id {rid!r}")
        if verdict not in VERDICTS:
            raise SchemaError(f"rules[{i}] bad verdict {verdict!r}")
        explanation = str(row.get("explanation") or "").strip()
        quote = str(row.get("quote") or "")
        if verdict != "not_enough_information" and not quote.strip():
            raise SchemaError(f"rules[{i}] {rid} needs a quote")
        if verdict != "not_enough_information" and not explanation:
            raise SchemaError(f"rules[{i}] {rid} needs an explanation")
        seen.add(rid)
        out.append(
            {
                "rule_id": rid,
                "verdict": verdict,
                "explanation": explanation,
                "quote": quote,
                "quote_source": source,
            }
        )
    return out
