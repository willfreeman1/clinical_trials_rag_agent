"""Re-label 37 brain slots whose quote is metastatic disease, not brain.

Immunotherapy labels on the same trials are left alone. Snapshot first.
Verbatim eligibility substring required; retry on failure.
"""

from __future__ import annotations

import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from keyword_section_check import JSONL_PATH  # noqa: E402
from mini_pilot import (  # noqa: E402
    BRAIN_WORDS,
    INPUT_USD_PER_MILLION,
    MODEL,
    OUTPUT_USD_PER_MILLION,
    ask_with_verbatim_retry,
    load_key,
    quote_match,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
KEY = DATA / "answer_key.jsonl"
SNAP = DATA / "answer_key_pre_brain37.jsonl"
OUT_LOG = DATA / "step9_brain37_relabel.json"
CHECKS = DATA / "step9_three_checks.json"
WORKERS = 8

SYSTEM = """You read eligibility criteria from a lung-cancer trial. Classify only cancer spread to the brain. Do not decide whether any patient qualifies.

Brain metastases are cancer involving the brain or central nervous system, including leptomeningeal disease, intracranial metastases, and carcinomatous meningitis.

A sentence about metastatic disease, distant metastases, or stage IV that does not mention the brain, CNS, intracranial disease, or leptomeningeal disease is not a brain-metastases rule. In that case choose not_mentioned and leave the quote empty.

Copy a passage verbatim from the eligibility criteria. Do not quote the trial title.

Use: required, allowed, allowed_with_exception, barred, barred_with_exception, both_classifications, not_mentioned, unclear.

Return JSON with keys: brain_metastases_classification, brain_metastases_quote, note.
"""


def load_ids() -> list[str]:
    payload = json.loads(CHECKS.read_text(encoding="utf-8"))
    ids = sorted({
        row["nct_id"]
        for row in payload["check3"]["c3_rows"]
        if row["fact"] == "brain_metastases"
    })
    return ids


def load_trials(ids: set[str]) -> dict[str, dict]:
    found = {}
    with JSONL_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row["nct_id"] in ids:
                found[row["nct_id"]] = row
    return found


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
    import urllib.request
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
        "brief_title": record.get("brief_title"),
        "answer": json.loads(content),
        "usage": {
            "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"),
        },
    }


def check_answer(text: str, answer: dict) -> list[str]:
    problems = []
    classification = answer.get("brain_metastases_classification")
    quote = answer.get("brain_metastases_quote") or ""
    allowed = {
        "required", "allowed", "allowed_with_exception", "barred",
        "barred_with_exception", "both_classifications", "not_mentioned", "unclear",
    }
    if classification not in allowed:
        problems.append("brain classification missing or unknown")
        return problems
    if classification == "not_mentioned":
        if quote:
            problems.append("not_mentioned but quote is not empty")
        return problems
    if not quote:
        problems.append("classification set but quote empty")
        return problems
    if quote_match(quote, text) == "missing":
        problems.append("brain_metastases_quote is not in the trial text")
        return problems
    if not BRAIN_WORDS.search(quote):
        problems.append("quote does not mention the brain")
    return problems


def main() -> None:
    ids = load_ids()
    print(f"brain C3 ids={len(ids)}", flush=True)
    if not SNAP.exists():
        shutil.copyfile(KEY, SNAP)
        print(f"snapshot {SNAP}", flush=True)
    trials = load_trials(set(ids))
    api_key = load_key()
    results = []
    lock = Lock()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {
            pool.submit(ask_with_verbatim_retry, ask, check_answer, api_key, trials[nct]): nct
            for nct in ids
            if nct in trials
        }
        for future in as_completed(futures):
            nct = futures[future]
            try:
                row = future.result()
            except Exception as exc:
                row = {"nct_id": nct, "answer": None, "error": str(exc), "checks": ["request failed"]}
            with lock:
                results.append(row)
                print(nct, (row.get("answer") or {}).get("brain_metastases_classification"), row.get("checks"), flush=True)

    by_nct = {r["nct_id"]: r for r in results}
    patched = []
    with KEY.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            fresh = by_nct.get(row["nct_id"])
            if fresh and fresh.get("answer") and row.get("answer"):
                old = dict(row["answer"])
                row["answer"]["brain_metastases_classification"] = fresh["answer"].get(
                    "brain_metastases_classification"
                )
                row["answer"]["brain_metastases_quote"] = fresh["answer"].get("brain_metastases_quote") or ""
                if "note" in fresh["answer"]:
                    row["answer"]["brain_relabel_note"] = fresh["answer"]["note"]
                row["brain_relabel"] = {
                    "old_class": old.get("brain_metastases_classification"),
                    "old_quote": old.get("brain_metastases_quote"),
                    "checks": fresh.get("checks") or [],
                }
            patched.append(row)
    with KEY.open("w", encoding="utf-8") as handle:
        for row in patched:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    in_tok = sum((r.get("usage") or {}).get("input_tokens") or 0 for r in results)
    out_tok = sum((r.get("usage") or {}).get("output_tokens") or 0 for r in results)
    cost = (in_tok * INPUT_USD_PER_MILLION + out_tok * OUTPUT_USD_PER_MILLION) / 1_000_000
    log = {
        "n": len(ids),
        "labeled": sum(1 for r in results if r.get("answer")),
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "estimated_usd": round(cost, 4),
        "classes": {},
        "rows": [
            {
                "nct_id": r["nct_id"],
                "class": (r.get("answer") or {}).get("brain_metastases_classification"),
                "quote": ((r.get("answer") or {}).get("brain_metastases_quote") or "")[:200],
                "checks": r.get("checks") or [],
            }
            for r in results
        ],
    }
    from collections import Counter
    log["classes"] = dict(Counter(
        (r.get("answer") or {}).get("brain_metastases_classification") for r in results
    ))
    OUT_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: log[k] for k in log if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
