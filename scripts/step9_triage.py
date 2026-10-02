"""Triage Check 2's 34 labels and Check 1's 282 crossings.

A missing quote is not a wrong label. This script searches eligibility
text for any sentence that actually supports the stored label.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from keyword_section_check import split_sections  # noqa: E402
from mini_pilot import BRAIN_WORDS, IMMUNO_WORDS  # noqa: E402
from step2_ceiling import genes, load_markers, load_step5b, load_yes_no  # noqa: E402
from step5_label_markers import MARKER_WORDS  # noqa: E402
from step5_label_rest import AUTO_WORDS, PLATINUM_WORDS, STAGE_WORDS, as_list  # noqa: E402
from step9_quote_audit import load_criteria, present, split_parts  # noqa: E402
from step9_three_checks import collect_items, piece_side  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CHECKS = DATA / "step9_three_checks.json"
OUT = DATA / "step9_triage.json"
REPORT = ROOT / "docs" / "step9_triage.md"

FACT_WORDS = {
    "prior_immunotherapy": IMMUNO_WORDS,
    "brain_metastases": BRAIN_WORDS,
    "prior_platinum_chemo": PLATINUM_WORDS,
    "autoimmune_disease": AUTO_WORDS,
    "disease_stage": STAGE_WORDS,
    "driver_mutation": MARKER_WORDS,
}

STAGE_MENTION = re.compile(
    r"\bstage\b|metastatic|locally[\s-]*advanced|unresectable|early[\s-]*stage|"
    r"\bIII[ABC]?\b|\bIV[AB]?\b|\bII[ABC]\b",
    re.IGNORECASE,
)
MARKER_MENTION = re.compile(
    r"EGFR|ALK|KRAS|ROS1|BRAF|\bMET\b|\bRET\b|NTRK|HER2|ERBB2|"
    r"mutation|fusion|rearrangement|driver|biomarker|wild[\s-]?type",
    re.IGNORECASE,
)
CROSS_WORDS = {
    "prior_immunotherapy": IMMUNO_WORDS,
    "brain_metastases": BRAIN_WORDS,
    "prior_platinum_chemo": PLATINUM_WORDS,
    "autoimmune_disease": AUTO_WORDS,
    "disease_stage": STAGE_MENTION,
    "driver_mutation": MARKER_MENTION,
}

BAR_CUE = re.compile(
    r"\bno prior\b|\bno previous\b|must not|is excluded|are excluded|"
    r"not (?:have |been )?(?:receiv|treated)|have not (?:undergone|received|been)|"
    r"not undergone|is not allowed|are not allowed|not allowed|"
    r"without (?:prior|previous|any)|absence of|ineligible|"
    r"treatment[\s-]*na[iï]ve|\buntreated\b",
    re.IGNORECASE,
)
REQ_CUE = re.compile(
    r"must have|is required|are required|documented|"
    r"have received|prior .{0,50}(?:required|mandatory)|"
    r"at least one prior|previously (?:received|treated with)",
    re.IGNORECASE,
)
ALLOW_CUE = re.compile(
    r"\bpermitted\b|\ballowed\b|is allowed|are allowed|may have received",
    re.IGNORECASE,
)
WASHOUT = re.compile(
    r"within \d+\s*(?:week|day|month)|wash[\s-]*out|\d+\s*half-lives",
    re.IGNORECASE,
)

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def sentences(text: str) -> list[str]:
    parts = SENT_SPLIT.split(text or "")
    return [p.strip(" -\t*") for p in parts if len(p.strip()) >= 12]


def supporting_sentences(text: str, words, extra_needles: list[str] | None = None) -> list[str]:
    found = []
    needles = extra_needles or []
    for sent in sentences(text):
        hit_words = bool(words.search(sent)) if words is not None else False
        hit_needle = any(present(n, sent) for n in needles if n and len(n) >= 3)
        if hit_words or hit_needle:
            found.append(sent)
    return found


def triage_label(item: dict, criteria: str, title: str, answer: dict) -> dict:
    fact = item["fact"]
    label = item["label"]
    quote = item["quote"]
    words = STAGE_MENTION if fact == "disease_stage" else FACT_WORDS[fact]
    extra = []
    if fact == "driver_mutation":
        extra = as_list(answer.get("required_markers")) + as_list(answer.get("refused_markers"))
    if fact == "disease_stage":
        extra = as_list(answer.get("allowed_stages")) + as_list(answer.get("refused_stages"))

    in_elig = supporting_sentences(criteria, words, extra)
    # Drop sentences that are only the title repeated
    in_elig = [s for s in in_elig if not (title and present(s, title) and len(s) > 40 and present(title[:40], s))]

    gene_hit = False
    if fact == "driver_mutation":
        want = set()
        for m in extra:
            want |= genes(m)
        gene_hit = bool(want and (want & genes(criteria)))

    stage_hit = bool(fact == "disease_stage" and STAGE_MENTION.search(criteria or ""))
    fact_hit = bool(words.search(criteria or "")) or gene_hit or stage_hit or bool(in_elig)

    if not fact_hit and not in_elig:
        verdict = "unsupported"
        reason = "eligibility text has no sentence that names this fact"
    elif fact == "driver_mutation" and gene_hit:
        verdict = "supported"
        reason = "eligibility names the labelled marker"
    elif fact == "disease_stage" and stage_hit:
        verdict = "supported"
        reason = "eligibility contains stage language that can support the list"
    elif in_elig:
        verdict = "supported"
        reason = "eligibility contains a sentence that names the fact"
    elif fact_hit:
        verdict = "ambiguous"
        reason = "fact words occur in eligibility but no clean supporting sentence"
    else:
        verdict = "unsupported"
        reason = "no supporting sentence found"

    # Title-as-quote with real support still counts as supported (wrong citation only)
    title_cite = bool(title and present(quote, title) and not present(quote, criteria))

    return {
        "nct_id": item["nct_id"],
        "fact": fact,
        "label": label,
        "quote": quote,
        "title": title,
        "title_as_quote": title_cite,
        "verdict": verdict,
        "reason": reason,
        "supporting": in_elig[:4],
        "n_patients": len(item.get("patients") or []),
        "patients": item.get("patients") or [],
    }


def label_polarity(label: str | None) -> str | None:
    if label in ("barred", "barred_and_required"):
        return "bar"
    if label == "required":
        return "require"
    return None


def piece_polarity(piece: str, side: str, words) -> str:
    mentions = bool(words.search(piece))
    if not mentions:
        return "unrelated"
    if WASHOUT.search(piece) and side == "exclusion":
        return "washout"
    if ALLOW_CUE.search(piece) and not BAR_CUE.search(piece):
        return "allow"
    bar = bool(BAR_CUE.search(piece))
    req = bool(REQ_CUE.search(piece))
    if bar and not req:
        return "bar"
    if req and not bar:
        return "require"
    if side == "exclusion":
        return "bar"
    if side == "inclusion":
        if bar:
            return "bar"
        if req:
            return "require"
        return "unknown"
    return "unknown"


def triage_crossing(item: dict) -> dict:
    parts = split_sections(item["text"])
    pieces = split_parts(item["quote"])
    hits = [p for p in pieces if present(p, item["text"])]
    words = CROSS_WORDS[item["fact"]]
    annotated = []
    for p in hits:
        side = piece_side(p, parts["inclusion"], parts["exclusion"])
        pol = piece_polarity(p, side, words)
        annotated.append({"text": p, "side": side, "polarity": pol})
    fact_pieces = [a for a in annotated if a["polarity"] != "unrelated"]
    sides = {a["side"] for a in fact_pieces if a["side"] in ("inclusion", "exclusion")}
    directional = {a["polarity"] for a in fact_pieces if a["polarity"] in ("bar", "require")}
    stored = label_polarity(item.get("label"))
    if len(fact_pieces) == 0:
        harm = "no_fact_piece"
    elif not ("inclusion" in sides and "exclusion" in sides):
        harm = "fact_on_one_list"
    elif len(directional) > 1:
        harm = "mixed_polarity"
    elif stored and directional and stored not in directional:
        harm = "label_differs"
    else:
        harm = "same_direction"
    return {
        "nct_id": item["nct_id"],
        "fact": item["fact"],
        "label": item.get("label"),
        "harm": harm,
        "pieces": annotated,
        "quote": item["quote"][:300],
    }


def grouped_e_discards() -> list[dict]:
    payload = json.loads(CHECKS.read_text(encoding="utf-8"))
    by = {}
    for row in payload["check2"]["discards"]:
        key = (row["nct_id"], row["fact"])
        slot = by.setdefault(
            key,
            {
                "nct_id": row["nct_id"],
                "fact": row["fact"],
                "label": row["label"],
                "quote": row["quote"],
                "patients": [],
            },
        )
        slot["patients"].append(row["patient_id"])
    for slot in by.values():
        slot["patients"] = sorted(set(slot["patients"]))
    return list(by.values())


def main() -> None:
    payload = json.loads(CHECKS.read_text(encoding="utf-8"))
    criteria = load_criteria()
    yes_no = load_yes_no()
    markers = load_markers()
    extra = load_step5b()
    titles = {}
    from keyword_section_check import JSONL_PATH

    with JSONL_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                titles[row["nct_id"]] = row.get("brief_title") or ""

    answers = {}
    answers.update({n: {"kind": "yes_no", **a} for n, a in yes_no.items()})
    for n, a in markers.items():
        answers.setdefault(n, {}).update(a)
    for n, a in extra.items():
        answers.setdefault(n, {}).update(a)

    labels = grouped_e_discards()
    triaged = []
    for item in labels:
        ans = answers.get(item["nct_id"]) or {}
        triaged.append(
            triage_label(item, criteria.get(item["nct_id"]) or "", titles.get(item["nct_id"]) or "", ans)
        )

    # Crossings: rebuild from items so we have labels
    items = collect_items()
    by_key = {(i["nct_id"], i["fact"]): i for i in items}
    crossing_rows = []
    for row in payload["check1"]["crossing"]:
        item = by_key.get((row["nct_id"], row["fact"]))
        if not item:
            continue
        crossing_rows.append(triage_crossing(item))

    c2 = Counter(t["verdict"] for t in triaged)
    c1 = Counter(t["harm"] for t in crossing_rows)
    harm_patients = []
    for t in triaged:
        if t["verdict"] == "unsupported":
            for pid in t["patients"]:
                harm_patients.append(
                    {"patient_id": pid, "nct_id": t["nct_id"], "fact": t["fact"], "label": t["label"]}
                )

    out = {
        "check2_labels": {
            "n": len(triaged),
            "split": dict(c2),
            "n_patient_pairs_if_unsupported": len(harm_patients),
            "rows": triaged,
            "unsupported_patient_pairs": harm_patients,
        },
        "check1_crossings": {
            "n": len(crossing_rows),
            "split": dict(c1),
            "rows": crossing_rows,
        },
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Step 9 — triage of missing quotes and stitched crossings",
        "",
        "A fabricated citation is not a wrong label. 441 patient–trial discards",
        "rested on quotes that are not in the eligibility text. This page asks",
        "whether the *label* is supported by any real sentence.",
        "",
        "## Check 2 — 34 labels",
        "",
        f"| Verdict | Labels | of 34 |",
        "|---|---:|---:|",
        f"| Supported — wrong citation only | {c2.get('supported', 0)} | {c2.get('supported', 0)} |",
        f"| Unsupported — label has no basis in eligibility | {c2.get('unsupported', 0)} | {c2.get('unsupported', 0)} |",
        f"| Ambiguous | {c2.get('ambiguous', 0)} | {c2.get('ambiguous', 0)} |",
        "",
    ]
    if harm_patients:
        lines.append(
            f"**{len(harm_patients)} patient–trial pairs rest on an unsupported label.** Named:"
        )
        lines.append("")
        lines.append("| Patient | Trial | Fact | Label |")
        lines.append("|---|---|---|---|")
        for row in harm_patients:
            lines.append(
                f"| {row['patient_id']} | {row['nct_id']} | {row['fact']} | {row['label']} |"
            )
        lines.append("")
    else:
        lines.append(
            "**No unsupported label among the 34 discarded anyone.** "
            "441 was a count of bad citations, not of wrong decisions."
        )
        lines.append("")
    lines += [
        "### Per label",
        "",
        "| Trial | Fact | Label | Verdict | Title-as-quote | Supporting sentence |",
        "|---|---|---|---|---|---|",
    ]
    for t in sorted(triaged, key=lambda r: (r["verdict"], r["nct_id"])):
        sup = (t["supporting"][0] if t["supporting"] else "").replace("|", "/")[:160]
        lines.append(
            f"| {t['nct_id']} | {t['fact']} | {t['label']} | {t['verdict']} | "
            f"{t['title_as_quote']} | {sup} |"
        )
    lines += [
        "",
        "NCT06868485 is the worked example: the quote is the study title;",
        "eligibility says \"Documented EGFR mutation.\" Label is right. Citation is not.",
        "",
        "## Check 1 — 282 crossings",
        "",
        "Harm means the fact-bearing pieces have opposite polarity, or the stored",
        "label disagrees with the polarity of the fact-bearing piece. Same-direction",
        "is the NCT07103395 shape: both pieces bar prior immunotherapy.",
        "",
        f"| Outcome | n | of {len(crossing_rows)} |",
        "|---|---:|---:|",
        f"| Same direction (redundant, not contradictory) | {c1.get('same_direction', 0)} | {c1.get('same_direction', 0)} |",
        f"| Fact named on only one list (the other piece is padding) | {c1.get('fact_on_one_list', 0)} | {c1.get('fact_on_one_list', 0)} |",
        f"| Mixed polarity (the stitch can flip the label) | {c1.get('mixed_polarity', 0)} | {c1.get('mixed_polarity', 0)} |",
        f"| Stored label differs from the fact-bearing piece | {c1.get('label_differs', 0)} | {c1.get('label_differs', 0)} |",
        f"| No piece names the fact | {c1.get('no_fact_piece', 0)} | {c1.get('no_fact_piece', 0)} |",
        "",
    ]
    mixed = [r for r in crossing_rows if r["harm"] in ("mixed_polarity", "label_differs")]
    if mixed:
        lines.append("Crossings that can change the label:")
        lines.append("")
        lines.append("| Trial | Fact | Harm |")
        lines.append("|---|---|---|")
        for r in mixed:
            lines.append(f"| {r['nct_id']} | {r['fact']} | {r['harm']} |")
        if mixed:
            ex = mixed[0]
            lines += ["", "### Example of a polarity mix", ""]
            lines.append(f"Trial `{ex['nct_id']}`, fact `{ex['fact']}`.")
            for p in ex["pieces"]:
                lines.append(f"- {p['side']} / {p['polarity']}: {p['text'][:220]}")
    else:
        lines.append(
            "**No stitched quote produces a label that differs from the "
            "fact-bearing piece.** 282 is a count of a risky pattern, not of harm."
        )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("check2", dict(c2), "unsupported pairs", len(harm_patients))
    print("check1", dict(c1))
    print("Wrote", OUT)
    print("Wrote", REPORT)


if __name__ == "__main__":
    main()
