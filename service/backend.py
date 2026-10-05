"""Model backends: replay stored replies, or call a live server.

Replay is the default. It is not a secret. Every response names the mode.
The system does not say a patient qualifies.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable

CompleteFn = Callable[[str, str], str]


class ReplayMiss(KeyError):
    pass


class ReplayComplete:
    """Return the stored raw reply for one patient–trial pair."""

    def __init__(self, raws: dict[tuple[str, str], str]) -> None:
        self.raws = raws
        self.patient_id = ""
        self.nct_id = ""

    def bind(self, patient_id: str, nct_id: str) -> ReplayComplete:
        self.patient_id = patient_id
        self.nct_id = nct_id
        return self

    def __call__(self, system: str, user: str) -> str:
        key = (self.patient_id, self.nct_id)
        if key not in self.raws:
            raise ReplayMiss(f"no stored reader reply for {key}")
        return self.raws[key]


class LiveComplete:
    """POST {system, user} to MODEL_URL and return the text."""

    def __init__(self, url: str, timeout: float = 60.0) -> None:
        self.url = url.rstrip("/")
        self.timeout = timeout

    def __call__(self, system: str, user: str) -> str:
        payload = json.dumps({"system": system, "user": user}).encode("utf-8")
        req = urllib.request.Request(
            self.url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            raise RuntimeError(f"live model HTTP {exc.code}: {detail}") from exc
        except Exception as exc:
            raise RuntimeError(f"live model failed: {exc}") from exc
        text = body.get("text") or body.get("content") or ""
        if not str(text).strip():
            raise RuntimeError("live model returned empty text")
        return str(text)


def mode_from_env() -> str:
    raw = (os.environ.get("MODEL_MODE") or "replay").strip().lower()
    if raw not in ("replay", "live"):
        return "replay"
    return raw


def complete_from_env(raws: dict[tuple[str, str], str]) -> tuple[str, CompleteFn]:
    mode = mode_from_env()
    if mode == "live":
        url = (os.environ.get("MODEL_URL") or "").strip()
        if not url:
            raise RuntimeError("MODEL_MODE=live needs MODEL_URL")
        return mode, LiveComplete(url)
    return mode, ReplayComplete(raws)
