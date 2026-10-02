"""UMLS REST helpers. Phrase → CUI; ancestors for is-a. No model-emitted identifiers."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from threading import Lock

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "umls_api_cache.json"
BASE = "https://uts-ws.nlm.nih.gov/rest"
SABS = "SNOMEDCT_US,RXNORM,MSH"
SLEEP = 0.05
CACHE_LOCK = Lock()


def load_umls_key() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("UMLS_API_KEY=") or line.startswith("UTS_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(
        "UMLS_API_KEY is missing from .env. Add the UTS API key from "
        "https://uts.nlm.nih.gov/uts/edit-profile (API key tab). "
        "Do not download the Metathesaurus for this run."
    )


def load_cache() -> dict:
    if CACHE.exists():
        data = json.loads(CACHE.read_text(encoding="utf-8"))
        data.setdefault("search", {})
        data.setdefault("ancestors", {})
        data.setdefault("hits", {})
        data.setdefault("names", {})
        return data
    return {"search": {}, "ancestors": {}, "hits": {}, "names": {}}


def save_cache(cache: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with CACHE_LOCK:
        CACHE.write_text(json.dumps(cache), encoding="utf-8")


def _get(url: str) -> dict | None:
    req = urllib.request.Request(url, headers={"User-Agent": "clinical-trials-rag-agent"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (429, 500, 502, 503):
            return None
        if exc.code == 404:
            return {"result": None}
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise SystemExit(f"UMLS HTTP {exc.code}: {detail}") from exc


def search_cui(api_key: str, phrase: str, cache: dict) -> str | None:
    key = (phrase or "").strip()
    if not key:
        return None
    if key in cache["search"]:
        return cache["search"][key]
    params = {
        "string": key[:300],
        "sabs": SABS,
        "returnIdType": "concept",
        "pageSize": "3",
        "apiKey": api_key,
    }
    url = BASE + "/search/current?" + urllib.parse.urlencode(params)
    time.sleep(SLEEP)
    body = _get(url)
    if body is None:
        time.sleep(2)
        body = _get(url)
    cui = None
    results = ((body or {}).get("result") or {}).get("results") or []
    for row in results:
        if row.get("ui") and row.get("ui") != "NONE":
            cui = row["ui"]
            break
    cache["search"][key] = cui
    if cui and results:
        name = results[0].get("name") if results[0].get("ui") == cui else None
        if not name:
            for row in results:
                if row.get("ui") == cui:
                    name = row.get("name")
                    break
        cache["hits"][key] = {"cui": cui, "name": name}
        if name:
            cache["names"][cui] = name
    else:
        cache["hits"][key] = {"cui": None, "name": None}
    return cui


def search_hit(api_key: str, phrase: str, cache: dict) -> dict:
    key = (phrase or "").strip()
    if key in cache.get("hits", {}):
        return cache["hits"][key]
    cui = search_cui(api_key, phrase, cache)
    if key in cache.get("hits", {}):
        return cache["hits"][key]
    name = None
    if cui:
        name = cache.get("names", {}).get(cui) or concept_name(api_key, cui, cache)
    hit = {"cui": cui, "name": name}
    cache.setdefault("hits", {})[key] = hit
    return hit


def concept_name(api_key: str, cui: str, cache: dict) -> str | None:
    if not cui:
        return None
    cache.setdefault("names", {})
    if cui in cache["names"]:
        return cache["names"][cui]
    params = {"apiKey": api_key}
    url = BASE + f"/content/current/CUI/{urllib.parse.quote(cui)}?" + urllib.parse.urlencode(params)
    time.sleep(SLEEP)
    body = _get(url)
    name = ((body or {}).get("result") or {}).get("name")
    cache["names"][cui] = name
    return name


def ancestors(api_key: str, cui: str, cache: dict) -> set[str]:
    if not cui:
        return set()
    if cui in cache["ancestors"]:
        return set(cache["ancestors"][cui])
    out: set[str] = set()
    page = 1
    while page <= 20:
        params = {
            "pageNumber": str(page),
            "pageSize": "100",
            "includeRelationLabels": "RB,PAR",
            "apiKey": api_key,
        }
        url = BASE + f"/content/current/CUI/{urllib.parse.quote(cui)}/relations?" + urllib.parse.urlencode(params)
        time.sleep(SLEEP)
        body = _get(url)
        if body is None:
            time.sleep(2)
            body = _get(url)
        recs = ((body or {}).get("result") or [])
        if not recs:
            break
        for rec in recs:
            related = rec.get("relatedId") or rec.get("ui") or ""
            # relatedId often a URI ending in C#######
            if "C" in related:
                token = related.rstrip("/").split("/")[-1]
                if token.startswith("C") and token[1:].isdigit():
                    out.add(token)
        if len(recs) < 100:
            break
        page += 1
    cache["ancestors"][cui] = sorted(out)
    return out


def comparison(patient_cui: str | None, trial_cui: str | None, anc: dict[str, set[str]]) -> str:
    """Same direction rule as therapy_containment.comparison."""
    if not patient_cui or not trial_cui:
        return "miss"
    if patient_cui == trial_cui:
        return "match"
    if trial_cui in anc.get(patient_cui, set()):
        return "match"
    if patient_cui in anc.get(trial_cui, set()):
        return "cant_tell"
    return "no_match"
