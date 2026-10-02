"""Launch A100 SXM for Qwen cheap-pass. Copy scores off, terminate via API."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lambda_common import api, load_lambda_key  # noqa: E402
from lambda_run_rerank import scp_from, scp_to, ssh_base, wait_ip, wait_ssh, write_unix  # noqa: E402
from trec_cheap_common import DATA, GPU_SCORES, PACK  # noqa: E402

SSH_KEY = Path.home() / ".ssh" / "lambda_key"
SSH_NAME = "paper-reviewer-project"
TYPE_PREF = (
    "gpu_1x_h100_sxm5",
    "gpu_1x_h100_pcie",
    "gpu_1x_a100_sxm4",
    "gpu_1x_a100",
    "gpu_1x_a6000",
)
NAME = "trec-cheap-qwen-a100"
REMOTE = "ubuntu"
DEADMAN_SEC = 90 * 60
STAGE = DATA / "lambda_stage"
SNAPSHOT = Path("E:/trec_snapshots/cheap_pass_gpu.json")
OLD_A10 = "f7466297e4ce456183ed70643b411320"


def pick_type(key: str) -> tuple[str, str]:
    types = api("GET", "/instance-types", key)
    data = types.get("data") or {}
    for name in TYPE_PREF:
        rec = data.get(name) or {}
        regs = rec.get("regions_with_capacity_available") or []
        rnames = [r.get("name") for r in regs if isinstance(r, dict) and r.get("name")]
        if not rnames:
            continue
        prefer = ("us-west-2", "us-east-1", "us-west-1")
        region = next((r for r in prefer if r in rnames), rnames[0])
        return name, region
    raise SystemExit("No A100/H100/A6000 capacity")


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


def verify(path: Path) -> None:
    if not path.exists() or path.stat().st_size < 1000:
        raise SystemExit(f"{path} missing or tiny")
    data = json.loads(path.read_text(encoding="utf-8"))
    n_qwen = 0
    for doc in (data.get("qwen") or {}).values():
        for year in doc.values():
            for topic in year.values():
                n_qwen += len(topic)
    if n_qwen < 10000:
        raise SystemExit(f"{path} only {n_qwen} Qwen decisions")
    print(f"verified {path} qwen {n_qwen} bytes {path.stat().st_size}", flush=True)


def main() -> None:
    if not SSH_KEY.exists():
        raise SystemExit(f"missing {SSH_KEY}")
    if not PACK.exists():
        raise SystemExit(f"missing {PACK}")
    if not GPU_SCORES.exists():
        raise SystemExit(f"missing {GPU_SCORES}")
    key = load_lambda_key()
    try:
        terminate(key, OLD_A10)
    except Exception as exc:
        print("old A10 terminate", type(exc).__name__, flush=True)
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
            Path(__file__).parent / "lambda_cheap_qwen_fast.py",
            STAGE / "lambda_cheap_qwen_fast.py",
        )
        scp_to(ip, deadman, "/tmp/deadman.sh")
        subprocess.check_call(ssh_base(ip) + ["chmod", "+x", "/tmp/deadman.sh"])
        subprocess.check_call(
            ssh_base(ip) + ["bash", "-lc", "nohup /tmp/deadman.sh >/tmp/deadman.log 2>&1 &"]
        )
        scp_to(ip, setup, "/tmp/lambda_setup_cheap.sh")
        subprocess.check_call(ssh_base(ip) + ["bash", "/tmp/lambda_setup_cheap.sh"])
        scp_to(ip, job, "lambda_cheap_qwen_fast.py")
        scp_to(ip, PACK, "cheap_pass_pack.json")
        scp_to(ip, GPU_SCORES, "cheap_pass_gpu.json")
        subprocess.check_call(
            ssh_base(ip) + ["/home/ubuntu/venv/bin/python", "-u", "lambda_cheap_qwen_fast.py"]
        )
        scp_from(ip, "cheap_pass_gpu.json", GPU_SCORES)
        try:
            SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
            scp_from(ip, "cheap_pass_gpu.json", SNAPSHOT)
        except Exception as exc:
            print("hdd copy skipped", type(exc).__name__, flush=True)
        verify(GPU_SCORES)
        print("copy verified", flush=True)
    finally:
        if instance_id:
            try:
                terminate(key, instance_id)
            except Exception as exc:
                print("terminate failed", type(exc).__name__, flush=True)
                raise


if __name__ == "__main__":
    main()
