"""Generate stripped coordinator notes. Leak-check excluded facts. Resumable."""

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

from mini_pilot import INPUT_USD_PER_MILLION, MODEL, OUTPUT_USD_PER_MILLION, load_key  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ROOT / "sparse_configs.json"
DRAW = ROOT / "data" / "fake_patients_draw.json"
OUT = ROOT / "data" / "step11_notes.jsonl"
SUMMARY = ROOT / "data" / "step11_notes_summary.json"
WORKERS = 8
MAX_TRIES = 5

LEAK = {
    "driver_mutation": re.compile(
        r"egfr|alk|kras|ros1|braf|\bmet\b|\bret\b|ntrk|her2|erbb2|"
        r"wild[\s-]?type|driver|ngs|targetable|l858r|exon 19|rearrangement|"
        r"no mutation|no driver|none identified",
        re.IGNORECASE,
    ),
    "disease_stage": re.compile(
        r"\bstage\b|\bIV\b|\bIIIB\b|\bIIIA\b|\bmetastatic\b|locally[\s-]*advanced",
        re.IGNORECASE,
    ),
    "prior_immunotherapy": re.compile(
        r"immuno|checkpoint|pembrolizumab|nivolumab|atezolizumab|durvalumab|"
        r"pd-1|pd-l1|\bpd1\b|\bpdl1\b|keytruda|opdivo",
        re.IGNORECASE,
    ),
    "prior_platinum_chemo": re.compile(
        r"platinum|cisplatin|carboplatin|carbo/|oxaliplatin",
        re.IGNORECASE,
    ),
    "brain_metastases": re.compile(
        r"brain|cerebral|\bcns\b|intracranial|leptomening|\bsrs\b|stereotactic",
        re.IGNORECASE,
    ),
    "autoimmune_disease": re.compile(
        r"autoimmune|rheumatoid|lupus|colitis|crohn|psoriasis",
        re.IGNORECASE,
    ),
}

SYSTEM = """You write a short coordinator-style note about a fictional lung-cancer patient. Do not decide whether they qualify for a trial.

Always include: age, sex, that they have non-small cell lung cancer, and that they were seen in clinic.
Include ONLY the extra facts listed under "Include". Use the values given. Clinical shorthand is fine. Two to four sentences.

Do not mention anything in "Do not mention". Do not hint at those facts by negation ("no brain mets", "never had immunotherapy", "wild type"). If a fact is not in Include, it is absent from the note.
"""


def fact_value(p: dict, fact: str) -> str:
    if fact == "driver_mutation":
        return f"tumour genetic marker = {p['driver_mutation']}"
    if fact == "disease_stage":
        return f"disease stage = {p['disease_stage']}"
    if fact == "prior_immunotherapy":
        return f"previous immunotherapy = {'yes' if p['prior_immunotherapy'] else 'no'}"
    if fact == "prior_platinum_chemo":
        return f"previous platinum chemotherapy = {'yes' if p['prior_platinum_chemo'] else 'no'}"
    if fact == "brain_metastases":
        extra = ""
        if p["brain_metastases"] and p.get("brain_mets_treated_stable") is True:
            extra = " (treated and stable)"
        elif p["brain_metastases"]:
            extra = " (untreated)"
        return f"cancer spread to the brain = {'yes' if p['brain_metastases'] else 'no'}{extra}"
    if fact == "autoimmune_disease":
        return f"autoimmune disease = {'yes' if p['autoimmune_disease'] else 'no'}"
    return fact


def leaks(text: str, exclude: list[str], gold: dict) -> list[str]:
    hits = []
    for fact in exclude:
        if LEAK[fact].search(text or ""):
            hits.append(fact)
            continue
        if fact == "driver_mutation":
            val = (gold.get("driver_mutation") or "").strip()
            if val and len(val) >= 4 and val.lower() in (text or "").lower():
                hits.append(fact)
    return hits


def load_done() -> set[str]:
    done = set()
    if not OUT.exists():
        return done
    with OUT.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("note") and not row.get("leaked"):
                done.add(row["id"])
    return done


def ask(api_key: str, user: str) -> dict:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        body = json.loads(response.read().decode("utf-8"))
    usage = body.get("usage") or {}
    return {
        "note": (body["choices"][0]["message"]["content"] or "").strip(),
        "usage": {
            "input_tokens": usage.get("prompt_tokens") or 0,
            "output_tokens": usage.get("completion_tokens") or 0,
        },
    }


def generate_one(api_key: str, cfg: dict, gold: dict) -> dict:
    include_lines = "\n".join(f"- {fact_value(gold, f)}" for f in cfg["include"]) or "- (none beyond age, sex, NSCLC, clinic)"
    exclude_lines = "\n".join(f"- {f}" for f in cfg["exclude"]) or "- (nothing)"
    user = (
        f"Patient {cfg['patient_id']}, age {gold['age']}, sex {gold['sex']}.\n\n"
        f"Include:\n{include_lines}\n\nDo not mention:\n{exclude_lines}"
    )
    acc_in = acc_out = 0
    leak_tries = 0
    last_note = ""
    last_hits: list[str] = []
    extra = ""
    for attempt in range(MAX_TRIES):
        try:
            result = ask(api_key, user + extra)
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503):
                time.sleep(2 ** attempt)
                continue
            return {
                "id": cfg["id"],
                "note": None,
                "error": f"HTTP {exc.code}",
                "leaked": True,
                "leak_hits": [],
                "leak_tries": leak_tries,
                "usage": {"input_tokens": acc_in, "output_tokens": acc_out},
            }
        except Exception as exc:
            time.sleep(2 ** attempt)
            last_note = str(exc)
            continue
        acc_in += result["usage"]["input_tokens"]
        acc_out += result["usage"]["output_tokens"]
        last_note = result["note"]
        last_hits = leaks(last_note, cfg["exclude"], gold)
        if not last_hits:
            return {
                "id": cfg["id"],
                "patient_id": cfg["patient_id"],
                "k": cfg["k"],
                "draw": cfg["draw"],
                "include": cfg["include"],
                "exclude": cfg["exclude"],
                "note": last_note,
                "leaked": False,
                "leak_hits": [],
                "leak_tries": leak_tries,
                "usage": {"input_tokens": acc_in, "output_tokens": acc_out},
            }
        leak_tries += 1
        extra = (
            "\n\nThe previous draft leaked these excluded facts: "
            + ", ".join(last_hits)
            + ". Rewrite with no mention of them, including by negation."
        )
    return {
        "id": cfg["id"],
        "patient_id": cfg["patient_id"],
        "k": cfg["k"],
        "draw": cfg["draw"],
        "include": cfg["include"],
        "exclude": cfg["exclude"],
        "note": last_note,
        "leaked": True,
        "leak_hits": last_hits,
        "leak_tries": leak_tries,
        "usage": {"input_tokens": acc_in, "output_tokens": acc_out},
    }


def main() -> None:
    payload = json.loads(CONFIGS.read_text(encoding="utf-8"))
    gold = {p["id"]: p for p in json.loads(DRAW.read_text(encoding="utf-8"))["patients"]}
    done = load_done()
    todo = [c for c in payload["configs"] if c["id"] not in done]
    print(f"configs={len(payload['configs'])} done={len(done)} todo={len(todo)}", flush=True)
    api_key = load_key()
    lock = Lock()
    rows = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(generate_one, api_key, c, gold[c["patient_id"]]): c["id"] for c in todo}
        for future in as_completed(futures):
            row = future.result()
            with lock:
                rows.append(row)
                with OUT.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                print(row["id"], "leaked" if row.get("leaked") else "ok", flush=True)

    all_rows = []
    if OUT.exists():
        with OUT.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    all_rows.append(json.loads(line))
    seen = {r["id"]: r for r in all_rows}
    unique = list(seen.values())
    leaked = sum(1 for r in unique if r.get("leaked"))
    first_pass_leaks = sum(1 for r in unique if (r.get("leak_tries") or 0) > 0)
    in_tok = sum((r.get("usage") or {}).get("input_tokens") or 0 for r in unique)
    out_tok = sum((r.get("usage") or {}).get("output_tokens") or 0 for r in unique)
    cost = (in_tok * INPUT_USD_PER_MILLION + out_tok * OUTPUT_USD_PER_MILLION) / 1_000_000
    summary = {
        "n": len(unique),
        "n_leaked_final": leaked,
        "n_needed_retry": first_pass_leaks,
        "leak_rate_final": round(leaked / len(unique), 4) if unique else None,
        "leak_rate_first_draft": round(first_pass_leaks / len(unique), 4) if unique else None,
        "estimated_usd": round(cost, 4),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
