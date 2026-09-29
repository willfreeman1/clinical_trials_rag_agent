"""Step 3b: matching on general-term subjects.

Three arms: word overlap, embeddings at 0.80, combined. Then the
matching-gated ceiling — the Step 2 oracle, but a trial is thrown out only
if matching found it. Thresholds in THRESHOLDS.md, committed before this ran.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from step1_analyze import EMBED_MODEL, load_key  # noqa: E402
from step2_ceiling import (  # noqa: E402
    load_markers,
    load_yes_no,
    marker_out,
    project,
    yes_no_out,
)
from step3_match import cosine, embed_new  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SUBJECTS = ROOT / "data" / "step3b_quote_subjects.jsonl"
PARSE = ROOT / "data" / "step4_parse.json"
PATIENTS = ROOT / "data" / "fake_patients_draw.json"
VEC_CACHE = ROOT / "data" / "step3b_term_vecs.npz"
OUT = ROOT / "data" / "step3b_match_report.json"

STOP = {"the", "a", "an", "of", "to", "for", "on", "in", "and", "or", "with", "by", "from", "into", "as", "at", "is", "are"}
KEEP_SHORT = {"cns", "alk", "hiv", "met", "ret", "egfr", "kras", "ros1", "braf", "her2", "pd1", "pdl1"}
TOKEN = re.compile(r"[a-z0-9]+")
EMBED_THRESHOLD = 0.80
EMBED_SWEEP = (0.70, 0.75, 0.80, 0.85, 0.90)

# Patient trait name (and aliases) → answer-key fact.
NAME_TO_FACT = {
    "previous immunotherapy": "prior_immunotherapy",
    "previous checkpoint inhibitor": "prior_immunotherapy",
    "cancer spread to the brain": "brain_metastases",
    "tumour genetic marker": "driver_mutation",
    "tumor genetic marker": "driver_mutation",
}


def tokens(text: str) -> set[str]:
    words = TOKEN.findall((text or "").lower().replace("-", ""))
    out = set()
    for w in words:
        if w in STOP:
            continue
        if len(w) >= 4 or w in KEEP_SHORT:
            out.add(w)
    return out


def word_match(a: str, b: str) -> bool:
    return bool(tokens(a) & tokens(b))


def load_subjects() -> list[dict]:
    rows = []
    with SUBJECTS.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("subject"):
                rows.append(row)
    return rows


def load_patient_queries() -> dict[str, dict[str, list[str]]]:
    """patient_id -> fact -> query strings (name, and value if any)."""
    parse = json.loads(PARSE.read_text(encoding="utf-8"))
    by_pid: dict[str, dict[str, list[str]]] = {}
    for row in parse["patients"]:
        pid = row["patient_id"]
        by_pid[pid] = {}
        for t in (row.get("answer") or {}).get("traits") or []:
            name = (t.get("name") or "").strip().lower()
            fact = NAME_TO_FACT.get(name)
            if not fact:
                continue
            queries = [t.get("name") or ""]
            if t.get("kind") == "one_of_many" and t.get("value"):
                queries.append(str(t["value"]))
            by_pid[pid][fact] = queries
    return by_pid


def embed_terms(terms: list[str]) -> dict[str, np.ndarray]:
    unique = []
    seen = set()
    for t in terms:
        if t and t not in seen:
            seen.add(t)
            unique.append(t)
    by_term: dict[str, np.ndarray] = {}
    missing = list(unique)
    if VEC_CACHE.exists():
        cached = np.load(VEC_CACHE, allow_pickle=True)
        index = {t: i for i, t in enumerate(list(cached["terms"]))}
        still = []
        for t in missing:
            if t in index:
                by_term[t] = cached["vectors"][index[t]]
            else:
                still.append(t)
        missing = still
        if not missing:
            return by_term
    api_key = load_key()
    matrix, _ = embed_new(missing, api_key)
    old_terms, old_vecs = [], None
    if VEC_CACHE.exists():
        cached = np.load(VEC_CACHE, allow_pickle=True)
        old_terms = list(cached["terms"])
        old_vecs = cached["vectors"]
    all_terms = old_terms + missing
    all_vecs = matrix if old_vecs is None else np.vstack([old_vecs, matrix])
    np.savez(VEC_CACHE, vectors=all_vecs, terms=np.array(all_terms, dtype=object))
    for t, vec in zip(missing, matrix):
        by_term[t] = vec
    return by_term


def has_rule(nct: str, fact: str, yes_no: dict, markers: dict) -> bool:
    if fact == "prior_immunotherapy":
        return (yes_no.get(nct) or {}).get("prior_immunotherapy_classification", "not_mentioned") != "not_mentioned"
    if fact == "brain_metastases":
        return (yes_no.get(nct) or {}).get("brain_metastases_classification", "not_mentioned") != "not_mentioned"
    answer = markers.get(nct) or {}
    return bool(answer.get("required_markers") or answer.get("refused_markers"))


def retrieved(queries: list[str], trial_subjects: list[str], vecs: dict, method: str, threshold: float) -> bool:
    for q in queries:
        for s in trial_subjects:
            if method in ("word", "combined") and word_match(q, s):
                return True
            if method in ("embed", "combined") and q in vecs and s in vecs:
                if cosine(vecs[q], vecs[s]) >= threshold:
                    return True
    return False


def rates(found: dict[str, set[str]], truth: dict[str, set[str]], universe: list[str], facts: list[str]) -> dict:
    out = {}
    recalls, fprs = [], []
    for fact in facts:
        tp = fp = fn = tn = 0
        for nct in universe:
            is_rule = nct in truth[fact]
            is_hit = nct in found[fact]
            if is_rule and is_hit:
                tp += 1
            elif is_rule and not is_hit:
                fn += 1
            elif not is_rule and is_hit:
                fp += 1
            else:
                tn += 1
        recall = tp / (tp + fn) if (tp + fn) else None
        fpr = fp / (fp + tn) if (fp + tn) else None
        out[fact] = {
            "recall": None if recall is None else round(recall, 4),
            "wrongly_picked_up": None if fpr is None else round(fpr, 4),
            "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        }
        if recall is not None:
            recalls.append(recall)
        if fpr is not None:
            fprs.append(fpr)
    out["mean_recall"] = round(sum(recalls) / len(recalls), 4) if recalls else None
    out["mean_wrongly_picked_up"] = round(sum(fprs) / len(fprs), 4) if fprs else None
    return out


def gated_ceiling(patients: list[dict], yes_no: dict, markers: dict, found_by_patient: dict) -> dict:
    trial_ids = sorted(set(yes_no) & set(markers))
    n = len(trial_ids)
    rows = []
    for p in patients:
        pid = p["id"]
        found = found_by_patient[pid]
        union: set[str] = set()
        per = {}
        for pfield, kfield, fact in (
            ("prior_immunotherapy", "prior_immunotherapy_classification", "prior_immunotherapy"),
            ("brain_metastases", "brain_metastases_classification", "brain_metastases"),
        ):
            oracle = {t for t in trial_ids if yes_no_out(yes_no[t].get(kfield, ""), bool(p[pfield]), False)}
            kept = oracle & found[fact]
            per[pfield] = {"oracle": len(oracle), "matched": len(kept), "share": round(len(kept) / n, 4)}
            union |= kept
        oracle_m = {t for t in trial_ids if marker_out(p["driver_mutation"], markers[t], False)}
        kept_m = oracle_m & found["driver_mutation"]
        per["driver_mutation"] = {"oracle": len(oracle_m), "matched": len(kept_m), "share": round(len(kept_m) / n, 4)}
        union |= kept_m
        rows.append({"id": pid, "per_trait": per, "union": len(union), "union_share": round(len(union) / n, 4)})
    unions = [r["union_share"] for r in rows]
    shares = [v["share"] for r in rows for v in r["per_trait"].values()]
    return {
        "n_trials": n,
        "mean_per_trait_share": round(sum(shares) / len(shares), 4),
        "union_mean": round(sum(unions) / len(unions), 4),
        "union_range": [round(min(unions), 4), round(max(unions), 4)],
        "projection_to_six_if_independent": round(project(sum(shares) / len(shares)), 4),
        "patients": rows,
    }


def main() -> None:
    subjects = load_subjects()
    yes_no = load_yes_no()
    markers = load_markers()
    patients = json.loads(PATIENTS.read_text(encoding="utf-8"))["patients"]
    queries = load_patient_queries()
    universe = sorted(set(yes_no) & set(markers))
    facts = ["prior_immunotherapy", "brain_metastases", "driver_mutation"]

    # trial -> all subjects (any fact)
    trial_subjects: dict[str, list[str]] = defaultdict(list)
    for row in subjects:
        trial_subjects[row["nct_id"]].append(row["subject"])

    truth: dict[str, set[str]] = {f: set() for f in facts}
    for nct in universe:
        for fact in facts:
            if has_rule(nct, fact, yes_no, markers):
                truth[fact].add(nct)

    all_terms = [row["subject"] for row in subjects]
    for pid in queries:
        for qs in queries[pid].values():
            all_terms.extend(qs)
    print(f"embedding {len(set(all_terms))} terms...", flush=True)
    vecs = embed_terms(all_terms)

    def find_all(method: str, threshold: float) -> dict[str, dict[str, set[str]]]:
        """patient -> fact -> retrieved trial ids."""
        out: dict[str, dict[str, set[str]]] = {}
        for p in patients:
            pid = p["id"]
            out[pid] = {f: set() for f in facts}
            for fact, qs in queries.get(pid, {}).items():
                for nct in universe:
                    if retrieved(qs, trial_subjects.get(nct, []), vecs, method, threshold):
                        out[pid][fact].add(nct)
        return out

    print("scoring word / embed / combined...", flush=True)
    found_word = find_all("word", EMBED_THRESHOLD)
    found_embed = find_all("embed", EMBED_THRESHOLD)
    found_comb = find_all("combined", EMBED_THRESHOLD)

    def mean_rates(found) -> dict:
        per_patient = []
        for p in patients:
            pid = p["id"]
            one = {f: set() for f in facts}
            for f in facts:
                one[f] = found[pid][f]
            per_patient.append(rates(one, truth, universe, facts))
        # average the per-fact recalls across patients
        summary = {"by_fact": {}, "mean_recall": None, "mean_wrongly_picked_up": None}
        recs, fprs = [], []
        for fact in facts:
            fact_recs = [r[fact]["recall"] for r in per_patient if r[fact]["recall"] is not None]
            fact_fprs = [r[fact]["wrongly_picked_up"] for r in per_patient if r[fact]["wrongly_picked_up"] is not None]
            summary["by_fact"][fact] = {
                "recall": round(sum(fact_recs) / len(fact_recs), 4) if fact_recs else None,
                "wrongly_picked_up": round(sum(fact_fprs) / len(fact_fprs), 4) if fact_fprs else None,
            }
            if fact_recs:
                recs.append(sum(fact_recs) / len(fact_recs))
            if fact_fprs:
                fprs.append(sum(fact_fprs) / len(fact_fprs))
        summary["mean_recall"] = round(sum(recs) / len(recs), 4) if recs else None
        summary["mean_wrongly_picked_up"] = round(sum(fprs) / len(fprs), 4) if fprs else None
        return summary

    word_rates = mean_rates(found_word)
    embed_rates = mean_rates(found_embed)
    comb_rates = mean_rates(found_comb)

    sweep = []
    for t in EMBED_SWEEP:
        found = find_all("embed", t)
        sweep.append({"threshold": t, "embed": mean_rates(found), "combined": mean_rates(find_all("combined", t))})

    print("gated ceiling...", flush=True)
    gated = gated_ceiling(patients, yes_no, markers, found_comb)

    report = {
        "embed_model": EMBED_MODEL,
        "embed_operating_threshold": EMBED_THRESHOLD,
        "n_subjects": len(subjects),
        "n_trials": len(universe),
        "n_patients": len(patients),
        "arms": {"word": word_rates, "embed": embed_rates, "combined": comb_rates},
        "sweep": sweep,
        "gates": {
            "recall_rethink_below": 0.60,
            "recall_not_bottleneck_above": 0.85,
            "wrongly_picked_up_max": 0.20,
            "combined_recall": comb_rates["mean_recall"],
            "combined_wrongly_picked_up": comb_rates["mean_wrongly_picked_up"],
            "recall_band": (
                "below_60" if (comb_rates["mean_recall"] or 0) < 0.60
                else "above_85" if comb_rates["mean_recall"] > 0.85
                else "60_to_85"
            ),
            "wrongly_picked_up_cleared": (comb_rates["mean_wrongly_picked_up"] or 1) <= 0.20,
        },
        "matching_gated_ceiling": gated,
        "perfect_oracle_union_mean": 0.399,
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    print(f"{'arm':<12}{'recall':>10}{'wrong':>10}")
    for name, stats in (("word", word_rates), ("embed", embed_rates), ("combined", comb_rates)):
        print(f"{name:<12}{stats['mean_recall']:>10.1%}{stats['mean_wrongly_picked_up']:>10.1%}")
        for fact, row in stats["by_fact"].items():
            print(f"  {fact:<22}{row['recall']:>8.1%}{row['wrongly_picked_up']:>10.1%}")
    print()
    print(f"matching-gated union mean : {gated['union_mean']:.1%}  "
          f"(range {gated['union_range'][0]:.1%} to {gated['union_range'][1]:.1%})")
    print(f"perfect-oracle union mean : 39.9%")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
