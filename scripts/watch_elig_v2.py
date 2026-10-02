"""Poll the v2 eligibility GPU job. Print a heartbeat; exit 2 on crash."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SSH_KEY = Path.home() / ".ssh" / "lambda_key"
STATE = Path(__file__).resolve().parents[1] / "data" / "trec" / "elig_v2_lambda_state.json"
LOCAL = Path(__file__).resolve().parents[1] / "data" / "trec" / "score_qwen_elig_v2.json"
REMOTE = "ubuntu"
BAD = (
    "Traceback",
    "CUDA out of memory",
    "OutOfMemoryError",
    "RuntimeError",
    "Killed",
)


def ip_from_state() -> str:
    if not STATE.exists():
        raise SystemExit(f"missing {STATE}")
    rec = json.loads(STATE.read_text(encoding="utf-8"))
    ip = rec.get("ip")
    if not ip:
        raise SystemExit("no ip in state yet")
    return ip


def ssh(ip: str, cmd: str) -> str:
    out = subprocess.run(
        [
            "ssh",
            "-i",
            str(SSH_KEY),
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            "ConnectTimeout=20",
            f"{REMOTE}@{ip}",
            cmd,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    return (out.stdout or "") + (out.stderr or "")


def main() -> None:
    ip = ip_from_state()
    text = ssh(
        ip,
        "echo PROGRESS; cat /tmp/qwen_progress.txt 2>/dev/null; "
        "echo GPU; nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total "
        "--format=csv,noheader; "
        "echo LOG; tail -n 8 /tmp/qwen_score.log 2>/dev/null; "
        "echo PROC; pgrep -af 'lambda_qwen_elig_v2.py' || echo PROC_MISSING; "
        "echo DONE; test -f /tmp/qwen_score.done && echo YES || echo NO",
    )
    print(text)
    if "PROC_MISSING" in text and "YES" not in text.split("DONE", 1)[-1]:
        print("process missing", flush=True)
        sys.exit(2)
    for token in BAD:
        if token in text and "oom, batch now" not in text:
            print(f"bad token {token}", flush=True)
            sys.exit(2)
    if LOCAL.exists():
        print(f"local scores {LOCAL.stat().st_size} bytes", flush=True)


if __name__ == "__main__":
    main()
