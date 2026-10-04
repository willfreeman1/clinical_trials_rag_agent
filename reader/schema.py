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
    coerced_to_nei: bool = False

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
    schema_error: str = ""
    missing_rule_ids: list[str] = field(default_factory=list)
    coerced_rule_ids: list[str] = field(default_factory=list)
    aggregates: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _normalise_verdict(verdict: str) -> str:
    verdict = str(verdict or "").strip().lower().replace(" ", "_")
    if verdict in {"not_met", "notmet", "failed"}:
        return "not_met"
    if verdict in {"met", "satisfied"}:
        return "met"
    if verdict in {
        "not_enough_information",
        "not_enough_info",
        "unknown",
        "unsure",
        "nei",
    }:
        return "not_enough_information"
    return verdict


def coerce_absence_row(row: dict) -> dict:
    """Silence is not_enough_information. That is not the quote guardrail.

    A met or not_met with no span cannot be an evidence judgement.
    Convert it to not_enough_information and flag the conversion.
    A quote that exists is still checked against the named source.
    """
    out = dict(row)
    verdict = _normalise_verdict(out.get("verdict"))
    quote = str(out.get("quote") or "")
    source = str(out.get("quote_source") or "").strip().lower()
    if verdict in {"met", "not_met"} and not quote.strip():
        out["verdict"] = "not_enough_information"
        out["coerced_to_nei"] = True
        if source not in QUOTE_SOURCES:
            out["quote_source"] = "trial"
        return out
    out["verdict"] = verdict
    out["coerced_to_nei"] = bool(out.get("coerced_to_nei"))
    if verdict == "not_enough_information" and source not in QUOTE_SOURCES:
        out["quote_source"] = "trial"
    return out


def _row_problem(row: object, i: int, expected_ids: set[str], seen: set[str]) -> str | None:
    if not isinstance(row, dict):
        return f"rules[{i}] is not an object"
    row = coerce_absence_row(row)
    rid = str(row.get("rule_id") or "").strip()
    verdict = _normalise_verdict(str(row.get("verdict") or ""))
    source = str(row.get("quote_source") or "").strip().lower()
    if not rid:
        return f"rules[{i}] missing rule_id"
    if rid not in expected_ids:
        return f"rules[{i}] unexpected rule_id {rid!r}"
    if rid in seen:
        return f"duplicate rule_id {rid!r}"
    if verdict not in VERDICTS:
        return f"rules[{i}] bad verdict {verdict!r}"
    if source not in QUOTE_SOURCES:
        return f"rules[{i}] quote_source must be patient or trial"
    explanation = str(row.get("explanation") or "").strip()
    quote = str(row.get("quote") or "")
    if verdict != "not_enough_information" and not explanation:
        return f"rules[{i}] {rid} needs an explanation"
    if verdict != "not_enough_information" and not quote.strip():
        return f"rules[{i}] {rid} needs a quote"
    return None


def list_schema_problems(payload: object, expected_ids: set[str]) -> list[str]:
    """Same checks as parse_model_rules, every problem, no accept-on-error."""
    if not isinstance(payload, dict):
        return ["model output is not a JSON object"]
    rules = payload.get("rules")
    if not isinstance(rules, list) or not rules:
        return ["rules must be a non-empty array"]
    problems = []
    seen: set[str] = set()
    for i, row in enumerate(rules):
        problem = _row_problem(row, i, expected_ids, seen)
        if problem:
            problems.append(problem)
            continue
        assert isinstance(row, dict)
        seen.add(str(row.get("rule_id") or "").strip())
    return problems


def parse_model_rules(payload: object, expected_ids: set[str]) -> list[dict]:
    """Accept only a JSON object with a rules array. Raise SchemaError."""
    problems = list_schema_problems(payload, expected_ids)
    if problems:
        raise SchemaError(problems[0])
    rules = payload.get("rules")  # type: ignore[union-attr]
    out = []
    for row in rules:
        row = coerce_absence_row(row)
        rid = str(row.get("rule_id") or "").strip()
        out.append(
            {
                "rule_id": rid,
                "verdict": _normalise_verdict(str(row.get("verdict") or "")),
                "explanation": str(row.get("explanation") or "").strip(),
                "quote": str(row.get("quote") or ""),
                "quote_source": str(row.get("quote_source") or "").strip().lower(),
                "coerced_to_nei": bool(row.get("coerced_to_nei")),
            }
        )
    return out
