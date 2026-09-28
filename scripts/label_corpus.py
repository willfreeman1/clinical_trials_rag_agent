"""Label every saved recruiting lung-cancer trial with GPT-5.4.

Writes one JSON line per trial to data/answer_key.jsonl so a stopped run
can continue. The quote check is the same one used on the 10-trial pilot.
"""

from __future__ import annotations

import json
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

from mini_pilot import (
    INPUT_USD_PER_MILLION,
    JSONL_PATH,
    MODEL,
    OUTPUT_USD_PER_MILLION,
    ask,
    check_answer,
    load_key,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "data" / "answer_key.jsonl"
SUMMARY_PATH = ROOT / "data" / "answer_key_summary.json"
WORKERS = 6


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
            time.sleep(2**attempt)
        except Exception as exc:
            last_error = str(exc)
            time.sleep(2**attempt)
    return {
        "nct_id": record["nct_id"],
        "brief_title": record.get("brief_title"),
        "answer": None,
        "checks": ["request failed"],
        "error": last_error,
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }


def write_summary(rows: list[dict]) -> None:
    input_tokens = 0
    output_tokens = 0
    failed = 0
    flagged = 0
    immuno: dict[str, int] = {}
    brain: dict[str, int] = {}
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
        immuno_label = answer.get("prior_immunotherapy_classification") or "missing"
        brain_label = answer.get("brain_metastases_classification") or "missing"
        immuno[immuno_label] = immuno.get(immuno_label, 0) + 1
        brain[brain_label] = brain.get(brain_label, 0) + 1
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
        "prior_immunotherapy": immuno,
        "brain_metastases": brain,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> None:
    api_key = load_key()
    trials = load_trials()
    done = load_done()
    pending = [trial for trial in trials if trial["nct_id"] not in done]
    print(
        f"total={len(trials)} already_done={len(done)} pending={len(pending)}",
        flush=True,
    )
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
    print(SUMMARY_PATH.read_text(encoding="utf-8"), flush=True)


if __name__ == "__main__":
    main()
