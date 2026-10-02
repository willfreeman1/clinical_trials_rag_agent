"""Parse stripped notes with the Step 4 parser. No Will sheet."""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mini_pilot import INPUT_USD_PER_MILLION, OUTPUT_USD_PER_MILLION  # noqa: E402
from step4_parse import parse_one  # noqa: E402
from mini_pilot import load_key  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
NOTES = ROOT / "data" / "step11_notes.jsonl"
OUT = ROOT / "data" / "step11_parse.jsonl"
SUMMARY = ROOT / "data" / "step11_parse_summary.json"
WORKERS = 6


def load_notes() -> list[dict]:
    rows = []
    with NOTES.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("note") and not row.get("leaked"):
                rows.append(row)
    return rows


def load_done() -> set[str]:
    done = set()
    if not OUT.exists():
        return done
    with OUT.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("answer"):
                done.add(row["id"])
    return done


def main() -> None:
    notes = load_notes()
    done = load_done()
    todo = [n for n in notes if n["id"] not in done]
    print(f"notes={len(notes)} done={len(done)} todo={len(todo)}", flush=True)
    api_key = load_key()
    lock = Lock()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {
            pool.submit(parse_one, api_key, n["patient_id"], n["note"]): n
            for n in todo
        }
        for future in as_completed(futures):
            src = futures[future]
            parsed = future.result()
            row = {
                "id": src["id"],
                "patient_id": src["patient_id"],
                "k": src["k"],
                "include": src["include"],
                "exclude": src["exclude"],
                "note": src["note"],
                "answer": parsed.get("answer"),
                "usage": parsed.get("usage"),
                "error": parsed.get("error"),
            }
            with lock:
                with OUT.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                print(src["id"], "ok" if row.get("answer") else "fail", flush=True)

    unique = {}
    if OUT.exists():
        with OUT.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    r = json.loads(line)
                    unique[r["id"]] = r
    rows = list(unique.values())
    in_tok = sum((r.get("usage") or {}).get("input_tokens") or 0 for r in rows)
    out_tok = sum((r.get("usage") or {}).get("output_tokens") or 0 for r in rows)
    cost = (in_tok * INPUT_USD_PER_MILLION + out_tok * OUTPUT_USD_PER_MILLION) / 1_000_000
    failed = sum(1 for r in rows if not r.get("answer"))
    SUMMARY.write_text(json.dumps({
        "n": len(rows),
        "n_failed": failed,
        "estimated_usd": round(cost, 4),
    }, indent=2), encoding="utf-8")
    print(f"parsed={len(rows)} failed={failed} usd={cost:.4f}")


if __name__ == "__main__":
    main()
