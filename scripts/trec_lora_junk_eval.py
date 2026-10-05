"""2-vs-0 and relevant-vs-0 on the frozen junk sample. Adapter vs topical slice."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_lora_common import (  # noqa: E402
    ADAPTER_SCORES,
    EVAL_PAIRS_PATH,
    JUNK_PAIRS_PATH,
    JUNK_SCORES,
    auroc,
    pct,
)
from trec_lora_eval import load, score_of  # noqa: E402
from trec_score_common import QWEN_SCORES  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "data" / "trec" / "trec_lora_junk_results.json"


def collect(score_maps: list[dict], year: str, topics: dict, want: set[int]) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {str(w): [] for w in want}
    for tid, rows in topics.items():
        buckets = [(m.get(year) or {}).get(tid) or {} for m in score_maps]
        for nct, lab in rows:
            if int(lab) not in want:
                continue
            rec = None
            for b in buckets:
                if nct in b:
                    rec = b[nct]
                    break
            sc = score_of(rec) if rec is not None else None
            if sc is not None:
                out[str(int(lab))].append(sc)
    return out


def slice_map() -> dict:
    qwen = load(QWEN_SCORES)
    return ((qwen.get("arms") or {}).get("topical_title_cond_slice") or {})


def pack(pos: list[float], neg: list[float]) -> dict:
    return {"n_pos": len(pos), "n_neg": len(neg), "auroc": auroc(pos, neg)}


def main() -> None:
    junk = load(JUNK_PAIRS_PATH)
    topics = junk["test_2022"]["topics"]
    ada_hard = (load(ADAPTER_SCORES).get("scores") or {})
    ada_junk = (load(JUNK_SCORES).get("scores") or {}) if JUNK_SCORES.exists() else {}
    sl = slice_map()
    hard = load(EVAL_PAIRS_PATH)["test_2022"]["topics"]
    ada = collect([ada_hard, ada_junk], "2022", hard, {1, 2})
    ada0 = collect([ada_junk], "2022", topics, {0, 9})
    sl_hard = collect([sl], "2022", hard, {1, 2})
    sl0 = collect([sl], "2022", topics, {0, 9})
    report = {
        "note": (
            "Judged-0 sample is from the shortlist pool behind the 0.85 "
            "logistic 2-vs-0 (all judged 0 on the 2022 shortlist). "
            "Unjudged (label 9) is a convention, not a human verdict."
        ),
        "adapter": {
            "2_vs_judged0": pack(ada["2"], ada0["0"]),
            "1_vs_judged0": pack(ada["1"], ada0["0"]),
            "relevant_vs_judged0": pack(ada["2"] + ada["1"], ada0["0"]),
            "2_vs_unjudged": pack(ada["2"], ada0["9"]),
            "relevant_vs_unjudged": pack(ada["2"] + ada["1"], ada0["9"]),
        },
        "topical_slice": {
            "2_vs_judged0": pack(sl_hard["2"], sl0["0"]),
            "1_vs_judged0": pack(sl_hard["1"], sl0["0"]),
            "relevant_vs_judged0": pack(sl_hard["2"] + sl_hard["1"], sl0["0"]),
            "2_vs_unjudged": pack(sl_hard["2"], sl0["9"]),
            "relevant_vs_unjudged": pack(sl_hard["2"] + sl_hard["1"], sl0["9"]),
        },
        "full_shortlist_reference": {
            "note": "All judged 0 on the 2022 shortlist, not the sample.",
            "logistic_2_vs_0": 0.846,
            "topical_slice_2_vs_0": 0.883,
        },
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Adapter vs topical slice on the same sampled junk", flush=True)
    for name in ("2_vs_judged0", "relevant_vs_judged0", "2_vs_unjudged"):
        a = report["adapter"][name]
        s = report["topical_slice"][name]
        print(
            f"  {name}: adapter {pct(a['auroc'])} (n0={a['n_neg']})  "
            f"slice {pct(s['auroc'])} (n0={s['n_neg']})",
            flush=True,
        )
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
