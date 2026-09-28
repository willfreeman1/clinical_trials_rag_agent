"""Spike 2, Step 1: what clinical facts do these trials actually gate on?

Draws a fixed sample of trials, asks GPT-5.4 to list every fact each trial's
criteria gate on at two granularity levels, then reports the concentration
curve. Granularity rules and thresholds are fixed in THRESHOLDS.md before
this runs.

Resumable: one JSON line per trial, so a stopped run continues.
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[1]
TRIALS_PATH = ROOT / "data" / "nsclc_recruiting.jsonl"
SAMPLE_PATH = ROOT / "data" / "step1_sample_ids.json"
OUT_PATH = ROOT / "data" / "step1_concepts.jsonl"
REPORT_PATH = ROOT / "data" / "step1_report.json"

MODEL = "gpt-5.4"
INPUT_USD_PER_MILLION = 2.50
OUTPUT_USD_PER_MILLION = 15.00
SAMPLE_N = 300
SEED = 20260928
WORKERS = 6

CATEGORIES = [
    "disease_or_stage",
    "histology_or_subtype",
    "biomarker_or_mutation",
    "prior_systemic_therapy",
    "prior_local_therapy",
    "performance_status",
    "organ_function_lab",
    "comorbidity_or_history",
    "metastasis_site",
    "infection_status",
    "pregnancy_or_contraception",
    "concurrent_medication",
    "trial_participation",
    "consent_or_compliance",
    "demographics",
    "measurable_disease",
    "other",
]

SYSTEM = f"""You read eligibility criteria from a clinical trial and list every distinct clinical fact the criteria gate on. Do not decide whether any patient qualifies. Do not judge whether a rule is sensible.

A fact is "gated on" when the trial's text makes joining depend on it, whether by requiring it, refusing it, or setting a limit on it.

For each fact, return three things.

1. category: exactly one value from this closed list. Do not invent a category. Use "other" when nothing fits.
{json.dumps(CATEGORIES)}

2. concept: a short lowercase noun phrase naming the specific clinical thing being gated on. Follow these rules exactly, because the phrasing is being counted.
- Name the thing, not the threshold. "Creatinine clearance must be at least 60 mL/min" gives the concept "creatinine clearance".
- Name the thing, not the direction. "No prior immunotherapy" gives the concept "prior immunotherapy". "Patients must have an EGFR mutation" gives "egfr mutation".
- No numbers, no units, no comparison words, no negation words.
- Singular where natural. Lowercase throughout, except keep standard gene and marker spellings readable (egfr, alk, pd-l1, ecog).
- Be specific enough to be useful but not so specific that every trial invents its own phrase. Prefer "brain metastases" over "untreated brain metastases measuring more than 1 cm".

3. quote: a short verbatim fragment of the trial text, copied exactly, that shows this fact is gated on.

List each distinct fact once. A fact mentioned in both the inclusion and exclusion lists is still one fact. Do not list administrative facts that are not clinical unless they gate joining, in which case use category consent_or_compliance or trial_participation.

Return JSON with one key, "facts", holding a list of objects with keys category, concept, quote. If the criteria text gates on nothing at all, return an empty list.
"""


def load_key() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENAI_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("OPENAI_API_KEY is missing")


def load_trials() -> list[dict]:
    trials = []
    with TRIALS_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                trials.append(json.loads(line))
    return trials


def draw_sample(trials: list[dict]) -> list[str]:
    """Fixed sample, written once and reused so the run is reproducible."""
    if SAMPLE_PATH.exists():
        return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))["nct_ids"]
    ids = sorted(t["nct_id"] for t in trials)
    rng = random.Random(SEED)
    drawn = sorted(rng.sample(ids, SAMPLE_N))
    SAMPLE_PATH.write_text(
        json.dumps({"seed": SEED, "n": SAMPLE_N, "drawn_from": len(ids), "nct_ids": drawn}, indent=2),
        encoding="utf-8",
    )
    return drawn


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
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        body = json.loads(response.read().decode("utf-8"))
    usage = body.get("usage") or {}
    return {
        "nct_id": record["nct_id"],
        "answer": json.loads(body["choices"][0]["message"]["content"]),
        "usage": {
            "input_tokens": usage.get("prompt_tokens") or 0,
            "output_tokens": usage.get("completion_tokens") or 0,
        },
    }


def extract_one(api_key: str, record: dict) -> dict:
    last_error = "unknown error"
    for attempt in range(5):
        try:
            return ask(api_key, record)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            last_error = f"HTTP {exc.code}: {detail}"
            if exc.code not in (429, 500, 502, 503):
                break
            time.sleep(2**attempt)
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            time.sleep(2**attempt)
    return {
        "nct_id": record["nct_id"],
        "answer": None,
        "error": last_error,
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }


def load_done() -> set[str]:
    done = set()
    if not OUT_PATH.exists():
        return done
    with OUT_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                if row.get("answer") is not None:
                    done.add(row["nct_id"])
    return done


def main() -> None:
    api_key = load_key()
    trials = load_trials()
    wanted = set(draw_sample(trials))
    records = [t for t in trials if t["nct_id"] in wanted]
    done = load_done()
    pending = [r for r in records if r["nct_id"] not in done]
    print(f"sample={len(records)} done={len(done)} pending={len(pending)}", flush=True)

    lock = Lock()
    finished = 0
    if pending:
        with OUT_PATH.open("a", encoding="utf-8") as handle:
            with ThreadPoolExecutor(max_workers=WORKERS) as pool:
                futures = [pool.submit(extract_one, api_key, r) for r in pending]
                for future in as_completed(futures):
                    result = future.result()
                    with lock:
                        handle.write(json.dumps(result, ensure_ascii=False) + "\n")
                        handle.flush()
                        finished += 1
                        if finished % 25 == 0 or finished == len(pending):
                            print(f"finished={finished} of {len(pending)}", flush=True)

    rows = []
    with OUT_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))

    ok = [r for r in rows if r.get("answer") is not None]
    failed = len(rows) - len(ok)
    in_tok = sum((r.get("usage") or {}).get("input_tokens") or 0 for r in rows)
    out_tok = sum((r.get("usage") or {}).get("output_tokens") or 0 for r in rows)
    cost = (in_tok * INPUT_USD_PER_MILLION + out_tok * OUTPUT_USD_PER_MILLION) / 1_000_000

    report = {
        "model": MODEL,
        "sample_n": len(records),
        "succeeded": len(ok),
        "failed": failed,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "estimated_usd": round(cost, 4),
        "total_facts": sum(len(r["answer"].get("facts") or []) for r in ok),
        "categories": dict(
            Counter(
                f.get("category", "MISSING")
                for r in ok
                for f in (r["answer"].get("facts") or [])
            ).most_common()
        ),
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
