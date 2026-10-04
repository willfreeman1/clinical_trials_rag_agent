"""Freeze 2022 patient and top-25 trial IDs before any reader score exists.

No GPU. Topical slice continuous, cutoff 25. 2023 is not used.
The system does not say a patient qualifies.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))

from reader.split_rules import split_rules  # noqa: E402
from trec_reader_common import CONFIG, CUTOFF, PAIRS, PROBE_PAIRS  # noqa: E402
from trec_score_common import PACK, QWEN_SCORES, load_qrels, load_shortlist  # noqa: E402
from trec_score_eval import order_by, qwen_maps  # noqa: E402


def main() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    if int(cfg["cutoff"]) != CUTOFF:
        raise SystemExit("cutoff must be 25")
    if int(cfg["year"]) != 2022:
        raise SystemExit("year must be 2022")
    short = load_shortlist()
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    qwen = json.loads(QWEN_SCORES.read_text(encoding="utf-8"))
    topical = (qwen_maps(qwen, "topical_title_cond_slice").get("2022") or {})
    labels = load_qrels(2022)
    docs = pack["docs"]
    topics = short["years"]["2022"]["topics"]

    all_topics: dict[str, list] = {}
    n_rules = []
    for tid in cfg["patients"]:
        base = (topics.get(tid) or {}).get("shortlist") or []
        if not base:
            raise SystemExit(f"missing 2022 shortlist for topic {tid}")
        scores = topical.get(str(tid)) or {}
        ordered = order_by(
            base,
            lambda nct, s=scores: float(s[nct][1]) if nct in s else -1.0,
        )[:CUTOFF]
        if len(ordered) != CUTOFF:
            raise SystemExit(f"topic {tid} has {len(ordered)} trials, want {CUTOFF}")
        labs = labels.get(tid) or {}
        rows = []
        for nct in ordered:
            elig = (docs.get(nct) or {}).get("eligibility") or ""
            rules = split_rules(elig)
            n_rules.append(len(rules))
            rows.append(
                {
                    "nct_id": nct,
                    "label": int(labs[nct]) if nct in labs else 9,
                    "n_rules": len(rules),
                }
            )
        all_topics[tid] = rows

    if len(all_topics) != 50:
        raise SystemExit(f"expected 50 patients, got {len(all_topics)}")
    n_pairs = sum(len(v) for v in all_topics.values())
    n_rule_total = sum(n_rules)
    payload = {
        "year": 2022,
        "cutoff": CUTOFF,
        "ordering": cfg["ordering"],
        "note": cfg["note"],
        "n_patients": 50,
        "n_pairs": n_pairs,
        "n_rules": n_rule_total,
        "rules_mean": round(n_rule_total / max(n_pairs, 1), 2),
        "topics": all_topics,
    }
    PAIRS.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    probe_topics = {tid: all_topics[tid] for tid in cfg["probe_patients"]}
    probe = {
        "year": 2022,
        "cutoff": CUTOFF,
        "note": "Rate probe only. Two 2022 patients, top 25 each.",
        "n_patients": len(probe_topics),
        "n_pairs": sum(len(v) for v in probe_topics.values()),
        "n_rules": sum(r["n_rules"] for rows in probe_topics.values() for r in rows),
        "topics": probe_topics,
    }
    PROBE_PAIRS.write_text(json.dumps(probe, indent=2), encoding="utf-8")
    print(
        f"wrote {PAIRS.name} pairs={n_pairs} rules={n_rule_total} "
        f"mean_rules={payload['rules_mean']}",
        flush=True,
    )
    print(
        f"wrote {PROBE_PAIRS.name} pairs={probe['n_pairs']} rules={probe['n_rules']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
