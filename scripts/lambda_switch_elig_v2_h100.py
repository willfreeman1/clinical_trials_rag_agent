"""Grab an H100, resume v2 scoring, then terminate the A100.

H100 only. Does not fall back to A100/A10. A100 keeps scoring until
the H100 process is confirmed running.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lambda_common import api, load_lambda_key  # noqa: E402
from lambda_run_elig_v2 import (  # noqa: E402
    PACK,
    POLL_SEC,
    SCORES,
    SSH_KEY,
    SSH_NAME,
    STAGE,
    STATE,
    copy_scores,
    remote_done,
    remote_progress,
    save_state,
    score_count,
    terminate,
    verify,
)
from lambda_run_rerank import scp_from, scp_to, ssh_base, wait_ip, wait_ssh, write_unix  # noqa: E402

H100_TYPES = ("gpu_1x_h100_sxm5", "gpu_1x_h100_pcie")
H100_NAME = "trec-elig-v2-h100"
RETRY_SEC = 30
A100_BACKUP = STATE.with_name("elig_v2_a100_state.json")


def pick_h100(key: str) -> tuple[str, str]:
    types = api("GET", "/instance-types", key)
    data = types.get("data") or {}
    for name in H100_TYPES:
        rec = data.get(name) or {}
        regs = rec.get("regions_with_capacity_available") or []
        rnames = [r.get("name") for r in regs if isinstance(r, dict) and r.get("name")]
        if not rnames:
            continue
        prefer = ("us-west-2", "us-east-1", "us-west-1")
        region = next((r for r in prefer if r in rnames), rnames[0])
        if region:
            return name, str(region)
    raise SystemExit("no H100 capacity")


def launch_h100(key: str) -> tuple[str, str, str]:
    itype, region = pick_h100(key)
    print(f"launch {itype} in {region}", flush=True)
    body = {
        "region_name": region,
        "instance_type_name": itype,
        "ssh_key_names": [SSH_NAME],
        "quantity": 1,
        "name": H100_NAME,
    }
    resp = api("POST", "/instance-operations/launch", key, body)
    ids = resp.get("data", {}).get("instance_ids") or resp.get("instance_ids") or []
    if not ids:
        raise SystemExit(f"launch returned no id: {list(resp)[:8]}")
    return ids[0], itype, region


def wait_for_h100(key: str) -> tuple[str, str, str]:
    started = time.time()
    last_print = 0.0
    while True:
        try:
            return launch_h100(key)
        except SystemExit as exc:
            msg = str(exc)
            if any(s in msg.lower() for s in ("no h100", "no id", "capacity", "out of stock", "429")):
                now = time.time()
                if now - last_print >= 300:
                    mins = int((now - started) / 60)
                    print(f"still no H100 after {mins} min ({msg})", flush=True)
                    last_print = now
                time.sleep(RETRY_SEC)
                continue
            raise


def count_scores(path: Path) -> int:
    for _ in range(6):
        try:
            return score_count(path)
        except (OSError, json.JSONDecodeError, PermissionError):
            time.sleep(1)
    return 0


def pull_a100(ip: str) -> Path | None:
    tmp = SCORES.with_name("score_qwen_elig_v2.a100pull.json")
    try:
        scp_from(ip, "score_qwen_elig_v2.json", tmp)
    except subprocess.CalledProcessError as exc:
        print("a100 copy failed", exc, flush=True)
        if SCORES.exists():
            return SCORES
        return tmp if tmp.exists() else None
    for _ in range(6):
        try:
            tmp.replace(SCORES)
            n = count_scores(SCORES)
            print(f"a100 scores {n}", flush=True)
            return SCORES
        except OSError:
            time.sleep(1)
    n = count_scores(tmp)
    print(f"a100 scores {n} (kept side file)", flush=True)
    return tmp if n else (SCORES if SCORES.exists() else None)


def kill_old_launcher() -> None:
    me = os.getpid()
    ps = (
        "Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -match 'python' -and $_.CommandLine -match 'lambda_run_elig_v2.py' "
        "-and $_.CommandLine -notmatch 'switch' } | "
        "Select-Object -ExpandProperty ProcessId"
    )
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", ps],
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.CalledProcessError:
        print("no old launcher pid found", flush=True)
        return
    for tok in out.split():
        if not tok.strip().isdigit():
            continue
        pid = int(tok.strip())
        if pid == me:
            continue
        print(f"kill old launcher {pid}", flush=True)
        subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"], check=False)


def setup_and_start(ip: str, instance_id: str, key: str, a100_ip: str) -> None:
    STAGE.mkdir(parents=True, exist_ok=True)
    iid_file = STAGE / "instance_id"
    iid_file.write_text(instance_id + "\n", encoding="utf-8")
    scp_to(ip, iid_file, "/tmp/instance_id")
    lkey = STAGE / ".lkey_tmp"
    lkey.write_bytes(key.encode("utf-8"))
    try:
        scp_to(ip, lkey, "/tmp/lkey")
        subprocess.check_call(ssh_base(ip) + ["chmod", "600", "/tmp/lkey"])
    finally:
        lkey.unlink(missing_ok=True)
    here = Path(__file__).parent
    deadman = write_unix(here / "lambda_deadman_elig_v2.sh", STAGE / "deadman_elig_v2.sh")
    start = write_unix(here / "lambda_start_elig_v2.sh", STAGE / "start_elig_v2.sh")
    setup = write_unix(here / "lambda_setup_cheap.sh", STAGE / "lambda_setup_cheap.sh")
    job = write_unix(here / "lambda_qwen_elig_v2.py", STAGE / "lambda_qwen_elig_v2.py")
    scp_to(ip, deadman, "/tmp/deadman.sh")
    subprocess.check_call(ssh_base(ip) + ["chmod", "+x", "/tmp/deadman.sh"])
    subprocess.check_call(
        ssh_base(ip) + ["bash", "-lc", "nohup /tmp/deadman.sh >/tmp/deadman.log 2>&1 &"]
    )
    scp_to(ip, setup, "/tmp/lambda_setup_cheap.sh")
    subprocess.check_call(ssh_base(ip) + ["bash", "/tmp/lambda_setup_cheap.sh"])
    scp_to(ip, job, "lambda_qwen_elig_v2.py")
    scp_to(ip, PACK, "score_pack.json")
    src = pull_a100(a100_ip)
    if src is not None and count_scores(src) > 0:
        scp_to(ip, src, "score_qwen_elig_v2.json")
        print(f"uploaded resume scores {count_scores(src)}", flush=True)
    scp_to(ip, start, "/tmp/start_elig_v2.sh")
    subprocess.check_call(ssh_base(ip) + ["chmod", "+x", "/tmp/start_elig_v2.sh"])
    subprocess.check_call(ssh_base(ip) + ["bash", "/tmp/start_elig_v2.sh"])
    print("remote job started", flush=True)


def confirm_running(ip: str) -> None:
    for _ in range(20):
        out = subprocess.run(
            ssh_base(ip)
            + [
                "bash",
                "-lc",
                "pgrep -af lambda_qwen_elig_v2.py || echo PROC_MISSING; "
                "nvidia-smi --query-gpu=utilization.gpu,memory.used "
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        text = (out.stdout or "") + (out.stderr or "")
        print(text.strip(), flush=True)
        if "lambda_qwen_elig_v2.py" in text and "PROC_MISSING" not in text:
            return
        time.sleep(15)
    raise SystemExit("H100 process did not start")


def main() -> None:
    if not SSH_KEY.exists():
        raise SystemExit(f"missing {SSH_KEY}")
    if not PACK.exists():
        raise SystemExit(f"missing {PACK}")
    old = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    a100_id = old.get("instance_id")
    a100_ip = old.get("ip")
    if not a100_id or not a100_ip:
        raise SystemExit("A100 state missing ip/id")
    A100_BACKUP.write_text(json.dumps(old, indent=2), encoding="utf-8")
    key = load_lambda_key()
    print(f"A100 {a100_id} {a100_ip} keeps running until H100 is scoring", flush=True)
    pull_a100(a100_ip)
    instance_id = None
    itype = ""
    region = ""
    t0 = time.time()
    try:
        instance_id, itype, region = wait_for_h100(key)
        ip = wait_ip(key, instance_id)
        wait_ssh(ip)
        print(f"H100 up {instance_id} {itype} {ip}", flush=True)
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                setup_and_start(ip, instance_id, key, a100_ip)
                last_exc = None
                break
            except (OSError, PermissionError) as exc:
                last_exc = exc
                print(f"setup retry {attempt + 1}: {type(exc).__name__}", flush=True)
                time.sleep(5)
        if last_exc is not None:
            raise last_exc
        confirm_running(ip)
        kill_old_launcher()
        print(f"terminate A100 {a100_id}", flush=True)
        terminate(key, a100_id)
        save_state(
            {
                "instance_id": instance_id,
                "type": itype,
                "region": region,
                "ip": ip,
                "t0": t0,
                "replaced_a100": a100_id,
            }
        )
        print("switched to H100", flush=True)
        while True:
            if remote_done(ip):
                print("remote done", flush=True)
                break
            msg = remote_progress(ip)
            if msg:
                print(msg, flush=True)
            copy_scores(ip)
            rec = {}
            try:
                listed = api("GET", "/instances", key)
                for row in listed.get("data") or []:
                    if row.get("id") == instance_id:
                        rec = row
                        break
            except SystemExit:
                rec = {}
            if rec.get("status") in {"terminated", "terminating", "unhealthy"}:
                print(f"instance status {rec.get('status')}", flush=True)
                copy_scores(ip)
                break
            time.sleep(POLL_SEC)
        copy_scores(ip)
        verify(SCORES)
        print(
            f"copy verified hours {(time.time() - t0) / 3600:.2f} type {itype}",
            flush=True,
        )
    finally:
        if instance_id:
            try:
                terminate(key, instance_id)
            except Exception as exc:
                print("terminate failed", type(exc).__name__, flush=True)
                raise
            save_state(
                {
                    "instance_id": instance_id,
                    "type": itype,
                    "region": region,
                    "terminated": True,
                    "hours": round((time.time() - t0) / 3600, 3),
                    "replaced_a100": a100_id,
                }
            )


if __name__ == "__main__":
    main()
