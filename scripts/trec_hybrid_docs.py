"""Download TREC snapshots and keep only judged-pool trial text.

2021/2022: 27 April 2021 dump. 2023: 8 May 2023 dump. Confirmed on
trec-cds.org, not assumed. Zips go to E:/trec_snapshots. Extracted
judged records go to data/trec (gitignored).
"""

from __future__ import annotations

import ssl
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from trec_hybrid_common import (  # noqa: E402
    DATA,
    SNAPSHOT,
    YEAR_SNAP,
    YEARS,
    load_qrels,
    parse_trial_xml,
)

CTX = ssl.create_default_context()
UA = {"User-Agent": "clinical-trials-rag-agent-trec-hybrid"}


def wanted_ids(snap_key: int) -> set[str]:
    years = SNAPSHOT[snap_key]["years"]
    ids: set[str] = set()
    for year in years:
        ids.update(nct for _, nct, _ in load_qrels(year))
    return ids


def download_zip(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, method="HEAD", headers=UA)
    with urllib.request.urlopen(req, timeout=60, context=CTX) as resp:
        expected = int(resp.headers.get("Content-Length") or 0)
    if dest.exists() and expected and dest.stat().st_size == expected:
        print(f"have {dest.name} ({expected} bytes)", flush=True)
        return
    print(f"download {url}", flush=True)
    req = urllib.request.Request(url, headers=UA)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, timeout=600, context=CTX) as resp, tmp.open("wb") as out:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    tmp.replace(dest)
    print(f"wrote {dest} ({dest.stat().st_size} bytes)", flush=True)


def extract_judged(snap_key: int) -> None:
    meta = SNAPSHOT[snap_key]
    wanted = wanted_ids(snap_key)
    out_path = meta["docs"]
    DATA.mkdir(parents=True, exist_ok=True)
    found: dict[str, dict] = {}
    if out_path.exists():
        from trec_hybrid_common import load_docs

        found = load_docs(out_path)
        print(f"resume {out_path.name}: {len(found)}/{len(wanted)}", flush=True)
    still = wanted - set(found)
    if not still:
        print(f"{snap_key} complete {len(found)}", flush=True)
        return
    zip_dir: Path = meta["dir"]
    for url in meta["zips"]:
        if not still:
            break
        dest = zip_dir / url.rsplit("/", 1)[-1]
        download_zip(url, dest)
        print(f"scan {dest.name} want {len(still)}", flush=True)
        with zipfile.ZipFile(dest) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                name = info.filename.replace("\\", "/").split("/")[-1]
                nct_guess = name.split(".")[0].upper()
                if nct_guess.startswith("NCT") and nct_guess not in still:
                    continue
                if not name.lower().endswith((".xml", ".txt")):
                    continue
                raw = zf.read(info)
                row = parse_trial_xml(raw)
                if not row or row["nct_id"] not in still:
                    continue
                found[row["nct_id"]] = row
                still.discard(row["nct_id"])
                if len(found) % 1000 == 0:
                    print(f"  extracted {len(found)}/{len(wanted)}", flush=True)
        _write_docs(out_path, found)
    missing = wanted - set(found)
    print(
        f"{snap_key} extracted {len(found)}/{len(wanted)} missing {len(missing)}",
        flush=True,
    )
    if missing:
        sample = sorted(missing)[:10]
        print("missing sample", sample, flush=True)
    _write_docs(out_path, found)


def _write_docs(path: Path, found: dict[str, dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for nct in sorted(found):
            handle.write(__import__("json").dumps(found[nct], ensure_ascii=False) + "\n")


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    print("years", YEARS)
    for year in YEARS:
        snap = YEAR_SNAP[year]
        print(f"year {year} uses snapshot {SNAPSHOT[snap]['date']}")
    for snap_key in (2021, 2023):
        extract_judged(snap_key)


if __name__ == "__main__":
    main()
