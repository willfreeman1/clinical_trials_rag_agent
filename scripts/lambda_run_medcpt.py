"""Launch A10, encode MedCPT, copy off, verify, terminate via API.

save-then-terminate: never leave the box billing. Deadman at 45 minutes.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lambda_common import api, load_lambda_key  # noqa: E402
from trec_hybrid_common import DATA  # noqa: E402

SSH_KEY = Path.home() / ".ssh" / "lambda_key"
SSH_NAME = "paper-reviewer-project"
TYPE_PREF = ("gpu_1x_a10", "gpu_1x_a6000")
NAME = "trec-medcpt-20260930"
PACK = DATA / "lambda_pack"
OUT_LOCAL = DATA
OUT_E = Path("E:/trec_snapshots/medcpt_out")
REMOTE = "ubuntu"
DEADMAN_SEC = 45 * 60
EXPECT = {
    2021: (48714, 48714 * 768 * 4),
    2023: (17105, 17105 * 768 * 4),
}


def ssh_base(ip: str) -> list[str]:
    return [
        "ssh",
        "-i",
        str(SSH_KEY),
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ConnectTimeout=15",
        f"{REMOTE}@{ip}",
    ]


def scp_to(ip: str, local: Path, remote: str) -> None:
    subprocess.check_call(
        [
            "scp",
            "-i",
            str(SSH_KEY),
            "-o",
            "StrictHostKeyChecking=accept-new",
            str(local),
            f"{REMOTE}@{ip}:{remote}",
        ]
    )


def scp_from(ip: str, remote: str, local: Path) -> None:
    local.parent.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(
        [
            "scp",
            "-i",
            str(SSH_KEY),
            "-o",
            "StrictHostKeyChecking=accept-new",
            f"{REMOTE}@{ip}:{remote}",
            str(local),
        ]
    )


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


def _find_instance(key: str, instance_id: str) -> dict:
    try:
        inst = api("GET", f"/instances/{instance_id}", key)
        rec = inst.get("data") or inst
        if rec.get("id") or rec.get("ip") or rec.get("status"):
            return rec
    except SystemExit:
        pass
    listed = api("GET", "/instances", key)
    for rec in listed.get("data") or []:
        if rec.get("id") == instance_id:
            return rec
    return {}


def wait_ip(key: str, instance_id: str) -> str:
    for _ in range(60):
        rec = _find_instance(key, instance_id)
        ip = rec.get("ip")
        print(f"status {rec.get('status')} ip {bool(ip)}", flush=True)
        if ip:
            return ip
        time.sleep(10)
    raise SystemExit("no IP after 10 minutes")


def wait_ssh(ip: str) -> None:
    for _ in range(36):
        try:
            subprocess.check_call(ssh_base(ip) + ["echo", "ok"], timeout=20)
            return
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            time.sleep(10)
    raise SystemExit("ssh never came up")


def terminate(key: str, instance_id: str) -> None:
    print(f"terminate {instance_id}", flush=True)
    api("POST", "/instance-operations/terminate", key, {"instance_ids": [instance_id]})


def verify(snap: int, npy: Path) -> None:
    n, nbytes = EXPECT[snap]
    if not npy.exists() or npy.stat().st_size == 0:
        raise SystemExit(f"{npy} missing or empty")
    if npy.stat().st_size != nbytes:
        raise SystemExit(f"{npy} size {npy.stat().st_size} expected {nbytes}")
    print(f"verified {npy} {nbytes} bytes for {n} trials", flush=True)


def main() -> None:
    if not SSH_KEY.exists():
        raise SystemExit(f"missing {SSH_KEY}")
    key = load_lambda_key()
    instance_id = None
    try:
        instance_id = launch(key)
        ip = wait_ip(key, instance_id)
        wait_ssh(ip)
        subprocess.check_call(
            ssh_base(ip) + ["bash", "-lc", f"echo {instance_id} > /tmp/instance_id"]
        )
        (PACK / ".lkey").write_text(key, encoding="utf-8")
        try:
            scp_to(ip, PACK / ".lkey", "/tmp/lkey")
            subprocess.check_call(ssh_base(ip) + ["chmod", "600", "/tmp/lkey"])
        finally:
            (PACK / ".lkey").unlink(missing_ok=True)
        scp_to(ip, Path(__file__).parent / "lambda_deadman.sh", "/tmp/deadman.sh")
        subprocess.check_call(
            ssh_base(ip)
            + [
                "bash",
                "-lc",
                "tr -d '\\r' < /tmp/deadman.sh > /tmp/deadman.unix && mv /tmp/deadman.unix /tmp/deadman.sh && chmod +x /tmp/deadman.sh && nohup /tmp/deadman.sh >/tmp/deadman.log 2>&1 &",
            ]
        )
        cuda_ok = subprocess.call(
            ssh_base(ip)
            + ["bash", "-lc", "python3 -c 'import torch; raise SystemExit(0 if torch.cuda.is_available() else 1)'"]
        )
        if cuda_ok != 0:
            subprocess.check_call(
                ssh_base(ip)
                + [
                    "bash",
                    "-lc",
                    "python3 -m pip install -q --user -U pip && "
                    "python3 -m pip install -q --user torch --index-url https://download.pytorch.org/whl/cu121 && "
                    "python3 -m pip install -q --user transformers numpy",
                ]
            )
        else:
            subprocess.check_call(
                ssh_base(ip)
                + ["bash", "-lc", "python3 -m pip install -q --user transformers"]
            )
        scp_to(ip, Path(__file__).parent / "lambda_medcpt_encode.py", "lambda_medcpt_encode.py")
        for snap in (2021, 2023):
            scp_to(ip, PACK / f"input_{snap}.jsonl", f"input_{snap}.jsonl")
            subprocess.check_call(
                ssh_base(ip)
                + [
                    "python3",
                    "lambda_medcpt_encode.py",
                    f"input_{snap}.jsonl",
                    f"out_{snap}",
                ]
            )
            dest_c = OUT_LOCAL / f"index_{snap}"
            dest_e = OUT_E / f"index_{snap}"
            for dest in (dest_c, dest_e):
                dest.mkdir(parents=True, exist_ok=True)
            scp_from(ip, f"out_{snap}/medcpt.npy", dest_c / "medcpt.npy")
            scp_from(ip, f"out_{snap}/chunk_nct.json", dest_c / "chunk_nct.json")
            scp_from(ip, f"out_{snap}/medcpt.npy", dest_e / "medcpt.npy")
            scp_from(ip, f"out_{snap}/chunk_nct.json", dest_e / "chunk_nct.json")
            verify(snap, dest_c / "medcpt.npy")
            verify(snap, dest_e / "medcpt.npy")
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
