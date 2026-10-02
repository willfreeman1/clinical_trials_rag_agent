"""Lambda Cloud API helpers. Never print the key."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOSTS = (
    "https://cloud.lambda.ai/api/v1",
    "https://cloud.lambdalabs.com/api/v1",
)
CTX = ssl.create_default_context()


def load_lambda_key() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("LAMBDA_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("LAMBDA_API_KEY is missing")


def api(method: str, path: str, key: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    last = None
    for host in HOSTS:
        req = urllib.request.Request(
            host + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (compatible; clinical-trials-rag-agent)",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60, context=CTX) as resp:
                raw = resp.read().decode()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            last = f"Lambda HTTP {exc.code} {host}{path}: {detail}"
            if exc.code not in (403, 404):
                raise SystemExit(last) from exc
    raise SystemExit(last or "Lambda API failed")
