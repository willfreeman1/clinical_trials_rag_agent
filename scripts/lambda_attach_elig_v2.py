"""Poll an already-running v2 eligibility GPU. Copy scores. Terminate when done."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lambda_common import api, load_lambda_key  # noqa: E402
from lambda_run_elig_v2 import (  # noqa: E402
    POLL_SEC,
    SCORES,
    STATE,
    copy_scores,
    remote_done,
    remote_progress,
    save_state,
    terminate,
    verify,
)


def main() -> None:
    rec = json.loads(STATE.read_text(encoding="utf-8"))
    instance_id = rec.get("instance_id")
    ip = rec.get("ip")
    itype = rec.get("type") or ""
    region = rec.get("region") or ""
    if not instance_id or not ip:
        raise SystemExit("state missing instance_id/ip")
    if rec.get("terminated"):
        raise SystemExit("state says terminated")
    key = load_lambda_key()
    t0 = time.time()
    print(f"attach {instance_id} {itype} {ip}", flush=True)
    try:
        while True:
            if remote_done(ip):
                print("remote done", flush=True)
                break
            msg = remote_progress(ip)
            if msg:
                print(msg, flush=True)
            copy_scores(ip)
            listed = {}
            try:
                listed = api("GET", "/instances", key)
            except SystemExit:
                listed = {}
            row = {}
            for item in listed.get("data") or []:
                if item.get("id") == instance_id:
                    row = item
                    break
            if row.get("status") in {"terminated", "terminating", "unhealthy"}:
                print(f"instance status {row.get('status')}", flush=True)
                copy_scores(ip)
                break
            time.sleep(POLL_SEC)
        copy_scores(ip)
        verify(SCORES)
        print(f"copy verified hours {(time.time() - t0) / 3600:.2f} type {itype}", flush=True)
    finally:
        terminate(key, instance_id)
        save_state(
            {
                "instance_id": instance_id,
                "type": itype,
                "region": region,
                "terminated": True,
                "hours": round((time.time() - t0) / 3600, 3),
                "replaced_a100": rec.get("replaced_a100"),
            }
        )


if __name__ == "__main__":
    main()
