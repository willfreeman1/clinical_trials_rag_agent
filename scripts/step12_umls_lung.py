"""Lung-slice UMLS API diagnostic. Gene-symbol matching untouched.

Gates in THRESHOLDS.md commit a2dfda5, before any REST call.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from step2_ceiling import load_markers, load_step5b, load_yes_no  # noqa: E402
from step3b_match import has_rule  # noqa: E402
from step3c_closed_names import FACT_TO_NAME  # noqa: E402
from step3d_match import (  # noqa: E402
    FACTS,
    load_assigned,
    rates,
    retrieve,
)
from step3d_reassign import canonical_name  # noqa: E402
from therapy_containment import MATCH, comparison as name_cmp, load_child_to_parent  # noqa: E402
from umls_rest import ancestors, comparison, load_cache, load_umls_key, save_cache, search_cui  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PATIENTS = ROOT / "data" / "fake_patients_draw.json"
OUT = ROOT / "data" / "step12_umls_lung.json"
REPORT = ROOT / "docs" / "step12_umls_lung.md"

UMLS_FACTS = [
    "prior_immunotherapy",
    "brain_metastases",
    "prior_platinum_chemo",
    "autoimmune_disease",
    "disease_stage",
]
MARKER = "driver_mutation"
SIX_NAME_MEAN = 0.939
RECALL_GATE = 0.84
FPR_GATE = 0.05


def patient_phrase(p: dict, fact: str) -> str:
    if fact == "prior_immunotherapy":
        return "immunotherapy"
    if fact == "prior_platinum_chemo":
        return "platinum-based chemotherapy"
    if fact == "brain_metastases":
        return "cancer spread to the brain"
    if fact == "autoimmune_disease":
        return "autoimmune disease"
    if fact == "disease_stage":
        return f"stage {p['disease_stage']}"
    return fact


def main() -> None:
    api_key = load_umls_key()
    cache = load_cache()
    edges = load_child_to_parent()
    rows = load_assigned()
    yes_no = load_yes_no()
    markers = load_markers()
    extra = load_step5b()
    patients = json.loads(PATIENTS.read_text(encoding="utf-8"))["patients"]
    universe = sorted(set(yes_no) & set(markers) & set(extra))

    truth: dict[str, set[str]] = {f: set() for f in FACTS}
    for nct in universe:
        for fact in FACTS:
            if has_rule(nct, fact, yes_no, markers, extra):
                truth[fact].add(nct)

    trial_names: dict[str, set[str]] = defaultdict(set)
    quotes_by_nct_fact: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    unique_quotes: set[str] = set()
    for row in rows:
        nct = row["nct_id"]
        fact = row.get("fact")
        name = canonical_name(row.get("assigned_name") or "")
        trial_names[nct].add(name)
        q = (row.get("quote") or "").strip()
        if fact in UMLS_FACTS and q:
            quotes_by_nct_fact[nct][fact].append(q)
            unique_quotes.add(q)

    patient_phrases = sorted({patient_phrase(p, f) for p in patients for f in UMLS_FACTS})
    to_search = sorted(unique_quotes | set(patient_phrases))
    print(f"unique_quote_lookups={len(unique_quotes)} patient_phrases={len(patient_phrases)}", flush=True)

    cui_of: dict[str, str | None] = {}
    for i, phrase in enumerate(to_search, 1):
        cui_of[phrase] = search_cui(api_key, phrase, cache)
        if i % 50 == 0:
            save_cache(cache)
            print(f"search {i}/{len(to_search)}", flush=True)
    save_cache(cache)

    needed = {c for c in cui_of.values() if c}
    print(f"unique_cuis={len(needed)} fetching ancestors", flush=True)
    anc: dict[str, set[str]] = {}
    for i, cui in enumerate(sorted(needed), 1):
        anc[cui] = ancestors(api_key, cui, cache)
        if i % 25 == 0:
            save_cache(cache)
            print(f"ancestors {i}/{len(needed)}", flush=True)
    save_cache(cache)

    n_quote = len(unique_quotes)
    n_quote_hit = sum(1 for q in unique_quotes if cui_of.get(q))
    n_pat_hit = sum(1 for ph in patient_phrases if cui_of.get(ph))

    found: dict[str, dict[str, set[str]]] = {}
    fallback_n = 0
    umls_decided = 0
    for p in patients:
        pid = p["id"]
        found[pid] = {}
        found[pid][MARKER] = retrieve(FACT_TO_NAME[MARKER], trial_names, False, edges)
        for fact in UMLS_FACTS:
            p_cui = cui_of.get(patient_phrase(p, fact))
            hits: set[str] = set()
            for nct in universe:
                quotes = quotes_by_nct_fact[nct].get(fact) or []
                decided = False
                matched = False
                for q in quotes:
                    t_cui = cui_of.get(q)
                    verdict = comparison(p_cui, t_cui, anc)
                    if verdict == "miss":
                        continue
                    decided = True
                    umls_decided += 1
                    if verdict == "match":
                        matched = True
                        break
                if decided:
                    if matched:
                        hits.add(nct)
                    continue
                fallback_n += 1
                names = trial_names.get(nct, set())
                query = FACT_TO_NAME[fact]
                if any(name_cmp(query, n, edges) == MATCH for n in names):
                    hits.add(nct)
            found[pid][fact] = hits

    per_patient = [rates(found[p["id"]], truth, universe, FACTS) for p in patients]
    by_fact = {}
    recs, fprs = [], []
    for fact in FACTS:
        fact_recs = [r[fact]["recall"] for r in per_patient if r[fact]["recall"] is not None]
        fact_fprs = [r[fact]["wrongly_picked_up"] for r in per_patient if r[fact]["wrongly_picked_up"] is not None]
        sample = per_patient[0][fact]
        by_fact[fact] = {
            "recall": round(sum(fact_recs) / len(fact_recs), 4) if fact_recs else None,
            "wrongly_picked_up": round(sum(fact_fprs) / len(fact_fprs), 4) if fact_fprs else None,
            "via": "existing_gene_symbol_matcher" if fact == MARKER else "umls_api",
            "tp": sample["tp"],
            "fn": sample["fn"],
            "fp": sample["fp"],
            "tn": sample["tn"],
        }
        if fact_recs:
            recs.append(sum(fact_recs) / len(fact_recs))
        if fact_fprs:
            fprs.append(sum(fact_fprs) / len(fact_fprs))
    mean_r = round(sum(recs) / len(recs), 4) if recs else None
    mean_f = round(sum(fprs) / len(fprs), 4) if fprs else None
    report = {
        "thresholds_commit": "a2dfda5",
        "marker_untouched": True,
        "mean_recall": mean_r,
        "mean_wrongly_picked_up": mean_f,
        "six_name_mean_recall": SIX_NAME_MEAN,
        "gates": {
            "recall_cleared": mean_r is not None and mean_r >= RECALL_GATE,
            "fpr_cleared": mean_f is not None and mean_f <= FPR_GATE,
        },
        "by_fact": by_fact,
        "lookup": {
            "n_unique_quotes": n_quote,
            "n_quotes_resolved": n_quote_hit,
            "quote_miss_rate": round(1 - n_quote_hit / n_quote, 4) if n_quote else None,
            "n_patient_phrases": len(patient_phrases),
            "n_patient_resolved": n_pat_hit,
            "n_fallback_closed_name": fallback_n,
            "n_umls_decided_pairs": umls_decided,
        },
        "scispacy": "no concept is-a; unused. docs/scispacy_umls_check.md",
        "no_metathesaurus": True,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "# UMLS lung-slice gate (REST API)",
        "",
        "Gene-symbol matching for tumour genetic marker was not replaced.",
        "scispaCy unused (no concept is-a). No Metathesaurus download.",
        "",
        f"Mean recall **{mean_r}** vs six-name 93.9% (gate ≥84%). "
        f"{'cleared' if report['gates']['recall_cleared'] else 'MISSED'}.",
        f"Mean false pickup **{mean_f}** (gate ≤5%). "
        f"{'cleared' if report['gates']['fpr_cleared'] else 'BREACHED'}.",
        "",
        "| Fact | Recall | False pickup | Path |",
        "|---|---:|---:|---|",
    ]
    for fact in FACTS:
        b = by_fact[fact]
        lines.append(
            f"| {fact} | {b['recall']} | {b['wrongly_picked_up']} | {b['via']} |"
        )
    lines += [
        "",
        f"Quote lookup miss rate: {report['lookup']['quote_miss_rate']} "
        f"({n_quote - n_quote_hit}/{n_quote}). Misses fall back to closed-name matching.",
        "",
        "Will's extraction prompt was not rewritten. Steps 6 and 7 not started.",
        "TREC assignment not started.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("Wrote", OUT)


if __name__ == "__main__":
    main()
