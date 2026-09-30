"""Draw the 40 least-sure answer-key rows for Will's Step 9 check.

Seed and mix committed in step9_design.json / THRESHOLDS.md before this
file was used as a check sheet.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AK = ROOT / "data" / "answer_key.jsonl"
OUT_MD = ROOT / "docs" / "step9_will_check.md"
OUT_JSON = ROOT / "data" / "step9_sample.json"
SEED = 20260930

# All unclear, all brain both, then fill from immuno both and barred_with_exception.
N_IMMUNO_BOTH = 8
N_IMMUNO_BWE = 3
N_BRAIN_BWE = 3


def load_key() -> list[dict]:
    rows = []
    with AK.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("answer"):
                rows.append(row)
    return rows


def bucket(rows: list[dict], class_key: str, label: str) -> list[dict]:
    out = []
    for row in rows:
        if (row["answer"].get(class_key) or "") == label:
            out.append(row)
    out.sort(key=lambda r: r["nct_id"])
    return out


def item(row: dict, trait: str, class_key: str, quote_key: str) -> dict:
    answer = row["answer"]
    return {
        "nct_id": row["nct_id"],
        "brief_title": row.get("brief_title") or "",
        "trait": trait,
        "classification": answer.get(class_key),
        "quote": (answer.get(quote_key) or "").strip(),
        "note": (answer.get("note") or "").strip(),
    }


def main() -> None:
    rows = load_key()
    rng = random.Random(SEED)
    immuno_unclear = bucket(rows, "prior_immunotherapy_classification", "unclear")
    immuno_both = bucket(rows, "prior_immunotherapy_classification", "both_classifications")
    immuno_bwe = bucket(rows, "prior_immunotherapy_classification", "barred_with_exception")
    brain_unclear = bucket(rows, "brain_metastases_classification", "unclear")
    brain_both = bucket(rows, "brain_metastases_classification", "both_classifications")
    brain_bwe = bucket(rows, "brain_metastases_classification", "barred_with_exception")

    picked = []
    for row in immuno_unclear:
        picked.append(item(row, "prior immunotherapy", "prior_immunotherapy_classification", "prior_immunotherapy_quote"))
    for row in brain_unclear:
        picked.append(item(row, "brain metastases", "brain_metastases_classification", "brain_metastases_quote"))
    for row in brain_both:
        picked.append(item(row, "brain metastases", "brain_metastases_classification", "brain_metastases_quote"))

    immuno_both_s = list(immuno_both)
    rng.shuffle(immuno_both_s)
    for row in immuno_both_s[:N_IMMUNO_BOTH]:
        picked.append(item(row, "prior immunotherapy", "prior_immunotherapy_classification", "prior_immunotherapy_quote"))

    immuno_bwe_s = list(immuno_bwe)
    brain_bwe_s = list(brain_bwe)
    rng.shuffle(immuno_bwe_s)
    rng.shuffle(brain_bwe_s)
    for row in immuno_bwe_s[:N_IMMUNO_BWE]:
        picked.append(item(row, "prior immunotherapy", "prior_immunotherapy_classification", "prior_immunotherapy_quote"))
    for row in brain_bwe_s[:N_BRAIN_BWE]:
        picked.append(item(row, "brain metastases", "brain_metastases_classification", "brain_metastases_quote"))

    if len(picked) != 40:
        raise SystemExit(f"expected 40 rows, got {len(picked)}")

    sample = {
        "seed": SEED,
        "n": len(picked),
        "mix": {
            "immuno_unclear_all": len(immuno_unclear),
            "brain_unclear_all": len(brain_unclear),
            "brain_both_all": len(brain_both),
            "immuno_both_sampled": N_IMMUNO_BOTH,
            "immuno_both_available": len(immuno_both),
            "immuno_barred_with_exception_sampled": N_IMMUNO_BWE,
            "brain_barred_with_exception_sampled": N_BRAIN_BWE,
        },
        "items": picked,
    }
    OUT_JSON.write_text(json.dumps(sample, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Step 9 — Will check: 40 least-sure answer-key rows",
        "",
        "Reading comprehension only. For each row: does the quoted sentence say",
        "what the **classification** claims, in plain English?",
        "",
        "- **agree** — the quote supports that label",
        "- **disagree** — the quote does not say that",
        "- **needs medical knowledge** — you cannot tell without knowing whether",
        "  one medical term falls under another. Record it and move on.",
        "",
        "Do not judge whether a patient would qualify. These 40 are the labels the",
        "key was least sure about, not a random sample of the whole key.",
        "",
        f"Seed **{SEED}**. All 12 immunotherapy `unclear`, all 7 brain `unclear`,",
        f"all 7 brain `both_classifications`, {N_IMMUNO_BOTH} of 22 immunotherapy",
        f"`both_classifications`, {N_IMMUNO_BWE} immunotherapy `barred_with_exception`,",
        f"{N_BRAIN_BWE} brain `barred_with_exception`.",
        "",
        "Gate (committed in THRESHOLDS.md): disagreement above **25% of the",
        "checkable ones** (agree + disagree, excluding needs-medical-knowledge)",
        "→ rework the labelling instructions before quoting the key.",
        "",
    ]
    for i, row in enumerate(picked, 1):
        lines.append(f"## {i}. {row['nct_id']} — {row['trait']}")
        lines.append("")
        if row["brief_title"]:
            lines.append(f"_{row['brief_title']}_")
            lines.append("")
        lines.append(f"- classification: `{row['classification']}`")
        lines.append(f"- quote: {row['quote'] or '(empty)'}")
        if row["note"]:
            lines.append(f"- model note: {row['note']}")
        lines.append("")
        lines.append("Will: agree / disagree / needs medical knowledge")
        lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"n={len(picked)} wrote {OUT_MD}")
    print(json.dumps(sample["mix"], indent=2))


if __name__ == "__main__":
    main()
