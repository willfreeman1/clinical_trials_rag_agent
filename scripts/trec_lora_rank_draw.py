"""Freeze full-shortlist pair IDs for the ranker comparison. No GPU.

Every shortlisted trial for the 50 2022 patients. Nothing discarded.
2023 is not used. The system does not say a patient qualifies.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_lora_common import RANK_CONFIG, RANK_PAIRS, RANK_PROBE_PAIRS  # noqa: E402
from trec_score_common import load_qrels, load_shortlist  # noqa: E402


def main() -> None:
    cfg = json.loads(RANK_CONFIG.read_text(encoding="utf-8"))
    short = load_shortlist()
    labels = load_qrels(2022)
    topics = short["years"]["2022"]["topics"]
    all_topics = {}
    n = 0
    for tid in cfg["patients"]:
        base = (topics.get(tid) or {}).get("shortlist") or []
        labs = labels.get(tid) or {}
        rows = [[nct, int(labs[nct]) if nct in labs else 9] for nct in base]
        all_topics[tid] = rows
        n += len(rows)
    payload = {
        "adapter_seed": cfg["adapter_seed"],
        "note": cfg["note"],
        "n": n,
        "n_patients": len(all_topics),
        "test_2022": {"topics": all_topics},
        "dev_2021": {"topics": {}},
    }
    RANK_PAIRS.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    probe_topics = {tid: all_topics[tid] for tid in cfg["probe_patients"]}
    probe = {
        "adapter_seed": cfg["adapter_seed"],
        "note": "Rate probe only. Two 2022 patients, full shortlist.",
        "n": sum(len(v) for v in probe_topics.values()),
        "n_patients": len(probe_topics),
        "test_2022": {"topics": probe_topics},
        "dev_2021": {"topics": {}},
    }
    RANK_PROBE_PAIRS.write_text(json.dumps(probe, indent=2), encoding="utf-8")
    print(f"wrote {RANK_PAIRS} n={n}", flush=True)
    print(f"wrote {RANK_PROBE_PAIRS} n={probe['n']}", flush=True)


if __name__ == "__main__":
    main()
