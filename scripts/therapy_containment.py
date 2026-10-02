"""Directional containment for the prior-therapy family.

Neither side is rewritten. The hierarchy is read from therapy_hierarchy.json
and used only to decide whether a trial rule applies to this patient.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
HIERARCHY_PATH = ROOT / "therapy_hierarchy.json"

MATCH = "match"
CANT_TELL = "cant_tell"
NO_MATCH = "no_match"


@lru_cache(maxsize=4)
def load_child_to_parent(path: Optional[str] = None) -> dict[str, str]:
    data = json.loads((Path(path) if path else HIERARCHY_PATH).read_text(encoding="utf-8"))
    return dict(data["child_to_parent"])


def ancestors(name: str, child_to_parent: dict[str, str] | None = None) -> set[str]:
    """The name itself, then each parent up the chain."""
    edges = child_to_parent if child_to_parent is not None else load_child_to_parent()
    out = {name}
    cur = name
    seen: set[str] = set()
    while cur in edges and cur not in seen:
        seen.add(cur)
        cur = edges[cur]
        out.add(cur)
    return out


def comparison(patient_name: str, trial_name: str, child_to_parent: dict[str, str] | None = None) -> str:
    """Case 1 same → match; 2 patient narrower → match; 3 patient broader → can't-tell; 4 else no match."""
    edges = child_to_parent if child_to_parent is not None else load_child_to_parent()
    patient_name = (patient_name or "").strip()
    trial_name = (trial_name or "").strip()
    if not patient_name or not trial_name or trial_name == "other" or patient_name == "other":
        return NO_MATCH
    if patient_name == trial_name:
        return MATCH
    if trial_name in ancestors(patient_name, edges):
        return MATCH
    if patient_name in ancestors(trial_name, edges):
        return CANT_TELL
    return NO_MATCH


def rule_applies(patient_name: str, trial_name: str, child_to_parent: dict[str, str] | None = None) -> bool:
    return comparison(patient_name, trial_name, child_to_parent) == MATCH


def _self_check() -> None:
    """The four cases, plus the immuno-is-not-chemo trap. Fails loud if the file is edited wrong."""
    p, c, s, any_rx = (
        "previous platinum chemotherapy",
        "previous chemotherapy (any kind)",
        "previous systemic anticancer treatment (any kind)",
        "previous anticancer therapy of any kind",
    )
    i = "previous immunotherapy"
    assert comparison(p, p) == MATCH
    assert comparison(p, c) == MATCH
    assert comparison(p, s) == MATCH
    assert comparison(p, any_rx) == MATCH
    assert comparison(i, any_rx) == MATCH
    assert comparison(s, any_rx) == MATCH
    assert comparison(any_rx, p) == CANT_TELL
    assert comparison(any_rx, i) == CANT_TELL
    assert comparison(c, p) == CANT_TELL
    assert comparison(s, p) == CANT_TELL
    assert comparison(s, c) == CANT_TELL
    assert comparison(i, s) == MATCH
    assert comparison(i, c) == NO_MATCH
    assert comparison(c, i) == NO_MATCH
    assert comparison(p, i) == NO_MATCH
    assert comparison(i, p) == NO_MATCH
    assert comparison("cancer spread to the brain", "cancer spread to the brain") == MATCH
    assert comparison("cancer spread to the brain", p) == NO_MATCH
    assert comparison("other", p) == NO_MATCH


if __name__ == "__main__":
    _self_check()
    print("therapy_containment self-check ok")
