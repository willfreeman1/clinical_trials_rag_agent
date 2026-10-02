"""Task A: TREC 2021/2022 pool size, snapshot, live-API sample.

Gates were committed in THRESHOLDS.md (03d95b5) before this ran.
"""

from __future__ import annotations

import json
import random
import re
import ssl
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "trec"
OUT = ROOT / "data" / "trec_retrievability.json"
REPORT = ROOT / "docs" / "trec_retrievability.md"
SEED = 202609305
SAMPLE_PER_LEVEL = 150
RELS = {0: "not_relevant", 1: "excluded", 2: "eligible"}

QRELS = {
    2021: "https://trec.nist.gov/data/trials/qrels2021.txt",
    2022: "https://trec.nist.gov/data/trials/qrels2022.txt",
}
SNAPSHOT_PARTS = [
    "https://www.trec-cds.org/2021_data/ClinicalTrials.2021-04-27.part1.zip",
    "https://www.trec-cds.org/2021_data/ClinicalTrials.2021-04-27.part2.zip",
    "https://www.trec-cds.org/2021_data/ClinicalTrials.2021-04-27.part3.zip",
    "https://www.trec-cds.org/2021_data/ClinicalTrials.2021-04-27.part4.zip",
    "https://www.trec-cds.org/2021_data/ClinicalTrials.2021-04-27.part5.zip",
]
TOPICS = {
    2021: "https://www.trec-cds.org/topics2021.xml",
    2022: "https://www.trec-cds.org/topics2022.xml",
}
CTX = ssl.create_default_context()


def fetch(url: str, dest: Path | None = None, head: bool = False) -> dict:
    req = urllib.request.Request(
        url,
        method="HEAD" if head else "GET",
        headers={"User-Agent": "clinical-trials-rag-agent-trec-check"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60, context=CTX) as resp:
            info = {
                "url": url,
                "status": getattr(resp, "status", 200),
                "ok": True,
                "content_length": resp.headers.get("Content-Length"),
                "content_type": resp.headers.get("Content-Type"),
            }
            if not head:
                body = resp.read()
                if dest:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(body)
                info["bytes"] = len(body)
            return info
    except urllib.error.HTTPError as exc:
        return {"url": url, "status": exc.code, "ok": False, "error": str(exc)}
    except Exception as exc:
        return {"url": url, "status": None, "ok": False, "error": str(exc)}


def parse_qrels(path: Path) -> list[tuple[str, str, int]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        topic, _iter, nct, rel = parts[0], parts[1], parts[2], int(parts[3])
        rows.append((topic, nct, rel))
    return rows


def count_year(year: int, rows: list[tuple[str, str, int]], n_topics_xml: int) -> dict:
    topics = {t for t, _, _ in rows}
    ncts = {n for _, n, _ in rows}
    by_rel = Counter(r for _, _, r in rows)
    ncts_by_rel = {rel: {n for _, n, r in rows if r == rel} for rel in RELS}
    return {
        "year": year,
        "n_topics_in_qrels": len(topics),
        "n_topics_in_xml": n_topics_xml,
        "n_judgments": len(rows),
        "n_unique_nct": len(ncts),
        "judgments_by_rel": {RELS[k]: by_rel[k] for k in sorted(RELS)},
        "unique_nct_by_rel": {RELS[k]: len(ncts_by_rel[k]) for k in sorted(RELS)},
    }


def count_topics_xml(path: Path) -> int:
    text = path.read_text(encoding="utf-8", errors="replace")
    return len(re.findall(r"<topic\s", text, flags=re.IGNORECASE))


def sample_ids(rows: list[tuple[str, str, int]], rng: random.Random) -> dict[int, list[str]]:
    by_rel: dict[int, set[str]] = defaultdict(set)
    for _, nct, rel in rows:
        by_rel[rel].add(nct)
    picked = {}
    for rel, ids in by_rel.items():
        pool = sorted(ids)
        k = min(SAMPLE_PER_LEVEL, len(pool))
        picked[rel] = rng.sample(pool, k)
    return picked


def ctgov_exists(ncts: list[str]) -> dict[str, bool]:
    found: dict[str, bool] = {}
    for i in range(0, len(ncts), 50):
        chunk = ncts[i : i + 50]
        ids = ",".join(chunk)
        url = (
            "https://clinicaltrials.gov/api/v2/studies"
            f"?filter.ids={ids}&fields=NCTId&pageSize=50"
        )
        for attempt in range(4):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "clinical-trials-rag-agent-trec-check"})
                with urllib.request.urlopen(req, timeout=60, context=CTX) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                got = set()
                for st in body.get("studies") or []:
                    proto = (st.get("protocolSection") or {})
                    ident = (proto.get("identificationModule") or {})
                    nct = ident.get("nctId")
                    if nct:
                        got.add(nct)
                # some payloads nest differently
                if not got:
                    text = json.dumps(body)
                    for nct in chunk:
                        if nct in text:
                            got.add(nct)
                for nct in chunk:
                    found[nct] = nct in got
                break
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 500, 502, 503) and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                for nct in chunk:
                    found[nct] = False
                break
            except Exception:
                if attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                for nct in chunk:
                    found[nct] = False
                break
        time.sleep(0.15)
    return found


def pct(k: int, n: int) -> float | None:
    return round(k / n, 4) if n else None


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    snapshot = [fetch(u, head=True) for u in SNAPSHOT_PARTS]
    snapshot_ok = all(s.get("ok") for s in snapshot)

    year_files = {}
    for year, url in QRELS.items():
        dest = DATA / f"qrels{year}.txt"
        if dest.exists() and dest.stat().st_size > 1000:
            year_files[year] = dest
            continue
        info = fetch(url, dest)
        if not info.get("ok"):
            raise SystemExit(f"qrels {year} failed: {info}")
        year_files[year] = dest
    topic_n = {}
    for year, url in TOPICS.items():
        dest = DATA / f"topics{year}.xml"
        info = fetch(url, dest)
        if not info.get("ok"):
            raise SystemExit(f"topics {year} failed: {info}")
        topic_n[year] = count_topics_xml(dest)

    parsed = {y: parse_qrels(p) for y, p in year_files.items()}
    years = {y: count_year(y, parsed[y], topic_n[y]) for y in parsed}

    all_rows = parsed[2021] + parsed[2022]
    unique_all = {n for _, n, _ in all_rows}
    unique_by_rel = {rel: {n for _, n, r in all_rows if r == rel} for rel in RELS}

    rng = random.Random(SEED)
    picked = sample_ids(all_rows, rng)
    probe_ids = sorted({nct for ids in picked.values() for nct in ids})
    print(f"snapshot_ok={snapshot_ok} probing {len(probe_ids)} NCT IDs", flush=True)
    found = ctgov_exists(probe_ids)

    live = {}
    for rel, ids in picked.items():
        ok = sum(1 for nct in ids if found.get(nct))
        live[RELS[rel]] = {
            "sampled": len(ids),
            "retrievable": ok,
            "rate": pct(ok, len(ids)),
        }
    overall_ok = sum(1 for nct in probe_ids if found.get(nct))
    live["overall_unique_sampled"] = {
        "sampled": len(probe_ids),
        "retrievable": overall_ok,
        "rate": pct(overall_ok, len(probe_ids)),
    }

    n_judged = len(unique_all)
    rules = n_judged * 43
    # gpt-5.4: ~500 in / 80 out per rule (phrase extraction), same prices as mini_pilot
    in_tok, out_tok = 500, 80
    usd_rule = (in_tok * 2.50 + out_tok * 15.00) / 1_000_000
    frontier = round(rules * usd_rule, 0)

    payload = {
        "seed": SEED,
        "thresholds_commit": "03d95b5",
        "snapshot": {
            "exists": snapshot_ok,
            "description": "April 27, 2021 ClinicalTrials.gov dump, 375,581 records, five zip parts. Same corpus for 2021 and 2022.",
            "parts": snapshot,
            "pages": [
                "https://www.trec-cds.org/2021.html",
                "https://www.trec-cds.org/2022.html",
                "https://ir-datasets.com/clinicaltrials.html",
            ],
        },
        "years": years,
        "combined": {
            "n_topics": years[2021]["n_topics_in_qrels"] + years[2022]["n_topics_in_qrels"],
            "n_judgments": len(all_rows),
            "n_unique_nct": n_judged,
            "unique_nct_by_rel": {RELS[k]: len(unique_by_rel[k]) for k in RELS},
        },
        "live_api": live,
        "gate": {
            "snapshot_usable": snapshot_ok,
            "live_api_decides": not snapshot_ok,
            "stop_if_no_snapshot_and_any_level_below_70": True,
        },
        "cost_estimate": {
            "unique_judged_trials": n_judged,
            "rules_at_43_each": rules,
            "usd_per_rule_gpt54_rough": round(usd_rule, 5),
            "frontier_gpt54_usd": frontier,
            "note": "Assigning the judged pool only, not the 375k-trial snapshot. Bring to Will. Do not start.",
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    print("Wrote", OUT)


if __name__ == "__main__":
    main()
