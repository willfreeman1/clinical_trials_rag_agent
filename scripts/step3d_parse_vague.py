"""Parse the five vague-history patients with the extended prior-therapy names.

Does not re-parse the original 20. Thresholds in THRESHOLDS.md, committed
before this ran.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mini_pilot import (  # noqa: E402
    INPUT_USD_PER_MILLION,
    OUTPUT_USD_PER_MILLION,
)
from step3d_reassign import canonical_name  # noqa: E402
from step4_parse import SYSTEM, parse_one, load_key  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PATIENTS_MD = ROOT / "fake_patients_vague.md"
OUT = ROOT / "data" / "step3d_vague_parse.json"

EXPECTED = {
    "V01": "previous chemotherapy (any kind)",
    "V02": "previous systemic anticancer treatment (any kind)",
    "V03": "previous chemotherapy (any kind)",
    "V04": "previous systemic anticancer treatment (any kind)",
    "V05": "previous chemotherapy (any kind)",
}

FORBIDDEN = {
    "previous platinum chemotherapy",
    "previous immunotherapy",
}


def load_descriptions() -> dict[str, str]:
    text = PATIENTS_MD.read_text(encoding="utf-8")
    found: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        header = re.match(r"^## (V\d+)\s*$", line)
        if header:
            current = header.group(1)
            found[current] = []
            continue
        if current is None:
            continue
        if line.startswith("## "):
            current = None
            continue
        if line.startswith(">"):
            found[current].append(line[1:].strip())
    return {pid: " ".join(parts) for pid, parts in found.items() if parts}


def main() -> None:
    descriptions = load_descriptions()
    missing = [pid for pid in EXPECTED if pid not in descriptions]
    if missing:
        raise SystemExit(f"missing descriptions: {missing}")
    api_key = load_key()
    rows = []
    input_tokens = output_tokens = 0
    for pid in sorted(EXPECTED):
        row = parse_one(api_key, pid, descriptions[pid])
        traits = (row.get("answer") or {}).get("traits") or []
        names = [canonical_name(t.get("name") or "") for t in traits]
        expected = EXPECTED[pid]
        forbidden_hit = sorted({n for n in names if n in FORBIDDEN})
        row["canonical_names"] = names
        row["expected_therapy_name"] = expected
        row["has_expected_therapy"] = expected in names
        row["forbidden_therapy_names"] = forbidden_hit
        row["safety_valve_parse_ok"] = expected in names and not forbidden_hit
        rows.append(row)
        input_tokens += (row.get("usage") or {}).get("input_tokens") or 0
        output_tokens += (row.get("usage") or {}).get("output_tokens") or 0
        print(
            pid,
            "ok" if row.get("answer") else row.get("error"),
            names,
            flush=True,
        )

    cost = (input_tokens * INPUT_USD_PER_MILLION + output_tokens * OUTPUT_USD_PER_MILLION) / 1_000_000
    report = {
        "model": "gpt-5.4",
        "n_patients": len(rows),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "estimated_usd": round(cost, 4),
        "n_safety_valve_parse_ok": sum(1 for r in rows if r.get("safety_valve_parse_ok")),
        "patients": rows,
    }
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: report[k] for k in report if k != "patients"}, indent=2), flush=True)
    print(f"Wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
