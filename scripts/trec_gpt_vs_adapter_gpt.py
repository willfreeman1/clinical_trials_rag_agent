"""Score the locked 2022 pairs with GPT-5.4, v1 prompt only. Resume-safe.

Stops if spend reaches $20. Reuses stored v1 scores from the 411-pair run
when the topic and trial match. The system does not say a patient qualifies.
"""

from __future__ import annotations

import json
import math
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mini_pilot import load_key  # noqa: E402
from trec_frontier_elig_common import full_criteria, user_text  # noqa: E402
from trec_gpt_vs_adapter_common import (  # noqa: E402
    GPT_INPUT_USD,
    GPT_MODEL,
    GPT_OUTPUT_USD,
    GPT_SCORES,
    OLD_GPT,
    PAIRS,
    SPEND_CAP_USD,
    V1_SYSTEM,
    pair_rows,
)
from trec_score_common import PACK  # noqa: E402

WORKERS = 6
DIGIT_RE = re.compile(r"[0-3]")


def load_pack() -> dict:
    return json.loads(PACK.read_text(encoding="utf-8"))


def load_payload() -> dict:
    if GPT_SCORES.exists():
        return json.loads(GPT_SCORES.read_text(encoding="utf-8"))
    return {
        "model": GPT_MODEL,
        "prompt": "v1_ELIG_SYSTEM_DIGIT",
        "pairs": str(PAIRS),
        "input_tokens": 0,
        "output_tokens": 0,
        "usd": 0.0,
        "reused": 0,
        "errors": 0,
        "logprobs_ok": None,
        "scores": {"2022": {}},
    }


def save_payload(payload: dict) -> None:
    GPT_SCORES.parent.mkdir(parents=True, exist_ok=True)
    cost = (
        (payload.get("input_tokens") or 0) * GPT_INPUT_USD
        + (payload.get("output_tokens") or 0) * GPT_OUTPUT_USD
    ) / 1_000_000
    payload["usd"] = round(cost, 4)
    tmp = GPT_SCORES.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(GPT_SCORES)


def have(payload: dict, tid: str, nct: str) -> bool:
    rec = ((payload.get("scores") or {}).get("2022") or {}).get(tid, {}).get(nct)
    return bool(rec) and not rec.get("error")


def reused_v1() -> dict[tuple[str, str], dict]:
    if not OLD_GPT.exists():
        return {}
    old = json.loads(OLD_GPT.read_text(encoding="utf-8"))
    block = ((old.get("arms") or {}).get("v1") or {}).get("2022") or {}
    out = {}
    for tid, trials in block.items():
        for nct, rec in trials.items():
            if rec.get("error"):
                continue
            if rec.get("cont") is None and rec.get("digit") is None:
                continue
            out[(str(tid), nct)] = {
                "digit": rec.get("digit"),
                "cont": rec.get("cont"),
                "p_digits": rec.get("p_digits"),
                "logprobs": rec.get("logprobs"),
                "text": rec.get("text"),
                "reused": True,
                "in": 0,
                "out": 0,
            }
    return out


def call(api_key: str, user: str, want_logprobs: bool) -> dict:
    payload: dict = {
        "model": GPT_MODEL,
        "messages": [
            {"role": "system", "content": V1_SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    if want_logprobs:
        payload["logprobs"] = True
        payload["top_logprobs"] = 5
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def digit_from_logprobs(logprobs: dict | None) -> tuple[list[float] | None, float | None]:
    content = (logprobs or {}).get("content") or []
    if not content:
        return None, None
    raw: dict[int, float] = {}
    for item in content[0].get("top_logprobs") or []:
        tok = (item.get("token") or "").strip()
        if tok in {"0", "1", "2", "3"}:
            raw[int(tok)] = math.exp(float(item.get("logprob") or -99))
    if not raw:
        return None, None
    z = sum(raw.values())
    probs = [raw.get(i, 0.0) / z for i in range(4)]
    return [round(p, 6) for p in probs], round(sum(i * p for i, p in enumerate(probs)), 4)


def score_one(api_key: str, user: str, try_logprobs: bool) -> dict:
    last = "unknown"
    for attempt in range(5):
        try:
            body = call(api_key, user, try_logprobs)
            choice = (body.get("choices") or [{}])[0]
            text = ((choice.get("message") or {}).get("content") or "").strip()
            usage = body.get("usage") or {}
            digit = int(m.group()) if (m := DIGIT_RE.search(text or "")) else None
            rec: dict = {
                "text": text[:500],
                "digit": digit,
                "in": usage.get("prompt_tokens") or 0,
                "out": usage.get("completion_tokens") or 0,
                "logprobs": bool(choice.get("logprobs")),
                "reused": False,
            }
            probs, cont = digit_from_logprobs(choice.get("logprobs"))
            if probs is not None:
                rec["p_digits"] = probs
                rec["cont"] = cont
            return rec
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            last = f"HTTP {exc.code}: {detail}"
            if exc.code == 400 and try_logprobs and "logprob" in detail.lower():
                try_logprobs = False
                continue
            if exc.code not in (400, 429, 500, 502, 503):
                break
            time.sleep(min(30, 2 ** attempt))
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
            time.sleep(min(30, 2 ** attempt))
    return {"error": last, "in": 0, "out": 0, "reused": False}


def main() -> None:
    if not PAIRS.exists():
        raise SystemExit(f"missing {PAIRS}; run trec_gpt_vs_adapter_draw.py")
    key = load_key()
    pack = load_pack()
    docs = pack["docs"]
    rows = pair_rows()
    payload = load_payload()
    cached = reused_v1()
    for row in rows:
        tid, nct = row["topic"], row["nct"]
        if have(payload, tid, nct):
            continue
        old = cached.get((tid, nct))
        if old:
            payload["scores"]["2022"].setdefault(tid, {})[nct] = old
            payload["reused"] = int(payload.get("reused") or 0) + 1
    save_payload(payload)

    jobs = []
    missing_doc = 0
    for row in rows:
        tid, nct = row["topic"], row["nct"]
        if have(payload, tid, nct):
            continue
        doc = docs.get(nct)
        if not doc:
            missing_doc += 1
            payload["scores"]["2022"].setdefault(tid, {})[nct] = {
                "error": "missing pack doc",
                "in": 0,
                "out": 0,
            }
            payload["errors"] = int(payload.get("errors") or 0) + 1
            continue
        trow = pack["years"]["2022"]["topics"][tid]
        note = trow.get("raw_query") or " "
        jobs.append((row, user_text(note, full_criteria(doc))))
    if missing_doc:
        print(f"missing pack docs {missing_doc}", flush=True)
    print(
        f"todo {len(jobs)} reused {payload.get('reused')} already "
        f"{len(rows) - len(jobs) - missing_doc} cap ${SPEND_CAP_USD}",
        flush=True,
    )
    try_logprobs = payload.get("logprobs_ok") is not False
    done = 0
    stopped = False
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = {pool.submit(score_one, key, user, try_logprobs): row for row, user in jobs}
        for fut in as_completed(futs):
            row = futs[fut]
            rec = fut.result()
            payload["scores"]["2022"].setdefault(row["topic"], {})[row["nct"]] = rec
            payload["input_tokens"] = int(payload.get("input_tokens") or 0) + int(rec.get("in") or 0)
            payload["output_tokens"] = int(payload.get("output_tokens") or 0) + int(rec.get("out") or 0)
            if rec.get("error"):
                payload["errors"] = int(payload.get("errors") or 0) + 1
            if rec.get("logprobs") is True:
                payload["logprobs_ok"] = True
            elif rec.get("logprobs") is False and payload.get("logprobs_ok") is None:
                payload["logprobs_ok"] = False
            done += 1
            if done % 25 == 0 or done == len(jobs):
                save_payload(payload)
                print(
                    f"  {done}/{len(jobs)} usd {payload['usd']} err {payload.get('errors')}",
                    flush=True,
                )
            cost = (
                (payload.get("input_tokens") or 0) * GPT_INPUT_USD
                + (payload.get("output_tokens") or 0) * GPT_OUTPUT_USD
            ) / 1_000_000
            if cost >= SPEND_CAP_USD:
                stopped = True
                break
    save_payload(payload)
    n_ok = sum(
        1
        for tid in payload["scores"]["2022"].values()
        for rec in tid.values()
        if not rec.get("error")
    )
    print(
        f"wrote {GPT_SCORES} usd {payload['usd']} ok {n_ok}/{len(rows)} "
        f"reused {payload.get('reused')} err {payload.get('errors')} "
        f"stopped_at_cap {stopped}",
        flush=True,
    )
    if stopped:
        raise SystemExit("spend cap reached; remaining pairs left for a later ask")


if __name__ == "__main__":
    main()
