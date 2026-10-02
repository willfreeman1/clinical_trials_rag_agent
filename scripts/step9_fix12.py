"""Clear the 12 title-inferred stage labels. Mechanical. No model.

Eligibility states no stage rule. The stored required-stage label came from
the title and caused 212 wrong discards. Snapshot the Step 5b key first.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
KEY = DATA / "answer_key_step5b.jsonl"
SNAP = DATA / "answer_key_step5b_pre_remaining.jsonl"
LOG = DATA / "step9_fix12.json"
TRIAGE = DATA / "step9_triage.json"

STAGE_FIELDS = ("allowed_stages", "refused_stages", "stage_quote", "stage_condition")


def load_ids() -> list[str]:
    payload = json.loads(TRIAGE.read_text(encoding="utf-8"))
    ids = sorted({
        row["nct_id"]
        for row in payload["check2_labels"]["rows"]
        if row["verdict"] == "unsupported" and row["fact"] == "disease_stage"
    })
    if len(ids) != 12:
        raise SystemExit(f"expected 12 unsupported stage labels, got {len(ids)}: {ids}")
    return ids


def empty_stage(answer: dict) -> dict:
    old = {field: answer.get(field) for field in STAGE_FIELDS}
    answer["allowed_stages"] = []
    answer["refused_stages"] = []
    answer["stage_quote"] = ""
    answer["stage_condition"] = ""
    return old


def main() -> None:
    ids = set(load_ids())
    if not SNAP.exists():
        shutil.copyfile(KEY, SNAP)
        print(f"snapshot {SNAP}", flush=True)
    patched = []
    log_rows = []
    found = set()
    with KEY.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            nct = row["nct_id"]
            if nct in ids and row.get("answer"):
                found.add(nct)
                old = empty_stage(row["answer"])
                row["stage_cleared_title_inference"] = True
                log_rows.append({"nct_id": nct, "old": old})
            patched.append(row)
    missing = ids - found
    if missing:
        raise SystemExit(f"not in step5b key: {sorted(missing)}")
    with KEY.open("w", encoding="utf-8") as handle:
        for row in patched:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    LOG.write_text(json.dumps({"n": len(log_rows), "rows": log_rows}, indent=2), encoding="utf-8")
    print(f"cleared {len(log_rows)} stage labels")
    print("Wrote", KEY)
    print("Wrote", LOG)


if __name__ == "__main__":
    main()
