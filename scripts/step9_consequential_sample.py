"""Draw 30 barred/required rows for Will. Writes ids first; sheet is a second step.

Seed 202609301. Thresholds committed before the ids were written.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from step5_label_markers import as_list as marker_as_list  # noqa: E402
from step5_label_rest import as_list  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SEED = 202609301
IDS_PATH = ROOT / "step9_consequential_ids.json"
SHEET = ROOT / "docs" / "step9_consequential_check.md"
NOTES = ROOT / "docs" / "step9_consequential_notes.md"

# fact -> (n, file, how to list barred, how to list required, quote_key, note_key, display)
# filled in main from loaders


def load(name: str) -> dict[str, dict]:
    found = {}
    with (DATA / name).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("answer"):
                found[row["nct_id"]] = row
    return found


def split_counts(n: int, n_bar: int, n_req: int) -> tuple[int, int]:
    total = n_bar + n_req
    if total == 0:
        raise SystemExit("empty pool")
    n_b = int(round(n * n_bar / total))
    n_b = min(max(n_b, 0), n, n_bar)
    n_r = n - n_b
    if n_r > n_req:
        n_r = n_req
        n_b = n - n_r
    if n_b > n_bar:
        n_b = n_bar
        n_r = n - n_b
    return n_b, n_r


def pick(rng: random.Random, ids: list[str], n: int) -> list[str]:
    pool = list(ids)
    rng.shuffle(pool)
    if n > len(pool):
        raise SystemExit(f"need {n} from {len(pool)}")
    return pool[:n]


def yes_no_pools(rows: dict, class_key: str) -> tuple[list[str], list[str]]:
    barred, required = [], []
    for nct, row in rows.items():
        label = row["answer"].get(class_key)
        if label == "barred":
            barred.append(nct)
        elif label == "required":
            required.append(nct)
    return barred, required


def write_ids() -> dict:
    rng = random.Random(SEED)
    yes_no = load("answer_key.jsonl")
    markers = load("answer_key_markers.jsonl")
    extra = load("answer_key_step5b.jsonl")

    marker_bar = [n for n, r in markers.items() if marker_as_list(r["answer"].get("refused_markers"))]
    marker_req = [n for n, r in markers.items() if marker_as_list(r["answer"].get("required_markers"))]
    stage_bar = [n for n, r in extra.items() if as_list(r["answer"].get("refused_stages"))]
    stage_req = [n for n, r in extra.items() if as_list(r["answer"].get("allowed_stages"))]
    plat_b, plat_r = yes_no_pools(extra, "prior_platinum_chemo_classification")
    imm_b, imm_r = yes_no_pools(yes_no, "prior_immunotherapy_classification")
    br_b, br_r = yes_no_pools(yes_no, "brain_metastases_classification")
    auto_b, auto_r = yes_no_pools(extra, "autoimmune_disease_classification")

    plan = [
        ("tumour genetic marker", 8, marker_bar, marker_req, "answer_key_markers.jsonl", "genetic_marker_quote"),
        ("disease stage", 8, stage_bar, stage_req, "answer_key_step5b.jsonl", "stage_quote"),
        ("previous platinum chemotherapy", 5, plat_b, plat_r, "answer_key_step5b.jsonl", "prior_platinum_chemo_quote"),
        ("previous immunotherapy", 5, imm_b, imm_r, "answer_key.jsonl", "prior_immunotherapy_quote"),
        ("cancer spread to the brain", 3, br_b, br_r, "answer_key.jsonl", "brain_metastases_quote"),
        ("autoimmune disease", 1, auto_b, auto_r, "answer_key_step5b.jsonl", "autoimmune_disease_quote"),
    ]
    items = []
    mix = {}
    for fact, n, bar_ids, req_ids, file_name, quote_key in plan:
        n_b, n_r = split_counts(n, len(bar_ids), len(req_ids))
        mix[fact] = {
            "n": n,
            "barred_available": len(bar_ids),
            "required_available": len(req_ids),
            "barred_drawn": n_b,
            "required_drawn": n_r,
        }
        for nct in pick(rng, bar_ids, n_b):
            items.append({"nct_id": nct, "fact": fact, "label": "barred", "file": file_name, "quote_key": quote_key})
        for nct in pick(rng, req_ids, n_r):
            items.append({"nct_id": nct, "fact": fact, "label": "required", "file": file_name, "quote_key": quote_key})

    if len(items) != 30:
        raise SystemExit(f"expected 30, got {len(items)}")
    payload = {"seed": SEED, "n": 30, "mix": mix, "items": items}
    IDS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(mix, indent=2))
    print(f"Wrote {IDS_PATH}")
    return payload


def write_sheet() -> None:
    spec = json.loads(IDS_PATH.read_text(encoding="utf-8"))
    caches = {}
    lines = [
        "# Step 9 — 30 consequential answer-key rows",
        "",
        "Does this quote say that the trial **bars** / **requires** this thing?",
        "",
        "Mark: **agree** / **disagree** / **needs medical knowledge**.",
        "",
        f"Seed **{spec['seed']}**. Only `barred` and `required`. Weighted by",
        "narrowing. Model notes are **not** on this page; they are in",
        "`docs/step9_consequential_notes.md` — open that only after you record",
        "a judgment.",
        "",
        "Gates (THRESHOLDS.md): disagreement among checkable rows under 5% →",
        "quote the numbers; 5–10% → add to the 6.3% lost-joinable discussion;",
        "above 10% → re-examine 6.3% before quoting it.",
        "",
    ]
    notes = [
        "# Step 9 consequential — model notes",
        "",
        "**Do not open this until judgments are recorded on",
        "`docs/step9_consequential_check.md`.** These notes explain why the",
        "model chose the label. Reading them first anchors agreement.",
        "",
    ]
    for i, item in enumerate(spec["items"], 1):
        if item["file"] not in caches:
            caches[item["file"]] = load(item["file"])
        row = caches[item["file"]][item["nct_id"]]
        answer = row["answer"]
        quote = (answer.get(item["quote_key"]) or "").strip()
        title = row.get("brief_title") or ""
        note = (answer.get("note") or "").strip()
        lines += [
            f"## {i}. {item['nct_id']}",
            "",
            f"_{title}_" if title else "",
            "",
            f"- fact: {item['fact']}",
            f"- label: **{item['label']}**",
            f"- quote: {quote or '(empty)'}",
            "",
            "Will:",
            "",
        ]
        notes += [
            f"## {i}. {item['nct_id']} — {item['fact']} `{item['label']}`",
            "",
            note or "(no note)",
            "",
        ]
    SHEET.write_text("\n".join(line for line in lines if line is not None), encoding="utf-8")
    NOTES.write_text("\n".join(notes), encoding="utf-8")
    print(f"Wrote {SHEET}")
    print(f"Wrote {NOTES}")


if __name__ == "__main__":
    if "--sheet" in sys.argv:
        write_sheet()
    else:
        write_ids()
