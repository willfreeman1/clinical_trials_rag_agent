"""Cheap topical-relevance scores on 2021 top 200. Raw note. Not eligibility."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mini_pilot import load_key  # noqa: E402
from trec_hybrid_common import SNAPSHOT, YEAR_SNAP, load_docs  # noqa: E402
from trec_rerank_common import (  # noqa: E402
    DATA,
    LLM_DEPTH,
    LLM_MODEL,
    LLM_SCORES,
    LLM_YEAR,
    SHORTLIST,
    trial_article,
)

SYSTEM = """You score how topically related a clinical-trial record is to a patient description.

This is not an eligibility decision. Do not say whether the patient can join the trial.
Score only whether the trial is about a disease, procedure, or situation that appears in the description.

Return only JSON: {"scores": [{"nct_id": "...", "score": 0}, ...]}
score is an integer 0, 1, 2, or 3.
0 = unrelated
1 = weakly related
2 = same disease area or a listed problem
3 = clearly about the main problem in the description"""

BATCH = 15
INPUT_USD = 0.15
OUTPUT_USD = 0.60


def ask(api_key: str, note: str, trials: list[dict]) -> list[dict]:
    lines = [f"Patient description:\n{note}\n", "Trials:"]
    for row in trials:
        text = trial_article(row)[:1200]
        lines.append(f"- {row['nct_id']}: {text}")
    payload = {
        "model": LLM_MODEL,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "\n".join(lines)},
        ],
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    last = None
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                body = json.loads(resp.read().decode())
            content = json.loads(body["choices"][0]["message"]["content"])
            usage = body.get("usage") or {}
            return content.get("scores") or [], usage
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            time.sleep(2 ** min(attempt, 5))
    raise SystemExit(f"llm score failed: {last}")


def main() -> None:
    short = json.loads(SHORTLIST.read_text(encoding="utf-8"))
    year = str(LLM_YEAR)
    docs = load_docs(SNAPSHOT[YEAR_SNAP[LLM_YEAR]]["docs"])
    topics = short["years"][year]["topics"]
    existing = {}
    if LLM_SCORES.exists():
        existing = json.loads(LLM_SCORES.read_text(encoding="utf-8"))
    scores = existing.setdefault("scores", {})
    usage_in = existing.get("input_tokens", 0)
    usage_out = existing.get("output_tokens", 0)
    api_key = load_key()
    for tid, trow in topics.items():
        bucket = scores.setdefault(tid, {})
        needed = [nct for nct in trow["shortlist"][:LLM_DEPTH] if nct not in bucket]
        if not needed:
            continue
        note = trow["raw_query"]
        for i in range(0, len(needed), BATCH):
            batch_ids = needed[i : i + BATCH]
            trials = []
            for nct in batch_ids:
                row = docs.get(nct) or {}
                trials.append(
                    {
                        "nct_id": nct,
                        "title": row.get("title") or "",
                        "text": row.get("text") or "",
                    }
                )
            rows, usage = ask(api_key, note, trials)
            usage_in += int(usage.get("prompt_tokens") or 0)
            usage_out += int(usage.get("completion_tokens") or 0)
            by_id = {str(r.get("nct_id")): r for r in rows if isinstance(r, dict)}
            for nct in batch_ids:
                rec = by_id.get(nct) or {}
                try:
                    val = int(rec.get("score"))
                except (TypeError, ValueError):
                    val = 0
                bucket[nct] = max(0, min(3, val))
            print(f"  2021 topic {tid} {min(i + BATCH, len(needed))}/{len(needed)}", flush=True)
        existing["scores"] = scores
        existing["input_tokens"] = usage_in
        existing["output_tokens"] = usage_out
        existing["model"] = LLM_MODEL
        existing["usd"] = (usage_in * INPUT_USD + usage_out * OUTPUT_USD) / 1_000_000
        LLM_SCORES.write_text(json.dumps(existing), encoding="utf-8")
    existing["thresholds_commit"] = "44878a7"
    existing["year"] = LLM_YEAR
    existing["depth"] = LLM_DEPTH
    existing["query"] = "raw"
    existing["usd"] = (usage_in * INPUT_USD + usage_out * OUTPUT_USD) / 1_000_000
    LLM_SCORES.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    print(f"wrote {LLM_SCORES} usd {existing['usd']:.2f}", flush=True)


if __name__ == "__main__":
    main()
