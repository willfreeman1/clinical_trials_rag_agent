"""Step 3d: re-assign platinum, immunotherapy, and current-other quotes.

Extended closed list includes previous chemotherapy (any kind) and previous
systemic anticancer treatment (any kind). Other four facts' assignments are
copied from Step 3c unchanged. Thresholds committed before this ran.
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
OLD = ROOT / "data" / "step3c_closed_names.jsonl"
OUT = ROOT / "data" / "step3d_closed_names.jsonl"
SUMMARY = ROOT / "data" / "step3d_reassign_summary.json"
BATCH = 20

SOURCE_RERUN = {"prior_platinum_chemo", "prior_immunotherapy"}

NAME_ALIASES = {
    "previous immunotherapy": "previous immunotherapy",
    "previous checkpoint inhibitor": "previous immunotherapy",
    "cancer spread to the brain": "cancer spread to the brain",
    "tumour genetic marker": "tumour genetic marker",
    "tumor genetic marker": "tumour genetic marker",
    "previous platinum chemotherapy": "previous platinum chemotherapy",
    "previous chemotherapy (any kind)": "previous chemotherapy (any kind)",
    "previous chemotherapy": "previous chemotherapy (any kind)",
    "previous systemic anticancer treatment (any kind)": "previous systemic anticancer treatment (any kind)",
    "previous systemic anticancer treatment": "previous systemic anticancer treatment (any kind)",
    "previous systemic therapy": "previous systemic anticancer treatment (any kind)",
    "previous anticancer therapy of any kind": "previous anticancer therapy of any kind",
    "previous anticancer therapy": "previous anticancer therapy of any kind",
    "no prior anticancer therapy": "previous anticancer therapy of any kind",
    "autoimmune disease": "autoimmune disease",
    "autoimmune condition": "autoimmune disease",
    "disease stage": "disease stage",
    "other": "other",
}

SYSTEM = """You read eligibility-criteria sentences from clinical trials. For each sentence, assign the thing the rule is about to exactly one name from this closed list:

- previous immunotherapy
- previous platinum chemotherapy
- previous chemotherapy (any kind)
- previous systemic anticancer treatment (any kind)
- cancer spread to the brain
- tumour genetic marker
- autoimmune disease
- disease stage
- other

Rules:
- Use those spellings exactly. Do not invent a name. Do not put a value or a direction in the name.
- Assign the level the sentence actually states. Do not promote a platinum sentence up to chemotherapy, and do not demote a chemotherapy sentence down to platinum.
- previous platinum chemotherapy — the sentence names cisplatin, carboplatin, oxaliplatin, or says platinum / platinum-based.
- previous chemotherapy (any kind) — the sentence is about chemotherapy and does not name platinum or a platinum drug. Pemetrexed or docetaxel alone belongs here.
- previous immunotherapy — checkpoint inhibitors, PD-1, PD-L1, CTLA-4, and named drugs in that class (pembrolizumab, nivolumab, atezolizumab, durvalumab, ipilimumab). Not under chemotherapy.
- previous systemic anticancer treatment (any kind) — the sentence is about systemic therapy / systemic anticancer treatment / systemic antitumor therapy and does not say chemotherapy vs immunotherapy vs a named class.
- cancer spread to the brain covers brain metastases, CNS metastases, cerebral metastases, intracranial metastases, leptomeningeal disease. Bone metastases alone are other.
- tumour genetic marker is always that name, even when the sentence names a specific gene or says none / wild type.
- autoimmune disease covers named autoimmune conditions and "autoimmune disease" as a class.
- disease stage covers numbered stages and descriptive stage language (metastatic, locally advanced, unresectable) when that is what the rule is about.
- If the sentence is not about any of these, return other.

Worked examples:
- "No prior platinum-based chemotherapy." → previous platinum chemotherapy
- "No prior chemotherapy." / "Any prior chemotherapy." → previous chemotherapy (any kind)
- "No prior systemic anticancer treatment." / "No prior systemic therapy." → previous systemic anticancer treatment (any kind)
- "No prior PD-1 or PD-L1 inhibitor therapy." → previous immunotherapy
- "Patients with untreated CNS metastases are excluded." → cancer spread to the brain
- "ECOG performance status 0-1." → other

Return JSON with one key, items, an array of objects with keys id and name. Keep the id exactly as given. One name per id, from the list above.
"""


def canonical_name(raw: str) -> str:
    text = " ".join((raw or "").strip().lower().split())
    text = text.replace("tumor", "tumour")
    if text in NAME_ALIASES:
        return NAME_ALIASES[text]
    return "other"


def load_old() -> dict[str, dict]:
    seen: dict[str, dict] = {}
    with OLD.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            seen[row["id"]] = row
    return seen


def load_done() -> set[str]:
    done = set()
    if not OUT.exists():
        return done
    with OUT.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("assigned_name") and row.get("reassigned"):
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
    quotes = {q["id"]: q for q in collect_quotes()}
    old = load_old()
    rerun_ids = []
    copied = 0
    for qid, q in quotes.items():
        prev = old.get(qid) or {}
        prev_name = prev.get("assigned_name") or ""
        if q.get("fact") in SOURCE_RERUN or prev_name == "other":
            rerun_ids.append(qid)
        else:
            copied += 1
    done = load_done()
    pending_ids = [i for i in rerun_ids if i not in done]
    print(
        f"quotes={len(quotes)} rerun={len(rerun_ids)} copied_unchanged={copied} "
        f"already_done={len(done)} pending={len(pending_ids)}",
        flush=True,
    )

    # Write copied rows once if this is a fresh file.
    if not OUT.exists():
        with OUT.open("w", encoding="utf-8") as handle:
            for qid, q in quotes.items():
                prev = old.get(qid) or {}
                prev_name = prev.get("assigned_name") or ""
                if q.get("fact") in SOURCE_RERUN or prev_name == "other":
                    continue
                row = {**q, "assigned_name": canonical_name(prev_name) if prev_name else "other", "reassigned": False}
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    api_key = load_key()
    input_tokens = output_tokens = 0
    pending_rows = [quotes[i] for i in pending_ids]
    with OUT.open("a", encoding="utf-8") as handle:
        for start in range(0, len(pending_rows), BATCH):
            batch = pending_rows[start : start + BATCH]
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
                out = {**row, "assigned_name": assigned, "reassigned": True}
                handle.write(json.dumps(out, ensure_ascii=False) + "\n")
            handle.flush()
            finished = min(start + BATCH, len(pending_rows))
            if finished % 100 == 0 or finished == len(pending_rows):
                print(f"finished={finished} of {len(pending_rows)}", flush=True)

    unique: dict[str, dict] = {}
    if OUT.exists():
        with OUT.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    row = json.loads(line)
                    unique[row["id"]] = row
    cost = (input_tokens * INPUT_USD_PER_MILLION + output_tokens * OUTPUT_USD_PER_MILLION) / 1_000_000
    counts: dict[str, int] = {}
    for row in unique.values():
        name = row.get("assigned_name") or "other"
        counts[name] = counts.get(name, 0) + 1
    summary = {
        "model": MODEL,
        "n_quotes": len(quotes),
        "n_written_unique": len(unique),
        "n_reassigned": sum(1 for r in unique.values() if r.get("reassigned")),
        "assigned_counts": counts,
        "this_run_input_tokens": input_tokens,
        "this_run_output_tokens": output_tokens,
        "this_run_estimated_usd": round(cost, 4),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
