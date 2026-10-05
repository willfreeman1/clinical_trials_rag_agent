"""Step 1: logistic regression on stored scores. No GPU. No new model scores.

Fits on 2021 train patients. Dev is the 15 held-out 2021 sample patients.
Test is all 50 2022 patients. Eligibility v1 is not a feature: those scores
exist only on the 30-patient sample.

The system does not say a patient qualifies.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from trec_lora_common import (  # noqa: E402
    FEATURE_NAMES,
    LOGIT_RESULTS,
    load_splits,
    pct,
    split_auroc,
)
from trec_score_common import (  # noqa: E402
    CE_SCORES,
    MINI_SCORES,
    QWEN_SCORES,
    load_qrels,
    load_shortlist,
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def qwen_arm(raw: dict, arm: str) -> dict[str, dict[str, dict[str, tuple[int, float]]]]:
    block = (raw.get("arms") or {}).get(arm) or {}
    out: dict[str, dict[str, dict[str, tuple[int, float]]]] = {}
    for year, topics in block.items():
        yout = out.setdefault(str(year), {})
        for tid, scores in topics.items():
            dest = {}
            for nct, rec in scores.items():
                if isinstance(rec, list) and len(rec) >= 2:
                    dest[nct] = (int(rec[0]), float(rec[1]))
            yout[str(tid)] = dest
    return out


def mini_map(raw: dict) -> dict[str, dict[str, dict[str, float]]]:
    scores = raw.get("scores") or {}
    return {
        y: {str(t): {n: float(v) for n, v in bucket.items()} for t, bucket in year.items()}
        for y, year in scores.items()
    }


def ce_map(raw: dict, query: str) -> dict[str, dict[str, dict[str, float]]]:
    block = ((raw.get("truncate") or {}).get("medcpt_ce") or {}).get(query) or {}
    return {
        y: {str(t): {n: float(v) for n, v in bucket.items()} for t, bucket in year.items()}
        for y, year in block.items()
    }


def build_rows(
    year: int,
    tids: list[str],
    short: dict,
    labels_all: dict[str, dict[str, int]],
    title_cond: dict,
    slice_arm: dict,
    elig: dict,
    mini: dict,
    ce_raw: dict,
    ce_kw: dict,
) -> list[dict]:
    y = str(year)
    topics = short["years"][y]["topics"]
    rows = []
    for tid in tids:
        base = (topics.get(tid) or {}).get("shortlist") or []
        labs = labels_all.get(tid) or {}
        n = max(len(base) - 1, 1)
        tc = (title_cond.get(y) or {}).get(tid) or {}
        sl = (slice_arm.get(y) or {}).get(tid) or {}
        el = (elig.get(y) or {}).get(tid) or {}
        mi = (mini.get(y) or {}).get(tid) or {}
        cr = (ce_raw.get(y) or {}).get(tid) or {}
        ck = (ce_kw.get(y) or {}).get(tid) or {}
        for rank, nct in enumerate(base):
            lab = labs.get(nct)
            if lab not in (0, 1, 2):
                continue
            if nct not in tc or nct not in sl or nct not in mi or nct not in cr or nct not in ck:
                continue
            row = {
                "year": year,
                "tid": tid,
                "nct": nct,
                "label": lab,
                "topical_title_cond_digit": float(tc[nct][0]),
                "topical_title_cond_cont": float(tc[nct][1]),
                "topical_slice_digit": float(sl[nct][0]),
                "topical_slice_cont": float(sl[nct][1]),
                "mini": float(mi[nct]),
                "medcpt_ce_raw": float(cr[nct]),
                "medcpt_ce_keywords": float(ck[nct]),
                "rank_frac": rank / n,
                "rank_score": 1.0 - (rank / n),
            }
            if nct in el:
                row["elig_v1_digit"] = float(el[nct][0])
                row["elig_v1_cont"] = float(el[nct][1])
            rows.append(row)
    return rows


def hard(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["label"] in (1, 2)]


def matrix(rows: list[dict]) -> list[list[float]]:
    return [[r[name] for name in FEATURE_NAMES] for r in rows]


def balanced_acc(rows: list[dict], key: str, thresh: float) -> float | None:
    t1 = t2 = n1 = n2 = 0
    for r in rows:
        if r["label"] not in (1, 2) or r.get(key) is None:
            continue
        pred2 = r[key] >= thresh
        if r["label"] == 1:
            n1 += 1
            if not pred2:
                t1 += 1
        else:
            n2 += 1
            if pred2:
                t2 += 1
    if not n1 or not n2:
        return None
    return 0.5 * (t1 / n1 + t2 / n2)


def auroc_vs0(rows: list[dict], key: str, pos_label: int) -> dict:
    pos = [r[key] for r in rows if r["label"] == pos_label and r.get(key) is not None]
    neg = [r[key] for r in rows if r["label"] == 0 and r.get(key) is not None]
    from trec_lora_common import auroc

    return {"n_pos": len(pos), "n0": len(neg), "pooled": auroc(pos, neg)}


def describe(name: str, rows: list[dict], keys: list[str]) -> dict:
    out: dict = {"n_rows": len(rows)}
    for key in keys:
        have = [r for r in rows if r.get(key) is not None]
        if not have:
            continue
        rec = split_auroc(have, key)
        if key == "logit_p2":
            rec["balanced_acc_0.5"] = balanced_acc(have, key, 0.5)
            rec["vs0_label2"] = auroc_vs0(rows, key, 2)
            rec["vs0_label1"] = auroc_vs0(rows, key, 1)
        out[key] = rec
    return out


def main() -> None:
    splits = load_splits()
    short = load_shortlist()
    qwen = load_json(QWEN_SCORES)
    title_cond = qwen_arm(qwen, "topical_title_cond")
    slice_arm = qwen_arm(qwen, "topical_title_cond_slice")
    elig = qwen_arm(qwen, "elig_full")
    mini = mini_map(load_json(MINI_SCORES))
    ce_raw_file = load_json(CE_SCORES)
    ce_raw = ce_map(ce_raw_file, "raw")
    ce_kw = ce_map(ce_raw_file, "keywords")
    qrels = {2021: load_qrels(2021), 2022: load_qrels(2022)}

    buckets = {
        "train": build_rows(2021, splits["train_2021"], short, qrels[2021], title_cond, slice_arm, elig, mini, ce_raw, ce_kw),
        "dev": build_rows(2021, splits["dev_2021"], short, qrels[2021], title_cond, slice_arm, elig, mini, ce_raw, ce_kw),
        "test": build_rows(2022, splits["test_2022"], short, qrels[2022], title_cond, slice_arm, elig, mini, ce_raw, ce_kw),
        "test_sample": build_rows(2022, splits["eval_sample_2022"], short, qrels[2022], title_cond, slice_arm, elig, mini, ce_raw, ce_kw),
    }

    train_hard = hard(buckets["train"])
    scaler = StandardScaler()
    x_train = scaler.fit_transform(matrix(train_hard))
    y_train = [1 if r["label"] == 2 else 0 for r in train_hard]
    clf = LogisticRegression(max_iter=1000)
    clf.fit(x_train, y_train)

    for rows in buckets.values():
        if not rows:
            continue
        probs = clf.predict_proba(scaler.transform(matrix(rows)))[:, 1]
        for r, p in zip(rows, probs):
            r["logit_p2"] = float(p)

    feature_keys = list(FEATURE_NAMES) + ["rank_score", "elig_v1_cont", "logit_p2"]
    report = {
        "features": list(FEATURE_NAMES),
        "note": (
            "Logistic is trained on 2021 train patients, judged 1 vs 2 only, "
            "using signals that exist for every patient. Eligibility v1 is "
            "reported as a single feature where it exists (the 15+15 sample). "
            "It is not in the logistic."
        ),
        "n_train_hard": len(train_hard),
        "coef": {name: float(w) for name, w in zip(FEATURE_NAMES, clf.coef_[0])},
        "intercept": float(clf.intercept_[0]),
        "splits": {},
    }
    for name, rows in buckets.items():
        report["splits"][name] = describe(name, rows, feature_keys)

    LOGIT_RESULTS.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "Logistic baseline on stored scores. No GPU.",
        f"Train hard pairs: {len(train_hard)}",
        "Weights after scaling (positive => more joinable):",
    ]
    for name, w in sorted(report["coef"].items(), key=lambda kv: -abs(kv[1])):
        lines.append(f"  {name:28s} {w:+.3f}")
    lines.append("")
    header = f"{'split':<12} {'n1':>6} {'n2':>6} {'logit':>8} {'slice':>8} {'title':>8} {'mini':>8} {'ce_kw':>8} {'rank':>8} {'elig':>8}"
    lines.append(header)
    for name in ("train", "dev", "test", "test_sample"):
        block = report["splits"][name]
        logit = block.get("logit_p2") or {}
        sl = block.get("topical_slice_cont") or {}
        tc = block.get("topical_title_cond_cont") or {}
        mi = block.get("mini") or {}
        ce = block.get("medcpt_ce_keywords") or {}
        rk = block.get("rank_score") or {}
        el = block.get("elig_v1_cont") or {}
        n1 = logit.get("n1") or sl.get("n1")
        n2 = logit.get("n2") or sl.get("n2")
        lines.append(
            f"{name:<12} {n1:6d} {n2:6d} "
            f"{pct(logit.get('pooled')):>8} {pct(sl.get('pooled')):>8} "
            f"{pct(tc.get('pooled')):>8} {pct(mi.get('pooled')):>8} "
            f"{pct(ce.get('pooled')):>8} {pct(rk.get('pooled')):>8} "
            f"{pct(el.get('pooled')):>8}"
        )
    lines.append("")
    lines.append("Macro (mean of per-patient AUROC) and 0-below check:")
    for name in ("train", "dev", "test", "test_sample"):
        lg = report["splits"][name]["logit_p2"]
        sl = report["splits"][name]["topical_slice_cont"]
        v0 = lg.get("vs0_label2") or {}
        lines.append(
            f"  {name}: logit macro {pct(lg.get('macro'))}  "
            f"slice macro {pct(sl.get('macro'))}  "
            f"bal-acc {pct(lg.get('balanced_acc_0.5'))}  "
            f"2-vs-0 {pct(v0.get('pooled'))}"
        )
    text = "\n".join(lines)
    print(text, flush=True)
    print(f"wrote {LOGIT_RESULTS}", flush=True)


if __name__ == "__main__":
    main()
