"""Copy the frozen 2022 1-versus-2 pairs. Do not draw a new sample."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_gpt_vs_adapter_common import CONFIG, EVAL_PAIRS, PAIRS  # noqa: E402


def main() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    src = json.loads(EVAL_PAIRS.read_text(encoding="utf-8"))
    topics = src["test_2022"]["topics"]
    n1 = n2 = 0
    for bucket in topics.values():
        for _nct, lab in bucket:
            if lab == 1:
                n1 += 1
            elif lab == 2:
                n2 += 1
            else:
                raise SystemExit(f"non 1/2 label {lab}")
    total = n1 + n2
    if total != cfg["n_pairs_expected"] or n1 != cfg["n1_expected"] or n2 != cfg["n2_expected"]:
        raise SystemExit(f"count drift: n1={n1} n2={n2} total={total}")
    rec = {
        "copied_from": "scripts/trec_lora_eval_pairs.json test_2022",
        "pair_seed_of_source": src.get("pair_seed"),
        "sample_seed_of_source": src.get("sample_seed"),
        "year": 2022,
        "n_patients": len(topics),
        "n1": n1,
        "n2": n2,
        "n_pairs": total,
        "note": (
            "Copied, not redrawn. Same pairs as the 0.779 adapter mean. "
            "The system does not say a patient qualifies."
        ),
        "topics": topics,
    }
    PAIRS.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    print(f"wrote {PAIRS} patients {len(topics)} n1 {n1} n2 {n2}", flush=True)


if __name__ == "__main__":
    main()
