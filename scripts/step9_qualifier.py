"""Apply the qualifier convention: a word that narrows a bar makes it conditional.

Mechanical. Four yes/no facts. barred + (active | uncontrolled | untreated |
symptomatic | within N months) on the quote → barred_with_exception.
This keeps the trial. It will lower the ceiling and the 44.7% headline.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LOG = DATA / "step9_qualifier.json"

QUAL = re.compile(
    r"\bactive\b|\buncontrolled\b|\buntreated\b|\bsymptomatic\b|"
    r"within\s+\d+\s*(?:days?|weeks?|months?)",
    re.IGNORECASE,
)

PAIRS = [
    (DATA / "answer_key.jsonl", "prior_immunotherapy_classification", "prior_immunotherapy_quote"),
    (DATA / "answer_key.jsonl", "brain_metastases_classification", "brain_metastases_quote"),
    (DATA / "answer_key_step5b.jsonl", "prior_platinum_chemo_classification", "prior_platinum_chemo_quote"),
    (DATA / "answer_key_step5b.jsonl", "autoimmune_disease_classification", "autoimmune_disease_quote"),
]


def convert_file(path: Path, class_key: str, quote_key: str) -> list[dict]:
    rows = []
    changed = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            answer = row.get("answer") or {}
            classification = answer.get(class_key)
            quote = answer.get(quote_key) or ""
            if classification == "barred" and quote and QUAL.search(quote):
                answer[class_key] = "barred_with_exception"
                changed.append({
                    "nct_id": row["nct_id"],
                    "fact": class_key.replace("_classification", ""),
                    "quote": quote[:240],
                    "matched": QUAL.search(quote).group(0),
                })
            rows.append(row)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return changed


def main() -> None:
    seen_files: set[Path] = set()
    all_changed = []
    # Convert each pair, but a file with two pairs must be loaded once.
    by_file: dict[Path, list[tuple[str, str]]] = {}
    for path, class_key, quote_key in PAIRS:
        by_file.setdefault(path, []).append((class_key, quote_key))
    for path, pairs in by_file.items():
        rows = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                rows.append(json.loads(line))
        for class_key, quote_key in pairs:
            for row in rows:
                answer = row.get("answer") or {}
                classification = answer.get(class_key)
                quote = answer.get(quote_key) or ""
                if classification == "barred" and quote and QUAL.search(quote):
                    answer[class_key] = "barred_with_exception"
                    all_changed.append({
                        "nct_id": row["nct_id"],
                        "file": path.name,
                        "fact": class_key.replace("_classification", ""),
                        "quote": quote[:240],
                        "matched": QUAL.search(quote).group(0),
                    })
        with path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        seen_files.add(path)
        print(f"wrote {path}", flush=True)
    counts = Counter(r["fact"] for r in all_changed)
    log = {
        "n_converted": len(all_changed),
        "by_fact": dict(counts),
        "note": (
            "barred quotes containing a narrowing word became barred_with_exception. "
            "That keeps the trial. The ceiling and the matching-gated headline will fall. "
            "A smaller number that discards fewer joinable trials is the better system."
        ),
        "rows": all_changed,
    }
    LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"n_converted": log["n_converted"], "by_fact": log["by_fact"]}, indent=2))


if __name__ == "__main__":
    main()
