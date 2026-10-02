"""Pack judged-pool title/text for the GPU box. No secrets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_hybrid_common import DATA, SNAPSHOT, load_docs, pool_ids  # noqa: E402

PACK = DATA / "lambda_pack"


def main() -> None:
    PACK.mkdir(parents=True, exist_ok=True)
    for snap_key in (2021, 2023):
        meta = SNAPSHOT[snap_key]
        docs = load_docs(meta["docs"])
        ncts = sorted({nct for year in meta["years"] for nct in pool_ids(year) if nct in docs})
        out = PACK / f"input_{snap_key}.jsonl"
        with out.open("w", encoding="utf-8") as handle:
            for nct in ncts:
                row = docs[nct]
                handle.write(
                    json.dumps(
                        {
                            "nct_id": nct,
                            "title": row.get("title") or "",
                            "text": row.get("text") or "",
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        print(out, "n", len(ncts), "bytes", out.stat().st_size, flush=True)


if __name__ == "__main__":
    main()
