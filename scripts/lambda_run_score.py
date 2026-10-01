"""Launch H100/A100, score Qwen topical + eligibility, copy off, terminate."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lambda_common import api, load_lambda_key  # noqa: E402
from lambda_run_rerank import scp_from, scp_to, ssh_base, wait_ip, wait_ssh, write_unix  # noqa: E402
from trec_score_common import DATA, PACK, QWEN_SCORES  # noqa: E402

SSH_KEY = Path.home() / ".ssh" / "lambda_key"
SSH_NAME = "paper-reviewer-project"
TYPE_PREF = (
    "gpu_1x_h100_sxm5",
    "gpu_1x_h100_pcie",
    "gpu_1x_a100_sxm4",
    "gpu_1x_a100",
    "gpu_1x_a6000",
)
NAME = "trec-score-qwen"
REMOTE = "ubuntu"
STAGE = DATA / "lambda_stage"
SNAPSHOT = Path("E:/trec_snapshots/score_qwen.json")
STATE = DATA / "score_lambda_state.json"
POLL_SEC = 120


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
    raise SystemExit("No H100/A100/A6000 capacity")


def launch(key: str) -> tuple[str, str, str]:
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
    return ids[0], itype, region


def terminate(key: str, instance_id: str) -> None:
    print(f"terminate {instance_id}", flush=True)
    api("POST", "/instance-operations/terminate", key, {"instance_ids": [instance_id]})


def save_state(payload: dict) -> None:
    STATE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def verify(path: Path) -> None:
    if not path.exists() or path.stat().st_size < 1000:
        raise SystemExit(f"{path} missing or tiny")
    data = json.loads(path.read_text(encoding="utf-8"))
    n = 0
    for arm in (data.get("arms") or {}).values():
        for year in arm.values():
            for topic in year.values():
                n += len(topic)
    if n < 10000:
        raise SystemExit(f"{path} only {n} Qwen scores")
    print(f"verified {path} scores {n} bytes {path.stat().st_size}", flush=True)


def copy_scores(ip: str) -> None:
    try:
        scp_from(ip, "score_qwen.json", QWEN_SCORES)
    except subprocess.CalledProcessError as exc:
        print("copy scores failed", exc, flush=True)
        return
    try:
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_bytes(QWEN_SCORES.read_bytes())
    except OSError as exc:
        print("hdd copy skipped", type(exc).__name__, flush=True)


def remote_done(ip: str) -> bool:
    try:
        subprocess.check_call(
            ssh_base(ip) + ["test", "-f", "/tmp/qwen_score.done"],
            timeout=20,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def remote_progress(ip: str) -> str:
    try:
        out = subprocess.check_output(
            ssh_base(ip) + ["bash", "-lc", "tail -n 3 /tmp/qwen_progress.txt; wc -c score_qwen.json 2>/dev/null || true"],
            timeout=30,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return out.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""


def main() -> None:
    if not SSH_KEY.exists():
        raise SystemExit(f"missing {SSH_KEY}")
    if not PACK.exists():
        raise SystemExit(f"missing {PACK}")
    key = load_lambda_key()
    instance_id = None
    itype = ""
    region = ""
    t0 = time.time()
    try:
        instance_id, itype, region = launch(key)
        save_state({"instance_id": instance_id, "type": itype, "region": region, "t0": t0})
        ip = wait_ip(key, instance_id)
        wait_ssh(ip)
        save_state({"instance_id": instance_id, "type": itype, "region": region, "ip": ip, "t0": t0})
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
            Path(__file__).parent / "lambda_deadman_score.sh",
            STAGE / "deadman_score.sh",
        )
        setup = write_unix(
            Path(__file__).parent / "lambda_setup_cheap.sh",
            STAGE / "lambda_setup_cheap.sh",
        )
        job = write_unix(
            Path(__file__).parent / "lambda_qwen_score.py",
            STAGE / "lambda_qwen_score.py",
        )
        scp_to(ip, deadman, "/tmp/deadman.sh")
        subprocess.check_call(ssh_base(ip) + ["chmod", "+x", "/tmp/deadman.sh"])
        subprocess.check_call(
            ssh_base(ip) + ["bash", "-lc", "nohup /tmp/deadman.sh >/tmp/deadman.log 2>&1 &"]
        )
        scp_to(ip, setup, "/tmp/lambda_setup_cheap.sh")
        subprocess.check_call(ssh_base(ip) + ["bash", "/tmp/lambda_setup_cheap.sh"])
        scp_to(ip, job, "lambda_qwen_score.py")
        scp_to(ip, PACK, "score_pack.json")
        if QWEN_SCORES.exists():
            scp_to(ip, QWEN_SCORES, "score_qwen.json")
        subprocess.check_call(
            ssh_base(ip)
            + [
                "bash",
                "-lc",
                "nohup /home/ubuntu/venv/bin/python -u lambda_qwen_score.py "
                ">/tmp/qwen_score.log 2>&1 & echo $!",
            ]
        )
        print("remote job started", flush=True)
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
        verify(QWEN_SCORES)
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
                }
            )


if __name__ == "__main__":
    main()
