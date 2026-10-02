"""UMLS coverage of Step 1 short phrases. Gates committed 107c1e2 before lookups.

No Metathesaurus. No TREC. No new extraction. Marker matching not replaced.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from step1_analyze import load_facts, normalise  # noqa: E402
from umls_rest import load_cache, load_umls_key, save_cache, search_hit  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "step13_umls_coverage.json"
REPORT = ROOT / "docs" / "step13_umls_coverage.md"
DISAGREE = ROOT / "docs" / "step13_umls_disagreements.md"
WORKERS = 5
MARKER_CAT = "biomarker_or_mutation"


def tokens(text: str) -> list[str]:
    return [t for t in re.sub(r"[^a-z0-9+]+", " ", (text or "").lower()).split() if t]


def names_agree(phrase: str, canonical: str | None) -> bool:
    if not canonical:
        return False
    a, b = tokens(phrase), tokens(canonical)
    if not a or not b:
        return False
    if a == b:
        return True
    sa, sb = " ".join(a), " ".join(b)
    if sa in sb or sb in sa:
        return True
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return all(t in longer for t in shorter)


def main() -> None:
    triples = load_facts()
    occ = Counter(c for _, _, c in triples)
    cat_occ: dict[str, Counter] = defaultdict(Counter)
    for _nct, cat, concept in triples:
        cat_occ[cat][concept] += 1
    phrases = sorted(occ)
    print(f"distinct={len(phrases)} occurrences={len(triples)}", flush=True)

    api_key = load_umls_key()
    cache = load_cache()
    lock = Lock()
    hits: dict[str, dict] = {}

    def one(phrase: str) -> tuple[str, dict]:
        return phrase, search_hit(api_key, phrase, cache)

    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = [pool.submit(one, p) for p in phrases]
        for fut in as_completed(futs):
            phrase, hit = fut.result()
            hits[phrase] = hit
            done += 1
            if done % 50 == 0:
                with lock:
                    save_cache(cache)
                print(f"lookup {done}/{len(phrases)}", flush=True)
    save_cache(cache)

    resolved = {p for p, h in hits.items() if h.get("cui")}
    n_dist = len(phrases)
    n_dist_hit = len(resolved)
    n_occ = sum(occ.values())
    n_occ_hit = sum(occ[p] for p in resolved)
    dist_cov = n_dist_hit / n_dist if n_dist else None
    occ_cov = n_occ_hit / n_occ if n_occ else None

    by_cat = {}
    for cat in sorted(cat_occ):
        c_occ = cat_occ[cat]
        c_dist = set(c_occ)
        c_hit = c_dist & resolved
        by_cat[cat] = {
            "n_distinct": len(c_dist),
            "n_distinct_resolved": len(c_hit),
            "distinct_coverage": round(len(c_hit) / len(c_dist), 4) if c_dist else None,
            "n_occurrences": sum(c_occ.values()),
            "n_occurrences_resolved": sum(c_occ[p] for p in c_hit),
            "occurrence_coverage": round(
                sum(c_occ[p] for p in c_hit) / sum(c_occ.values()), 4
            )
            if c_occ
            else None,
        }

    checked = []
    agree_n = 0
    for p in sorted(resolved):
        name = hits[p].get("name")
        ok = names_agree(p, name)
        if ok:
            agree_n += 1
        checked.append(
            {
                "phrase": p,
                "cui": hits[p].get("cui"),
                "canonical": name,
                "agree": ok,
                "n": occ[p],
                "category": Counter({cat: cat_occ[cat][p] for cat in cat_occ if p in cat_occ[cat]}).most_common(1)[0][0]
                if any(p in cat_occ[c] for c in cat_occ)
                else "",
            }
        )
    n_checked = len(checked)
    precision = agree_n / n_checked if n_checked else None
    disagreements = [r for r in checked if not r["agree"]]
    disagreements.sort(key=lambda r: -r["n"])

    occ_non_bio = sum(v for cat, c in cat_occ.items() if cat != MARKER_CAT for v in c.values())
    occ_non_bio_hit = sum(
        c[p] for cat, c in cat_occ.items() if cat != MARKER_CAT for p in c if p in resolved
    )

    below_60 = occ_cov is not None and occ_cov < 0.60
    partial = occ_cov is not None and 0.60 <= occ_cov < 0.85
    prec_fail = precision is not None and precision < 0.90

    report = {
        "thresholds_commit": "107c1e2",
        "n_distinct": n_dist,
        "n_occurrences": n_occ,
        "n_once": sum(1 for p in phrases if occ[p] == 1),
        "distinct_coverage": round(dist_cov, 4) if dist_cov is not None else None,
        "occurrence_coverage": round(occ_cov, 4) if occ_cov is not None else None,
        "occurrence_coverage_excluding_biomarker": round(occ_non_bio_hit / occ_non_bio, 4)
        if occ_non_bio
        else None,
        "resolution_precision": round(precision, 4) if precision is not None else None,
        "n_resolved": n_dist_hit,
        "n_agree": agree_n,
        "n_disagree": len(disagreements),
        "by_category": by_cat,
        "gates": {
            "occurrence_below_60_stop": below_60,
            "occurrence_partial_60_85": partial,
            "occurrence_cleared_60": occ_cov is not None and occ_cov >= 0.60,
            "precision_below_90": prec_fail,
            "precision_cleared": precision is not None and precision >= 0.90,
        },
        "marker_matching_untouched": True,
        "no_trec": True,
        "no_metathesaurus": True,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    def pct(x):
        return "n/a" if x is None else f"{x:.1%}"

    lines = [
        "# Does UMLS cover this corpus's vocabulary?",
        "",
        "Short Step 1 `concept` phrases, not eligibility sentences.",
        "Gates committed in `107c1e2` before lookups. No download. No TREC.",
        "Gene-symbol matching is not replaced.",
        "",
        f"Distinct phrases: **{n_dist}**. Occurrences: **{n_occ}**. "
        f"Appear once: {report['n_once']} ({report['n_once']/n_dist:.1%} of distinct).",
        "",
        "## Gates",
        "",
        f"| Measure | Result | Gate |",
        f"|---|---|---|",
        f"| Coverage by occurrence | {pct(occ_cov)} | "
        + (
            "STOP below 60%"
            if below_60
            else ("partial 60–85%" if partial else "cleared 60%")
        )
        + " |",
        f"| Coverage of distinct phrases | {pct(dist_cov)} | reported, no gate |",
        f"| Resolution precision (name agreement) | {pct(precision)} "
        f"({agree_n}/{n_checked}) | "
        + ("BREACHED below 90%" if prec_fail else "cleared 90%")
        + " |",
        "",
        f"Excluding biomarker/mutation occurrences: {pct(report['occurrence_coverage_excluding_biomarker'])}.",
        "",
        "## By category (occurrence coverage is the one that matters)",
        "",
        "| Category | Distinct | Distinct resolved | Occurrences | Occurrence coverage |",
        "|---|---:|---:|---:|---:|",
    ]
    for cat, row in sorted(by_cat.items(), key=lambda kv: -(kv[1]["n_occurrences"] or 0)):
        lines.append(
            f"| {cat} | {row['n_distinct']} | {pct(row['distinct_coverage'])} | "
            f"{row['n_occurrences']} | {pct(row['occurrence_coverage'])} |"
        )
    lines += [
        "",
        "Biomarker/mutation is reported here and is **not** used to replace "
        "gene-symbol matching.",
        "",
        f"Disagreements listed in `docs/step13_umls_disagreements.md` ({len(disagreements)}). "
        "Claude reviews that list. Will is not asked to judge it.",
        "",
        "Steps 6 and 7 not started.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    dlines = [
        "# UMLS resolution disagreements (automatable check)",
        "",
        "Input phrase vs returned canonical name. Sorted by occurrence.",
        "Claude reviews this list. Not a Will sheet.",
        "",
        f"{len(disagreements)} of {n_checked} resolved phrases.",
        "",
        "| n | category | phrase | canonical | CUI |",
        "|---:|---|---|---|---|",
    ]
    for r in disagreements:
        can = (r.get("canonical") or "").replace("|", "/")
        dlines.append(
            f"| {r['n']} | {r['category']} | {r['phrase']} | {can} | {r['cui']} |"
        )
    DISAGREE.write_text("\n".join(dlines), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("n_distinct", "n_occurrences", "distinct_coverage", "occurrence_coverage", "resolution_precision", "gates")}, indent=2))
    print("Wrote", OUT)


if __name__ == "__main__":
    main()
