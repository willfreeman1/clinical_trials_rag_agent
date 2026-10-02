"""Collect conditional rules and assign each to the closed question list."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mini_pilot import (  # noqa: E402
    INPUT_USD_PER_MILLION,
    MODEL,
    OUTPUT_USD_PER_MILLION,
    load_key,
)
from step10_common import QUESTION_IDS  # noqa: E402
from step2_ceiling import load_markers, load_step5b, load_yes_no  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "step10_assigned.jsonl"
SUMMARY = DATA / "step10_assigned_summary.json"
BATCH = 20

CLOSED = """- brain_treatment — how the brain metastases were treated (untreated vs treated)
- brain_stable_weeks — how long the brain lesions have been radiographically stable
- brain_symptoms — current neurological symptoms from brain metastases
- brain_steroids — corticosteroids required for CNS disease
- leptomeningeal — leptomeningeal / carcinomatous meningitis
- autoimmune_activity — whether autoimmune disease is currently active
- autoimmune_systemic_months — how long since autoimmune disease last needed systemic treatment
- immuno_washout_weeks — time since last immunotherapy
- systemic_washout_weeks — time since last systemic anticancer treatment
- amenable_to_curative_therapy — whether the disease can still be treated with curative surgery or radiotherapy
- other — not a fact about the patient (cohort, study part, trial histology, biomarker of the tumour the trial is for)
"""

SYSTEM = f"""You read a short eligibility condition from a lung-cancer trial. Assign it to one or more names from this closed list of coordinator questions. Do not invent a name. Do not write a new question.

{CLOSED}

Rules:
- Use those spellings exactly.
- If the sentence states several patient conditions (treated AND stable four weeks AND off steroids), return one tag per condition, each from the list.
- If the sentence is about a cohort, arm, protocol part, or a cancer type the trial enrols, return only other.
- For time limits, copy the number into threshold and the unit into unit (weeks, months, days, years). Do not convert units.
- Do not put a value or a direction in the question name. The threshold field holds the trial's own limit.
- brain_stable_weeks is for stability duration. brain_treatment is for untreated vs treated. They are different names.
- A washout ("no immunotherapy within 4 weeks") is immuno_washout_weeks or systemic_washout_weeks, not other.
- "Active autoimmune disease requiring systemic treatment in the past 2 years" tags autoimmune_activity and autoimmune_systemic_months.

Return JSON with key items, an array of objects: id (exactly as given), tags (array). Each tag has question, threshold, unit.
threshold is a number when the condition has a time limit, or a short string for a categorical limit, or null.
unit is weeks/months/days/years/null.
"""


def collect_items() -> list[dict]:
    yes_no = load_yes_no()
    extra = load_step5b()
    markers = load_markers()
    items = []
    for nct, answer in yes_no.items():
        for fact, class_key, quote_key in (
            ("prior_immunotherapy", "prior_immunotherapy_classification", "prior_immunotherapy_quote"),
            ("brain_metastases", "brain_metastases_classification", "brain_metastases_quote"),
        ):
            if answer.get(class_key) == "barred_with_exception":
                quote = (answer.get(quote_key) or "").strip()
                if quote:
                    items.append({"id": f"{nct}|{fact}|bwe", "nct_id": nct, "fact": fact, "source": "bwe", "text": quote})
    for nct, answer in extra.items():
        for fact, class_key, quote_key in (
            ("prior_platinum_chemo", "prior_platinum_chemo_classification", "prior_platinum_chemo_quote"),
            ("autoimmune_disease", "autoimmune_disease_classification", "autoimmune_disease_quote"),
        ):
            if answer.get(class_key) == "barred_with_exception":
                quote = (answer.get(quote_key) or "").strip()
                if quote:
                    items.append({"id": f"{nct}|{fact}|bwe", "nct_id": nct, "fact": fact, "source": "bwe", "text": quote})
        cond = (answer.get("stage_condition") or "").strip()
        if cond:
            quote = (answer.get("stage_quote") or "").strip()
            text = cond if not quote else f"{cond}\n\n{quote}"
            items.append({"id": f"{nct}|disease_stage|cond", "nct_id": nct, "fact": "disease_stage", "source": "condition", "text": text})
    for nct, answer in markers.items():
        cond = (answer.get("genetic_marker_condition") or "").strip()
        if cond:
            quote = (answer.get("genetic_marker_quote") or "").strip()
            text = cond if not quote else f"{cond}\n\n{quote}"
            items.append({"id": f"{nct}|driver_mutation|cond", "nct_id": nct, "fact": "driver_mutation", "source": "condition", "text": text})
    return items


def load_done() -> set[str]:
    done = set()
    if not OUT.exists():
        return done
    with OUT.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("tags") is not None:
                done.add(row["id"])
    return done


def clean_tags(raw) -> list[dict]:
    tags = []
    if not isinstance(raw, list):
        return [{"question": "other", "threshold": None, "unit": None}]
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("question") or "other").strip()
        if name not in QUESTION_IDS:
            name = "other"
        tags.append({
            "question": name,
            "threshold": item.get("threshold"),
            "unit": item.get("unit"),
        })
    if not tags:
        tags = [{"question": "other", "threshold": None, "unit": None}]
    return tags


def ask_batch(api_key: str, batch: list[dict]) -> dict:
    payload_items = []
    for row in batch:
        text = row["text"]
        if len(text) > 900:
            text = text[:900]
        payload_items.append({"id": row["id"], "sentence": text})
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps({"items": payload_items}, ensure_ascii=False)},
        ],
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        raw = json.loads(response.read().decode("utf-8"))
    content = json.loads(raw["choices"][0]["message"]["content"])
    usage = raw.get("usage") or {}
    mapping = {}
    for item in content.get("items") or []:
        if item.get("id"):
            mapping[item["id"]] = clean_tags(item.get("tags"))
    return {
        "names": mapping,
        "input_tokens": usage.get("prompt_tokens") or 0,
        "output_tokens": usage.get("completion_tokens") or 0,
    }


def main() -> None:
    items = collect_items()
    done = load_done()
    pending = [q for q in items if q["id"] not in done]
    print(f"items={len(items)} already_done={len(done)} pending={len(pending)}", flush=True)
    api_key = load_key()
    input_tokens = output_tokens = 0
    with OUT.open("a", encoding="utf-8") as handle:
        for start in range(0, len(pending), BATCH):
            batch = pending[start : start + BATCH]
            last = "unknown"
            result = None
            for attempt in range(5):
                try:
                    result = ask_batch(api_key, batch)
                    break
                except urllib.error.HTTPError as exc:
                    last = f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:300]}"
                    if exc.code not in (429, 500, 502, 503):
                        break
                    time.sleep(2 ** attempt)
                except Exception as exc:
                    last = str(exc)
                    time.sleep(2 ** attempt)
            if result is None:
                print(f"batch failed at {start}: {last}", flush=True)
                continue
            input_tokens += result["input_tokens"]
            output_tokens += result["output_tokens"]
            for row in batch:
                tags = result["names"].get(row["id"]) or [{"question": "other", "threshold": None, "unit": None}]
                out = {**row, "tags": tags}
                handle.write(json.dumps(out, ensure_ascii=False) + "\n")
            handle.flush()
            finished = min(start + BATCH, len(pending))
            if finished % 100 == 0 or finished == len(pending):
                print(f"finished={finished} of {len(pending)}", flush=True)

    all_rows = []
    if OUT.exists():
        with OUT.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    all_rows.append(json.loads(line))
    seen: dict[str, dict] = {}
    for row in all_rows:
        seen[row["id"]] = row
    unique = list(seen.values())
    from collections import Counter
    qcount = Counter()
    other_only = 0
    for row in unique:
        names = {t["question"] for t in row.get("tags") or []}
        for n in names:
            qcount[n] += 1
        if names == {"other"} or not names:
            other_only += 1
    cost = (input_tokens * INPUT_USD_PER_MILLION + output_tokens * OUTPUT_USD_PER_MILLION) / 1_000_000
    summary = {
        "model": MODEL,
        "n_items": len(items),
        "n_written_unique": len(unique),
        "n_other_only": other_only,
        "question_counts": dict(qcount.most_common()),
        "this_run_input_tokens": input_tokens,
        "this_run_output_tokens": output_tokens,
        "this_run_estimated_usd": round(cost, 4),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
