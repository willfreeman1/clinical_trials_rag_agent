"""Spike 2, Step 1 analysis: how concentrated are the facts trials gate on?

Reads data/step1_concepts.jsonl, normalises the concept strings three ways as
THRESHOLDS.md specifies, and writes the concentration curves to
data/step1_concentration.json. Embeds the distinct concept strings once and
caches them.

Run after step1_concepts.py.
"""

from __future__ import annotations

import json
import re
import urllib.request
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FACTS_PATH = ROOT / "data" / "step1_concepts.jsonl"
VEC_PATH = ROOT / "data" / "step1_concept_vecs.npz"
OUT_PATH = ROOT / "data" / "step1_concentration.json"

EMBED_MODEL = "text-embedding-3-small"
CUTS = (10, 20, 40, 80, 160, 320, 640)
MERGE_THRESHOLDS = (0.90, 0.85, 0.80, 0.75)
DECISION_CUT = 40

# Categories a patient description would plausibly raise, as opposed to
# boilerplate every trial carries (consent, pregnancy testing, demographics).
DISCRIMINATING = {
    "disease_or_stage",
    "histology_or_subtype",
    "biomarker_or_mutation",
    "prior_systemic_therapy",
    "prior_local_therapy",
    "performance_status",
    "organ_function_lab",
    "comorbidity_or_history",
    "metastasis_site",
}


def load_key() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENAI_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("OPENAI_API_KEY is missing")


def normalise(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[\"'.,;:()]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def load_facts() -> list[tuple[str, str, str]]:
    triples = []
    with FACTS_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if not row.get("answer"):
                continue
            for fact in row["answer"].get("facts") or []:
                concept = normalise(fact.get("concept", ""))
                if concept:
                    triples.append((row["nct_id"], fact.get("category", ""), concept))
    return triples


def embed_terms(terms: list[str]) -> np.ndarray:
    """Cached: the concept vocabulary changes only if the extraction is rerun."""
    if VEC_PATH.exists():
        cached = np.load(VEC_PATH, allow_pickle=True)
        if list(cached["terms"]) == terms:
            return cached["vectors"]
    api_key = load_key()
    vectors: list[list[float]] = []
    for start in range(0, len(terms), 512):
        batch = terms[start : start + 512]
        request = urllib.request.Request(
            "https://api.openai.com/v1/embeddings",
            data=json.dumps({"model": EMBED_MODEL, "input": batch}).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            body = json.loads(response.read().decode("utf-8"))
        vectors.extend(item["embedding"] for item in body["data"])
    matrix = np.asarray(vectors, dtype=np.float32)
    matrix /= np.clip(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-8, None)
    np.savez(VEC_PATH, vectors=matrix, terms=np.array(terms, dtype=object))
    return matrix


def merge(counts: Counter, vectors: np.ndarray, index: dict[str, int], threshold: float) -> dict[str, str]:
    """Greedy, frequency-ordered clustering.

    Each concept joins the first existing cluster whose representative is within
    the threshold, else becomes a representative itself. Frequency ordering means
    the commonest phrasing becomes the representative, and the result is
    deterministic.
    """
    assignment: dict[str, str] = {}
    reps: list[str] = []
    rep_vectors: list[np.ndarray] = []
    for term, _ in counts.most_common():
        vector = vectors[index[term]]
        if reps:
            sims = np.asarray(rep_vectors) @ vector
            best = int(np.argmax(sims))
            if sims[best] >= threshold:
                assignment[term] = reps[best]
                continue
        assignment[term] = term
        reps.append(term)
        rep_vectors.append(vector)
    return assignment


def curve(pairs: list[tuple[str, str]], assignment: dict[str, str]) -> dict:
    clusters = Counter(assignment[c] for _, c in pairs)
    total = len(pairs)
    per_trial: dict[str, set[str]] = {}
    for nct, concept in pairs:
        per_trial.setdefault(nct, set()).add(assignment[concept])
    top = {t for t, _ in clusters.most_common(DECISION_CUT)}
    return {
        "n_facts": total,
        "n_clusters": len(clusters),
        "coverage": {str(n): round(sum(v for _, v in clusters.most_common(n)) / total, 4) for n in CUTS},
        "trials_fully_inside_top40": sum(1 for s in per_trial.values() if s <= top),
        "n_trials": len(per_trial),
        "mean_share_of_trial_inside_top40": round(
            float(np.mean([len(s & top) / len(s) for s in per_trial.values()])), 4
        ),
        "mean_facts_per_trial": round(total / len(per_trial), 2),
        "top40": [{"concept": t, "count": v} for t, v in clusters.most_common(DECISION_CUT)],
    }


def main() -> None:
    triples = load_facts()
    all_pairs = [(nct, concept) for nct, _, concept in triples]
    disc_pairs = [(nct, concept) for nct, cat, concept in triples if cat in DISCRIMINATING]

    counts = Counter(c for _, c in all_pairs)
    terms = [t for t, _ in counts.most_common()]
    vectors = embed_terms(terms)
    index = {t: i for i, t in enumerate(terms)}

    report: dict = {
        "decision_cut": DECISION_CUT,
        "embed_model": EMBED_MODEL,
        "n_trials": len({n for n, _ in all_pairs}),
        "variants": {},
    }
    identity = {t: t for t in terms}
    report["variants"]["exact_merge"] = curve(all_pairs, identity)
    for threshold in MERGE_THRESHOLDS:
        assignment = merge(counts, vectors, index, threshold)
        report["variants"][f"cosine_{threshold}"] = curve(all_pairs, assignment)

    disc_counts = Counter(c for _, c in disc_pairs)
    disc_assignment = merge(disc_counts, vectors, index, 0.85)
    report["discriminating_only_cosine_0.85"] = curve(disc_pairs, disc_assignment)

    OUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"{'variant':<22}{'clusters':>9}  " + "  ".join(f"top{n}" for n in (10, 20, 40, 80, 160)))
    for name, data in report["variants"].items():
        row = f"{name:<22}{data['n_clusters']:>9}  "
        row += " ".join(f"{data['coverage'][str(n)]:6.1%}" for n in (10, 20, 40, 80, 160))
        print(row)
    d = report["discriminating_only_cosine_0.85"]
    print(f"\ndiscriminating only, cosine 0.85: top40 = {d['coverage']['40']:.1%}, "
          f"{d['n_facts']} facts, {d['mean_facts_per_trial']} per trial")
    print(f"trials fully inside top 40: {d['trials_fully_inside_top40']}/{d['n_trials']}")
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()
