"""Free count: basket trials in conditions, and quotes that name a non-lung cancer.

No model. No gate. Sizes whether a wider scoping re-label is worth it.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from keyword_section_check import JSONL_PATH

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
YES_NO = DATA / "answer_key.jsonl"
MARKERS = DATA / "answer_key_markers.jsonl"
STEP5B = DATA / "answer_key_step5b.jsonl"
OUT = DATA / "step9_scope_count.json"
REPORT = ROOT / "docs" / "step9_scope_count.md"

LUNG = re.compile(
    r"\blung\b|\bnsclc\b|\bsclc\b|non[\s-]*small[\s-]*cell|small[\s-]*cell[\s-]*lung|"
    r"bronch|pulmonar|thoracic",
    re.IGNORECASE,
)
OTHER = re.compile(
    r"\bovarian\b|\bbreast cancer\b|\bbreast carcinoma\b|\bTNBC\b|"
    r"\bcolorectal\b|\bcolon cancer\b|\brectal cancer\b|\bendometrial\b|"
    r"\buterine cancer\b|\bcervical cancer\b|\bmelanoma\b|\bpancreatic\b|"
    r"\bpancreas cancer\b|\bgastric\b|\bstomach cancer\b|\bsarcoma\b|"
    r"\bthymic\b|\bthymoma\b|\bthymus cancer\b|\bprostate cancer\b|"
    r"\brenal cell\b|\bkidney cancer\b|\bhepatocellular\b|\bcholangio|"
    r"\bbile[\s-]*duct\b|\bbladder cancer\b|\burothelial\b|\besophageal\b|"
    r"\boesophag|head[\s-]*and[\s-]*neck|\bhnscc\b|\bmesothelioma\b|"
    r"\bglioblastoma\b|\bglioma\b|\bastrocytoma\b|\bleukemia\b|\bleukaemia\b|"
    r"\blymphoma\b|\bmyeloma\b|\bmyelodysplas|\bthyroid cancer\b|"
    r"\bnasopharyn|\bmerkel\b|fallopian|\bprimary peritoneal\b|"
    r"\bperitoneal cancer\b|\bgist\b|\bliver cancer\b|\bbiliary tract",
    re.IGNORECASE,
)
GENERIC_BASKET = re.compile(
    r"solid[\s-]*tumou?r|advanced malignanc|any malignanc|all[\s-]*comer|"
    r"multiple tumou?r|basket|pan[\s-]*tumou?r|tumor[\s-]*agnostic",
    re.IGNORECASE,
)

QUOTE_FIELDS = [
    (YES_NO, "prior_immunotherapy", "prior_immunotherapy_quote"),
    (YES_NO, "brain_metastases", "brain_metastases_quote"),
    (MARKERS, "driver_mutation", "genetic_marker_quote"),
    (STEP5B, "prior_platinum_chemo", "prior_platinum_chemo_quote"),
    (STEP5B, "autoimmune_disease", "autoimmune_disease_quote"),
    (STEP5B, "disease_stage", "stage_quote"),
]


def load_labelled_ids() -> set[str]:
    ids = None
    for path in (YES_NO, MARKERS, STEP5B):
        have = set()
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("answer"):
                    have.add(row["nct_id"])
        ids = have if ids is None else ids & have
    return ids


def classify_condition(text: str) -> str:
    if OTHER.search(text) and not LUNG.search(text):
        return "other_cancer"
    if OTHER.search(text) and LUNG.search(text):
        return "lung_and_other"
    if LUNG.search(text):
        return "lung"
    if GENERIC_BASKET.search(text):
        return "generic_basket"
    return "other_phrase"


def other_hits(text: str) -> list[str]:
    return sorted({m.group(0).lower() for m in OTHER.finditer(text or "")})


def main() -> None:
    labelled = load_labelled_ids()
    n_labelled = len(labelled)
    multi = []
    generic_only = []
    n_conditions = 0
    with JSONL_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            nct = row["nct_id"]
            if nct not in labelled:
                continue
            n_conditions += 1
            tags = [classify_condition(c) for c in (row.get("conditions") or [])]
            has_other = any(t in ("other_cancer", "lung_and_other") for t in tags)
            has_lung = any(t in ("lung", "lung_and_other") for t in tags)
            has_generic = any(t == "generic_basket" for t in tags)
            named_other = []
            for cond in row.get("conditions") or []:
                named_other.extend(other_hits(cond))
            named_other = sorted(set(named_other))
            if has_other:
                multi.append({
                    "nct_id": nct,
                    "conditions": row.get("conditions") or [],
                    "other_cancers": named_other,
                })
            elif has_generic and has_lung:
                generic_only.append({"nct_id": nct, "conditions": row.get("conditions") or []})

    quote_rows = []
    by_fact = Counter()
    by_word = Counter()
    ncts_with_other_quote = set()
    for path, fact, quote_key in QUOTE_FIELDS:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row["nct_id"] not in labelled or not row.get("answer"):
                    continue
                quote = (row["answer"].get(quote_key) or "").strip()
                if not quote:
                    continue
                hits = other_hits(quote)
                if not hits:
                    continue
                quote_rows.append({
                    "nct_id": row["nct_id"],
                    "fact": fact,
                    "other_cancers": hits,
                    "quote": quote[:240],
                })
                by_fact[fact] += 1
                ncts_with_other_quote.add(row["nct_id"])
                for h in hits:
                    by_word[h] += 1

    report = {
        "n_labelled_trials": n_labelled,
        "n_with_conditions_loaded": n_conditions,
        "conditions_name_another_cancer": {
            "n": len(multi),
            "share": round(len(multi) / n_labelled, 4) if n_labelled else None,
            "note": (
                "Trials whose ClinicalTrials.gov conditions list names a cancer "
                "other than lung, besides or instead of lung. Lung synonyms "
                "(NSCLC, SCLC, thoracic) do not count as a second cancer."
            ),
        },
        "conditions_generic_basket_only": {
            "n": len(generic_only),
            "share": round(len(generic_only) / n_labelled, 4) if n_labelled else None,
            "note": "Lung plus 'solid tumour' / 'malignancy' / 'basket', with no named other cancer.",
        },
        "quotes_name_another_cancer": {
            "n_quotes": len(quote_rows),
            "n_trials": len(ncts_with_other_quote),
            "share_of_trials": round(len(ncts_with_other_quote) / n_labelled, 4) if n_labelled else None,
            "by_fact": dict(by_fact),
            "by_word": dict(by_word.most_common()),
        },
        "examples_multi_cancer_conditions": multi[:15],
        "examples_other_cancer_quotes": quote_rows[:20],
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Step 9 — basket-trial and other-cancer quote count",
        "",
        "Free. No model. Sizes whether a wider scoping re-label is worth it.",
        "The 12 title-inferred stage labels were the only unsupported labels",
        "among the 34 missing-quote discards; none of those 12 were basket-scoping.",
        "",
        f"Labelled corpus: **{n_labelled}** trials.",
        "",
        "## Conditions that name another cancer",
        "",
        f"**{len(multi)} of {n_labelled}** "
        f"({len(multi) / n_labelled:.1%}) list a named cancer other than lung "
        "on the ClinicalTrials.gov conditions field.",
        "",
        f"**{len(generic_only)} of {n_labelled}** "
        f"({len(generic_only) / n_labelled:.1%}) list lung plus a generic basket "
        "phrase (solid tumour, malignancy) and no named other cancer.",
        "",
        "## Quotes that name another cancer",
        "",
        f"**{len(quote_rows)} quotes** across **{len(ncts_with_other_quote)} trials** "
        f"({len(ncts_with_other_quote) / n_labelled:.1%} of the key) name a cancer "
        "other than lung.",
        "",
        "Organ-function wording (thyroid hormone, renal function, cervical lymph",
        "nodes) is not counted. Distinctive cancer names (melanoma, lymphoma,",
        "colorectal) are.",
        "",
        "| Fact | Quotes naming another cancer |",
        "|---|---:|",
    ]
    for fact, n in by_fact.most_common():
        lines.append(f"| {fact} | {n} |")
    lines += ["", "Most frequent named cancers in those quotes:", ""]
    lines.append("| Word | Hits |")
    lines.append("|---|---:|")
    for word, n in by_word.most_common(15):
        lines.append(f"| {word} | {n} |")
    lines += [
        "",
        "A wider scoping re-label is worth it if this count is large. If it is",
        "small, the four Step 9 disagreements already caught the worst cases",
        "and the remaining risk is in the tail.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({
        "n_labelled": n_labelled,
        "multi_cancer_conditions": len(multi),
        "generic_basket": len(generic_only),
        "other_cancer_quotes": len(quote_rows),
        "trials_with_other_cancer_quote": len(ncts_with_other_quote),
        "by_fact": dict(by_fact),
    }, indent=2))
    print("Wrote", OUT)
    print("Wrote", REPORT)


if __name__ == "__main__":
    main()
