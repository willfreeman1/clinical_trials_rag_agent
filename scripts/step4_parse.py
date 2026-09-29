"""Spike 2, Step 4: can gpt-5.4 take a patient description apart?

Feeds each of the 20 invented descriptions to the same model the answer key
was labelled with, asks for the trait-list shape in the plan, and writes a
check sheet for Will. Thresholds are in THRESHOLDS.md, committed before this
ran.

Does not judge. It flags. Will reads English against the list already written
under each patient in data/fake_patients.md.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mini_pilot import (  # noqa: E402
    INPUT_USD_PER_MILLION,
    MODEL,
    OUTPUT_USD_PER_MILLION,
    load_key,
)

ROOT = Path(__file__).resolve().parents[1]
PATIENTS_MD = ROOT / "data" / "fake_patients.md"
DRAW_PATH = ROOT / "data" / "fake_patients_draw.json"
OUT_PATH = ROOT / "data" / "step4_parse.json"
CHECK_PATH = ROOT / "data" / "step4_check.md"
WORKERS = 4

# Revised once after review, 2026-09-29. First prompt is in git history
# (4597f41). Two fixes: fixed names for one_of_many fields, and tumour
# genetic marker is always one_of_many with value "none" when none found.
SYSTEM = """You read a description of a (fictional) patient and turn it into a clean list of traits. Do not decide whether the patient qualifies for any trial. Do not invent facts that the description does not state.

Each trait has three things, kept separate on purpose:

1. name — a short noun phrase for the subject, with no direction and no number in it. Searching later looks only at this name, so a direction word or a number in it breaks the search.
2. kind — exactly one of: yes_no, one_of_many, number.
3. situation — has, does_not_have, or value. Use has / does_not_have for yes_no traits. Use value for one_of_many and number traits, and put the value in the value field. For yes_no traits set value to null.

Kinds:
- yes_no: the patient either has it or does not. Previous chemotherapy. An autoimmune condition. Cancer spread to the brain.
- one_of_many: the patient has exactly one item from a set of alternatives, which means they do not have the others. Record the value they have, and nothing about the values they lack. These fields are exclusive.
- number: a measured quantity. Age, performance status score, creatinine clearance, number of previous treatment courses. Keep these as number even if a later step will ignore them.

These one_of_many traits must use these exact names. Put the specific value in the value slot, never in the name:

- tumour genetic marker — e.g. EGFR L858R, ALK fusion, none
- disease stage — e.g. IV, IIIB
- histology — e.g. adenocarcinoma
- sex — e.g. female

The tumour genetic marker is always one_of_many, never yes_no. Do not name the trait after one marker ("ALK rearrangement", "EGFR mutation", "targetable alteration on NGS"). A yes_no named after one marker cannot throw out a trial that demands a different marker, because that trial finds no matching trait and silence keeps it. If the description says no marker was found, wild type, no driver, or no targetable alteration, the value is none — not does_not_have on some other trait name.

Worked examples:

- "ALK-rearranged adenocarcinoma" → {"name": "tumour genetic marker", "kind": "one_of_many", "situation": "value", "value": "ALK fusion"}
- "no targetable alteration on NGS" / "wild type" / "no driver" → {"name": "tumour genetic marker", "kind": "one_of_many", "situation": "value", "value": "none"}
- "stage IV lung adeno" → {"name": "disease stage", "kind": "one_of_many", "situation": "value", "value": "IV"} and {"name": "histology", "kind": "one_of_many", "situation": "value", "value": "adenocarcinoma"}
- "67F" → {"name": "sex", "kind": "one_of_many", "situation": "value", "value": "female"}

Other traits keep a stable name with no direction and no number: "previous platinum chemotherapy", "previous immunotherapy", "cancer spread to the brain". Do not turn a drug name into a yes_no named after that drug if the fact is membership of a class — "carbo/pemetrexed" is previous platinum chemotherapy, "pembrolizumab" is previous immunotherapy.

Do not list the alternatives a one_of_many patient lacks.

Return JSON with keys patient_id and traits. traits is a list of objects with keys name, kind, situation, value.
"""

# After the revision, these four names must be exact. Others still flag by alias.
FIXED_ONE_OF_MANY = {
    "tumour genetic marker": "one_of_many",
    "disease stage": "one_of_many",
    "histology": "one_of_many",
    "sex": "one_of_many",
}

ALWAYS = [
    ("age", "number", ("age",)),
    ("disease stage", "one_of_many", ("disease stage",)),
    ("histology", "one_of_many", ("histology",)),
    ("tumour genetic marker", "one_of_many", ("tumour genetic marker", "tumor genetic marker")),
    ("performance status", "number", ("performance", "ecog")),
    ("creatinine clearance", "number", ("creatinine", "crcl", "renal")),
    ("prior lines of therapy", "number", ("line of therapy", "lines of therapy", "prior line", "prior regimen", "treatment line", "treatment courses")),
    ("previous platinum chemotherapy", "yes_no", ("platinum", "cisplatin", "carboplatin")),
    ("previous immunotherapy", "yes_no", ("immunotherapy", "checkpoint", "pd-1", "pd-l1")),
    ("cancer spread to the brain", "yes_no", ("brain", "cerebral", "cns", "central nervous")),
    ("sex", "one_of_many", ("sex",)),
]

OPTIONAL_IF_TRUE = [
    ("autoimmune_disease", "autoimmune disease", "yes_no", ("autoimmune", "rheumatoid", "arthritis")),
    ("interstitial_lung_disease", "interstitial lung disease", "yes_no", ("interstitial", "ild")),
    ("hepatitis_b", "hepatitis b", "yes_no", ("hepatitis b", "hbsag", "entecavir")),
    ("hepatitis_c", "hepatitis c", "yes_no", ("hepatitis c",)),
    ("hiv", "hiv", "yes_no", ("hiv",)),
    ("major_surgery_within_4_weeks", "major surgery", "yes_no", ("surgery", "lobectomy")),
    ("pleural_effusion", "pleural effusion", "yes_no", ("pleural",)),
]

DIRECTION_IN_NAME = re.compile(
    r"\b(must|never|cannot|required|forbidden|without|no prior|not had|untreated|treated)\b"
    r"|[≥≤><]|/\d|(?<![a-zA-Z-])\d+(?:\.\d+)?(?![a-zA-Z])",
    re.IGNORECASE,
)


def load_descriptions() -> dict[str, str]:
    text = PATIENTS_MD.read_text(encoding="utf-8")
    found: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        header = re.match(r"^## (P\d+)\s*$", line)
        if header:
            current = header.group(1)
            found[current] = []
            continue
        if current is None:
            continue
        if line.startswith("## "):
            current = None
            continue
        if line.startswith(">"):
            found[current].append(line[1:].strip())
    return {pid: " ".join(parts) for pid, parts in found.items() if parts}


def ask(api_key: str, patient_id: str, description: str) -> dict:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": f"patient_id: {patient_id}\n\n{description}",
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
    answer = json.loads(content)
    answer["patient_id"] = patient_id
    return {
        "patient_id": patient_id,
        "description": description,
        "answer": answer,
        "usage": {
            "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"),
        },
    }


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def name_hits(name: str, aliases: tuple[str, ...]) -> bool:
    n = norm(name)
    return any(a in n for a in aliases)


def first_hit(traits: list[dict], aliases: tuple[str, ...]) -> dict | None:
    for t in traits:
        if name_hits(t.get("name") or "", aliases):
            return t
    return None


def flag_patient(pid: str, gold: dict, traits: list[dict]) -> dict:
    flags = {"missed": [], "invented_candidates": [], "direction_or_number_in_name": [], "wrong_kind": []}
    matched_idx = set()

    def consider(label: str, expected_kind: str, aliases: tuple[str, ...], required: bool) -> None:
        hit = None
        hit_i = None
        for i, t in enumerate(traits):
            if name_hits(t.get("name") or "", aliases):
                hit, hit_i = t, i
                break
        if hit is None:
            if required:
                flags["missed"].append(label)
            return
        matched_idx.add(hit_i)
        kind = hit.get("kind")
        name = (hit.get("name") or "").strip()
        if label in FIXED_ONE_OF_MANY and name != label:
            flags["wrong_kind"].append(
                f"{label}: name must be exactly '{label}', got '{name}'"
            )
        if kind != expected_kind:
            flags["wrong_kind"].append(
                f"{label}: expected {expected_kind}, got {kind} ({name})"
            )
        if label == "tumour genetic marker" and kind == "yes_no":
            flags["wrong_kind"].append(
                f"tumour genetic marker recorded as yes_no ({name})"
            )
        if DIRECTION_IN_NAME.search(name):
            flags["direction_or_number_in_name"].append(name)

    for label, kind, aliases in ALWAYS:
        consider(label, kind, aliases, required=True)
    for field, label, kind, aliases in OPTIONAL_IF_TRUE:
        consider(label, kind, aliases, required=bool(gold.get(field)))

    known_aliases = [a for *_, aliases in ALWAYS for a in aliases]
    known_aliases += [a for _, _, _, aliases in OPTIONAL_IF_TRUE for a in aliases]
    known_aliases += ("sex", "gender", "male", "female", "woman", "man")
    for i, t in enumerate(traits):
        if i in matched_idx:
            continue
        name = t.get("name") or ""
        if not any(a in norm(name) for a in known_aliases):
            flags["invented_candidates"].append(name or "(empty name)")
        if DIRECTION_IN_NAME.search(name):
            flags["direction_or_number_in_name"].append(name)

    fail = bool(
        flags["missed"]
        or flags["invented_candidates"]
        or flags["direction_or_number_in_name"]
        or flags["wrong_kind"]
    )
    return {"flags": flags, "script_fail": fail}


def parse_one(api_key: str, pid: str, description: str) -> dict:
    last = "unknown error"
    for attempt in range(5):
        try:
            return ask(api_key, pid, description)
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
        "patient_id": pid,
        "description": description,
        "answer": None,
        "error": last,
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }


def write_check(rows: list[dict], gold_by_id: dict, n_fail: int, cost: float) -> None:
    lines = [
        "# Step 4 check sheet — read the English, do not make a medical call",
        "",
        "For each patient: the description, the structured answer already written",
        "in fake_patients.md, the model's trait list, and script flags. The flags",
        "are hints. A close name that the script missed is yours to accept.",
        "",
        f"Script-flagged fails: **{n_fail} of 20**. This is the one permitted",
        "revision. Gate: more than 4 of 20 after revision → stop.",
        "",
        f"Estimated cost: ${cost:.4f}",
        "",
    ]
    for row in rows:
        pid = row["patient_id"]
        gold = gold_by_id[pid]
        lines.append(f"## {pid}")
        lines.append("")
        lines.append(f"> {row['description']}")
        lines.append("")
        lines.append(
            f"- gold: stage {gold['disease_stage']}, {gold['histology']}, "
            f"driver {gold['driver_mutation']}, ECOG {gold['ecog']}, "
            f"CrCl {gold['creatinine_clearance']}, lines {gold['prior_lines_of_therapy']}"
        )
        lines.append(
            f"- gold yes/no: platinum={gold['prior_platinum_chemo']}, "
            f"immuno={gold['prior_immunotherapy']}, "
            f"brain={gold['brain_metastases']} "
            f"(treated/stable={gold['brain_mets_treated_stable']})"
        )
        extras = [k for k, _, _, _ in OPTIONAL_IF_TRUE if gold.get(k)]
        if extras:
            lines.append(f"- gold comorbidities present: {', '.join(extras)}")
        lines.append("")
        if not row.get("answer"):
            lines.append(f"**request failed:** {row.get('error')}")
            lines.append("")
            continue
        lines.append("Model traits:")
        lines.append("")
        lines.append("| name | kind | situation | value |")
        lines.append("|---|---|---|---|")
        for t in row["answer"].get("traits") or []:
            lines.append(
                f"| {t.get('name','')} | {t.get('kind','')} | "
                f"{t.get('situation','')} | {t.get('value')} |"
            )
        lines.append("")
        flags = row["flags"]
        if row["script_fail"]:
            lines.append("**script: FAIL**")
        else:
            lines.append("**script: clear**")
        for kind, items in flags.items():
            if items:
                lines.append(f"- {kind}: " + "; ".join(items))
        lines.append("")
    CHECK_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    descriptions = load_descriptions()
    draw = json.loads(DRAW_PATH.read_text(encoding="utf-8"))
    gold_by_id = {p["id"]: p for p in draw["patients"]}
    missing = [pid for pid in gold_by_id if pid not in descriptions]
    if missing:
        raise SystemExit(f"missing descriptions: {missing}")

    api_key = load_key()
    order = sorted(gold_by_id, key=lambda s: int(s[1:]))
    rows_by_id: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = {
            pool.submit(parse_one, api_key, pid, descriptions[pid]): pid
            for pid in order
        }
        for fut in as_completed(futs):
            row = fut.result()
            rows_by_id[row["patient_id"]] = row
            print(row["patient_id"], "ok" if row.get("answer") else row.get("error"), flush=True)

    rows = []
    input_tokens = output_tokens = 0
    n_fail = 0
    for pid in order:
        row = rows_by_id[pid]
        traits = (row.get("answer") or {}).get("traits") or []
        flagged = flag_patient(pid, gold_by_id[pid], traits)
        row.update(flagged)
        if row["script_fail"] or not row.get("answer"):
            n_fail += 1
        input_tokens += (row["usage"] or {}).get("input_tokens") or 0
        output_tokens += (row["usage"] or {}).get("output_tokens") or 0
        rows.append(row)

    cost = (
        input_tokens * INPUT_USD_PER_MILLION + output_tokens * OUTPUT_USD_PER_MILLION
    ) / 1_000_000
    report = {
        "model": MODEL,
        "n_patients": len(rows),
        "n_script_fail": n_fail,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_usd": round(cost, 4),
        "revision": 1,
        "gates": {"revise_if_more_than": 2, "stop_after_revision_if_more_than": 4},
        "patients": rows,
    }
    OUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_check(rows, gold_by_id, n_fail, cost)
    print()
    print(f"script-flagged fails: {n_fail} of 20")
    print(f"tokens in={input_tokens} out={output_tokens}  est ${cost:.4f}")
    print(f"Wrote {OUT_PATH}")
    print(f"Wrote {CHECK_PATH}")


if __name__ == "__main__":
    main()
