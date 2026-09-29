"""Regenerate the wording groups Step 1's cosine merge produced.

Step 1's concentration file only saved {concept, count} for the top 40.
The groups of different wordings that were merged together were never written
out. Step 3 needs them.

Uses the cached vectors in data/step1_concept_vecs.npz, so this makes no API
call if the cache is intact. No cost.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from step1_analyze import (  # noqa: E402
    load_facts,
    merge,
    embed_terms,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "step3_wording_groups.json"
THRESHOLD = 0.85


def main() -> None:
    triples = load_facts()
    counts = Counter(concept for _, _, concept in triples)
    terms = [t for t, _ in counts.most_common()]
    vectors = embed_terms(terms)
    index = {t: i for i, t in enumerate(terms)}
    assignment = merge(counts, vectors, index, THRESHOLD)

    groups: dict[str, list[str]] = defaultdict(list)
    for term, _ in counts.most_common():
        groups[assignment[term]].append(term)

    multi = []
    bone_brain = None
    for rep, members in groups.items():
        if len(members) < 2:
            continue
        packed = {
            "rep": rep,
            "size": len(members),
            "count_sum": sum(counts[m] for m in members),
            "members": [{"term": m, "count": counts[m]} for m in members],
        }
        multi.append(packed)
        names = {rep, *members}
        if "brain metastases" in names and "bone metastases" in names:
            bone_brain = packed

    multi.sort(key=lambda g: (-g["count_sum"], -g["size"], g["rep"]))

    report = {
        "threshold": THRESHOLD,
        "embed_model": "text-embedding-3-small",
        "n_terms": len(terms),
        "n_clusters": len(groups),
        "n_multi_member_clusters": len(multi),
        "n_singletons": len(groups) - len(multi),
        "bone_and_brain_metastases_merged": bone_brain is not None,
        "bone_brain_cluster": bone_brain,
        "clusters": multi,
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{len(terms)} terms -> {len(groups)} clusters, "
          f"{len(multi)} with more than one wording")
    print(f"bone metastases merged into brain metastases: "
          f"{report['bone_and_brain_metastases_merged']}")
    if bone_brain:
        print("  members:", ", ".join(m["term"] for m in bone_brain["members"]))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
