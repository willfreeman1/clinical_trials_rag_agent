"""Build the committed demo seed from local TREC files. Not a measurement.

Writes demo/seed/. Needs data/trec/ on this machine. Embedding the
trial texts uses the OpenAI key once; the demo itself does not.
The system does not say a patient qualifies.
"""

from __future__ import annotations

import json
import random
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from reader.split_rules import split_sections  # noqa: E402
from trec_score_common import DATA, load_qrels  # noqa: E402

OUT = ROOT / "demo" / "seed"
PATIENTS = ("1", "8", "18")
YEAR = "2022"
ZERO_PER_PATIENT = 40
EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536


def topics() -> dict[str, str]:
    tree = ET.parse(DATA / "topics2022.xml")
    out = {}
    for node in tree.getroot().findall("topic"):
        out[str(node.get("number"))] = (node.text or "").strip()
    return out


def load_keywords() -> dict:
    raw = json.loads((DATA / "keywords.json").read_text(encoding="utf-8"))
    return raw.get(YEAR) or {}


def load_scores() -> dict:
    raw = json.loads((DATA / "score_qwen.json").read_text(encoding="utf-8"))
    return ((raw.get("arms") or {}).get("topical_title_cond_slice") or {}).get(YEAR) or {}


def load_docs() -> dict[str, dict]:
    out = {}
    with (DATA / "docs_2021.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            nct = rec.get("nct_id")
            if nct:
                out[nct] = rec
    return out


def reader_ncts() -> dict[str, set[str]]:
    got: dict[str, set[str]] = {p: set() for p in PATIENTS}
    reads = DATA / "trec_reader_reads.jsonl"
    if not reads.exists():
        return got
    with reads.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            pid = str(rec.get("patient_id") or "")
            if pid in got and rec.get("nct_id"):
                got[pid].add(rec["nct_id"])
    return got


def reader_raw() -> dict[tuple[str, str], str]:
    out = {}
    reads = DATA / "trec_reader_reads.jsonl"
    if not reads.exists():
        return out
    with reads.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            pid = str(rec.get("patient_id") or "")
            nct = rec.get("nct_id")
            if pid in PATIENTS and nct and rec.get("raw_model_output"):
                out[(pid, nct)] = rec["raw_model_output"]
    return out


def pick_ncts(qrels: dict[str, dict[str, int]], extra: dict[str, set[str]]) -> list[str]:
    rng = random.Random(20261005)
    chosen: set[str] = set()
    for pid in PATIENTS:
        labs = qrels.get(pid) or {}
        for nct, lab in labs.items():
            if lab in (1, 2):
                chosen.add(nct)
        zeros = [nct for nct, lab in labs.items() if lab == 0]
        rng.shuffle(zeros)
        chosen.update(zeros[:ZERO_PER_PATIENT])
        chosen.update(extra.get(pid) or [])
    return sorted(chosen)


def embed_texts(texts: list[str]) -> list[list[float]]:
    from mini_pilot import load_key
    import urllib.request

    key = load_key()
    vectors: list[list[float]] = []
    batch = 64
    for i in range(0, len(texts), batch):
        chunk = texts[i : i + batch]
        payload = {"model": EMBED_MODEL, "input": chunk}
        req = urllib.request.Request(
            "https://api.openai.com/v1/embeddings",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        by_i = {int(row["index"]): row["embedding"] for row in body["data"]}
        for j in range(len(chunk)):
            vectors.append(by_i[j])
        print(f"  embedded {min(i + batch, len(texts))}/{len(texts)}", flush=True)
    return vectors


def trial_text(rec: dict) -> str:
    title = (rec.get("title") or "").strip()
    conds = rec.get("conditions") or []
    if isinstance(conds, str):
        conds = [conds]
    elig = (rec.get("eligibility") or "").strip()[:1500]
    return "\n".join(p for p in (title, "; ".join(str(c) for c in conds if c), elig) if p) or " "


def main() -> None:
    notes = topics()
    for pid in PATIENTS:
        if pid not in notes:
            raise SystemExit(f"missing topic {pid}")
    qrels_all = load_qrels(2022)
    extra = reader_ncts()
    ncts = pick_ncts(qrels_all, extra)
    docs = load_docs()
    missing = [n for n in ncts if n not in docs]
    if missing:
        print(f"drop {len(missing)} ncts not in docs", flush=True)
        ncts = [n for n in ncts if n in docs]
    keywords = load_keywords()
    scores = load_scores()
    raws = reader_raw()

    modes = {n: split_sections(docs[n].get("eligibility") or "")["mode"] for n in ncts}
    n_line = sum(1 for m in modes.values() if m == "line_header")
    n_none = sum(1 for m in modes.values() if m == "no_header")
    awkward = next((n for n, m in modes.items() if m == "no_header"), None)

    OUT.mkdir(parents=True, exist_ok=True)
    trials = []
    for nct in ncts:
        rec = docs[nct]
        conds = rec.get("conditions") or []
        if isinstance(conds, str):
            conds = [conds]
        trials.append(
            {
                "nct_id": nct,
                "title": rec.get("title") or "",
                "conditions": [str(c) for c in conds if c],
                "eligibility": rec.get("eligibility") or "",
                "summary": rec.get("summary") or "",
                "overall_status": "",
                "phase": "",
                "location": "",
                "splitter_mode": modes[nct],
            }
        )
    (OUT / "trials.jsonl").write_text(
        "\n".join(json.dumps(t, ensure_ascii=False) for t in trials) + "\n",
        encoding="utf-8",
    )

    patients = []
    for pid in PATIENTS:
        kw = keywords.get(pid) or {}
        patients.append(
            {
                "patient_id": pid,
                "year": 2022,
                "note": notes[pid],
                "keywords": list(kw.get("keywords") or []),
                "summary": kw.get("summary") or "",
            }
        )
    (OUT / "patients.json").write_text(json.dumps(patients, indent=2, ensure_ascii=False), encoding="utf-8")

    q_rows = []
    for pid in PATIENTS:
        for nct, lab in (qrels_all.get(pid) or {}).items():
            if nct in set(ncts) and lab in (0, 1, 2):
                q_rows.append({"patient_id": pid, "nct_id": nct, "label": lab})
    (OUT / "qrels.jsonl").write_text(
        "\n".join(json.dumps(r) for r in q_rows) + "\n", encoding="utf-8"
    )

    score_rows = []
    for pid in PATIENTS:
        block = scores.get(pid) or {}
        for nct in ncts:
            rec = block.get(nct)
            if rec is None:
                continue
            cont = float(rec[1]) if isinstance(rec, list) and len(rec) >= 2 else None
            if cont is None:
                continue
            score_rows.append({"patient_id": pid, "nct_id": nct, "topical": cont})
    (OUT / "scores.jsonl").write_text(
        "\n".join(json.dumps(r) for r in score_rows) + "\n", encoding="utf-8"
    )

    read_rows = [
        {"patient_id": pid, "nct_id": nct, "raw_model_output": raw}
        for (pid, nct), raw in raws.items()
        if nct in set(ncts)
    ]
    (OUT / "reads.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in read_rows) + "\n",
        encoding="utf-8",
    )

    print("embedding trials and patient queries", flush=True)
    trial_vecs = embed_texts([trial_text(docs[n]) for n in ncts])
    query_texts = []
    for p in patients:
        kws = " ".join(p["keywords"]) or p["note"]
        query_texts.append(kws)
    query_vecs = embed_texts(query_texts)
    np.savez_compressed(
        OUT / "embeddings.npz",
        nct_ids=np.array(ncts),
        trial=np.asarray(trial_vecs, dtype=np.float32),
        patient_ids=np.array(PATIENTS),
        query=np.asarray(query_vecs, dtype=np.float32),
    )

    mix = {}
    for pid in PATIENTS:
        labs = [r["label"] for r in q_rows if r["patient_id"] == pid]
        mix[pid] = {str(k): labs.count(k) for k in (0, 1, 2)}
    manifest = {
        "year": 2022,
        "patients": list(PATIENTS),
        "n_trials": len(ncts),
        "n_qrels": len(q_rows),
        "n_scores": len(score_rows),
        "n_reads": len(read_rows),
        "label_mix": mix,
        "splitter": {"line_header": n_line, "no_header": n_none, "awkward_nct": awkward},
        "embedding_model": EMBED_MODEL,
        "embedding_dim": EMBED_DIM,
        "note": "Seed for the laptop demo. Not a new measurement. The system does not say a patient qualifies.",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2), flush=True)
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
