"""Optional observability hooks with a no-op fallback.

When Langfuse env vars are absent, calls are ignored and app behavior is unchanged.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from importlib import import_module
from typing import Any


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class NoopObs:
    enabled: bool = False
    provider: str = "none"
    reason: str = "disabled"

    def start_trace(self, _name: str, input: Any = None, metadata: dict | None = None) -> NoopObs:
        _ = (input, metadata)
        return self

    def start_span(self, _name: str, input: Any = None, metadata: dict | None = None) -> NoopObs:
        _ = (input, metadata)
        return self

    def event(self, _name: str, _metadata: dict | None = None) -> None:
        return None

    def end(self, output: Any = None, metadata: dict | None = None) -> None:
        _ = (output, metadata)
        return None

    def flush(self) -> None:
        return None


class LangfuseObs:
    """Thin wrapper around Langfuse client/trace/span objects."""

    def __init__(self, client: Any, node: Any, kind: str = "trace") -> None:
        self.client = client
        self.node = node
        self.kind = kind
        self.enabled = True
        self.provider = "langfuse"
        self.reason = "enabled"

    def start_trace(self, name: str, input: Any = None, metadata: dict | None = None) -> LangfuseObs:
        trace = self.client.start_observation(
            name=name,
            as_type="chain",
            input=input,
            metadata=metadata or {},
        )
        return LangfuseObs(self.client, trace, kind="trace")

    def start_span(self, name: str, input: Any = None, metadata: dict | None = None) -> LangfuseObs:
        span = self.node.start_observation(
            name=name,
            as_type="span",
            input=input,
            metadata=metadata or {},
        )
        return LangfuseObs(self.client, span, kind="span")

    def event(self, name: str, metadata: dict | None = None) -> None:
        payload = metadata or {}
        # trace/span wrappers expose create_event on Langfuse v2 SDK.
        self.node.create_event(name=name, metadata=payload)

    def end(self, output: Any = None, metadata: dict | None = None) -> None:
        payload = metadata or {}
        # On Langfuse v2 wrappers, output/metadata belong to update(), then end().
        if (output is not None or payload) and hasattr(self.node, "update"):
            kwargs: dict[str, Any] = {}
            if output is not None:
                kwargs["output"] = output
            if payload:
                kwargs["metadata"] = payload
            self.node.update(**kwargs)
        if hasattr(self.node, "end"):
            self.node.end()

    def flush(self) -> None:
        if hasattr(self.client, "flush"):
            self.client.flush()


def obs_from_env() -> NoopObs | LangfuseObs:
    explicit = _truthy(os.environ.get("LANGFUSE_ENABLED"))
    host = (os.environ.get("LANGFUSE_HOST") or "").strip()
    public_key = (os.environ.get("LANGFUSE_PUBLIC_KEY") or "").strip()
    secret_key = (os.environ.get("LANGFUSE_SECRET_KEY") or "").strip()

    if not explicit and not (host and public_key and secret_key):
        return NoopObs(reason="not configured")
    if not (host and public_key and secret_key):
        return NoopObs(reason="missing host/public/secret key")

    try:
        langfuse_mod = import_module("langfuse")
        Langfuse = getattr(langfuse_mod, "Langfuse")
        client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
        return LangfuseObs(client, client, kind="client")
    except Exception as exc:
        return NoopObs(reason=f"init failed: {exc}")
