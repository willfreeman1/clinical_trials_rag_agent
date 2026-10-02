"""Ask GPT-5.4 mini about a handful of trials, and record the cost.

This is a pilot of the labeler. It is not the gold set. The trial ids were
picked because the wording is easy to check by hand: a plain bar, a plain
requirement, a negation written on the required list, a biomarker that only
looks like a drug, and brain-metastasis rules with an exception.
"""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

from keyword_section_check import JSONL_PATH

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "data" / "gpt54_pilot_pass2.json"
MODEL = "gpt-5.4"
INPUT_USD_PER_MILLION = 2.50
OUTPUT_USD_PER_MILLION = 15.00

TRIAL_IDS = [
    "NCT05940532",
    "NCT07154706",
    "NCT06780085",
    "NCT06983899",
    "NCT04302025",
    "NCT07103395",
    "NCT06660407",
    "NCT06363734",
    "NCT05498428",
    "NCT06424067",
]

SYSTEM = """You read eligibility criteria from clinical trials to categorize what the trial text says about given medical treatments or conditions. Do not decide whether any patient qualifies.

A treatment or condition can be required, allowed, allowed with an exception, barred, barred with an exception, both required and barred, not mentioned, or unclear. Accuracy and evidence matter, so choose a classification only when an exact passage from the trial text supports it, and copy that passage verbatim from the eligibility criteria. Do not quote the trial title. If the passage is about a different fact, choose not_mentioned and leave the quote empty. You will return both the classification and the quoted support for that classification.

You will classify two facts.

Prior immunotherapy is treatment the person has already received, or that is already underway, when they join this trial. It includes immunotherapy, an immune checkpoint inhibitor, or a drug aimed at PD-1, PD-L1, or CTLA-4. A laboratory result about PD-1 or PD-L1 on the tumor is not a treatment history. Treatment the protocol gives or forbids during the study is not prior immunotherapy.

Brain metastases are cancer involving the brain or central nervous system, including leptomeningeal disease.

Use these classifications for every fact:
- required: the trial wants people who have that treatment or condition
- allowed: the trial accepts people who have it, does not demand that they have it, and states no limit
- allowed_with_exception: the trial accepts people who have it, and the passage states a limit on that acceptance
- barred: the trial refuses people who have it, and states no exception
- barred_with_exception: the trial refuses people who have it, except in cases the passage states
- both_classifications: one passage says the trial wants it and another says the trial refuses it, and the passages disagree about the same fact
- not_mentioned: the text does not mention it
- unclear: the text mentions it but does not say whether people who have it are wanted or refused

Choose allowed_with_exception or barred_with_exception by the rule, not by the verb in the sentence. Use allowed_with_exception when people who have it are accepted with a limit. Use barred_with_exception when people who have it are refused except in stated cases.

Return JSON with these keys: prior_immunotherapy_classification, prior_immunotherapy_quote, brain_metastases_classification, brain_metastases_quote, note.
The note is one sentence, or more than one only when that is needed to explain the classification.
"""


def load_key() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENAI_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("OPENAI_API_KEY is missing")


def load_records() -> dict[str, dict]:
    wanted = set(TRIAL_IDS)
    found = {}
    with JSONL_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if record["nct_id"] in wanted:
                found[record["nct_id"]] = record
    missing = wanted - set(found)
    if missing:
        raise SystemExit(f"missing trials: {sorted(missing)}")
    return found


QUOTE_NOT_VERBATIM = (
    "The quote you returned is not a verbatim substring of the eligibility "
    "criteria. Copy a passage exactly from the eligibility text. Do not use "
    "the trial title as a quote."
)


def ask(api_key: str, record: dict, extra_user: str = "") -> dict:
    user = (
        f"Trial {record['nct_id']}: {record['brief_title']}\n\n"
        f"{record['eligibility_criteria']}"
    )
    if extra_user:
        user += "\n\n" + extra_user
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        body = json.loads(response.read().decode("utf-8"))
    content = body["choices"][0]["message"]["content"]
    usage = body.get("usage") or {}
    return {
        "nct_id": record["nct_id"],
        "brief_title": record["brief_title"],
        "answer": json.loads(content),
        "usage": {
            "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"),
        },
    }


def quotes_not_in_text(checks: list[str]) -> bool:
    return any("not in the trial text" in c for c in checks)


def ask_with_verbatim_retry(ask_fn, check_fn, api_key: str, record: dict, max_quote_tries: int = 3):
    """Call ask_fn until quotes are a substring of eligibility, or tries run out."""
    extra = ""
    last = None
    acc_in = acc_out = 0
    text = record.get("eligibility_criteria") or ""
    for attempt in range(max_quote_tries):
        last = ask_fn(api_key, record, extra) if extra else ask_fn(api_key, record)
        last["checks"] = check_fn(text, last["answer"])
        last["quote_retries"] = attempt
        in_tok = (last.get("usage") or {}).get("input_tokens") or 0
        out_tok = (last.get("usage") or {}).get("output_tokens") or 0
        acc_in += in_tok
        acc_out += out_tok
        last["usage"] = {"input_tokens": acc_in, "output_tokens": acc_out}
        if not quotes_not_in_text(last["checks"]):
            return last
        extra = QUOTE_NOT_VERBATIM
    return last


BRAIN_WORDS = re.compile(
    r"brain|central nervous system|\bCNS\b|leptomeningeal|intracranial|carcinomatous meningitis",
    re.IGNORECASE,
)
IMMUNO_WORDS = re.compile(
    r"immunotherapy|checkpoint inhibitor|pembrolizumab|nivolumab|atezolizumab|anti-PD-1|anti-PD-L1|\bPD-1\b|\bPD-L1\b",
    re.IGNORECASE,
)


def normalize_for_match(value: str) -> str:
    """Ignore line breaks, bullet marks, and backslashes the registry inserts.

    ClinicalTrials.gov often stores a comparison sign as ``\\<=``. A copied
    sentence that drops that slash, or that joins two lines, is still the
    same sentence. A sentence that is not in the trial still fails.
    """
    value = value.replace("\\", "")
    value = value.replace("*", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def quote_match(quote: str, text: str) -> str:
    if quote in text:
        return "exact"
    if normalize_for_match(quote) in normalize_for_match(text):
        return "normalized"
    return "missing"


def check_answer(text: str, answer: dict) -> list[str]:
    """Flag labels whose quote is missing, invented, or about the wrong fact."""
    problems = []
    pairs = [
        ("prior_immunotherapy_classification", "prior_immunotherapy_quote", IMMUNO_WORDS),
        ("brain_metastases_classification", "brain_metastases_quote", BRAIN_WORDS),
    ]
    allowed = {
        "required",
        "allowed",
        "allowed_with_exception",
        "barred",
        "barred_with_exception",
        "both_classifications",
        "not_mentioned",
        "unclear",
    }
    for class_key, quote_key, words in pairs:
        classification = answer.get(class_key)
        quote = answer.get(quote_key) or ""
        if classification not in allowed:
            problems.append(f"{class_key} is missing or not a known classification")
            continue
        if classification == "not_mentioned":
            if quote:
                problems.append(f"{class_key} is not_mentioned but the quote is not empty")
            continue
        if not quote:
            problems.append(f"{class_key} is {classification} but the quote is empty")
            continue
        if quote_match(quote, text) == "missing":
            problems.append(f"{quote_key} is not in the trial text")
            continue
        if not words.search(quote):
            problems.append(f"{quote_key} does not mention the fact being classified")
    return problems


def main() -> None:
    api_key = load_key()
    records = load_records()
    results = []
    input_tokens = 0
    output_tokens = 0
    for nct_id in TRIAL_IDS:
        result = ask_with_verbatim_retry(ask, check_answer, api_key, records[nct_id])
        results.append(result)
        input_tokens += result["usage"]["input_tokens"] or 0
        output_tokens += result["usage"]["output_tokens"] or 0
        print(nct_id, json.dumps(result["answer"], ensure_ascii=False), flush=True)
        if result["checks"]:
            print("  checks:", "; ".join(result["checks"]), flush=True)
    cost = (
        input_tokens * INPUT_USD_PER_MILLION + output_tokens * OUTPUT_USD_PER_MILLION
    ) / 1_000_000
    report = {
        "model": MODEL,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_usd": round(cost, 4),
        "results": results,
    }
    OUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"input_tokens": input_tokens, "output_tokens": output_tokens, "estimated_usd": round(cost, 4)}))


if __name__ == "__main__":
    main()
