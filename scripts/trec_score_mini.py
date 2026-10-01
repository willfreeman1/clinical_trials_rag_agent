"""Extend gpt-4o-mini topical scores to the full shortlist, both years.

Same SYSTEM and trial_article[:1200] as scripts/trec_rerank_llm.py.
Reuses the existing 2021 top-200 scores. Gates: 114cce7.
"""

from __future__ import annotations

import json
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mini_pilot import load_key  # noqa: E402
from trec_hybrid_common import SNAPSHOT, YEAR_SNAP, load_docs  # noqa: E402
from trec_rerank_common import trial_article  # noqa: E402
from trec_score_common import (  # noqa: E402
    MINI_ARTICLE_CHARS,
    MINI_INPUT_USD,
    MINI_MODEL,
    MINI_OUTPUT_USD,
    MINI_SCORES,
    OLD_MINI,
    THRESHOLDS_COMMIT,
    TOPICAL_SYSTEM,
    YEARS,
    load_shortlist,
)

BATCH = 15
WORKERS = 8
LOCK = threading.Lock()


def ask(api_key: str, note: str, trials: list[dict]) -> tuple[list[dict], dict]:
    lines = [f"Patient description:\n{note}\n", "Trials:"]
    for row in trials:
        text = trial_article(row)[:MINI_ARTICLE_CHARS]
        lines.append(f"- {row['nct_id']}: {text}")
    payload = {
        "model": MINI_MODEL,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": TOPICAL_SYSTEM},
            {"role": "user", "content": "\n".join(lines)},
        ],
    }
    last = None
    for attempt in range(6):
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                body = json.loads(resp.read().decode())
            content = json.loads(body["choices"][0]["message"]["content"])
            usage = body.get("usage") or {}
            return content.get("scores") or [], usage
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            last = exc
            wait = 20 if isinstance(exc, urllib.error.HTTPError) and exc.code == 429 else 2 ** min(attempt, 5)
            print(f"retry {attempt} {type(exc).__name__} sleep {wait}", flush=True)
            time.sleep(wait)
    raise SystemExit(f"mini full shortlist failed: {last}")


def save(scores: dict, usage_in: int, usage_out: int, seconds: float, reused: int) -> dict:
    payload = {
        "thresholds_commit": THRESHOLDS_COMMIT,
        "model": MINI_MODEL,
        "query": "raw",
        "document": "trial_article_1200",
        "input_tokens": usage_in,
        "completion_tokens": usage_out,
        "usd": round(
            usage_in / 1_000_000 * MINI_INPUT_USD
            + usage_out / 1_000_000 * MINI_OUTPUT_USD,
            4,
        ),
        "seconds": round(seconds, 1),
        "reused_2021_top200": reused,
        "scores": scores,
    }
    tmp = MINI_SCORES.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(MINI_SCORES)
    return payload


def one_batch(api_key, note, batch_ids, docs):
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
    return batch_ids, ask(api_key, note, trials)


def seed_old_scores(scores: dict) -> int:
    if not OLD_MINI.exists():
        return 0
    old = json.loads(OLD_MINI.read_text(encoding="utf-8"))
    reused = 0
    year_bucket = scores.setdefault("2021", {})
    for tid, bucket in (old.get("scores") or {}).items():
        dest = year_bucket.setdefault(str(tid), {})
        for nct, val in bucket.items():
            if nct in dest:
                continue
            try:
                dest[nct] = max(0, min(3, int(val)))
                reused += 1
            except (TypeError, ValueError):
                continue
    return reused


def main() -> None:
    short = load_shortlist()
    existing = {}
    if MINI_SCORES.exists():
        existing = json.loads(MINI_SCORES.read_text(encoding="utf-8"))
    scores = existing.setdefault("scores", {})
    usage_in = int(existing.get("input_tokens") or 0)
    usage_out = int(existing.get("completion_tokens") or 0)
    seconds = float(existing.get("seconds") or 0)
    reused = seed_old_scores(scores)
    api_key = load_key()
    started = time.time()
    print("loading docs", flush=True)
    docs_by_year = {year: load_docs(SNAPSHOT[YEAR_SNAP[year]]["docs"]) for year in YEARS}
    print(f"docs loaded reused {reused}", flush=True)
    for year in YEARS:
        y = str(year)
        docs = docs_by_year[year]
        topics = short["years"][y]["topics"]
        for tid, trow in topics.items():
            bucket = scores.setdefault(y, {}).setdefault(tid, {})
            needed = [nct for nct in trow["shortlist"] if nct not in bucket]
            if not needed:
                print(f"skip {y} {tid} already {len(bucket)}", flush=True)
                continue
            note = trow["raw_query"]
            batches = [needed[i : i + BATCH] for i in range(0, len(needed), BATCH)]
            with ThreadPoolExecutor(max_workers=WORKERS) as pool:
                futs = [
                    pool.submit(one_batch, api_key, note, batch_ids, docs)
                    for batch_ids in batches
                ]
                done = 0
                for fut in as_completed(futs):
                    batch_ids, (rows, usage) = fut.result()
                    by_id = {str(r.get("nct_id")): r for r in rows if isinstance(r, dict)}
                    with LOCK:
                        usage_in += int(usage.get("prompt_tokens") or 0)
                        usage_out += int(usage.get("completion_tokens") or 0)
                        for nct in batch_ids:
                            rec = by_id.get(nct) or {}
                            try:
                                val = int(rec.get("score"))
                            except (TypeError, ValueError):
                                val = 0
                            bucket[nct] = max(0, min(3, val))
                    done += 1
                    if done == 1 or done % 8 == 0:
                        print(f"{y} {tid} batches {done}/{len(batches)}", flush=True)
            elapsed = seconds + (time.time() - started)
            payload = save(scores, usage_in, usage_out, elapsed, reused)
            print(
                f"{y} {tid} {len(bucket)}/{len(trow['shortlist'])} ${payload['usd']}",
                flush=True,
            )
    elapsed = seconds + (time.time() - started)
    payload = save(scores, usage_in, usage_out, elapsed, reused)
    n = sum(len(t) for y in scores.values() for t in y.values())
    print(f"wrote {MINI_SCORES} n={n} usd {payload['usd']} {elapsed:.1f}s", flush=True)


if __name__ == "__main__":
    main()
