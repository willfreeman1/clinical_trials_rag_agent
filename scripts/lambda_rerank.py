"""GPU reranker. MedCPT-CE + MS MARCO MiniLM. Truncation first; chunk-max if time.

Run on the Lambda box. Pairs are [query, title\\nbody], 512 tokens.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MEDCPT = "ncbi/MedCPT-Cross-Encoder"
GENERIC = "cross-encoder/ms-marco-MiniLM-L-12-v2"
BATCH = 64
MAX_LEN = 512
CHUNK_STRIDE = 380
TIME_BUDGET_CHUNK = 25 * 60
QUERY_KEY = {"keywords": "keyword_query", "raw": "raw_query"}


def load_model(name: str, device: str):
    tok = AutoTokenizer.from_pretrained(name)
    model = AutoModelForSequenceClassification.from_pretrained(name).to(device)
    model.eval()
    return tok, model


@torch.no_grad()
def score_pairs(pairs: list[list[str]], tok, model, device: str) -> list[float]:
    out = []
    for i in range(0, len(pairs), BATCH):
        batch = pairs[i : i + BATCH]
        enc = tok(
            batch,
            truncation=True,
            padding=True,
            return_tensors="pt",
            max_length=MAX_LEN,
        ).to(device)
        logits = model(**enc).logits
        if logits.ndim == 2 and logits.size(-1) == 1:
            vals = logits.squeeze(-1)
        elif logits.ndim == 2:
            vals = logits[:, -1]
        else:
            vals = logits.squeeze()
        out.extend(vals.float().cpu().tolist())
        if (i // BATCH) % 40 == 0:
            print(f"  scored {min(i + BATCH, len(pairs))}/{len(pairs)}", flush=True)
    return [float(x) for x in out]


def article(title: str, text: str) -> str:
    title = (title or "").strip()
    text = (text or "").strip()
    if title and text:
        return f"{title}\n{text}"
    return title or text or " "


def chunk_articles(title: str, text: str, tok) -> list[str]:
    title = (title or "").strip()
    body = (text or "").strip()
    if not body:
        return [title or " "]
    ids = tok.encode(body, add_special_tokens=False)
    if len(ids) <= MAX_LEN - 8:
        return [article(title, body)]
    prefix = (title + "\n") if title else ""
    prefix_ids = tok.encode(prefix, add_special_tokens=False)
    room = max(32, MAX_LEN - 8 - len(prefix_ids))
    chunks = []
    start = 0
    while start < len(ids):
        piece = ids[start : start + room]
        chunks.append(prefix + tok.decode(piece, skip_special_tokens=True))
        if start + room >= len(ids):
            break
        start += CHUNK_STRIDE
    return chunks or [article(title, body)]


def main() -> None:
    if not torch.cuda.is_available():
        raise SystemExit("CUDA not available")
    device = "cuda"
    print("gpu", torch.cuda.get_device_name(0), flush=True)
    pack = json.loads(Path("rerank_pack.json").read_text(encoding="utf-8"))
    docs = pack["docs"]
    started = time.time()
    scores = {"truncate": {}, "chunk_max": {}}
    for model_name, tag in ((MEDCPT, "medcpt_ce"), (GENERIC, "msmarco_ce")):
        print(f"load {model_name}", flush=True)
        tok, model = load_model(model_name, device)
        for qname in ("keywords", "raw"):
            print(f"{tag} {qname} truncate", flush=True)
            pairs = []
            keys = []
            for year, ypack in pack["years"].items():
                for tid, trow in ypack["topics"].items():
                    query = trow[QUERY_KEY[qname]]
                    for nct in trow["shortlist"]:
                        row = docs[nct]
                        pairs.append([query, article(row.get("title") or "", row.get("text") or "")])
                        keys.append((year, tid, nct))
            vals = score_pairs(pairs, tok, model, device)
            bucket = scores["truncate"].setdefault(tag, {}).setdefault(qname, {})
            for (year, tid, nct), val in zip(keys, vals):
                bucket.setdefault(year, {}).setdefault(tid, {})[nct] = val
        elapsed = time.time() - started
        print(f"{tag} truncate done in {elapsed:.0f}s", flush=True)
        if elapsed > TIME_BUDGET_CHUNK:
            print("skip chunk-max: over time budget", flush=True)
            del model
            torch.cuda.empty_cache()
            continue
        for qname in ("keywords", "raw"):
            print(f"{tag} {qname} chunk-max", flush=True)
            pairs = []
            keys = []
            for year, ypack in pack["years"].items():
                for tid, trow in ypack["topics"].items():
                    query = trow[QUERY_KEY[qname]]
                    for nct in trow["shortlist"]:
                        row = docs[nct]
                        for chunk in chunk_articles(row.get("title") or "", row.get("text") or "", tok):
                            pairs.append([query, chunk])
                            keys.append((year, tid, nct))
            vals = score_pairs(pairs, tok, model, device)
            bucket = scores["chunk_max"].setdefault(tag, {}).setdefault(qname, {})
            for (year, tid, nct), val in zip(keys, vals):
                year_b = bucket.setdefault(year, {}).setdefault(tid, {})
                prev = year_b.get(nct)
                if prev is None or val > prev:
                    year_b[nct] = val
        del model
        torch.cuda.empty_cache()
    Path("rerank_ce_scores.json").write_text(json.dumps(scores), encoding="utf-8")
    print("wrote rerank_ce_scores.json", "elapsed", int(time.time() - started), flush=True)


if __name__ == "__main__":
    main()
