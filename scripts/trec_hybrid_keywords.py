"""LLM search-keyword generation. Patient note only. No trial text.

Fresh prompt: search terms, not fact extraction. Gates in 613635e.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mini_pilot import load_key  # noqa: E402
from trec_hybrid_common import DATA, KEYWORD_MODEL, YEARS, load_topics  # noqa: E402

OUT = DATA / "keywords.json"
SYSTEM = """You write search terms that would find matching clinical trials in a public registry.

Read the patient description. Write a one-sentence summary of the main medical problems. Then list up to 32 search keywords, most important first.

Each keyword is a short phrase a trial record might use for a disease, condition, procedure, finding, or drug that is in the description. Do not invent diagnoses, drugs, or history that the description does not state. Do not write inclusion or exclusion rules. Do not write directions or values for matching.

Return only JSON with keys summary (string) and keywords (array of strings)."""


def ask(api_key: str, note: str) -> dict:
    payload = {
        "model": KEYWORD_MODEL,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Patient description:\n{note}"},
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
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode())
            content = body["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            kws = parsed.get("keywords") or parsed.get("conditions") or []
            kws = [str(k).strip() for k in kws if str(k).strip()]
            return {
                "summary": str(parsed.get("summary") or ""),
                "keywords": kws[:32],
                "model": KEYWORD_MODEL,
            }
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
            time.sleep(2 ** attempt)
    raise SystemExit(f"keyword call failed: {last}")


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    existing = {}
    if OUT.exists():
        existing = json.loads(OUT.read_text(encoding="utf-8"))
    api_key = load_key()
    for year in YEARS:
        topics = load_topics(year)
        bucket = existing.setdefault(str(year), {})
        for tid, note in topics.items():
            if tid in bucket and bucket[tid].get("keywords"):
                continue
            print(f"keywords {year} topic {tid}", flush=True)
            bucket[tid] = ask(api_key, note)
            OUT.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    n = sum(len(v) for v in existing.values())
    print(f"wrote {OUT} topics={n}")


if __name__ == "__main__":
    main()
