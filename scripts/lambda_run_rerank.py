"""Launch A10/A6000, rerank, copy scores off, verify, terminate via API."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lambda_common import api, load_lambda_key  # noqa: E402
from trec_rerank_common import CE_SCORES, DATA  # noqa: E402

SSH_KEY = Path.home() / ".ssh" / "lambda_key"
SSH_NAME = "paper-reviewer-project"
TYPE_PREF = ("gpu_1x_a10", "gpu_1x_a6000")
NAME = "trec-rerank-20260930"
REMOTE = "ubuntu"
DEADMAN_SEC = 90 * 60
PACK = DATA / "rerank_pack.json"
STAGE = DATA / "lambda_stage"


def write_unix(src: Path, dest: Path, replacements: dict[str, str] | None = None) -> Path:
    text = src.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    for old, new in (replacements or {}).items():
        text = text.replace(old, new)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(text.encode("utf-8"))
    return dest


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


def verify(path: Path) -> None:
    if not path.exists() or path.stat().st_size < 1000:
        raise SystemExit(f"{path} missing or tiny")
    data = json.loads(path.read_text(encoding="utf-8"))
    trunc = data.get("truncate") or {}
    if "medcpt_ce" not in trunc or "msmarco_ce" not in trunc:
        raise SystemExit(f"{path} missing a cross-encoder arm")
    n = 0
    for model in trunc.values():
        for q in model.values():
            for year in q.values():
                for topic in year.values():
                    n += len(topic)
    if n < 100000:
        raise SystemExit(f"{path} only {n} truncate scores")
    print(f"verified {path} truncate scores {n} bytes {path.stat().st_size}", flush=True)


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
        setup = write_unix(Path(__file__).parent / "lambda_setup.sh", STAGE / "lambda_setup.sh")
        encode = write_unix(Path(__file__).parent / "lambda_rerank.py", STAGE / "lambda_rerank.py")
        scp_to(ip, deadman, "/tmp/deadman.sh")
        subprocess.check_call(ssh_base(ip) + ["chmod", "+x", "/tmp/deadman.sh"])
        subprocess.check_call(
            ssh_base(ip) + ["bash", "-lc", "nohup /tmp/deadman.sh >/tmp/deadman.log 2>&1 &"]
        )
        scp_to(ip, setup, "/tmp/lambda_setup.sh")
        subprocess.check_call(ssh_base(ip) + ["bash", "/tmp/lambda_setup.sh"])
        scp_to(ip, encode, "lambda_rerank.py")
        scp_to(ip, PACK, "rerank_pack.json")
        subprocess.check_call(
            ssh_base(ip) + ["/home/ubuntu/venv/bin/python", "lambda_rerank.py"]
        )
        dest_e = Path("E:/trec_snapshots/rerank_ce_scores.json")
        scp_from(ip, "rerank_ce_scores.json", CE_SCORES)
        scp_from(ip, "rerank_ce_scores.json", dest_e)
        verify(CE_SCORES)
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
