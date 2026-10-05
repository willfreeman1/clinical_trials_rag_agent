"""Shared TREC hybrid-retrieval helpers. Gates committed in 613635e.

Judged pool is the collection. No six-name code. No trial text to an LLM.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "trec"
SNAP_ROOT = Path("E:/trec_snapshots")
REPORT = ROOT / "docs" / "trec_hybrid_retrieval.md"
THRESHOLDS_COMMIT = "613635e"

YEARS = (2021, 2022, 2023)
DEPTHS = (10, 20, 50, 100, 200, 500)
RRF_K = 60
RETRIEVE_N = 1000
KEYWORD_MODEL = "gpt-4o"

SNAPSHOT = {
    2021: {
        "date": "2021-04-27",
        "n_records": 375581,
        "years": (2021, 2022),
        "zips": [
            f"https://www.trec-cds.org/2021_data/ClinicalTrials.2021-04-27.part{i}.zip"
            for i in range(1, 6)
        ],
        "dir": SNAP_ROOT / "2021",
        "docs": DATA / "docs_2021.jsonl",
    },
    2023: {
        "date": "2023-05-08",
        "n_records": None,
        "years": (2023,),
        "zips": [
            f"https://www.trec-cds.org/2023_data/ClinicalTrials.2023-05-08.trials{i}.zip"
            for i in range(6)
        ],
        "dir": SNAP_ROOT / "2023",
        "docs": DATA / "docs_2023.jsonl",
    },
}

YEAR_SNAP = {2021: 2021, 2022: 2021, 2023: 2023}


def snap_for(year: int) -> dict:
    return SNAPSHOT[YEAR_SNAP[year]]


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def load_qrels(year: int) -> list[tuple[str, str, int]]:
    rows = []
    for line in (DATA / f"qrels{year}.txt").read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        rows.append((parts[0], parts[2].upper(), int(parts[3])))
    return rows


def pool_ids(year: int) -> list[str]:
    return sorted({nct for _, nct, _ in load_qrels(year)})


def qrels_by_topic(year: int) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = defaultdict(dict)
    for topic, nct, rel in load_qrels(year):
        out[topic][nct] = rel
    return dict(out)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _first_text(root: ET.Element, names: set[str]) -> str:
    for el in root.iter():
        if _local(el.tag) in names:
            bits = [t.strip() for t in el.itertext() if t.strip()]
            if bits:
                return " ".join(bits)
    return ""


def _all_text(root: ET.Element, names: set[str]) -> list[str]:
    found = []
    for el in root.iter():
        if _local(el.tag) in names:
            bits = [t.strip() for t in el.itertext() if t.strip()]
            if bits:
                found.append(" ".join(bits))
    return found


def parse_trial_xml(raw: bytes) -> dict | None:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return None
    nct = _first_text(root, {"nct_id", "nctId"}).upper()
    if not nct.startswith("NCT"):
        return None
    title = _first_text(root, {"brief_title", "official_title", "briefTitle", "officialTitle"})
    conditions = _all_text(root, {"condition", "conditionName"})
    summary = _first_text(root, {"brief_summary", "briefSummary", "detailed_description", "detailedDescription"})
    eligibility = _first_text(root, {"criteria", "eligibilityCriteria"})
    text = "\n".join(p for p in (title, " ".join(conditions), summary, eligibility) if p)
    return {
        "nct_id": nct,
        "title": title,
        "conditions": conditions,
        "summary": summary,
        "eligibility": eligibility,
        "text": text,
    }


def flatten_topic_xml(topic: ET.Element) -> tuple[str, str]:
    number = topic.attrib.get("number", "")
    template = topic.attrib.get("template", "")
    fields = []
    if template:
        fields.append(f"condition template: {template}")
    for child in list(topic):
        tag = _local(child.tag)
        if tag == "field":
            name = child.attrib.get("name", "")
            val = (child.text or "").strip()
            if val:
                fields.append(f"{name}: {val}")
        else:
            val = " ".join(t.strip() for t in child.itertext() if t.strip())
            if val:
                fields.append(val)
    body = "\n".join(fields).strip()
    if not body:
        body = " ".join(t.strip() for t in topic.itertext() if t.strip())
    return number, body


def load_topics(year: int) -> dict[str, str]:
    tree = ET.parse(DATA / f"topics{year}.xml")
    out = {}
    for topic in tree.getroot().findall("topic"):
        number, text = flatten_topic_xml(topic)
        if number:
            out[str(number)] = text
    return out


def load_docs(path: Path) -> dict[str, dict]:
    docs = {}
    if not path.exists():
        return docs
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            docs[row["nct_id"]] = row
    return docs


def rrf(rankings: list[list[str]], k: int = RRF_K) -> list[str]:
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, doc in enumerate(ranking, start=1):
            scores[doc] += 1.0 / (k + rank)
    return [doc for doc, _ in sorted(scores.items(), key=lambda kv: -kv[1])]


def recall_at(ranked: list[str], relevant: set[str], depth: int) -> float | None:
    if not relevant:
        return None
    hit = sum(1 for d in ranked[:depth] if d in relevant)
    return hit / len(relevant)


def mean_ignore_none(values: list[float | None]) -> float | None:
    xs = [v for v in values if v is not None]
    return sum(xs) / len(xs) if xs else None
