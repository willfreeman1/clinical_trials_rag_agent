"""Step 3c: assign each answer-key quote to one closed name.

The model sees the sentence only — not which fact it was labelled as.
Matching later is exact equality on these names. Thresholds in
THRESHOLDS.md, committed before this ran.
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
from step3b_normalise import collect_quotes  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "step3c_closed_names.jsonl"
SUMMARY = ROOT / "data" / "step3c_closed_names_summary.json"
BATCH = 20

CLOSED_NAMES = (
    "previous immunotherapy",
    "cancer spread to the brain",
    "tumour genetic marker",
    "previous platinum chemotherapy",
    "autoimmune disease",
    "disease stage",
    "other",
)

FACT_TO_NAME = {
    "prior_immunotherapy": "previous immunotherapy",
    "brain_metastases": "cancer spread to the brain",
    "driver_mutation": "tumour genetic marker",
    "prior_platinum_chemo": "previous platinum chemotherapy",
    "autoimmune_disease": "autoimmune disease",
    "disease_stage": "disease stage",
}

NAME_ALIASES = {
    "previous immunotherapy": "previous immunotherapy",
    "previous checkpoint inhibitor": "previous immunotherapy",
    "cancer spread to the brain": "cancer spread to the brain",
    "tumour genetic marker": "tumour genetic marker",
    "tumor genetic marker": "tumour genetic marker",
    "previous platinum chemotherapy": "previous platinum chemotherapy",
    "autoimmune disease": "autoimmune disease",
    "autoimmune condition": "autoimmune disease",
    "disease stage": "disease stage",
    "other": "other",
}

SYSTEM = """You read eligibility-criteria sentences from clinical trials. For each sentence, assign the thing the rule is about to exactly one name from this closed list:

- previous immunotherapy
- cancer spread to the brain
- tumour genetic marker
- previous platinum chemotherapy
- autoimmune disease
- disease stage
- other

Rules:
- Use those spellings exactly. Do not invent a name. Do not put a value or a direction in the name.
- The tumour genetic marker is always that name, even when the sentence names a specific gene or says no marker / wild type / none found. Never invent a yes-or-no name after one gene.
- previous immunotherapy covers checkpoint inhibitors, PD-1, PD-L1, CTLA-4, and named drugs in that class (pembrolizumab, nivolumab, atezolizumab, durvalumab, ipilimumab).
- previous platinum chemotherapy covers cisplatin, carboplatin, oxaliplatin, and "platinum-based" chemotherapy. Pemetrexed or docetaxel alone is other unless platinum is also named.
- cancer spread to the brain covers brain metastases, CNS metastases, cerebral metastases, intracranial metastases, leptomeningeal disease. Bone metastases alone are other.
- autoimmune disease covers named autoimmune conditions (rheumatoid arthritis, lupus, IBD, and the like) and "autoimmune disease" as a class.
- disease stage covers numbered stages (I–IV, IIIB) and descriptive stage language (metastatic, locally advanced, unresectable) when that is what the rule is about. "Histologically confirmed" of a stage is disease stage.
- If the sentence is not about any of the six, return other.

Worked examples:
- "No prior PD-1 or PD-L1 inhibitor therapy." → previous immunotherapy
- "Patients with untreated CNS metastases are excluded." → cancer spread to the brain
- "Must have a documented EGFR exon 19 deletion." → tumour genetic marker
- "No targetable driver alteration identified on NGS." → tumour genetic marker
- "No prior platinum-based chemotherapy." → previous platinum chemotherapy
- "History of active autoimmune disease requiring systemic treatment." → autoimmune disease
- "Histologically or cytologically confirmed stage IV NSCLC." → disease stage
- "ECOG performance status 0-1." → other

Return JSON with one key, items, an array of objects with keys id and name. Keep the id exactly as given. One name per id, from the list above.
"""


def canonical_name(raw: str) -> str:
    text = " ".join((raw or "").strip().lower().split())
    text = text.replace("tumor", "tumour")
    return NAME_ALIASES.get(text, "other")


def load_done() -> set[str]:
    done = set()
    if not OUT.exists():
        return done
    with OUT.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("assigned_name"):
                done.add(row["id"])
    return done


def ask_batch(api_key: str, batch: list[dict]) -> dict:
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
        if item.get("id") and item.get("name"):
            mapping[item["id"]] = canonical_name(str(item["name"]))
    return {
        "names": mapping,
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
                assigned = result["names"].get(row["id"], "other")
                out = {**row, "assigned_name": assigned}
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
    empty = sum(1 for r in unique if not r.get("assigned_name") or r["assigned_name"] == "other")
    agree = sum(1 for r in unique if r.get("assigned_name") == FACT_TO_NAME.get(r.get("fact")))
    cost = (input_tokens * INPUT_USD_PER_MILLION + output_tokens * OUTPUT_USD_PER_MILLION) / 1_000_000
    summary = {
        "model": MODEL,
        "n_quotes": len(quotes),
        "n_written_unique": len(unique),
        "n_other_or_empty": empty,
        "assignment_agree_with_source": agree,
        "assignment_accuracy": round(agree / len(unique), 4) if unique else None,
        "this_run_input_tokens": input_tokens,
        "this_run_output_tokens": output_tokens,
        "this_run_estimated_usd": round(cost, 4),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
