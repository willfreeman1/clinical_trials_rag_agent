"""Encode judged-pool trials. MedCPT article encoder + text-embedding-3-small.

Truncation: one [title, body] pair per trial, 512 tokens. Same as TrialGPT.
A typical trial is 3,581 characters, so the tail of eligibility is dropped.
Chunking was started (2.7 windows/trial) and abandoned on CPU: ~5 hours per
snapshot. Truncation is the published setup we are reproducing.

MedCPT was trained on PubMed search logs — out of domain here.
Cross-encoder is downloaded and not used.
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mini_pilot import load_key  # noqa: E402
from trec_hybrid_common import DATA, SNAPSHOT, load_docs, pool_ids  # noqa: E402

MODELS = (
    "ncbi/MedCPT-Query-Encoder",
    "ncbi/MedCPT-Article-Encoder",
    "ncbi/MedCPT-Cross-Encoder",
)
ARTICLE = "ncbi/MedCPT-Article-Encoder"
OPENAI_MODEL = "text-embedding-3-small"
BATCH = 32


def prefetch_models() -> None:
    for name in MODELS:
        print(f"prefetch {name}", flush=True)
        AutoTokenizer.from_pretrained(name)
        AutoModel.from_pretrained(name)


def windows(title: str, text: str) -> list[tuple[str, str]]:
    body = text or title or ""
    return [(title or "", body)]


@torch.no_grad()
def encode_articles(pairs: list[tuple[str, str]], model, tokenizer) -> np.ndarray:
    vecs = []
    for i in range(0, len(pairs), BATCH):
        batch = [list(p) for p in pairs[i : i + BATCH]]
        enc = tokenizer(
            batch,
            truncation=True,
            padding=True,
            return_tensors="pt",
            max_length=512,
        )
        hidden = model(**enc).last_hidden_state[:, 0, :]
        vecs.append(hidden.cpu().numpy())
        if (i // BATCH) % 50 == 0:
            print(f"  medcpt {min(i + BATCH, len(pairs))}/{len(pairs)}", flush=True)
    return np.vstack(vecs)


def embed_openai(texts: list[str], api_key: str) -> np.ndarray:
    out = []
    for i in range(0, len(texts), 64):
        batch = [t[:24000] if t else " " for t in texts[i : i + 64]]
        payload = {"model": OPENAI_MODEL, "input": batch}
        req = urllib.request.Request(
            "https://api.openai.com/v1/embeddings",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = json.loads(resp.read().decode())
        by_i = {row["index"]: row["embedding"] for row in body["data"]}
        out.extend(by_i[j] for j in range(len(batch)))
        print(f"  openai {min(i + 64, len(texts))}/{len(texts)}", flush=True)
    return np.asarray(out, dtype=np.float32)


def index_snapshot(snap_key: int) -> None:
    meta = SNAPSHOT[snap_key]
    docs = load_docs(meta["docs"])
    years = meta["years"]
    ncts = sorted({nct for year in years for nct in pool_ids(year) if nct in docs})
    missing = [nct for year in years for nct in pool_ids(year) if nct not in docs]
    missing = sorted(set(missing))
    print(f"snap {snap_key} docs {len(ncts)} missing {len(missing)}", flush=True)
    dest = DATA / f"index_{snap_key}"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "nctids.json").write_text(json.dumps(ncts), encoding="utf-8")

    medcpt_path = dest / "medcpt.npy"
    chunk_path = dest / "chunk_nct.json"
    if medcpt_path.exists() and chunk_path.exists():
        print("medcpt cache hit", flush=True)
    else:
        tokenizer = AutoTokenizer.from_pretrained(ARTICLE)
        model = AutoModel.from_pretrained(ARTICLE)
        model.eval()
        pairs = []
        chunk_nct = []
        for nct in ncts:
            row = docs[nct]
            for pair in windows(row.get("title") or "", row.get("text") or ""):
                pairs.append(pair)
                chunk_nct.append(nct)
        print(f"chunks {len(pairs)} from {len(ncts)} trials", flush=True)
        vecs = encode_articles(pairs, model, tokenizer)
        np.save(medcpt_path, vecs)
        chunk_path.write_text(json.dumps(chunk_nct), encoding="utf-8")
        del model

    openai_path = dest / "openai.npy"
    if openai_path.exists() and np.load(openai_path).shape[0] == len(ncts):
        print("openai cache hit", flush=True)
    else:
        api_key = load_key()
        texts = [(docs[nct].get("text") or docs[nct].get("title") or " ") for nct in ncts]
        vecs = embed_openai(texts, api_key)
        np.save(openai_path, vecs)


def main() -> None:
    torch.set_num_threads(max(1, (torch.get_num_threads() or 4)))
    prefetch_models()
    for snap_key in (2021, 2023):
        index_snapshot(snap_key)


if __name__ == "__main__":
    main()
