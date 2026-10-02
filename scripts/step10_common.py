"""Shared clarifying-question helpers. Thresholds in THRESHOLDS.md."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN = json.loads((ROOT / "questions_design.json").read_text(encoding="utf-8"))
DATA = ROOT / "data"
DRAW = DATA / "fake_patients_draw.json"
ORACLE = ROOT / "questions_oracle_draw.json"
QUESTIONS_PATIENTS = DATA / "fake_patients_questions.json"
ASSIGNED = DATA / "step10_assigned.jsonl"

DONT_KNOW = "dont_know"
QUESTION_IDS = {q["id"] for q in DESIGN["canonical_questions"]}
ASKABLE = sorted(QUESTION_IDS - {"other"})

FACT_CLASS = {
    "prior_immunotherapy": ("yes_no", "prior_immunotherapy_classification", "prior_immunotherapy_quote"),
    "brain_metastases": ("yes_no", "brain_metastases_classification", "brain_metastases_quote"),
    "prior_platinum_chemo": ("yes_no", "prior_platinum_chemo_classification", "prior_platinum_chemo_quote"),
    "autoimmune_disease": ("yes_no", "autoimmune_disease_classification", "autoimmune_disease_quote"),
    "driver_mutation": ("list", None, "genetic_marker_quote"),
    "disease_stage": ("list", None, "stage_quote"),
}


def load_extended_patients() -> list[dict]:
    if QUESTIONS_PATIENTS.exists():
        return json.loads(QUESTIONS_PATIENTS.read_text(encoding="utf-8"))["patients"]
    base = {p["id"]: p for p in json.loads(DRAW.read_text(encoding="utf-8"))["patients"]}
    extra = json.loads(ORACLE.read_text(encoding="utf-8"))
    out = []
    for row in extra["patients"]:
        merged = dict(base[row["id"]])
        merged.update({k: v for k, v in row.items() if k != "id"})
        out.append(merged)
    return out


def weeks_of(field) -> tuple[float | None, str]:
    if field is None:
        return None, DONT_KNOW
    if isinstance(field, dict):
        status = field.get("status") or "known"
        if status == "never":
            return None, "never"
        if field.get("value") is None:
            return None, DONT_KNOW
        return float(field["value"]), "known"
    try:
        return float(field), "known"
    except (TypeError, ValueError):
        return None, DONT_KNOW


def coordinator_answer(patient: dict, question: str):
    if question == "brain_treatment":
        val = patient.get("brain_treatment")
        return DONT_KNOW if val in (None, "") else val
    if question == "brain_stable_weeks":
        n, status = weeks_of(patient.get("brain_stable_weeks"))
        if status == DONT_KNOW:
            return DONT_KNOW
        if status == "never":
            return "never"
        return n
    if question == "brain_symptoms":
        return patient.get("brain_symptoms") or DONT_KNOW
    if question == "brain_steroids":
        return patient.get("brain_steroids") or DONT_KNOW
    if question == "leptomeningeal":
        return patient.get("leptomeningeal") or DONT_KNOW
    if question == "autoimmune_activity":
        return patient.get("autoimmune_activity") or DONT_KNOW
    if question == "autoimmune_systemic_months":
        n, status = weeks_of(patient.get("autoimmune_systemic_months"))
        if status == DONT_KNOW:
            return DONT_KNOW
        if status == "never":
            return "never"
        return n
    if question == "immuno_washout_weeks":
        n, status = weeks_of(patient.get("immuno_washout_weeks"))
        if status == DONT_KNOW:
            return DONT_KNOW
        if status == "never":
            return "never"
        return n
    if question == "systemic_washout_weeks":
        n, status = weeks_of(patient.get("systemic_washout_weeks"))
        if status == DONT_KNOW:
            return DONT_KNOW
        if status == "never":
            return "never"
        return n
    if question == "amenable_to_curative_therapy":
        return patient.get("amenable_to_curative_therapy") or DONT_KNOW
    return DONT_KNOW


def is_live(patient: dict, question: str) -> bool:
    if question == "other" or question not in QUESTION_IDS:
        return False
    if question in {"brain_treatment", "brain_stable_weeks", "brain_symptoms", "brain_steroids", "leptomeningeal"}:
        return bool(patient.get("brain_metastases"))
    if question in {"autoimmune_activity", "autoimmune_systemic_months"}:
        return bool(patient.get("autoimmune_disease"))
    if question == "immuno_washout_weeks":
        return bool(patient.get("prior_immunotherapy"))
    if question == "systemic_washout_weeks":
        lines = patient.get("prior_lines_of_therapy") or 0
        try:
            n_lines = int(lines)
        except (TypeError, ValueError):
            n_lines = 0
        return bool(patient.get("prior_platinum_chemo") or patient.get("prior_immunotherapy") or n_lines >= 1)
    if question == "amenable_to_curative_therapy":
        return True
    return False


def to_weeks(threshold, unit: str | None) -> float | None:
    if threshold is None or threshold == "":
        return None
    try:
        n = float(threshold)
    except (TypeError, ValueError):
        return None
    u = (unit or "weeks").lower()
    if u.startswith("month"):
        return n * 4.345
    if u.startswith("day"):
        return n / 7.0
    if u.startswith("year"):
        return n * 52.0
    return n


def to_months(threshold, unit: str | None) -> float | None:
    if threshold is None or threshold == "":
        return None
    try:
        n = float(threshold)
    except (TypeError, ValueError):
        return None
    u = (unit or "months").lower()
    if u.startswith("week"):
        return n / 4.345
    if u.startswith("day"):
        return n / 30.4
    if u.startswith("year"):
        return n * 12.0
    return n


def tag_excludes(tag: dict, answer) -> bool:
    """Compare this trial's stored threshold to the answer. Don't-know never excludes."""
    if answer == DONT_KNOW:
        return False
    question = tag.get("question")
    threshold = tag.get("threshold")
    unit = tag.get("unit")
    if question == "brain_treatment":
        return answer == "untreated"
    if question == "brain_stable_weeks":
        if answer == "never":
            return True
        need = to_weeks(threshold, unit) or 4.0
        try:
            return float(answer) < need
        except (TypeError, ValueError):
            return False
    if question == "brain_symptoms":
        return answer in {"present", "progressive"}
    if question == "brain_steroids":
        raw = str(threshold or "").lower()
        if raw in {"any", "none", "all"}:
            return answer != "none"
        return answer == "increasing"
    if question == "leptomeningeal":
        return answer == "present"
    if question == "autoimmune_activity":
        return answer == "active"
    if question == "autoimmune_systemic_months":
        if answer == "never":
            return False
        need = to_months(threshold, unit) or 24.0
        try:
            return float(answer) < need
        except (TypeError, ValueError):
            return False
    if question == "immuno_washout_weeks":
        if answer == "never":
            return False
        need = to_weeks(threshold, unit) or 4.0
        try:
            return float(answer) < need
        except (TypeError, ValueError):
            return False
    if question == "systemic_washout_weeks":
        if answer == "never":
            return False
        need = to_weeks(threshold, unit) or 4.0
        try:
            return float(answer) < need
        except (TypeError, ValueError):
            return False
    if question == "amenable_to_curative_therapy":
        return answer == "yes"
    return False


def load_assignment() -> list[dict]:
    rows = []
    if not ASSIGNED.exists():
        return rows
    with ASSIGNED.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def assignment_by_nct(rows: list[dict] | None = None) -> dict[str, list[dict]]:
    by: dict[str, list[dict]] = {}
    for row in rows or load_assignment():
        by.setdefault(row["nct_id"], []).append(row)
    return by
