"""Task 1: recategorise every flagged answer-key quote. No API. No human.

Thresholds in THRESHOLDS.md, committed before this ran.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mini_pilot import BRAIN_WORDS, IMMUNO_WORDS, normalize_for_match, quote_match  # noqa: E402
from keyword_section_check import JSONL_PATH  # noqa: E402
from step5_label_markers import MARKER_WORDS, as_list as marker_as_list  # noqa: E402
from step5_label_rest import AUTO_WORDS, PLATINUM_WORDS, STAGE_WORDS, as_list  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "step9_quote_audit.json"
REPORT = ROOT / "docs" / "step9_quote_audit.md"

SLOTS = (
    ("answer_key.jsonl", "prior_immunotherapy", "prior_immunotherapy_classification", "prior_immunotherapy_quote", "yes_no", IMMUNO_WORDS),
    ("answer_key.jsonl", "brain_metastases", "brain_metastases_classification", "brain_metastases_quote", "yes_no", BRAIN_WORDS),
    ("answer_key_markers.jsonl", "driver_mutation", None, "genetic_marker_quote", "marker", MARKER_WORDS),
    ("answer_key_step5b.jsonl", "prior_platinum_chemo", "prior_platinum_chemo_classification", "prior_platinum_chemo_quote", "yes_no", PLATINUM_WORDS),
    ("answer_key_step5b.jsonl", "autoimmune_disease", "autoimmune_disease_classification", "autoimmune_disease_quote", "yes_no", AUTO_WORDS),
    ("answer_key_step5b.jsonl", "disease_stage", None, "stage_quote", "stage", STAGE_WORDS),
)


def load_jsonl(name: str) -> dict[str, dict]:
    found = {}
    with (DATA / name).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("answer"):
                found[row["nct_id"]] = row
    return found


def load_criteria() -> dict[str, str]:
    found = {}
    with JSONL_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            found[row["nct_id"]] = row.get("eligibility_criteria") or ""
    return found


def strong_norm(value: str) -> str:
    text = normalize_for_match(value).lower()
    replacements = {
        "\u00a0": " ",
        "–": "-",
        "—": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "≤": "<=",
        "≥": ">=",
        "×": "x",
        "µ": "u",
        "μ": "u",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    text = re.sub(r"^[\s\-\*\u2022\d.]+", "", text)
    text = re.sub(r"[^\w\s=<>]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def present(quote: str, text: str) -> bool:
    if not quote.strip():
        return False
    if quote_match(quote, text) != "missing":
        return True
    sq, st = strong_norm(quote), strong_norm(text)
    return bool(sq) and sq in st


def split_parts(quote: str) -> list[str]:
    raw = re.split(r"(?<=[.!?])\s+|\s*[;•]\s+|\s+\*\s+|\n+", quote)
    parts = [p.strip(" -\t") for p in raw if len(p.strip()) >= 15]
    if len(parts) < 2:
        # two clauses joined with " and " after a long stretch
        m = re.split(r"\s+and\s+(?=[A-Z*])", quote)
        parts = [p.strip() for p in m if len(p.strip()) >= 15]
    return parts


def is_stitched(quote: str, text: str) -> bool:
    if present(quote, text):
        return False
    parts = split_parts(quote)
    if len(parts) < 2:
        return False
    hits = [p for p in parts if present(p, text)]
    return len(hits) >= 2


def content_words(value: str) -> list[str]:
    return [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", value or "")]


def in_order_ratio(quote: str, text: str) -> float:
    need = content_words(quote)
    if len(need) < 6:
        return 0.0
    hay = content_words(text)
    i = 0
    for word in hay:
        if i < len(need) and word == need[i]:
            i += 1
    return i / len(need)


def slot_active(answer: dict, kind: str, class_key: str | None) -> bool:
    if kind == "yes_no":
        return (answer.get(class_key) or "not_mentioned") != "not_mentioned"
    if kind == "marker":
        return bool(marker_as_list(answer.get("required_markers")) or marker_as_list(answer.get("refused_markers")))
    return bool(as_list(answer.get("allowed_stages")) or as_list(answer.get("refused_stages")))


def bucket_quote(quote: str, text: str, words) -> str:
    quote = quote or ""
    if not quote.strip():
        return "E"
    in_basic = quote_match(quote, text) != "missing"
    in_strong = present(quote, text)
    if in_basic or in_strong:
        if words is not None and not words.search(quote):
            return "C"
        if in_basic:
            return "ok"
        return "B"
    if is_stitched(quote, text):
        return "A"
    if in_order_ratio(quote, text) >= 0.85:
        return "D"
    return "E"


def main() -> None:
    criteria = load_criteria()
    caches: dict[str, dict[str, dict]] = {}
    items = []
    for file_name, fact, class_key, quote_key, kind, words in SLOTS:
        if file_name not in caches:
            caches[file_name] = load_jsonl(file_name)
        for nct, row in caches[file_name].items():
            answer = row["answer"]
            if not slot_active(answer, kind, class_key):
                continue
            quote = (answer.get(quote_key) or "").strip()
            text = criteria.get(nct) or ""
            stored_blob = " ".join(row.get("checks") or [])
            orig_flag = quote_key in stored_blob or (
                kind == "stage" and "stage" in stored_blob
            ) or (
                kind == "marker" and ("genetic_marker" in stored_blob or "list" in stored_blob)
            )
            bucket = bucket_quote(quote, text, words)
            items.append({
                "nct_id": nct,
                "fact": fact,
                "quote_key": quote_key,
                "file": file_name,
                "orig_flag": orig_flag,
                "stored_checks": [c for c in (row.get("checks") or []) if quote_key.split("_quote")[0] in c or (kind == "stage" and "stage" in c) or (kind == "marker" and ("marker" in c or "list" in c))],
                "bucket": bucket,
                "quote": quote[:240],
            })

    n_slots = len(items)
    orig_flagged = [i for i in items if i["orig_flag"]]
    buckets = Counter(i["bucket"] for i in orig_flagged)
    all_buckets = Counter(i["bucket"] for i in items)
    de = sum(1 for i in items if i["bucket"] in ("D", "E"))
    # Residual flags: originally flagged, still D or E (A/B/C handled)
    residual_flagged = [i for i in orig_flagged if i["bucket"] in ("D", "E")]
    by_fact = {}
    for fact in {i["fact"] for i in items}:
        sub = [i for i in items if i["fact"] == fact]
        flagged = [i for i in sub if i["orig_flag"]]
        by_fact[fact] = {
            "slots": len(sub),
            "orig_flagged": len(flagged),
            "buckets_among_flagged": dict(Counter(i["bucket"] for i in flagged)),
            "D_plus_E": sum(1 for i in sub if i["bucket"] in ("D", "E")),
        }

    rate = de / n_slots if n_slots else None
    report = {
        "n_checked_quote_slots": n_slots,
        "n_originally_flagged_slots": len(orig_flagged),
        "buckets_among_originally_flagged": dict(buckets),
        "buckets_among_all_slots": dict(all_buckets),
        "D_plus_E": de,
        "D_plus_E_rate": round(rate, 4) if rate is not None else None,
        "gate_fail_above": 0.05,
        "cleared": (rate or 1) <= 0.05,
        "step8_reader_missing_quotes": 0.012,
        "residual_flag_rate_after_ABC": round(len(residual_flagged) / n_slots, 4) if n_slots else None,
        "by_fact": by_fact,
        "examples": {
            letter: [
                {"nct_id": i["nct_id"], "fact": i["fact"], "quote": i["quote"]}
                for i in orig_flagged if i["bucket"] == letter
            ][:8]
            for letter in "ABCDE"
        },
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Step 9 Task 1 — mechanical quote-flag recategorisation",
        "",
        "No human. No API. Thresholds committed before this ran.",
        "",
        f"Checked quote-slots (six facts, labels that need a quote): **{n_slots}**.",
        f"Originally flagged by the stored checker: **{len(orig_flagged)}**.",
        "",
        "## Buckets among originally flagged slots",
        "",
        "| Bucket | n | share of flagged |",
        "|---|---:|---:|",
    ]
    for letter, label in (
        ("A", "Stitched"),
        ("B", "Whitespace / punctuation"),
        ("C", "Word-list miss"),
        ("D", "Paraphrased"),
        ("E", "Absent"),
        ("ok", "Would now pass (stored flag was stale)"),
    ):
        n = buckets.get(letter, 0)
        share = n / len(orig_flagged) if orig_flagged else 0
        lines.append(f"| {letter} — {label} | {n} | {share:.1%} |")
    lines += [
        "",
        f"**D + E = {de} of {n_slots} slots ({rate:.1%}.)** Gate: above 5% is a support problem.",
        f"Cleared: **{report['cleared']}**. Step 8 reader missing-quote rate was 1.2%.",
        "",
        f"Residual flag rate once A, B, C are handled: **{report['residual_flag_rate_after_ABC']:.1%}** "
        "(D+E that were originally flagged, over all slots).",
        "",
        "## By fact",
        "",
        "| Fact | slots | orig. flagged | D+E |",
        "|---|---:|---:|---:|",
    ]
    for fact, row in sorted(by_fact.items()):
        lines.append(f"| {fact} | {row['slots']} | {row['orig_flagged']} | {row['D_plus_E']} |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in report if k != "examples"}, indent=2))
    print(f"Wrote {OUT}")
    print(f"Wrote {REPORT}")


if __name__ == "__main__":
    main()
