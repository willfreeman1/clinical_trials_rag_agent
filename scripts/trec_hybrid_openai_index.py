"""OpenAI text-embedding-3-small for the judged pool. Safe to run beside MedCPT."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_hybrid_index import index_snapshot  # noqa: E402


def main() -> None:
    # Only the OpenAI half: reuse index_snapshot after a tiny patch by calling
    # embed path directly.
    import json

    import numpy as np

    from mini_pilot import load_key
    from trec_hybrid_common import DATA, SNAPSHOT, load_docs, pool_ids
    from trec_hybrid_index import embed_openai

    api_key = load_key()
    for snap_key in (2021, 2023):
        meta = SNAPSHOT[snap_key]
        docs = load_docs(meta["docs"])
        years = meta["years"]
        ncts = sorted({nct for year in years for nct in pool_ids(year) if nct in docs})
        dest = DATA / f"index_{snap_key}"
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "nctids.json").write_text(json.dumps(ncts), encoding="utf-8")
        openai_path = dest / "openai.npy"
        if openai_path.exists() and np.load(openai_path).shape[0] == len(ncts):
            print(f"openai {snap_key} cache hit", flush=True)
            continue
        texts = [(docs[nct].get("text") or docs[nct].get("title") or " ") for nct in ncts]
        print(f"openai {snap_key} {len(texts)}", flush=True)
        vecs = embed_openai(texts, api_key)
        np.save(openai_path, vecs)


if __name__ == "__main__":
    main()
