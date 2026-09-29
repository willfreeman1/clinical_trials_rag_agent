"""Step 3b: turn answer-key quotes into general-term subjects.

The big model sees the sentence only — not which fact it was labelled as, and
not the patient field names. Writes one JSON line per quote. Resumable.

Thresholds in THRESHOLDS.md, committed before this ran.
"""

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

ROOT = Path(__file__).resolve().parents[1]
ANSWER_KEY = ROOT / "data" / "answer_key.jsonl"
MARKERS = ROOT / "data" / "answer_key_markers.jsonl"
STEP5B = ROOT / "data" / "answer_key_step5b.jsonl"
OUT = ROOT / "data" / "step3b_quote_subjects.jsonl"
SUMMARY = ROOT / "data" / "step3b_normalise_summary.json"
BATCH = 20

SYSTEM = """You read eligibility-criteria sentences from clinical trials. For each sentence, return a short general-term subject: the thing the rule is about.

Rules:
- No direction, no number, no "must" / "no" / "prior" / "untreated".
- Prefer the class over a specific drug: carboplatin → platinum chemotherapy; pembrolizumab → immunotherapy.
- Prefer a gene name over a specific variant when the sentence is about that gene: EGFR exon 19 deletion → EGFR mutation.
- Do not use a closed list of field names. Write the ordinary general term.
- If the sentence is mainly about two things, join them with " and ".

Return JSON with one key, items, an array of objects with keys id and subject. Keep the id exactly as given. One subject per id.
"""


def collect_quotes() -> list[dict]:
    rows = []
    with ANSWER_KEY.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            answer = row.get("answer") or {}
            nct = row["nct_id"]
            for fact, class_key, quote_key in (
                ("prior_immunotherapy", "prior_immunotherapy_classification", "prior_immunotherapy_quote"),
                ("brain_metastases", "brain_metastases_classification", "brain_metastases_quote"),
            ):
                verdict = answer.get(class_key) or "not_mentioned"
                quote = (answer.get(quote_key) or "").strip()
                if verdict == "not_mentioned" or not quote:
                    continue
                rows.append({"id": f"{nct}::{fact}", "nct_id": nct, "fact": fact, "quote": quote, "verdict": verdict})
    if MARKERS.exists():
        with MARKERS.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                answer = row.get("answer") or {}
                req = answer.get("required_markers") or []
                ref = answer.get("refused_markers") or []
                quote = (answer.get("genetic_marker_quote") or "").strip()
                if (not req and not ref) or not quote:
                    continue
                rows.append({
                    "id": f"{row['nct_id']}::driver_mutation",
                    "nct_id": row["nct_id"],
                    "fact": "driver_mutation",
                    "quote": quote,
                    "verdict": "has_rule",
                })
    if STEP5B.exists():
        with STEP5B.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                answer = row.get("answer") or {}
                nct = row["nct_id"]
                for fact, class_key, quote_key in (
                    ("prior_platinum_chemo", "prior_platinum_chemo_classification", "prior_platinum_chemo_quote"),
                    ("autoimmune_disease", "autoimmune_disease_classification", "autoimmune_disease_quote"),
                ):
                    verdict = answer.get(class_key) or "not_mentioned"
                    quote = (answer.get(quote_key) or "").strip()
                    if verdict == "not_mentioned" or not quote:
                        continue
                    rows.append({"id": f"{nct}::{fact}", "nct_id": nct, "fact": fact, "quote": quote, "verdict": verdict})
                allowed = answer.get("allowed_stages") or []
                refused = answer.get("refused_stages") or []
                quote = (answer.get("stage_quote") or "").strip()
                if (allowed or refused) and quote:
                    rows.append({
                        "id": f"{nct}::disease_stage",
                        "nct_id": nct,
                        "fact": "disease_stage",
                        "quote": quote,
                        "verdict": "has_rule",
                    })
    return rows


def load_done() -> set[str]:
    done = set()
    if not OUT.exists():
        return done
    with OUT.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("subject"):
                done.add(row["id"])
    return done


def ask_batch(api_key: str, batch: list[dict]) -> dict[str, str]:
    payload_items = [{"id": r["id"], "sentence": r["quote"]} for r in batch]
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
        if item.get("id") and item.get("subject"):
            mapping[item["id"]] = str(item["subject"]).strip()
    return {
        "subjects": mapping,
        "input_tokens": usage.get("prompt_tokens") or 0,
        "output_tokens": usage.get("completion_tokens") or 0,
    }


def main() -> None:
    quotes = collect_quotes()
    done = load_done()
    pending = [q for q in quotes if q["id"] not in done]
    print(f"quotes={len(quotes)} already_done={len(done)} pending={len(pending)}", flush=True)
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
                subject = result["subjects"].get(row["id"], "")
                out = {**row, "subject": subject}
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
    empty = sum(1 for r in all_rows if not r.get("subject"))
    cost = (input_tokens * INPUT_USD_PER_MILLION + output_tokens * OUTPUT_USD_PER_MILLION) / 1_000_000
    # tokens above are this run only; say so
    summary = {
        "model": MODEL,
        "n_quotes": len(quotes),
        "n_written": len(all_rows),
        "n_empty_subject": empty,
        "this_run_input_tokens": input_tokens,
        "this_run_output_tokens": output_tokens,
        "this_run_estimated_usd": round(cost, 4),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
