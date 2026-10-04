"""Freeze 2021 shortlist pair IDs for the cutoff-25 replication. No GPU.

All 75 2021 patients. Nothing discarded. Cutoff 25 is already fixed
in the committed config. 2023 is not used.
The system does not say a patient qualifies.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_lora_common import RANK_2021_CONFIG, RANK_2021_PAIRS, RANK_2021_PROBE_PAIRS  # noqa: E402
from trec_score_common import load_qrels, load_shortlist  # noqa: E402


def main() -> None:
    cfg = json.loads(RANK_2021_CONFIG.read_text(encoding="utf-8"))
    if int(cfg["cutoff"]) != 25:
        raise SystemExit("2021 config cutoff must be 25")
    short = load_shortlist()
    labels = load_qrels(2021)
    topics = short["years"]["2021"]["topics"]
    all_topics = {}
    n = 0
    for tid in cfg["patients"]:
        base = (topics.get(tid) or {}).get("shortlist") or []
        if not base:
            raise SystemExit(f"missing 2021 shortlist for topic {tid}")
        labs = labels.get(tid) or {}
        rows = [[nct, int(labs[nct]) if nct in labs else 9] for nct in base]
        all_topics[tid] = rows
        n += len(rows)
    if len(all_topics) != 75:
        raise SystemExit(f"expected 75 patients, got {len(all_topics)}")
    payload = {
        "adapter_seed": cfg["adapter_seed"],
        "cutoff": 25,
        "note": cfg["note"],
        "n": n,
        "n_patients": len(all_topics),
        "dev_2021": {"topics": all_topics},
        "test_2022": {"topics": {}},
    }
    RANK_2021_PAIRS.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    probe_topics = {tid: all_topics[tid] for tid in cfg["probe_patients"]}
    probe = {
        "adapter_seed": cfg["adapter_seed"],
        "cutoff": 25,
        "note": "Rate probe only. Two 2021 patients, full shortlist.",
        "n": sum(len(v) for v in probe_topics.values()),
        "n_patients": len(probe_topics),
        "dev_2021": {"topics": probe_topics},
        "test_2022": {"topics": {}},
    }
    RANK_2021_PROBE_PAIRS.write_text(json.dumps(probe, indent=2), encoding="utf-8")
    print(f"wrote {RANK_2021_PAIRS} n={n}", flush=True)
    print(f"wrote {RANK_2021_PROBE_PAIRS} n={probe['n']}", flush=True)


if __name__ == "__main__":
    main()
