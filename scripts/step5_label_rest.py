"""Spike 2, Step 5b: label platinum, autoimmune, and disease stage.

One request per trial, three traits. New file, so earlier keys are not
touched. Resumable, six workers. Thresholds in THRESHOLDS.md, committed
before this ran.
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mini_pilot import (  # noqa: E402
    INPUT_USD_PER_MILLION,
    MODEL,
    OUTPUT_USD_PER_MILLION,
    ask_with_verbatim_retry,
    load_key,
    quote_match,
)
from keyword_section_check import JSONL_PATH  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "data" / "answer_key_step5b.jsonl"
SUMMARY_PATH = ROOT / "data" / "answer_key_step5b_summary.json"
WORKERS = 6

ALLOWED = {
    "required",
    "allowed",
    "allowed_with_exception",
    "barred",
    "barred_with_exception",
    "both_classifications",
    "not_mentioned",
    "unclear",
}

SYSTEM = """You read eligibility criteria from clinical trials to categorize what the trial text says about given medical treatments or conditions. Do not decide whether any patient qualifies.

Accuracy and evidence matter, so choose a classification only when an exact passage from the trial text supports it, and copy that passage verbatim from the eligibility criteria. Do not quote the trial title. If the passage is about a different fact, choose not_mentioned and leave the quote empty.

A laboratory result is not a treatment history. A drug the trial itself would administer is not something the patient had before. A family history alone is not a disease the patient has.

This run labels three facts.

Previous platinum chemotherapy is chemotherapy containing a platinum drug (cisplatin, carboplatin, oxaliplatin, nedaplatin, lobaplatin) that the person received, or was receiving, before joining. Chemotherapy without a platinum drug does not count. A platinum drug the trial itself would administer does not count.

Autoimmune disease is a condition in which the immune system attacks the body's own tissue, whether active now or in the past. Includes named examples the text gives. A family history alone does not count. Being on a drug that suppresses the immune system is not by itself an autoimmune disease, though the text often mentions both together.

Disease stages the trial accepts: record two lists. allowed_stages holds every stage or descriptive stage-like label the trial accepts (including locally advanced, metastatic, unresectable, early). refused_stages holds every one it excludes. Use the labels the trial uses. Do not translate a description into a numbered stage. If the trial accepts none specifically and excludes none, both lists are empty.

Use these classifications for platinum and autoimmune:
- required: the trial wants people who have that treatment or condition
- allowed: the trial accepts people who have it, does not demand that they have it, and states no limit
- allowed_with_exception: the trial accepts people who have it, and the passage states a limit on that acceptance
- barred: the trial refuses people who have it, and states no exception
- barred_with_exception: the trial refuses people who have it, except in cases the passage states
- both_classifications: one passage says the trial wants it and another says the trial refuses it
- not_mentioned: the text does not mention it
- unclear: the text mentions it but does not say whether people who have it are wanted or refused

Choose allowed_with_exception or barred_with_exception by the rule, not by the verb in the sentence.

stage_condition: a short copy of the qualifying clause when the stage rule is conditional. Empty string when unqualified.

Return JSON with keys: prior_platinum_chemo_classification, prior_platinum_chemo_quote, autoimmune_disease_classification, autoimmune_disease_quote, allowed_stages, refused_stages, stage_condition, stage_quote, note.
allowed_stages and refused_stages are arrays of strings. The note is one sentence, or more only when needed.
"""

PLATINUM_WORDS = re.compile(
    r"platinum|cisplatin|carboplatin|oxaliplatin|nedaplatin|lobaplatin",
    re.IGNORECASE,
)
AUTO_WORDS = re.compile(
    r"autoimmune|rheumatoid|lupus|colitis|crohn|psoriasis|scleroderma|"
    r"sjogren|ankylosing|hashimoto|graves|vasculitis|myasthenia|ibd|"
    r"inflammatory bowel",
    re.IGNORECASE,
)
STAGE_WORDS = re.compile(
    r"stage|metastatic|locally advanced|unresectable|early|operable|"
    r"\bI{1,3}[ABC]?\b|\bIV\b|\b[1-4]\b",
    re.IGNORECASE,
)


def load_trials() -> list[dict]:
    trials = []
    with JSONL_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                trials.append(json.loads(line))
    return trials


def load_done() -> set[str]:
    done = set()
    if not OUT_PATH.exists():
        return done
    with OUT_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("answer"):
                done.add(row["nct_id"])
    return done


def as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


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
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
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


def check_class_quote(text: str, answer: dict, class_key: str, quote_key: str, words) -> list[str]:
    problems = []
    classification = answer.get(class_key)
    quote = answer.get(quote_key) or ""
    if classification not in ALLOWED:
        problems.append(f"{class_key} is missing or not a known classification")
        return problems
    if classification == "not_mentioned":
        if quote:
            problems.append(f"{class_key} is not_mentioned but the quote is not empty")
        return problems
    if not quote:
        problems.append(f"{class_key} is {classification} but the quote is empty")
        return problems
    if quote_match(quote, text) == "missing":
        problems.append(f"{quote_key} is not in the trial text")
        return problems
    if not words.search(quote):
        problems.append(f"{quote_key} does not mention the fact being classified")
    return problems


def check_answer(text: str, answer: dict) -> list[str]:
    problems = []
    problems += check_class_quote(
        text, answer, "prior_platinum_chemo_classification", "prior_platinum_chemo_quote", PLATINUM_WORDS
    )
    problems += check_class_quote(
        text, answer, "autoimmune_disease_classification", "autoimmune_disease_quote", AUTO_WORDS
    )
    allowed = as_list(answer.get("allowed_stages"))
    refused = as_list(answer.get("refused_stages"))
    answer["allowed_stages"] = allowed
    answer["refused_stages"] = refused
    quote = answer.get("stage_quote") or ""
    if not allowed and not refused:
        if quote:
            problems.append("stage lists are empty but the quote is not empty")
    else:
        if not quote:
            problems.append("a stage list is non-empty but the quote is empty")
        elif quote_match(quote, text) == "missing":
            problems.append("stage_quote is not in the trial text")
        elif not STAGE_WORDS.search(quote):
            problems.append("stage_quote does not mention a stage")
    return problems


def label_one(api_key: str, record: dict) -> dict:
    last_error = "unknown error"
    for attempt in range(5):
        try:
            result = ask_with_verbatim_retry(ask, check_answer, api_key, record)
            return result
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            last_error = f"HTTP {exc.code}: {detail}"
            if exc.code not in (429, 500, 502, 503):
                break
            time.sleep(2 ** attempt)
        except Exception as exc:
            last_error = str(exc)
            time.sleep(2 ** attempt)
    return {
        "nct_id": record["nct_id"],
        "brief_title": record.get("brief_title"),
        "answer": None,
        "checks": ["request failed"],
        "error": last_error,
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }


def write_summary(rows: list[dict]) -> None:
    input_tokens = output_tokens = failed = flagged = 0
    plat: dict[str, int] = {}
    auto: dict[str, int] = {}
    n_allowed = n_refused = n_no_stage = n_cond = 0
    for row in rows:
        usage = row.get("usage") or {}
        input_tokens += usage.get("input_tokens") or 0
        output_tokens += usage.get("output_tokens") or 0
        if not row.get("answer"):
            failed += 1
            continue
        if row.get("checks"):
            flagged += 1
        a = row["answer"]
        p = a.get("prior_platinum_chemo_classification") or "missing"
        u = a.get("autoimmune_disease_classification") or "missing"
        plat[p] = plat.get(p, 0) + 1
        auto[u] = auto.get(u, 0) + 1
        al, rf = as_list(a.get("allowed_stages")), as_list(a.get("refused_stages"))
        if al:
            n_allowed += 1
        if rf:
            n_refused += 1
        if not al and not rf:
            n_no_stage += 1
        if (a.get("stage_condition") or "").strip():
            n_cond += 1
    cost = (input_tokens * INPUT_USD_PER_MILLION + output_tokens * OUTPUT_USD_PER_MILLION) / 1_000_000
    summary = {
        "model": MODEL,
        "labeled": len(rows) - failed,
        "failed": failed,
        "quote_check_flagged": flagged,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_usd": round(cost, 4),
        "prior_platinum_chemo": plat,
        "autoimmune_disease": auto,
        "trials_with_allowed_stages": n_allowed,
        "trials_with_refused_stages": n_refused,
        "trials_with_no_stage_rule": n_no_stage,
        "trials_with_stage_condition": n_cond,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


def main() -> None:
    api_key = load_key()
    trials = load_trials()
    done = load_done()
    pending = [t for t in trials if t["nct_id"] not in done]
    print(f"total={len(trials)} already_done={len(done)} pending={len(pending)}", flush=True)
    if not pending:
        rows = [json.loads(l) for l in OUT_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
        write_summary(rows)
        return
    lock = Lock()
    finished = 0
    with OUT_PATH.open("a", encoding="utf-8") as handle:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = [pool.submit(label_one, api_key, trial) for trial in pending]
            for future in as_completed(futures):
                result = future.result()
                with lock:
                    handle.write(json.dumps(result, ensure_ascii=False) + "\n")
                    handle.flush()
                    finished += 1
                    if finished % 25 == 0 or finished == len(pending):
                        print(f"finished={finished} of {len(pending)}", flush=True)
    rows = [json.loads(l) for l in OUT_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    write_summary(rows)


if __name__ == "__main__":
    main()
