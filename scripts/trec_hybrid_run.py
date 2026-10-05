"""Orchestrate stages 1–2. Gates committed in 613635e before this exists."""

from __future__ import annotations

import runpy
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent


def main() -> None:
    for name in (
        "trec_hybrid_docs.py",
        "trec_hybrid_keywords.py",
        "trec_hybrid_index.py",
        "trec_hybrid_eval.py",
    ):
        print("====", name, flush=True)
        runpy.run_path(str(SCRIPTS / name), run_name="__main__")


if __name__ == "__main__":
    main()
