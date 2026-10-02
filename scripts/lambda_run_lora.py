"""Launch H100: score base v1 first, report, then pairwise LoRA. Copy off, terminate."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lambda_common import api, load_lambda_key  # noqa: E402
from lambda_run_rerank import scp_from, scp_to, ssh_base, wait_ip, wait_ssh, write_unix  # noqa: E402
from trec_lora_common import (  # noqa: E402
    ADAPTER_DIR,
    ADAPTER_SCORES,
    BASE_RESULTS,
    BASE_SCORES,
    CONFIG_PATH,
    EVAL_PAIRS_PATH,
    TRAIN_PAIRS_PATH,
)
from trec_score_common import DATA, PACK  # noqa: E402

SSH_KEY = Path.home() / ".ssh" / "lambda_key"
SSH_NAME = "paper-reviewer-project"
TYPE_PREF = ("gpu_1x_h100_sxm5", "gpu_1x_h100_pcie")
HOURLY = {"gpu_1x_h100_sxm5": 4.29, "gpu_1x_h100_pcie": 3.29}
NAME = "trec-lora-elig"
STAGE = DATA / "lambda_stage"
STATE = DATA / "lora_lambda_state.json"
TRAIN_LOG = DATA / "lora_train_log.json"
LORA_RESULTS = DATA / "trec_lora_adapter_results.json"
POLL_SEC = 45
SPEND_CAP = 25.0
MIN_BASE = 8000


def pick_type(key: str) -> tuple[str, str]:
    types = api("GET", "/instance-types", key)
    data = types.get("data") or {}
    for name in TYPE_PREF:
        rec = data.get(name) or {}
        regs = rec.get("regions_with_capacity_available") or []
        rnames = [r.get("name") for r in regs if isinstance(r, dict) and r.get("name")]
        if not rnames:
            continue
        prefer = ("us-west-2", "us-west-3", "us-east-1", "us-west-1")
        region = next((r for r in prefer if r in rnames), rnames[0])
        if region:
            return name, str(region)
    raise SystemExit("No H100 capacity")


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


def spend(t0: float, itype: str) -> float:
    return ((time.time() - t0) / 3600.0) * HOURLY.get(itype, 3.29)


def score_count(path: Path) -> int:
    if not path.exists() or path.stat().st_size < 200:
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    return sum(len(t) for y in (data.get("scores") or {}).values() for t in y.values())


def remote_has(ip: str, path: str) -> bool:
    try:
        subprocess.check_call(ssh_base(ip) + ["test", "-f", path], timeout=20)
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def tail_progress(ip: str) -> str:
    try:
        return subprocess.check_output(
            ssh_base(ip) + ["bash", "-lc", "tail -n 2 /tmp/qwen_progress.txt 2>/dev/null || true"],
            timeout=20,
            text=True,
            encoding="utf-8",
            errors="replace",
        ).strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""


def wait_flag(ip: str, flag: str, t0: float, itype: str, copy_fn=None) -> None:
    while True:
        if spend(t0, itype) > SPEND_CAP:
            raise SystemExit(f"spend would pass ${SPEND_CAP:.0f}; stopping to ask")
        if remote_has(ip, flag):
            return
        msg = tail_progress(ip)
        if msg:
            print(msg, flush=True)
        if copy_fn:
            try:
                copy_fn()
            except Exception:
                pass
        time.sleep(POLL_SEC)


def run_eval(score_path: Path, label: str, out: Path) -> dict:
    cmd = [sys.executable, str(Path(__file__).parent / "trec_lora_eval.py"), str(score_path), label, str(out)]
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["PYTHONIOENCODING"] = "utf-8"
    subprocess.check_call(cmd, env=env)
    return json.loads(out.read_text(encoding="utf-8"))


def stalled(log_path: Path) -> bool:
    if not log_path.exists():
        return False
    steps = (json.loads(log_path.read_text(encoding="utf-8")).get("steps") or [])
    losses = [float(s["loss"]) for s in steps if s.get("loss") is not None]
    if len(losses) < 8:
        return False
    n = max(3, len(losses) // 5)
    first = sum(losses[:n]) / n
    last = sum(losses[-n:]) / n
    print(f"loss first {first:.4f} last {last:.4f}", flush=True)
    return first - last < 0.03


def start_remote(ip: str, script: str, extra: list[str] | None = None) -> None:
    cmd = ["bash", f"/tmp/{script}"]
    if extra:
        cmd.extend(extra)
    subprocess.check_call(ssh_base(ip) + cmd)


def main() -> None:
    if not SSH_KEY.exists():
        raise SystemExit(f"missing {SSH_KEY}")
    if not PACK.exists():
        raise SystemExit(f"missing {PACK}")
    if not EVAL_PAIRS_PATH.exists() or not TRAIN_PAIRS_PATH.exists():
        raise SystemExit("pair lists missing; run trec_lora_draw.py")
    key = load_lambda_key()
    listed = api("GET", "/instances", key)
    for row in listed.get("data") or []:
        if row.get("name") == NAME and row.get("status") not in {"terminated", "terminating"}:
            raise SystemExit(f"already running {row.get('id')} status {row.get('status')}")
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
        STAGE.mkdir(parents=True, exist_ok=True)
        iid = STAGE / "instance_id"
        iid.write_text(instance_id + "\n", encoding="utf-8")
        scp_to(ip, iid, "/tmp/instance_id")
        lkey = STAGE / ".lkey_tmp"
        lkey.write_bytes(key.encode("utf-8"))
        try:
            scp_to(ip, lkey, "/tmp/lkey")
            subprocess.check_call(ssh_base(ip) + ["chmod", "600", "/tmp/lkey"])
        finally:
            lkey.unlink(missing_ok=True)
        here = Path(__file__).parent
        for src, dest in (
            (here / "lambda_deadman_lora.sh", STAGE / "deadman_lora.sh"),
            (here / "lambda_setup_lora.sh", STAGE / "lambda_setup_lora.sh"),
            (here / "lambda_qwen_lora_score.py", STAGE / "lambda_qwen_lora_score.py"),
            (here / "lambda_qwen_lora_train.py", STAGE / "lambda_qwen_lora_train.py"),
            (here / "lambda_start_lora_base.sh", STAGE / "start_lora_base.sh"),
            (here / "lambda_start_lora_train.sh", STAGE / "start_lora_train.sh"),
            (here / "lambda_start_lora_adapter.sh", STAGE / "start_lora_adapter.sh"),
        ):
            write_unix(src, dest)
        scp_to(ip, STAGE / "deadman_lora.sh", "/tmp/deadman.sh")
        subprocess.check_call(ssh_base(ip) + ["chmod", "+x", "/tmp/deadman.sh"])
        subprocess.check_call(ssh_base(ip) + ["bash", "-lc", "nohup /tmp/deadman.sh >/tmp/deadman.log 2>&1 &"])
        scp_to(ip, STAGE / "lambda_setup_lora.sh", "/tmp/lambda_setup_lora.sh")
        subprocess.check_call(ssh_base(ip) + ["bash", "/tmp/lambda_setup_lora.sh"])
        scp_to(ip, STAGE / "lambda_qwen_lora_score.py", "lambda_qwen_lora_score.py")
        scp_to(ip, STAGE / "lambda_qwen_lora_train.py", "lambda_qwen_lora_train.py")
        scp_to(ip, PACK, "score_pack.json")
        scp_to(ip, EVAL_PAIRS_PATH, "trec_lora_eval_pairs.json")
        scp_to(ip, TRAIN_PAIRS_PATH, "trec_lora_train_pairs.json")
        scp_to(ip, CONFIG_PATH, "trec_lora_config.json")
        for sh in ("start_lora_base.sh", "start_lora_train.sh", "start_lora_adapter.sh"):
            scp_to(ip, STAGE / sh, f"/tmp/{sh}")
            subprocess.check_call(ssh_base(ip) + ["chmod", "+x", f"/tmp/{sh}"])
        print("starting base v1 score", flush=True)
        start_remote(ip, "start_lora_base.sh")
        wait_flag(
            ip,
            "/tmp/lora_base.done",
            t0,
            itype,
            lambda: scp_from(ip, "score_qwen_elig_v1_base.json", BASE_SCORES),
        )
        scp_from(ip, "score_qwen_elig_v1_base.json", BASE_SCORES)
        n = score_count(BASE_SCORES)
        if n < MIN_BASE:
            raise SystemExit(f"base scores only {n}")
        print("==== BASE V1 ELIGIBILITY (before any adapter) ====", flush=True)
        base = run_eval(BASE_SCORES, "base_v1", BASE_RESULTS)
        print(
            f"BASE TEST pooled {base.get('test', {}).get('pooled')} "
            f"macro {base.get('test', {}).get('macro')} "
            f"vs topical slice {base.get('topical_slice_test', {}).get('pooled')}",
            flush=True,
        )
        print(f"spend so far ${spend(t0, itype):.2f}", flush=True)
        if spend(t0, itype) + 8 > SPEND_CAP:
            raise SystemExit("training would likely push past $25; stopping to ask")
        print("starting LoRA train (expected_digit)", flush=True)
        start_remote(ip, "start_lora_train.sh", ["expected_digit", "lora_adapter", "lora_train_log.json"])
        wait_flag(ip, "/tmp/lora_train.done", t0, itype)
        try:
            scp_from(ip, "lora_train_log.json", TRAIN_LOG)
        except subprocess.CalledProcessError:
            print("copy train log failed", flush=True)
        adapter = "lora_adapter"
        if stalled(TRAIN_LOG):
            print("first run stalled; fallback logit2_minus_logit1", flush=True)
            if spend(t0, itype) + 8 > SPEND_CAP:
                raise SystemExit("fallback train would likely push past $25; stopping to ask")
            start_remote(ip, "start_lora_train.sh", ["logit2_minus_logit1", "lora_adapter_b", "lora_train_log_b.json"])
            wait_flag(ip, "/tmp/lora_train.done", t0, itype)
            adapter = "lora_adapter_b"
        print(f"scoring adapter on dev ({adapter})", flush=True)
        start_remote(ip, "start_lora_adapter.sh", ["dev", adapter, "score_qwen_elig_lora_dev.json", "/tmp/lora_dev.done"])
        wait_flag(
            ip,
            "/tmp/lora_dev.done",
            t0,
            itype,
            lambda: scp_from(ip, "score_qwen_elig_lora_dev.json", DATA / "score_qwen_elig_lora_dev.json"),
        )
        scp_from(ip, "score_qwen_elig_lora_dev.json", DATA / "score_qwen_elig_lora_dev.json")
        run_eval(DATA / "score_qwen_elig_lora_dev.json", "lora_dev", DATA / "trec_lora_dev_results.json")
        print("scoring adapter on 2022 test once", flush=True)
        start_remote(ip, "start_lora_adapter.sh", ["test", adapter, "score_qwen_elig_lora.json", "/tmp/lora_test.done"])
        wait_flag(
            ip,
            "/tmp/lora_test.done",
            t0,
            itype,
            lambda: scp_from(ip, "score_qwen_elig_lora.json", ADAPTER_SCORES),
        )
        scp_from(ip, "score_qwen_elig_lora.json", ADAPTER_SCORES)
        run_eval(ADAPTER_SCORES, "lora_test", LORA_RESULTS)
        try:
            subprocess.check_call(
                [
                    "scp",
                    "-i",
                    str(SSH_KEY),
                    "-o",
                    "StrictHostKeyChecking=accept-new",
                    "-r",
                    f"ubuntu@{ip}:{adapter}",
                    str(ADAPTER_DIR),
                ]
            )
        except subprocess.CalledProcessError:
            print("copy adapter failed", flush=True)
        subprocess.check_call(ssh_base(ip) + ["bash", "-lc", "touch /tmp/lora_all.done"])
        print(
            f"copy verified hours {(time.time() - t0) / 3600:.2f} "
            f"type {itype} spend ${spend(t0, itype):.2f}",
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
                    "spend": round(spend(t0, itype), 2),
                }
            )


if __name__ == "__main__":
    main()
