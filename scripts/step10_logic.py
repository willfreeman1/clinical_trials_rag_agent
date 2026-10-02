"""Rank questions and apply answers. Arithmetic. No API."""

from __future__ import annotations

from collections import defaultdict

from step10_common import (  # noqa: E402
    ASKABLE,
    DONT_KNOW,
    coordinator_answer,
    is_live,
    tag_excludes,
)
from step2_ceiling import marker_out, stage_out, yes_no_out  # noqa: E402


def definite_discarded(patient: dict, yes_no: dict, markers: dict, extra: dict, universe: list[str]) -> set[str]:
    out = set()
    has_immuno = bool(patient["prior_immunotherapy"])
    has_brain = bool(patient["brain_metastases"])
    has_plat = bool(patient["prior_platinum_chemo"])
    has_auto = bool(patient["autoimmune_disease"])
    for nct in universe:
        if yes_no_out(yes_no[nct].get("prior_immunotherapy_classification", ""), has_immuno, False):
            out.add(nct)
            continue
        if yes_no_out(yes_no[nct].get("brain_metastases_classification", ""), has_brain, False):
            out.add(nct)
            continue
        if yes_no_out(extra[nct].get("prior_platinum_chemo_classification", ""), has_plat, False):
            out.add(nct)
            continue
        if yes_no_out(extra[nct].get("autoimmune_disease_classification", ""), has_auto, False):
            out.add(nct)
            continue
        if marker_out(patient["driver_mutation"], markers[nct], False):
            out.add(nct)
            continue
        if stage_out(patient["disease_stage"], extra[nct], False):
            out.add(nct)
    return out


def matching_discarded(patient: dict, yes_no, markers, extra, universe, found: dict[str, set[str]]) -> set[str]:
    out = set()
    has_immuno = bool(patient["prior_immunotherapy"])
    has_brain = bool(patient["brain_metastases"])
    has_plat = bool(patient["prior_platinum_chemo"])
    has_auto = bool(patient["autoimmune_disease"])
    for nct in universe:
        if nct in found.get("prior_immunotherapy", set()) and yes_no_out(
            yes_no[nct].get("prior_immunotherapy_classification", ""), has_immuno, False
        ):
            out.add(nct)
            continue
        if nct in found.get("brain_metastases", set()) and yes_no_out(
            yes_no[nct].get("brain_metastases_classification", ""), has_brain, False
        ):
            out.add(nct)
            continue
        if nct in found.get("prior_platinum_chemo", set()) and yes_no_out(
            extra[nct].get("prior_platinum_chemo_classification", ""), has_plat, False
        ):
            out.add(nct)
            continue
        if nct in found.get("autoimmune_disease", set()) and yes_no_out(
            extra[nct].get("autoimmune_disease_classification", ""), has_auto, False
        ):
            out.add(nct)
            continue
        if nct in found.get("driver_mutation", set()) and marker_out(patient["driver_mutation"], markers[nct], False):
            out.add(nct)
            continue
        if nct in found.get("disease_stage", set()) and stage_out(patient["disease_stage"], extra[nct], False):
            out.add(nct)
    return out


def live_tags(patient: dict, row: dict) -> list[dict]:
    return [
        tag
        for tag in (row.get("tags") or [])
        if tag.get("question") in ASKABLE and is_live(patient, tag["question"])
    ]


def candidate_rows(
    patient: dict,
    remaining: set[str],
    by_nct: dict[str, list[dict]],
    found: dict[str, set[str]] | None,
) -> list[dict]:
    rows = []
    for nct in remaining:
        for row in by_nct.get(nct, []):
            tags = live_tags(patient, row)
            if not tags:
                continue
            if found is not None and nct not in found.get(row["fact"], set()):
                continue
            rows.append(row)
    return rows


def rank_questions(
    patient: dict,
    remaining: set[str],
    by_nct: dict[str, list[dict]],
    found=None,
    answers: dict | None = None,
) -> list[tuple[str, int]]:
    already = set(answers or {})
    ncts_for: dict[str, set[str]] = defaultdict(set)
    for row in candidate_rows(patient, remaining, by_nct, found):
        for tag in live_tags(patient, row):
            q = tag["question"]
            if q in already:
                continue
            ncts_for[q].add(row["nct_id"])
    scored = [(q, len(ncts_for[q])) for q in ASKABLE if ncts_for[q]]
    scored.sort(key=lambda kv: (-kv[1], kv[0]))
    return scored


def trial_decision(patient: dict, nct: str, rows: list[dict], answers: dict) -> str:
    """exclude, keep_open, or keep_settled. Don't-know keeps the trial (keep_open)."""
    live = []
    for row in rows:
        live.extend(live_tags(patient, row))
    if not live:
        return "keep_settled"
    open_tags = 0
    for tag in live:
        q = tag["question"]
        if q not in answers:
            open_tags += 1
            continue
        if tag_excludes(tag, answers[q]):
            return "exclude"
        if answers[q] == DONT_KNOW:
            open_tags += 1
    if open_tags:
        return "keep_open"
    return "keep_settled"


def apply_answers(
    patient: dict,
    remaining: set[str],
    by_nct: dict[str, list[dict]],
    answers: dict,
    found=None,
) -> dict:
    extra_discard = set()
    settled_keep = set()
    still_open = set()
    considered = set()
    for row in candidate_rows(patient, remaining, by_nct, found):
        considered.add(row["nct_id"])
    for nct in considered:
        decision = trial_decision(patient, nct, by_nct.get(nct, []), answers)
        if decision == "exclude":
            extra_discard.add(nct)
        elif decision == "keep_settled":
            settled_keep.add(nct)
        else:
            still_open.add(nct)
    return {
        "extra_discard": extra_discard,
        "settled_keep": settled_keep,
        "still_open": still_open,
        "settled": extra_discard | settled_keep,
    }


def ask_and_fold(patient: dict, question: str, remaining: set[str], by_nct, answers: dict, found=None) -> dict:
    answers = dict(answers)
    answers[question] = coordinator_answer(patient, question)
    applied = apply_answers(patient, remaining, by_nct, answers, found)
    new_remaining = set(remaining) - applied["extra_discard"]
    return {
        "answers": answers,
        "remaining": new_remaining,
        "applied": applied,
        "value": answers[question],
    }
