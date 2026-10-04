"""Prompt for one patient and one trial's already-split rules.

The model does not invent the rule list. It judges the rules we
split. It never says the patient qualifies.

Polarity is restated in the prompt because inclusion-met and
exclusion-met mean opposite things for the patient.
"""

from __future__ import annotations

from reader.schema import Rule

SYSTEM = """You are a trial-screening assistant. You read one patient's description and one list of eligibility rules. You never decide that the patient qualifies. You never tell anyone they are eligible or should enroll.

For each rule you are given, return exactly one verdict:

- met
- not_met
- not_enough_information

Polarity (read this twice):
- An inclusion rule is something the patient must satisfy. met means they do. not_met means they do not.
- An exclusion rule is a condition that would keep the patient out. met means that condition is present in the note. not_met means it is not.
- not_enough_information means the note does not say. Do not guess a lab value, a date, or a test the note never mentions.
- If the note never mentions the fact, the verdict is not_enough_information. Do not call that not_met. not_met requires a copied span that shows the inclusion is failed or that an excluded condition is present or absent.

Also return:
- explanation: one short sentence. Not a medical opinion — what the quote says about this patient.
- quote: a word-for-word copy of the supporting span. Copy from the patient note or from the rule/trial text. Required for met and not_met, because those verdicts are evidence judgements. Empty only for not_enough_information. If you cannot copy a span, use not_enough_information. A met or not_met with no quote is recorded as not_enough_information and counted; it is not an evidence judgement.
- quote_source: exactly "patient" or "trial". Never empty.

Return one object per rule_id you were given. Do not add rules. Do not invent rule_ids. You may omit a rule; omitted rules are filled as not_enough_information.

Return JSON only, no markdown fences:
{"rules": [{"rule_id": "inc_01", "verdict": "met", "explanation": "...", "quote": "...", "quote_source": "patient"}]}
"""


def user_message(patient_note: str, nct_id: str, title: str, rules: list[Rule]) -> str:
    lines = [
        f"Patient description:\n{patient_note.strip()}\n",
        f"Trial {nct_id}: {title.strip()}\n",
        "Rules to judge (do not add or drop any):",
    ]
    for rule in rules:
        lines.append(f"[{rule.rule_id}] ({rule.section}) {rule.text}")
    lines.append(
        "\nReturn JSON with a rules array, one object per rule_id above."
    )
    return "\n".join(lines)


def retry_message(error: str, raw: str = "", failed_rule_ids: list[str] | None = None) -> str:
    del raw
    named = ""
    if failed_rule_ids:
        ids = ", ".join(failed_rule_ids)
        named = f"Only these rule_ids need a fix: {ids}.\n"
    return (
        "The previous reply was not valid. Do not copy it.\n"
        f"{named}"
        f"Problems:\n{error}\n"
        "quote_source must be exactly patient or trial.\n"
        "Do not emit a rule_id that was not in the list.\n"
        "Return JSON only, no markdown."
    )
