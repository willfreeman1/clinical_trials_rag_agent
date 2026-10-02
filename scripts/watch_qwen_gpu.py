"""Poll the Lambda Qwen job. Print a heartbeat; exit 2 on crash/OOM."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

SSH_KEY = Path.home() / ".ssh" / "lambda_key"
IP = "141.148.204.216"
REMOTE = "ubuntu"
LOCAL = Path(__file__).resolve().parents[1] / "data" / "trec" / "score_qwen.json"
HDD = Path("E:/trec_snapshots/score_qwen.json")
BAD = (
    "Traceback",
    "CUDA out of memory",
    "OutOfMemoryError",
    "RuntimeError",
    "Killed",
    "oom, batch now",
)

REMOTE_CMD = (
    "echo PROGRESS; cat /tmp/qwen_progress.txt 2>/dev/null; "
    "echo GPU; nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total "
    "--format=csv,noheader; "
    "echo LOG; tail -n 8 /tmp/qwen_score.log 2>/dev/null; "
    "echo PROC; pgrep -af '/venv/bin/python -u lambda_qwen_score.py' "
    "|| echo PROC_MISSING; "
    "echo DONE; test -f /tmp/qwen_score.done && echo YES || echo NO"
)


def ssh(cmd: str) -> str:
    out = subprocess.run(
        [
            "ssh",
            "-i",
            str(SSH_KEY),
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            "ConnectTimeout=20",
            f"{REMOTE}@{IP}",
            cmd,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    return (out.stdout or "") + (out.stderr or "")


def copy_scores() -> None:
    dest = LOCAL
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [
            "scp",
            "-i",
            str(SSH_KEY),
            "-o",
            "StrictHostKeyChecking=accept-new",
            f"{REMOTE}@{IP}:score_qwen.json",
            str(dest),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if r.returncode != 0:
        print("copy skipped", (r.stderr or "").strip()[:200], flush=True)
        return
    print(f"copied {dest.stat().st_size} bytes", flush=True)
    try:
        HDD.parent.mkdir(parents=True, exist_ok=True)
        HDD.write_bytes(dest.read_bytes())
    except OSError:
        pass


def main() -> None:
    while True:
        text = ssh(REMOTE_CMD)
        print(text, flush=True)
        low = text.lower()
        if any(line.strip() == "PROC_MISSING" for line in text.splitlines()):
            print("WATCHDOG: python process died", flush=True)
            sys.exit(2)
        for needle in BAD:
            if needle.lower() in low:
                if needle == "oom, batch now":
                    print("WATCHDOG: OOM backoff (script should continue)", flush=True)
                else:
                    print(f"WATCHDOG: saw {needle}", flush=True)
                    sys.exit(2)
        if "DONE" in text and "YES" in text.split("DONE")[-1]:
            copy_scores()
            print("WATCHDOG: job done", flush=True)
            sys.exit(0)
        copy_scores()
        time.sleep(120)


if __name__ == "__main__":
    main()
