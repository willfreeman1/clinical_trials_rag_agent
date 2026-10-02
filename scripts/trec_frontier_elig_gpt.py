"""Score the 411 pairs with GPT-5.4 on v1 and the TREC prompt. Resume-safe."""

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
from trec_frontier_elig_common import (  # noqa: E402
    GPT_INPUT_USD,
    GPT_MODEL,
    GPT_OUTPUT_USD,
    GPT_SCORES,
    TREC_SYSTEM,
    V1_SYSTEM,
    full_criteria,
    load_pairs,
    pair_rows,
    user_text,
)
from trec_score_common import PACK  # noqa: E402

WORKERS = 6
PAIRS_COMMIT = "99f795c"
DIGIT_RE = re.compile(r"[0-3]")
ARMS = ("v1", "trec")


def load_pack() -> dict:
    return json.loads(PACK.read_text(encoding="utf-8"))


def load_payload() -> dict:
    if GPT_SCORES.exists():
        return json.loads(GPT_SCORES.read_text(encoding="utf-8"))
    return {
        "pairs_commit": PAIRS_COMMIT,
        "model": GPT_MODEL,
        "input_tokens": 0,
        "output_tokens": 0,
        "usd": 0.0,
        "arms": {"v1": {}, "trec": {}},
        "logprobs_ok": None,
        "errors": 0,
    }


def save_payload(payload: dict) -> None:
    GPT_SCORES.parent.mkdir(parents=True, exist_ok=True)
    tmp = GPT_SCORES.with_suffix(".json.tmp")
    cost = (
        (payload.get("input_tokens") or 0) * GPT_INPUT_USD
        + (payload.get("output_tokens") or 0) * GPT_OUTPUT_USD
    ) / 1_000_000
    payload["usd"] = round(cost, 4)
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(GPT_SCORES)


def have(payload: dict, arm: str, year: str, tid: str, nct: str) -> bool:
    return nct in ((payload.get("arms") or {}).get(arm) or {}).get(year, {}).get(tid, {})


def call(api_key: str, system: str, user: str, *, json_mode: bool, want_logprobs: bool) -> dict:
    payload: dict = {
        "model": GPT_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
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


def parse_v1(text: str) -> int | None:
    m = DIGIT_RE.search(text or "")
    return int(m.group()) if m else None


def parse_trec(text: str) -> tuple[int | None, float | None]:
    try:
        rec = json.loads(text)
    except json.JSONDecodeError:
        return None, None
    lab = rec.get("label")
    p = rec.get("p_eligible")
    try:
        lab_i = int(lab)
    except (TypeError, ValueError):
        lab_i = None
    if lab_i not in (0, 1, 2):
        lab_i = None
    try:
        p_f = float(p)
    except (TypeError, ValueError):
        p_f = None
    if p_f is not None:
        p_f = max(0.0, min(1.0, p_f))
    return lab_i, p_f


def score_one(api_key: str, arm: str, user: str, try_logprobs: bool) -> dict:
    last = "unknown"
    for attempt in range(5):
        try:
            body = call(
                api_key,
                V1_SYSTEM if arm == "v1" else TREC_SYSTEM,
                user,
                json_mode=(arm == "trec"),
                want_logprobs=(arm == "v1" and try_logprobs),
            )
            choice = (body.get("choices") or [{}])[0]
            text = ((choice.get("message") or {}).get("content") or "").strip()
            usage = body.get("usage") or {}
            rec: dict = {
                "text": text[:500],
                "in": usage.get("prompt_tokens") or 0,
                "out": usage.get("completion_tokens") or 0,
            }
            if arm == "v1":
                rec["digit"] = parse_v1(text)
                rec["logprobs"] = bool(choice.get("logprobs"))
                probs, cont = digit_from_logprobs(choice.get("logprobs"))
                if probs is not None:
                    rec["p_digits"] = probs
                    rec["cont"] = cont
            else:
                lab, p = parse_trec(text)
                rec["label"] = lab
                rec["p_eligible"] = p
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
    return {"error": last, "in": 0, "out": 0}


def main() -> None:
    key = load_key()
    pack = load_pack()
    docs = pack["docs"]
    pairs = load_pairs()
    rows = pair_rows(pairs)
    payload = load_payload()
    jobs = []
    for arm in ARMS:
        for row in rows:
            if have(payload, arm, row["year"], row["topic"], row["nct"]):
                continue
            trow = pack["years"][row["year"]]["topics"][row["topic"]]
            note = trow.get("raw_query") or " "
            user = user_text(note, full_criteria(docs.get(row["nct"]) or {}))
            jobs.append((arm, row, user))
    print(f"todo {len(jobs)} already {411 * 2 - len(jobs)}", flush=True)
    try_logprobs = payload.get("logprobs_ok") is not False
    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futs = {
            pool.submit(score_one, key, arm, user, try_logprobs): (arm, row)
            for arm, row, user in jobs
        }
        for fut in as_completed(futs):
            arm, row = futs[fut]
            rec = fut.result()
            year_b = payload["arms"].setdefault(arm, {}).setdefault(row["year"], {})
            topic_b = year_b.setdefault(row["topic"], {})
            topic_b[row["nct"]] = rec
            payload["input_tokens"] = int(payload.get("input_tokens") or 0) + int(rec.get("in") or 0)
            payload["output_tokens"] = int(payload.get("output_tokens") or 0) + int(rec.get("out") or 0)
            if rec.get("error"):
                payload["errors"] = int(payload.get("errors") or 0) + 1
            if arm == "v1" and rec.get("logprobs") is True:
                payload["logprobs_ok"] = True
            elif arm == "v1" and rec.get("logprobs") is False and payload.get("logprobs_ok") is None:
                payload["logprobs_ok"] = False
            done += 1
            if done % 20 == 0 or done == len(jobs):
                save_payload(payload)
                print(
                    f"  {done}/{len(jobs)} usd {payload['usd']} err {payload.get('errors')}",
                    flush=True,
                )
    save_payload(payload)
    print(
        f"wrote {GPT_SCORES} usd {payload['usd']} in {payload['input_tokens']} "
        f"out {payload['output_tokens']} logprobs {payload.get('logprobs_ok')}",
        flush=True,
    )


if __name__ == "__main__":
    main()
