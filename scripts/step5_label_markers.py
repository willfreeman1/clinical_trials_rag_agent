"""Spike 2, Step 5a: label the genetic-marker trait on all 1,308 trials.

Extends the existing labelling instructions; does not rewrite them. Writes a
new file so the two-trait answer key is left alone. Resumable, six workers,
same quote-check idea as mini_pilot.py.

Thresholds in THRESHOLDS.md, committed before this ran.
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
    load_key,
    quote_match,
)
from keyword_section_check import JSONL_PATH  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "data" / "answer_key_markers.jsonl"
SUMMARY_PATH = ROOT / "data" / "answer_key_markers_summary.json"
WORKERS = 6

# Same preamble and traps as mini_pilot.SYSTEM, then the new trait instead of
# the two already labelled.
SYSTEM = """You read eligibility criteria from clinical trials to categorize what the trial text says about given medical treatments or conditions. Do not decide whether any patient qualifies.

Accuracy and evidence matter, so record a marker only when an exact passage from the trial text supports it, and copy that passage verbatim. If the passage is about a different fact, leave the lists empty and leave the quote empty.

A laboratory result about PD-1 or PD-L1 on the tumor is not a genetic marker of the kind asked for here, and is not a treatment history. A drug the trial itself would administer is not something the patient must already have.

This run labels one trait: which genetic marker the trial asks for.

Genetic marker the trial asks for — a specific tumour genetic change (mutation, fusion, rearrangement, amplification, insertion, deletion) that the trial demands or excludes. Record two lists:
- required_markers: every specific change the trial demands a patient already have in the tumour. Leave empty if it demands none. Use the exact names the trial uses, plus the general phrase if it gives one — a trial saying "any sensitising alteration in the EGFR gene" gets that general phrase rather than a guessed list of specific ones. If the trial requires simply "some actionable alteration" without naming which, record that literal phrase.
- refused_markers: every specific change the trial excludes.

Do not translate or expand a general phrase into a list of variants you were not given. Do not put a marker on both lists unless the text actually both requires it and refuses it, in which case put it on both and explain in the note.

genetic_marker_condition: a short copy of the qualifying clause when the requirement or refusal is conditional ("unless treated", "cohort B only", "if previously treated with an EGFR TKI"). Empty string when the rule is unqualified.

genetic_marker_quote: one verbatim passage that supports the lists. Empty string when both lists are empty.

note: one sentence, or more than one only when that is needed to explain the lists.

Return JSON with keys required_markers, refused_markers, genetic_marker_condition, genetic_marker_quote, note. required_markers and refused_markers are arrays of strings.
"""

MARKER_WORDS = re.compile(
    r"EGFR|ALK|KRAS|ROS1|BRAF|MET|RET|NTRK|HER2|ERBB2|NRG1|FGFR|PIK3CA|"
    r"mutation|fusion|rearrangement|alteration|insertion|deletion|amplification|"
    r"wild[\s-]?type|biomarker|oncogene|driver|molecular|NGS|sequenc",
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


def ask(api_key: str, record: dict) -> dict:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Trial {record['nct_id']}: {record['brief_title']}\n\n"
                    f"{record['eligibility_criteria']}"
                ),
            },
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


def as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def check_answer(text: str, answer: dict) -> list[str]:
    problems = []
    required = as_list(answer.get("required_markers"))
    refused = as_list(answer.get("refused_markers"))
    quote = answer.get("genetic_marker_quote") or ""
    answer["required_markers"] = required
    answer["refused_markers"] = refused
    if not required and not refused:
        if quote:
            problems.append("lists are empty but the quote is not empty")
        return problems
    if not quote:
        problems.append("a list is non-empty but the quote is empty")
        return problems
    if quote_match(quote, text) == "missing":
        problems.append("genetic_marker_quote is not in the trial text")
        return problems
    if not MARKER_WORDS.search(quote):
        problems.append("genetic_marker_quote does not mention a genetic marker")
    return problems


def label_one(api_key: str, record: dict) -> dict:
    last_error = "unknown error"
    for attempt in range(5):
        try:
            result = ask(api_key, record)
            result["checks"] = check_answer(
                record["eligibility_criteria"], result["answer"]
            )
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
    n_required = n_refused = n_both_empty = n_condition = 0
    for row in rows:
        usage = row.get("usage") or {}
        input_tokens += usage.get("input_tokens") or 0
        output_tokens += usage.get("output_tokens") or 0
        if not row.get("answer"):
            failed += 1
            continue
        if row.get("checks"):
            flagged += 1
        answer = row["answer"]
        req = as_list(answer.get("required_markers"))
        ref = as_list(answer.get("refused_markers"))
        if req:
            n_required += 1
        if ref:
            n_refused += 1
        if not req and not ref:
            n_both_empty += 1
        if (answer.get("genetic_marker_condition") or "").strip():
            n_condition += 1
    cost = (
        input_tokens * INPUT_USD_PER_MILLION + output_tokens * OUTPUT_USD_PER_MILLION
    ) / 1_000_000
    summary = {
        "model": MODEL,
        "labeled": len(rows) - failed,
        "failed": failed,
        "quote_check_flagged": flagged,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_usd": round(cost, 4),
        "trials_with_required_markers": n_required,
        "trials_with_refused_markers": n_refused,
        "trials_with_no_marker_rule": n_both_empty,
        "trials_with_condition": n_condition,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="label only the first N pending trials")
    args = parser.parse_args()

    api_key = load_key()
    trials = load_trials()
    done = load_done()
    pending = [trial for trial in trials if trial["nct_id"] not in done]
    if args.limit:
        pending = pending[: args.limit]
    print(
        f"total={len(trials)} already_done={len(done)} pending={len(pending)}",
        flush=True,
    )
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
                line = json.dumps(result, ensure_ascii=False)
                with lock:
                    handle.write(line + "\n")
                    handle.flush()
                    finished += 1
                    if finished % 25 == 0 or finished == len(pending):
                        print(f"finished={finished} of {len(pending)}", flush=True)
    rows = []
    with OUT_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    write_summary(rows)


if __name__ == "__main__":
    main()
