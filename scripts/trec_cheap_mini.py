"""Hosted gpt-4o-mini cheap pass on the 30-patient sample.

Keep / drop / unsure. Unsure keeps. Title+conditions, then title+conditions+slice.
Concurrent requests. Resumes from cheap_pass_mini.json.
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

from trec_cheap_common import (  # noqa: E402
    DOC_TEXT,
    LLM_SYSTEM,
    MINI_INPUT_USD,
    MINI_MODEL,
    MINI_OUTPUT_USD,
    MINI_SCORES,
    YEARS,
    load_keywords,
    load_sample,
    load_shortlist,
    openai_key,
    parse_llm_decision,
    summary_query,
)
from trec_hybrid_common import SNAPSHOT, YEAR_SNAP, load_docs  # noqa: E402

BATCH = 25
WORKERS = 8
DOC_NAMES = ("title_cond", "title_cond_slice")
LOCK = threading.Lock()


def ask(api_key: str, summary: str, trials: list[dict]) -> tuple[list[dict], dict]:
    lines = [f"Patient's main problems:\n{summary}\n", "Trials:"]
    for row in trials:
        lines.append(f"- {row['nct_id']}: {row['text']}")
    payload = {
        "model": MINI_MODEL,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": LLM_SYSTEM},
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
            rows = content.get("decisions") or content.get("scores") or []
            return rows, usage
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            last = exc
            wait = 20 if isinstance(exc, urllib.error.HTTPError) and exc.code == 429 else 2 ** min(attempt, 5)
            print(f"retry {attempt} {type(exc).__name__} sleep {wait}", flush=True)
            time.sleep(wait)
    raise SystemExit(f"mini cheap pass failed: {last}")


def save(decisions: dict, usage_in: int, usage_out: int, seconds: float) -> dict:
    payload = {
        "model": MINI_MODEL,
        "input_tokens": usage_in,
        "completion_tokens": usage_out,
        "usd": round(
            usage_in / 1_000_000 * MINI_INPUT_USD
            + usage_out / 1_000_000 * MINI_OUTPUT_USD,
            4,
        ),
        "seconds": round(seconds, 1),
        "decisions": decisions,
    }
    tmp = MINI_SCORES.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(MINI_SCORES)
    return payload


def one_batch(api_key, summary, batch_ids, docs, fn):
    trials = [{"nct_id": nct, "text": fn(docs.get(nct) or {})} for nct in batch_ids]
    return batch_ids, ask(api_key, summary, trials)


def main() -> None:
    sample = load_sample()
    short = load_shortlist()
    keywords = load_keywords()
    existing = {}
    if MINI_SCORES.exists():
        existing = json.loads(MINI_SCORES.read_text(encoding="utf-8"))
    decisions = existing.setdefault("decisions", {})
    usage_in = int(existing.get("input_tokens") or 0)
    usage_out = int(existing.get("completion_tokens") or 0)
    seconds = float(existing.get("seconds") or 0)
    api_key = openai_key()
    started = time.time()
    print("loading docs", flush=True)
    docs_by_year = {year: load_docs(SNAPSHOT[YEAR_SNAP[year]]["docs"]) for year in YEARS}
    print("docs loaded", flush=True)
    for doc_name in DOC_NAMES:
        fn = DOC_TEXT[doc_name]
        for year in YEARS:
            y = str(year)
            docs = docs_by_year[year]
            year_kw = keywords.get(y, {})
            topics = short["years"][y]["topics"]
            for tid in sample["years"][y]:
                bucket = (
                    decisions.setdefault(doc_name, {})
                    .setdefault(y, {})
                    .setdefault(tid, {})
                )
                trow = topics[tid]
                needed = [nct for nct in trow["shortlist"] if nct not in bucket]
                if not needed:
                    print(f"skip {doc_name} {y} {tid} already {len(bucket)}", flush=True)
                    continue
                summary = summary_query(year_kw.get(tid) or {})
                batches = [needed[i : i + BATCH] for i in range(0, len(needed), BATCH)]
                with ThreadPoolExecutor(max_workers=WORKERS) as pool:
                    futs = [
                        pool.submit(one_batch, api_key, summary, batch_ids, docs, fn)
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
                                raw = rec.get("decision") or rec.get("score") or rec.get("label")
                                bucket[nct] = parse_llm_decision(raw)
                        done += 1
                        if done == 1 or done % 8 == 0:
                            print(
                                f"{doc_name} {y} {tid} batches {done}/{len(batches)}",
                                flush=True,
                            )
                elapsed = seconds + (time.time() - started)
                payload = save(decisions, usage_in, usage_out, elapsed)
                print(
                    f"{doc_name} {y} {tid} {len(bucket)}/{len(trow['shortlist'])} ${payload['usd']}",
                    flush=True,
                )
    elapsed = seconds + (time.time() - started)
    payload = save(decisions, usage_in, usage_out, elapsed)
    print(f"wrote {MINI_SCORES} usd {payload['usd']} {elapsed:.1f}s", flush=True)


if __name__ == "__main__":
    main()
