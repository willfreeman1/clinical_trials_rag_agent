"""Run on the Lambda GPU. One [title, body] pair per trial, 512 tokens."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModel, AutoTokenizer

ARTICLE = "ncbi/MedCPT-Article-Encoder"
BATCH = 64
DEVICE = "cuda"


@torch.no_grad()
def encode(pairs: list[tuple[str, str]]) -> np.ndarray:
    tokenizer = AutoTokenizer.from_pretrained(ARTICLE)
    model = AutoModel.from_pretrained(ARTICLE).to(DEVICE)
    model.eval()
    vecs = []
    for i in range(0, len(pairs), BATCH):
        batch = [list(p) for p in pairs[i : i + BATCH]]
        enc = tokenizer(
            batch,
            truncation=True,
            padding=True,
            return_tensors="pt",
            max_length=512,
        ).to(DEVICE)
        hidden = model(**enc).last_hidden_state[:, 0, :]
        vecs.append(hidden.float().cpu().numpy())
        print(f"medcpt {min(i + BATCH, len(pairs))}/{len(pairs)}", flush=True)
    return np.vstack(vecs)


def main() -> None:
    if not torch.cuda.is_available():
        raise SystemExit("CUDA not available")
    print("gpu", torch.cuda.get_device_name(0), flush=True)
    src = Path(sys.argv[1])
    dest = Path(sys.argv[2])
    dest.mkdir(parents=True, exist_ok=True)
    ncts = []
    pairs = []
    with src.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            ncts.append(row["nct_id"])
            pairs.append((row.get("title") or "", row.get("text") or row.get("title") or ""))
    vecs = encode(pairs)
    np.save(dest / "medcpt.npy", vecs)
    (dest / "nctids.json").write_text(json.dumps(ncts), encoding="utf-8")
    (dest / "chunk_nct.json").write_text(json.dumps(ncts), encoding="utf-8")
    print("wrote", dest / "medcpt.npy", vecs.shape, flush=True)


if __name__ == "__main__":
    main()
