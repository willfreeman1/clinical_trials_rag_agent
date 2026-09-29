"""Download MeSH 2025 ASCII descriptors and supplementary concepts.

2026 ASCII was discontinued. These files are free, no licence step, and they
carry both synonym lists and tree numbers. Written to data/mesh/, which is
gitignored with the rest of data/.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MESH_DIR = ROOT / "data" / "mesh"

FILES = {
    "d2025.bin": "https://nlmpubs.nlm.nih.gov/projects/mesh/2025/asciimesh/d2025.bin",
    "c2025.bin": "https://nlmpubs.nlm.nih.gov/projects/mesh/2025/asciimesh/c2025.bin",
}


def main() -> None:
    MESH_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        dest = MESH_DIR / name
        if dest.exists() and dest.stat().st_size > 1_000_000:
            print(f"already have {dest} ({dest.stat().st_size} bytes)")
            continue
        print(f"downloading {url}")
        urllib.request.urlretrieve(url, dest)
        print(f"  wrote {dest} ({dest.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
