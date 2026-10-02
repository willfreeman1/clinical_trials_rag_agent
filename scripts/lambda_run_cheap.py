"""Launch A10/A6000, cheap-pass CE+Qwen, copy scores off, verify, terminate via API."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lambda_common import api, load_lambda_key  # noqa: E402
from lambda_run_rerank import (  # noqa: E402
    scp_from,
    scp_to,
    ssh_base,
    wait_ip,
    wait_ssh,
    write_unix,
)
from trec_cheap_common import DATA, GPU_SCORES, PACK  # noqa: E402

SSH_KEY = Path.home() / ".ssh" / "lambda_key"
SSH_NAME = "paper-reviewer-project"
TYPE_PREF = ("gpu_1x_a10", "gpu_1x_a6000")
NAME = "trec-cheap-20261001"
REMOTE = "ubuntu"
DEADMAN_SEC = 4 * 3600
STAGE = DATA / "lambda_stage"
SNAPSHOT = Path("E:/trec_snapshots/cheap_pass_gpu.json")


def pick_type(key: str) -> tuple[str, str]:
    types = api("GET", "/instance-types", key)
    data = types.get("data") or {}
    for name in TYPE_PREF:
        rec = data.get(name) or {}
        regs = rec.get("regions_with_capacity_available") or []
        rnames = [r.get("name") for r in regs if isinstance(r, dict) and r.get("name")]
        if rnames:
            region = "us-west-1" if "us-west-1" in rnames else rnames[0]
            return name, region
    raise SystemExit("No A10 or A6000 capacity")


def launch(key: str) -> str:
    itype, region = pick_type(key)
    print(f"launch {itype} in {region}", flush=True)
    body = {
        "region_name": region,
        "instance_type_name": itype,
        "ssh_key_names": [SSH_NAME],
        "quantity": 1,
        "name": NAME,
    }
    resp = api("POST", "/instance-operations/launch", key, body)
    ids = resp.get("data", {}).get("instance_ids") or resp.get("instance_ids") or []
    if not ids:
        raise SystemExit(f"launch returned no id: {list(resp)[:8]}")
    return ids[0]


def terminate(key: str, instance_id: str) -> None:
    print(f"terminate {instance_id}", flush=True)
    api("POST", "/instance-operations/terminate", key, {"instance_ids": [instance_id]})


def verify(path: Path, require_qwen: bool = True) -> None:
    if not path.exists() or path.stat().st_size < 1000:
        raise SystemExit(f"{path} missing or tiny")
    data = json.loads(path.read_text(encoding="utf-8"))
    if "ce" not in data:
        raise SystemExit(f"{path} missing ce")
    n_ce = 0
    for doc in (data.get("ce") or {}).values():
        for year in doc.values():
            for topic in year.values():
                n_ce += len(topic)
    n_qwen = 0
    for doc in (data.get("qwen") or {}).values():
        for year in doc.values():
            for topic in year.values():
                n_qwen += len(topic)
    if n_ce < 10000:
        raise SystemExit(f"{path} only {n_ce} CE scores")
    if require_qwen and n_qwen < 10000:
        raise SystemExit(f"{path} only {n_qwen} Qwen decisions")
    print(f"verified {path} ce {n_ce} qwen {n_qwen} bytes {path.stat().st_size}", flush=True)


def main() -> None:
    if not SSH_KEY.exists():
        raise SystemExit(f"missing {SSH_KEY}")
    if not PACK.exists():
        raise SystemExit(f"missing {PACK}")
    key = load_lambda_key()
    instance_id = None
    try:
        instance_id = launch(key)
        ip = wait_ip(key, instance_id)
        wait_ssh(ip)
        subprocess.check_call(
            ssh_base(ip) + ["bash", "-lc", f"echo {instance_id} > /tmp/instance_id"]
        )
        STAGE.mkdir(parents=True, exist_ok=True)
        lkey = STAGE / ".lkey_tmp"
        lkey.write_bytes(key.encode("utf-8"))
        try:
            scp_to(ip, lkey, "/tmp/lkey")
            subprocess.check_call(ssh_base(ip) + ["chmod", "600", "/tmp/lkey"])
        finally:
            lkey.unlink(missing_ok=True)
        deadman = write_unix(
            Path(__file__).parent / "lambda_deadman.sh",
            STAGE / "deadman.sh",
            {"sleep 2700": f"sleep {DEADMAN_SEC}"},
        )
        setup = write_unix(
            Path(__file__).parent / "lambda_setup_cheap.sh",
            STAGE / "lambda_setup_cheap.sh",
        )
        job = write_unix(
            Path(__file__).parent / "lambda_cheap_pass.py",
            STAGE / "lambda_cheap_pass.py",
        )
        scp_to(ip, deadman, "/tmp/deadman.sh")
        subprocess.check_call(ssh_base(ip) + ["chmod", "+x", "/tmp/deadman.sh"])
        subprocess.check_call(
            ssh_base(ip) + ["bash", "-lc", "nohup /tmp/deadman.sh >/tmp/deadman.log 2>&1 &"]
        )
        scp_to(ip, setup, "/tmp/lambda_setup_cheap.sh")
        subprocess.check_call(ssh_base(ip) + ["bash", "/tmp/lambda_setup_cheap.sh"])
        scp_to(ip, job, "lambda_cheap_pass.py")
        scp_to(ip, PACK, "cheap_pass_pack.json")
        job_failed = None
        try:
            subprocess.check_call(
                ssh_base(ip) + ["/home/ubuntu/venv/bin/python", "lambda_cheap_pass.py"]
            )
        except Exception as exc:
            job_failed = exc
            print("gpu job failed, still copying", type(exc).__name__, flush=True)
        try:
            scp_from(ip, "cheap_pass_gpu.json", GPU_SCORES)
            SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
            scp_from(ip, "cheap_pass_gpu.json", SNAPSHOT)
        except Exception as exc:
            print("copy failed", type(exc).__name__, flush=True)
            if job_failed:
                raise job_failed
            raise
        verify(GPU_SCORES, require_qwen=job_failed is None)
        print("copy verified", flush=True)
        if job_failed:
            raise job_failed
    finally:
        if instance_id:
            try:
                terminate(key, instance_id)
            except Exception as exc:
                print("terminate failed", type(exc).__name__, flush=True)
                raise


if __name__ == "__main__":
    main()
