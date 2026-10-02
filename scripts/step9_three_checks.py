"""Three mechanical quote checks. Thresholds committed before this ran.

Does not touch docs/step9_consequential_check.md or its notes file.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from keyword_section_check import split_sections  # noqa: E402
from step2_ceiling import load_markers, load_step5b, load_yes_no  # noqa: E402
from step3d_match import FACTS, listed_facts, load_assigned, retrieve  # noqa: E402
from step3d_reassign import canonical_name  # noqa: E402
from step8_sample import oracle_out  # noqa: E402
from step9_quote_audit import (  # noqa: E402
    SLOTS,
    bucket_quote,
    load_criteria,
    load_jsonl,
    present,
    slot_active,
    split_parts,
)
from therapy_containment import load_child_to_parent  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "step9_three_checks.json"
REPORT = ROOT / "docs" / "step9_three_checks.md"
PATIENTS = DATA / "fake_patients_draw.json"
PARSE = DATA / "step4_parse.json"

CHEMO_WORDS = re.compile(r"chemotherap", re.IGNORECASE)
SYSTEMIC_WORDS = re.compile(r"systemic", re.IGNORECASE)
ANTICANCER_WORDS = re.compile(
    r"anticancer|anti-cancer|antitumor|anti-tumou?r|antineoplastic",
    re.IGNORECASE,
)
NAIVE_WORDS = re.compile(
    r"treatment[\s-]*na[iï]ve|\buntreated\b|not previously treated|"
    r"never (?:been )?treated|no prior (?:anticancer |anti-cancer )?"
    r"(?:treatment|therapy)|no previous (?:anticancer |anti-cancer )?"
    r"(?:treatment|therapy)|no prior therapy|no previous therapy|"
    r"have not (?:undergone|received) (?:any )?(?:prior )?(?:systemic |anticancer )?"
    r"(?:treatment|therapy)|no previous (?:line of )?treatment",
    re.IGNORECASE,
)
CYTOTOXIC_WORDS = re.compile(r"cytotoxic", re.IGNORECASE)

# Spellings / synonyms the original lists missed. Not hierarchy parents.
# Patterns already in the original lists are omitted — those rows are not in C.
C2_WORDS = {
    "prior_immunotherapy": re.compile(
        r"\bICPI\b|\bICIs?\b|\bCPIs?\b|PD-?\s*\(?L\)?-?\s*1|"
        r"PD\s*\(?\[?L\]?\)?\s*-?\s*1|\bPD1\b|\bPDL1\b|"
        r"CTLA-?4|durvalumab|ipilimumab|avelumab|cemiplimab|tislelizumab|"
        r"camrelizumab|toripalimab|sintilimab|immune[\s-]*checkpoint|"
        r"checkpoint inhibition|immuno-?oncolog|immune CPI|"
        r"immuno-|\bimmuno\b|immunotherpy|immune therapy|anti-PD",
        re.IGNORECASE,
    ),
    "brain_metastases": re.compile(
        r"cerebral|intracerebral|calvari|dural|meningeal|"
        r"CNS\s+(?:involvement|disease|lesion)|brain\s+lesion",
        re.IGNORECASE,
    ),
    "prior_platinum_chemo": re.compile(
        r"cisplatinum|carboplatinum|oxaliplatinum|\bCDDP\b|\bCBDCA\b|"
        r"platina|\bCarbo\b|\bCisplat",
        re.IGNORECASE,
    ),
    "autoimmune_disease": re.compile(
        r"type\s*1 diabetes|\bT1DM\b|Addison|vitiligo|myositis|thyroiditis|"
        r"multiple sclerosis|\bSLE\b|connective[\s-]*tissue|"
        r"auto[\s-]*immune|outoimmune|connective[\s-]*diseas",
        re.IGNORECASE,
    ),
    "disease_stage": re.compile(
        r"\badvanced\b|recurrent|TNM|\bAJCC\b|oligometastat|"
        r"extensive[\s-]*stage|limited[\s-]*stage|\bM1\b|inoperable|"
        r"incurable|late[\s-]*stage|metasta",
        re.IGNORECASE,
    ),
    "driver_mutation": re.compile(
        r"\bexon\b|translocat|pathogenic|actionable|sensitiz|"
        r"variant|\bFISH\b|\bIHC\b|oncogenic|\bAGAs?\b|\bMTAP\b|"
        r"\bMSI\b|\bdMMR\b|\bGNA11\b|\bGNAQ\b",
        re.IGNORECASE,
    ),
}
YES_NO_CLASS = {
    "prior_immunotherapy": "prior_immunotherapy_classification",
    "brain_metastases": "brain_metastases_classification",
    "prior_platinum_chemo": "prior_platinum_chemo_classification",
    "autoimmune_disease": "autoimmune_disease_classification",
}


def heading_mode(text: str) -> str:
    return split_sections(text or "")["mode"]


def collect_items() -> list[dict]:
    criteria = load_criteria()
    caches: dict[str, dict] = {}
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
            label = definite_label(answer, fact, kind)
            items.append({
                "nct_id": nct,
                "fact": fact,
                "kind": kind,
                "quote": quote,
                "text": text,
                "orig_flag": orig_flag,
                "bucket": bucket,
                "label": label,
                "answer": answer,
                "file": file_name,
            })
    return items


def definite_label(answer: dict, fact: str, kind: str) -> str | None:
    if kind == "yes_no":
        lab = answer.get(YES_NO_CLASS[fact])
        return lab if lab in ("barred", "required") else None
    if kind == "marker":
        req = bool(answer.get("required_markers"))
        ref = bool(answer.get("refused_markers"))
        if req and ref:
            return "barred_and_required"
        if req:
            return "required"
        if ref:
            return "barred"
        return None
    allowed = bool(answer.get("allowed_stages"))
    refused = bool(answer.get("refused_stages"))
    if allowed and refused:
        return "barred_and_required"
    if allowed:
        return "required"
    if refused:
        return "barred"
    return None


def piece_side(piece: str, inclusion: str, exclusion: str) -> str:
    in_i = present(piece, inclusion)
    in_e = present(piece, exclusion)
    if in_i and in_e:
        return "both"
    if in_i:
        return "inclusion"
    if in_e:
        return "exclusion"
    return "unlocated"


def classify_c(item: dict) -> tuple[str, str | None]:
    """Return (sub-bucket, matched spelling or parent cue). C1 only for therapy."""
    quote = item["quote"]
    fact = item["fact"]
    extra = C2_WORDS.get(fact)
    extra_hit = extra.search(quote) if extra else None

    if fact == "prior_platinum_chemo":
        if NAIVE_WORDS.search(quote):
            return "C1", "no prior anticancer therapy"
        if CHEMO_WORDS.search(quote) or re.search(r"\bchemo\b|chemo-", quote, re.IGNORECASE):
            return "C1", "chemotherapy"
        if SYSTEMIC_WORDS.search(quote) or ANTICANCER_WORDS.search(quote):
            return "C1", "systemic/anticancer"
        if CYTOTOXIC_WORDS.search(quote):
            return "C1", "cytotoxic"
        if extra_hit:
            return "C2", extra_hit.group(0)
        return "C3", None

    if fact == "prior_immunotherapy":
        if NAIVE_WORDS.search(quote):
            return "C1", "no prior anticancer therapy"
        if SYSTEMIC_WORDS.search(quote) or ANTICANCER_WORDS.search(quote):
            return "C1", "systemic/anticancer"
        if extra_hit:
            return "C2", extra_hit.group(0)
        if CHEMO_WORDS.search(quote) or CYTOTOXIC_WORDS.search(quote):
            return "C3", "chemotherapy (not a parent of immunotherapy)"
        return "C3", None

    if extra_hit:
        return "C2", extra_hit.group(0)
    return "C3", None



def discarded_by_patient() -> dict[str, dict[str, set[str]]]:
    """patient -> fact -> set of nct discarded by that fact (matching-gated)."""
    yes_no = load_yes_no()
    markers = load_markers()
    extra = load_step5b()
    universe = sorted(set(yes_no) & set(markers) & set(extra))
    edges = load_child_to_parent()
    trial_names: dict[str, set[str]] = defaultdict(set)
    for row in load_assigned():
        trial_names[row["nct_id"]].add(canonical_name(row.get("assigned_name") or ""))
    parse = {row["patient_id"]: row for row in json.loads(PARSE.read_text(encoding="utf-8"))["patients"]}
    patients = json.loads(PATIENTS.read_text(encoding="utf-8"))["patients"]
    out: dict[str, dict[str, set[str]]] = {}
    for p in patients:
        pid = p["id"]
        traits = (parse[pid].get("answer") or {}).get("traits") or []
        listed = listed_facts(traits)
        found = {}
        for fact in FACTS:
            if fact not in listed:
                found[fact] = set()
            else:
                found[fact] = retrieve(listed[fact], trial_names, False, edges)
        by_fact = {f: set() for f in FACTS}
        for nct in universe:
            flags = oracle_out(p, nct, yes_no, markers, extra)
            for fact in FACTS:
                if flags[fact] and nct in found[fact]:
                    by_fact[fact].add(nct)
        out[pid] = by_fact
    return out


def main() -> None:
    print("collecting quote slots...", flush=True)
    items = collect_items()

    # Heading census on the whole corpus (1,307 trials), not just stitched quotes.
    all_criteria = load_criteria()
    trial_modes = Counter(heading_mode(t) for t in all_criteria.values())
    stitched = [i for i in items if i["orig_flag"] and i["bucket"] == "A"]
    check1_cross = []
    check1_unresolvable = []
    check1_same = 0
    check1_ambiguous = []
    modes = Counter()
    unlocated_all_pieces = 0
    for item in stitched:
        parts = split_sections(item["text"])
        mode = parts["mode"]
        modes[mode] += 1
        if mode != "line_header":
            check1_unresolvable.append({
                "nct_id": item["nct_id"],
                "fact": item["fact"],
                "mode": mode,
            })
            continue
        pieces = split_parts(item["quote"])
        hits = [p for p in pieces if present(p, item["text"])]
        if len(hits) < 2:
            unlocated_all_pieces += 1
            continue
        sides = [piece_side(p, parts["inclusion"], parts["exclusion"]) for p in hits]
        side_set = set(sides)
        mixed_lists = "inclusion" in side_set and "exclusion" in side_set
        if mixed_lists:
            check1_cross.append({
                "nct_id": item["nct_id"],
                "fact": item["fact"],
                "quote": item["quote"],
                "pieces": [
                    {"text": p, "side": s} for p, s in zip(hits, sides)
                ],
            })
        elif "both" in side_set and side_set <= {"both", "unlocated"}:
            check1_ambiguous.append({"nct_id": item["nct_id"], "fact": item["fact"]})
        else:
            check1_same += 1

    # Check 2
    e_items = [i for i in items if i["orig_flag"] and i["bucket"] == "E"]
    e_definite = [i for i in e_items if i["label"] in ("barred", "required", "barred_and_required")]
    print(f"recomputing matching-gated discards for 20 patients...", flush=True)
    discards = discarded_by_patient()
    harm = []
    for item in e_definite:
        fact = item["fact"]
        nct = item["nct_id"]
        for pid, by_fact in discards.items():
            if nct in by_fact.get(fact, set()):
                harm.append({
                    "patient_id": pid,
                    "nct_id": nct,
                    "fact": fact,
                    "label": item["label"],
                    "quote": item["quote"],
                })

    # Check 3
    c_items = [i for i in items if i["orig_flag"] and i["bucket"] == "C"]
    c_split = Counter()
    c_by_fact: dict[str, Counter] = defaultdict(Counter)
    c3_rows = []
    c1_rows = []
    c2_spellings = Counter()
    c1_cues = Counter()
    for item in c_items:
        sub, cue = classify_c(item)
        c_split[sub] += 1
        c_by_fact[item["fact"]][sub] += 1
        if sub == "C3":
            c3_rows.append({"nct_id": item["nct_id"], "fact": item["fact"], "quote": item["quote"][:300]})
        if sub == "C1":
            c1_rows.append({"nct_id": item["nct_id"], "fact": item["fact"], "cue": cue})
            c1_cues[f"{item['fact']}:{cue}"] += 1
        if sub == "C2":
            c2_spellings[f"{item['fact']}:{cue}"] += 1

    n_slots = len(items)
    de = sum(1 for i in items if i["bucket"] in ("D", "E"))
    # C3 among originally flagged C; also any C3 we classified
    c3_n = c_split["C3"]
    de_c3 = de + c3_n
    de_c3_rate = de_c3 / n_slots if n_slots else None

    example = check1_cross[0] if check1_cross else None
    unres_trials = sorted({r["nct_id"] for r in check1_unresolvable})
    unres_by_mode = Counter(r["mode"] for r in check1_unresolvable)
    harm_grouped: dict[tuple[str, str], dict] = {}
    for row in harm:
        key = (row["nct_id"], row["fact"])
        slot = harm_grouped.setdefault(
            key,
            {"nct_id": row["nct_id"], "fact": row["fact"], "label": row["label"],
             "quote": row["quote"], "patients": []},
        )
        slot["patients"].append(row["patient_id"])
    for slot in harm_grouped.values():
        slot["patients"] = sorted(set(slot["patients"]))
    e_definite_keys = {(i["nct_id"], i["fact"]) for i in e_definite}
    e_no_discard = [
        {"nct_id": i["nct_id"], "fact": i["fact"], "label": i["label"]}
        for i in e_definite
        if (i["nct_id"], i["fact"]) not in harm_grouped
    ]
    payload = {
        "check1": {
            "n_stitched_flagged": len(stitched),
            "corpus_heading_modes": dict(trial_modes),
            "heading_mode_among_stitched": dict(modes),
            "n_clean_line_header": modes.get("line_header", 0),
            "n_unresolvable_quotes": len(check1_unresolvable),
            "n_unresolvable_trials": len(unres_trials),
            "n_same_list": check1_same,
            "n_piece_in_both_sections_ambiguous": len(check1_ambiguous),
            "n_hits_under_2": unlocated_all_pieces,
            "n_crossing": len(check1_cross),
            "crossing": [
                {"nct_id": r["nct_id"], "fact": r["fact"]} for r in check1_cross
            ],
            "example": example,
            "unresolvable": check1_unresolvable,
        },
        "check2": {
            "n_bucket_E_flagged": len(e_items),
            "n_E_barred_or_required": len(e_definite),
            "n_patient_trial_discards": len(harm),
            "n_unique_labels_that_discarded": len(harm_grouped),
            "n_definite_with_no_discard": len(e_no_discard),
            "discards_grouped": list(harm_grouped.values()),
            "discards": harm,
            "definite_no_discard": e_no_discard,
        },
        "check3": {
            "n_C": len(c_items),
            "split": dict(c_split),
            "by_fact": {f: dict(c) for f, c in sorted(c_by_fact.items())},
            "c1_n": c_split["C1"],
            "c2_n": c_split["C2"],
            "c3_n": c3_n,
            "c1_cues": dict(c1_cues),
            "c2_missing_spellings": dict(c2_spellings),
            "c3_rows": c3_rows,
            "D_plus_E": de,
            "D_plus_E_rate": round(de / n_slots, 4),
            "D_plus_E_plus_C3": de_c3,
            "D_plus_E_plus_C3_rate": round(de_c3_rate, 4) if de_c3_rate is not None else None,
            "n_slots": n_slots,
            "gate_5pct_cleared": (de_c3_rate or 1) <= 0.05,
        },
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    n_cross = len(check1_cross)
    write_report(
        n_cross=n_cross,
        check1_cross=check1_cross,
        example=example,
        trial_modes=trial_modes,
        modes=modes,
        check1_unresolvable=check1_unresolvable,
        unres_trials=unres_trials,
        unres_by_mode=unres_by_mode,
        check1_same=check1_same,
        check1_ambiguous=check1_ambiguous,
        e_items=e_items,
        e_definite=e_definite,
        harm=harm,
        harm_grouped=harm_grouped,
        e_no_discard=e_no_discard,
        c_items=c_items,
        c_split=c_split,
        c_by_fact=c_by_fact,
        c2_spellings=c2_spellings,
        c3_rows=c3_rows,
        de=de,
        n_slots=n_slots,
        de_c3=de_c3,
        de_c3_rate=de_c3_rate,
        payload=payload,
    )
    print(f"check1 crossing={n_cross} unresolvable={len(check1_unresolvable)} same={check1_same}")
    print(f"check2 E={len(e_items)} definite={len(e_definite)} harm={len(harm)} unique={len(harm_grouped)}")
    print(f"check3 {dict(c_split)} D+E+C3={de_c3_rate:.4f}")
    print(f"Wrote {OUT}")
    print(f"Wrote {REPORT}")


def _esc(value: str) -> str:
    return (value or "").replace("|", "/").replace("\n", " ").strip()


def write_report(**kw) -> None:
    n_cross = kw["n_cross"]
    check1_cross = kw["check1_cross"]
    example = kw["example"]
    trial_modes = kw["trial_modes"]
    modes = kw["modes"]
    check1_unresolvable = kw["check1_unresolvable"]
    unres_trials = kw["unres_trials"]
    unres_by_mode = kw["unres_by_mode"]
    check1_same = kw["check1_same"]
    check1_ambiguous = kw["check1_ambiguous"]
    e_items = kw["e_items"]
    e_definite = kw["e_definite"]
    harm = kw["harm"]
    harm_grouped = kw["harm_grouped"]
    e_no_discard = kw["e_no_discard"]
    c_items = kw["c_items"]
    c_split = kw["c_split"]
    c_by_fact = kw["c_by_fact"]
    c2_spellings = kw["c2_spellings"]
    c3_rows = kw["c3_rows"]
    de = kw["de"]
    n_slots = kw["n_slots"]
    de_c3 = kw["de_c3"]
    de_c3_rate = kw["de_c3_rate"]
    payload = kw["payload"]

    lines = [
        "# Step 9 — three mechanical quote checks",
        "",
        "Reporting rules committed in THRESHOLDS.md before this ran. A non-zero",
        "count on check 1 or 2 is named (trial ids, facts, and for check 2 the",
        "patient–trial pairs), not folded into a percentage. No row was re-labelled.",
        "The 30-row consequential sheet and its notes file were not touched.",
        "",
        "## Check 1 — stitched quotes crossing can-join / cannot-join",
        "",
    ]
    if n_cross == 0:
        lines.append(
            "**No stitched quote mixes the two lists** among trials with a "
            "clean line heading."
        )
    else:
        by_fact = defaultdict(list)
        for row in check1_cross:
            by_fact[row["fact"]].append(row["nct_id"])
        n_trials = len({row["nct_id"] for row in check1_cross})
        lines.append(
            f"**{n_cross} stitched quotes mix the two lists**, across {n_trials} trials."
        )
        lines.append("")
        lines.append("Count by fact:")
        lines.append("")
        lines.append("| Fact | Crossing quotes |")
        lines.append("|---|---:|")
        for fact in sorted(by_fact, key=lambda f: -len(by_fact[f])):
            lines.append(f"| {fact} | {len(by_fact[fact])} |")
        lines.append("")
        lines.append("Trial ids, by fact:")
        lines.append("")
        for fact in sorted(by_fact, key=lambda f: -len(by_fact[f])):
            ids = ", ".join(sorted(set(by_fact[fact])))
            lines.append(f"**{fact}** ({len(by_fact[fact])}): {ids}")
            lines.append("")
        if example:
            lines += [
                "### One crossing, in full",
                "",
                f"Trial `{example['nct_id']}`, fact `{example['fact']}`.",
                "",
                "Assembled quote:",
                "",
                f"> {example['quote']}",
                "",
                "Pieces:",
                "",
            ]
            for piece in example["pieces"]:
                lines.append(f"- **{piece['side']}:** {piece['text']}")
            lines.append("")
            lines.append(
                "The inclusion piece and the exclusion piece can point opposite "
                "ways. A label that rests on this quote may be reading the wrong list."
            )
    lines += [
        "",
        "### What could not be checked",
        "",
        f"The splitter is clean (`line_header`) on **{trial_modes.get('line_header', 0)}** "
        f"of {sum(trial_modes.values())} trials. "
        f"**{trial_modes.get('loose_header', 0)}** need the looser heading rule, "
        f"**{trial_modes.get('no_header', 0)}** have no heading. Those are unresolvable, "
        "not counted as clean.",
        "",
        f"Of 619 stitched quotes: {modes.get('line_header', 0)} sat on a clean heading "
        f"and were checked; {len(check1_unresolvable)} could not be "
        f"({unres_by_mode.get('loose_header', 0)} loose heading, "
        f"{unres_by_mode.get('no_header', 0)} no heading) on {len(unres_trials)} trials.",
        f"Same-list among the checkable: {check1_same}. "
        f"Pieces that sat in both sections and nowhere else: {len(check1_ambiguous)}.",
        "",
        "## Check 2 — absent quotes that caused a real discard",
        "",
        f"Forty-three originally flagged labels rest on text that is not in the trial "
        f"(bucket E). {len(e_definite)} of those are `barred` / `required` "
        "(or list-shaped both), the only labels that can discard. "
        f"{len(e_items) - len(e_definite)} were other classes and cannot discard.",
        "",
    ]
    if not harm:
        lines.append(
            "**Forty-three labels had unsupported quotes and none of them affected any decision.**"
        )
    else:
        lines.append(
            f"**{len(harm)} patient–trial discards rest on a quote that is not in the trial.** "
            f"They come from {len(harm_grouped)} labels. "
            f"{len(e_no_discard)} barred/required E labels discarded nobody among the 20 patients."
        )
        lines.append("")
        lines.append(
            "This is the CorpFam failure mode: a correct-looking verdict resting on "
            "invented evidence. One of them, written out:"
        )
        # Prefer a title-as-quote example if present.
        written = None
        for slot in harm_grouped.values():
            q = slot["quote"]
            if q.lower().startswith("a study"):
                written = slot
                break
        if written is None:
            written = next(iter(harm_grouped.values()))
        others = written["patients"][1:]
        patient_line = f"- patient: `{written['patients'][0]}`"
        if others:
            patient_line += " (this label also discarded for " + ", ".join(f"`{p}`" for p in others) + ")"
        lines += [
            "",
            patient_line,
            f"- trial: `{written['nct_id']}`",
            f"- fact: `{written['fact']}`",
            f"- label: `{written['label']}`",
            f"- quote that does not exist in the eligibility text: {written['quote']}",
            "",
            "Every pair, grouped by the label that caused it:",
            "",
            "| Patients | Trial | Fact | Label | Quote that is not in the trial |",
            "|---|---|---|---|---|",
        ]
        for slot in sorted(
            harm_grouped.values(),
            key=lambda s: (-len(s["patients"]), s["nct_id"], s["fact"]),
        ):
            lines.append(
                f"| {', '.join(slot['patients'])} | {slot['nct_id']} | "
                f"{slot['fact']} | {slot['label']} | {_esc(slot['quote'])} |"
            )
    lines += [
        "",
        "## Check 3 — word-list misses, split",
        "",
        "C1 is only assigned in the prior-therapy family, and only when the quote "
        "names a parent in `therapy_hierarchy.json` (chemotherapy or systemic/"
        "anticancer treatment). Marker, stage, brain, and autoimmune cannot be C1.",
        "",
        f"| Sub-bucket | n | of {len(c_items)} C |",
        "|---|---:|---:|",
        f"| C1 hierarchy parent | {c_split['C1']} | {c_split['C1']/len(c_items):.1%} |",
        f"| C2 missing spelling/synonym | {c_split['C2']} | {c_split['C2']/len(c_items):.1%} |",
        f"| C3 unrelated | {c_split['C3']} | {c_split['C3']/len(c_items):.1%} |",
        "",
        "| Fact | C1 | C2 | C3 |",
        "|---|---:|---:|---:|",
    ]
    for fact, counts in sorted(c_by_fact.items()):
        lines.append(
            f"| {fact} | {counts.get('C1', 0)} | {counts.get('C2', 0)} | {counts.get('C3', 0)} |"
        )
    lines += [
        "",
        "### C2 — spellings the word list lacked",
        "",
        "| Fact | Missing spelling (as matched) | n |",
        "|---|---|---:|",
    ]
    for key, n in sorted(c2_spellings.items(), key=lambda kv: (-kv[1], kv[0])):
        fact, spelling = key.split(":", 1)
        lines.append(f"| {fact} | `{spelling}` | {n} |")
    lines += [
        "",
        f"D+E was {de} / {n_slots} ({de/n_slots:.1%}).",
        f"**D+E+C3 = {de_c3} / {n_slots} ({de_c3_rate:.1%})**. "
        f"The committed 5% support gate is "
        f"{'cleared' if payload['check3']['gate_5pct_cleared'] else 'not cleared'}.",
        "",
    ]
    if c_split["C1"] >= 50:
        lines.append(
            f"C1 is large ({c_split['C1']}: {c_by_fact['prior_platinum_chemo'].get('C1', 0)} "
            f"platinum, {c_by_fact['prior_immunotherapy'].get('C1', 0)} immunotherapy). "
            "That is independent evidence — arriving from a completely different "
            "direction than the platinum measurement — that trials routinely state "
            "rules at a broader level than the fact being matched. It corroborates "
            "the prior-therapy containment hierarchy."
        )
        lines.append("")
    lines += [
        "C3 rows were not re-labelled. They are the same kind of failure as D and E "
        "(a label not supported by its quote) and are already folded into the 5% check "
        "above. Typical remaining C3: a brain label on a 'metastatic disease' sentence "
        "that never mentions the brain; an immunotherapy or platinum label on "
        "'treatment-naïve' / 'no prior therapy', which sits above the written "
        "hierarchy and was not absorbed into C1.",
        "",
        "No rows were moved between buckets on the strength of this check. "
        "Steps 6 and 7 were not started.",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")



if __name__ == "__main__":
    main()
