"""Step 8 reader. Two models, same sample, resumable JSONL.

Thresholds in THRESHOLDS.md, committed before this ran. Never says a
patient qualifies.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mini_pilot import load_key  # noqa: E402
from step8_common import (  # noqa: E402
    CHEAP,
    DATA,
    DESIGN,
    EXPENSIVE,
    cost_usd,
    load_trials,
)

SAMPLE = DATA / "step8_sample.json"
OUT = DATA / "step8_reads.jsonl"
SUMMARY = DATA / "step8_read_summary.json"
WORKERS = 6
TIMEOUT = 180

SYSTEM = """You are a trial-screening assistant. You read one patient's description and one trial's eligibility criteria. You never decide that the patient qualifies. You never tell anyone they are eligible or should enroll.

Your job is to find rules that would keep this patient out, and to flag rules a human must check because the note does not settle them.

For each rule you consider relevant, return:
- fact: a short noun phrase naming the thing the rule is about, with no direction and no number in it. Use these exact names when they fit: previous immunotherapy, previous platinum chemotherapy, previous chemotherapy (any kind), previous systemic anticancer treatment (any kind), cancer spread to the brain, tumour genetic marker, autoimmune disease, disease stage. Otherwise write an ordinary short name.
- verdict: exactly one of excludes_this_patient, does_not_exclude, not_enough_information
- quote: a word-for-word copy of the supporting sentence from the trial text. Required for excludes_this_patient and does_not_exclude. Empty only for not_enough_information.
- reasoning: one short sentence. Not a medical opinion — just what the quote says about this patient.

Do not list every rule in the trial. Only rules that could matter for this patient.

Then overall, exactly one of:
- definitely_excluded — at least one rule excludes this patient, with a quote
- candidate, needs human check — nothing you read excludes them. List the rules a human must verify. This is not a qualification.
- never_eligible — this trial is for a different population entirely (wrong disease or setting), not merely a criterion this patient fails

not_enough_information on a rule is a correct answer when the patient note does not contain the detail the rule needs (for example a treated-and-stable exception, a lab value, a date). Do not guess.

Return JSON with keys rules (array), overall, human_must_verify (array of short strings, empty if overall is definitely_excluded or never_eligible).
"""

LOCK = Lock()


def jobs(sample: dict) -> list[dict]:
    out = []
    for model in (EXPENSIVE, CHEAP):
        for pid, row in sample["patients"].items():
            for nct in row["discarded"]:
                out.append({"model": model, "patient_id": pid, "nct_id": nct, "stratum": "discarded", "pass": 1})
            for nct in row["kept"]:
                out.append({"model": model, "patient_id": pid, "nct_id": nct, "stratum": "kept", "pass": 1})
            for nct in row.get("consistency_discarded") or []:
                out.append({"model": model, "patient_id": pid, "nct_id": nct, "stratum": "discarded", "pass": 2})
            for nct in row.get("consistency_kept") or []:
                out.append({"model": model, "patient_id": pid, "nct_id": nct, "stratum": "kept", "pass": 2})
    return out


def job_id(job: dict) -> str:
    return f"{job['model']}::{job['patient_id']}::{job['nct_id']}::{job['pass']}"


def load_done() -> set[str]:
    done = set()
    if not OUT.exists():
        return done
    with OUT.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("answer"):
                done.add(job_id(row))
    return done


def ask(api_key: str, model: str, description: str, record: dict) -> dict:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Patient description:\n{description}\n\n"
                    f"Trial {record['nct_id']}: {record.get('brief_title') or ''}\n\n"
                    f"Eligibility criteria:\n{record['eligibility_criteria']}"
                ),
            },
        ],
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        body = json.loads(response.read().decode("utf-8"))
    elapsed = time.perf_counter() - started
    content = json.loads(body["choices"][0]["message"]["content"])
    usage = body.get("usage") or {}
    overall = (content.get("overall") or "").strip().lower().replace(" ", "_").replace(",", "")
    if overall == "candidate_needs_human_check" or overall.startswith("candidate"):
        overall = "candidate_needs_human_check"
    elif overall == "definitely_excluded":
        overall = "definitely_excluded"
    elif overall == "never_eligible":
        overall = "never_eligible"
    content["overall"] = overall
    return {
        "answer": content,
        "usage": {
            "input_tokens": usage.get("prompt_tokens") or 0,
            "output_tokens": usage.get("completion_tokens") or 0,
        },
        "elapsed_s": round(elapsed, 3),
    }


def read_one(api_key: str, job: dict, description: str, record: dict) -> dict:
    last = "unknown error"
    for attempt in range(5):
        try:
            result = ask(api_key, job["model"], description, record)
            return {**job, **result, "brief_title": record.get("brief_title")}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            last = f"HTTP {exc.code}: {detail}"
            if exc.code not in (429, 500, 502, 503):
                break
            time.sleep(2 ** attempt)
        except Exception as exc:
            last = str(exc)
            time.sleep(2 ** attempt)
    return {
        **job,
        "answer": None,
        "error": last,
        "usage": {"input_tokens": 0, "output_tokens": 0},
        "elapsed_s": 0,
        "brief_title": record.get("brief_title"),
    }


def main() -> None:
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    trials = load_trials()
    pending = [j for j in jobs(sample) if job_id(j) not in load_done()]
    print(f"pending={len(pending)} total_jobs={len(jobs(sample))}", flush=True)
    api_key = load_key()
    descriptions = {pid: row["description"] for pid, row in sample["patients"].items()}
    input_tokens = output_tokens = 0
    by_model_cost = {EXPENSIVE: 0.0, CHEAP: 0.0}
    n_done = 0
    t0 = time.perf_counter()

    def work(job: dict) -> dict:
        record = trials[job["nct_id"]]
        return read_one(api_key, job, descriptions[job["patient_id"]], record)

    with OUT.open("a", encoding="utf-8") as handle:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futs = {pool.submit(work, job): job for job in pending}
            for fut in as_completed(futs):
                row = fut.result()
                with LOCK:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                    handle.flush()
                    n_done += 1
                    inp = (row.get("usage") or {}).get("input_tokens") or 0
                    out = (row.get("usage") or {}).get("output_tokens") or 0
                    input_tokens += inp
                    output_tokens += out
                    by_model_cost[row["model"]] += cost_usd(row["model"], inp, out)
                    if n_done % 25 == 0 or n_done == len(pending):
                        elapsed = time.perf_counter() - t0
                        print(
                            f"done={n_done}/{len(pending)} "
                            f"usd={sum(by_model_cost.values()):.2f} "
                            f"elapsed_min={elapsed/60:.1f}",
                            flush=True,
                        )

    summary = {
        "this_run_pending_at_start": len(pending),
        "this_run_finished": n_done,
        "this_run_input_tokens": input_tokens,
        "this_run_output_tokens": output_tokens,
        "this_run_estimated_usd": round(sum(by_model_cost.values()), 4),
        "this_run_usd_by_model": {k: round(v, 4) for k, v in by_model_cost.items()},
        "elapsed_s": round(time.perf_counter() - t0, 1),
        "design": DESIGN,
    }
    SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
