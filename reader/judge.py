"""Judge one trial: split, call the model, validate, retry, verify quotes.

`complete` is the only model hook. A service later supplies it.
This module does not load a GPU.

Raw model text is stored on every attempt so the audit can be
redone without calling the model again.

A quote that fails verification is flagged and kept.

The system does not say a patient qualifies.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from reader.aggregate import aggregate
from reader.prompt import SYSTEM, retry_message, user_message
from reader.schema import (
    Rule,
    RuleJudgement,
    SchemaError,
    TrialRead,
    list_schema_problems,
    parse_model_rules,
)
from reader.split_rules import split_rules
from reader.verify_quote import verify_judgement

CompleteFn = Callable[[str, str], str]
# One repair only. Three greedy retries that paste the last reply
# reproduced the same empty-quote failure and wasted generations.
MAX_RETRIES = 1


def _parse_json(raw: str) -> object:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def _describe_failure(raw: str, expected: set[str], exc: Exception) -> str:
    if isinstance(exc, json.JSONDecodeError):
        return (
            f"JSON does not parse ({exc.msg} at char {exc.pos}). "
            "Return one JSON object only. No markdown fences."
        )
    try:
        payload = _parse_json(raw)
    except Exception:
        return str(exc)
    problems = list_schema_problems(payload, expected)
    if problems:
        return "\n".join(f"- {p}" for p in problems)
    return str(exc)


def _fill_missing(expected: list[Rule], parsed: list[dict]) -> tuple[list[dict], list[str]]:
    have = {row["rule_id"]: row for row in parsed}
    missing = [r.rule_id for r in expected if r.rule_id not in have]
    filled = [have[r.rule_id] for r in expected if r.rule_id in have]
    for rid in missing:
        filled.append(
            {
                "rule_id": rid,
                "verdict": "not_enough_information",
                "explanation": "model omitted this rule",
                "quote": "",
                "quote_source": "trial",
            }
        )
    return filled, missing


def _to_judgements(
    rows: list[dict],
    rules: list[Rule],
    patient_note: str,
    trial_text: str,
) -> list[RuleJudgement]:
    by_id = {r.rule_id: r for r in rules}
    out = []
    for row in rows:
        item = RuleJudgement(
            rule_id=row["rule_id"],
            verdict=row["verdict"],
            explanation=row["explanation"],
            quote=row["quote"],
            quote_source=row["quote_source"],
        )
        rule = by_id[row["rule_id"]]
        out.append(verify_judgement(item, rule, patient_note, trial_text))
    return out


def read_trial(
    patient_id: str,
    nct_id: str,
    patient_note: str,
    title: str,
    eligibility: str,
    complete: CompleteFn,
    max_retries: int = MAX_RETRIES,
) -> TrialRead:
    rules = split_rules(eligibility)
    trial_text = f"{title}\n{eligibility}"
    if not rules:
        return TrialRead(
            patient_id=patient_id,
            nct_id=nct_id,
            raw_model_output="",
            schema_ok=True,
            aggregates=aggregate([], []),
        )

    user = user_message(patient_note, nct_id, title, rules)
    expected = {r.rule_id for r in rules}
    last_raw = ""
    last_err = "no attempt"
    parsed: list[dict] | None = None
    retries = 0

    for attempt in range(max_retries + 1):
        prompt = user if attempt == 0 else user + "\n\n" + retry_message(last_err)
        last_raw = complete(SYSTEM, prompt)
        retries = attempt
        try:
            payload = _parse_json(last_raw)
            parsed = parse_model_rules(payload, expected)
            last_err = ""
            break
        except (json.JSONDecodeError, SchemaError, TypeError) as exc:
            last_err = _describe_failure(last_raw, expected, exc)
            parsed = None

    schema_ok = parsed is not None
    if parsed is None:
        parsed = []
    filled, missing = _fill_missing(rules, parsed)
    judgements = _to_judgements(filled, rules, patient_note, trial_text)
    return TrialRead(
        patient_id=patient_id,
        nct_id=nct_id,
        rules=judgements,
        raw_model_output=last_raw,
        retries=retries,
        schema_ok=schema_ok,
        schema_error=last_err,
        missing_rule_ids=missing,
        aggregates=aggregate(judgements, rules),
    )
