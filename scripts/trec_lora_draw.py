"""Draw eval pair IDs and train comparisons. Run once before any adapter.

No API calls. 2023 is not used.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_lora_common import (  # noqa: E402
    CONFIG_PATH,
    EVAL_PAIRS_PATH,
    TRAIN_PAIRS_PATH,
    load_splits,
)
from trec_score_common import load_qrels, load_shortlist  # noqa: E402


def take_pairs(wins: list[str], loses: list[str], k: int, rng: random.Random) -> list[tuple[str, str]]:
    if not wins or not loses or k <= 0:
        return []
    n_cart = len(wins) * len(loses)
    if n_cart <= max(k * 4, 2000):
        cart = [(w, l) for w in wins for l in loses]
        rng.shuffle(cart)
        return cart[:k]
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    tries = 0
    while len(out) < k and tries < k * 30:
        pair = (rng.choice(wins), rng.choice(loses))
        if pair not in seen:
            seen.add(pair)
            out.append(pair)
        tries += 1
    return out


def eval_bucket(year: int, tids: list[str], short: dict, labels: dict) -> dict:
    y = str(year)
    topics = {}
    n1 = n2 = 0
    for tid in tids:
        base = (short["years"][y]["topics"].get(tid) or {}).get("shortlist") or []
        labs = labels.get(tid) or {}
        rows = []
        for nct in base:
            lab = labs.get(nct)
            if lab in (1, 2):
                rows.append([nct, lab])
                if lab == 1:
                    n1 += 1
                else:
                    n2 += 1
        topics[tid] = rows
    return {"topics": topics, "n1": n1, "n2": n2, "n": n1 + n2}


def main() -> None:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    splits = load_splits()
    short = load_shortlist()
    qrels = {2021: load_qrels(2021), 2022: load_qrels(2022)}
    rng = random.Random(int(cfg["pair_seed"]))
    per = int(cfg["comparisons_per_patient"])
    mix = cfg["mix"]
    n21 = int(round(per * float(mix["2v1"])))
    n20 = int(round(per * float(mix["2v0"])))
    n10 = per - n21 - n20

    dev = eval_bucket(2021, splits["dev_2021"], short, qrels[2021])
    test = eval_bucket(2022, splits["test_2022"], short, qrels[2022])
    eval_payload = {
        "pair_seed": cfg["pair_seed"],
        "sample_seed": cfg["sample_seed"],
        "note": "Judged 1 and 2 only, on the shortlist. Dev is the 15 held-out 2021 patients. Test is all 50 2022 patients.",
        "dev_2021": dev,
        "test_2022": test,
    }
    EVAL_PAIRS_PATH.write_text(json.dumps(eval_payload, indent=2), encoding="utf-8")

    labels = qrels[2021]
    ytopics = short["years"]["2021"]["topics"]
    train_topics = {}
    mix_counts = {"2v1": 0, "2v0": 0, "1v0": 0}
    for tid in splits["train_2021"]:
        base = (ytopics.get(tid) or {}).get("shortlist") or []
        labs = labels.get(tid) or {}
        by = {0: [], 1: [], 2: []}
        for nct in base:
            lab = labs.get(nct)
            if lab in by:
                by[lab].append(nct)
        rows = []
        for kind, k, hi, lo in (
            ("2v1", n21, 2, 1),
            ("2v0", n20, 2, 0),
            ("1v0", n10, 1, 0),
        ):
            for win, lose in take_pairs(by[hi], by[lo], k, rng):
                rows.append({"win": win, "win_lab": hi, "lose": lose, "lose_lab": lo, "kind": kind})
                mix_counts[kind] += 1
        rng.shuffle(rows)
        train_topics[tid] = rows
    n_comp = sum(len(v) for v in train_topics.values())
    train_payload = {
        "pair_seed": cfg["pair_seed"],
        "comparisons_per_patient": per,
        "mix_requested": mix,
        "mix_drawn": mix_counts,
        "n_comparisons": n_comp,
        "n_patients": len(train_topics),
        "topics": train_topics,
    }
    TRAIN_PAIRS_PATH.write_text(json.dumps(train_payload, indent=2), encoding="utf-8")
    print(
        f"eval dev n={dev['n']} (1={dev['n1']} 2={dev['n2']}) "
        f"test n={test['n']} (1={test['n1']} 2={test['n2']})",
        flush=True,
    )
    print(f"train comparisons {n_comp} mix {mix_counts}", flush=True)
    print(f"wrote {EVAL_PAIRS_PATH} {TRAIN_PAIRS_PATH}", flush=True)


if __name__ == "__main__":
    main()
