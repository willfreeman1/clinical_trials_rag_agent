"""Train two more 1e-5 LoRA seeds on one GPU. Copy off, terminate."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lambda_common import api, load_lambda_key  # noqa: E402
import lambda_run_lora as lrl  # noqa: E402
from lambda_run_lora import (  # noqa: E402
    remote_has,
    run_eval,
    start_remote,
    terminate,
    wait_flag,
)
from lambda_run_rerank import scp_from, scp_to, ssh_base, wait_ip, wait_ssh, write_unix  # noqa: E402
from trec_lora_common import (  # noqa: E402
    CONFIG_PATH,
    EVAL_PAIRS_PATH,
    SEED_B,
    SEED_C,
    adapter_dir_for,
    adapter_scores_for,
    train_log_for,
    train_pairs_for,
)
from trec_score_common import DATA, PACK  # noqa: E402

SSH_KEY = Path.home() / ".ssh" / "lambda_key"
SSH_NAME = "paper-reviewer-project"
TYPE_PREF = (
    "gpu_1x_h100_sxm5",
    "gpu_1x_h100_pcie",
    "gpu_1x_a100_sxm4",
    "gpu_1x_a100",
    "gpu_1x_a6000",
    "gpu_1x_a10",
)
HOURLY = {
    "gpu_1x_h100_sxm5": 4.29,
    "gpu_1x_h100_pcie": 3.29,
    "gpu_1x_a100_sxm4": 1.79,
    "gpu_1x_a100": 1.29,
    "gpu_1x_a6000": 0.80,
    "gpu_1x_a10": 0.75,
}
NAME = "trec-lora-seeds"
STAGE = DATA / "lambda_stage"
STATE = DATA / "lora_seeds_lambda_state.json"
SEEDS = (SEED_B, SEED_C)
MIN_SCORES = 6000
SPEND_CAP = 25.0


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
    raise SystemExit("No GPU capacity")


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


def spend(t0: float, itype: str) -> float:
    return ((time.time() - t0) / 3600.0) * HOURLY.get(itype, 1.79)


def score_count(path: Path) -> int:
    if not path.exists() or path.stat().st_size < 200:
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    return sum(len(t) for y in (data.get("scores") or {}).values() for t in y.values())


def copy_adapter(ip: str, remote_name: str, dest: Path) -> None:
    if dest.exists():
        import shutil

        shutil.rmtree(dest)
    subprocess.check_call(
        [
            "scp",
            "-i",
            str(SSH_KEY),
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-r",
            f"ubuntu@{ip}:{remote_name}",
            str(dest),
        ]
    )


def run_one(ip: str, seed: int, t0: float, itype: str) -> None:
    pairs = train_pairs_for(seed)
    if not pairs.exists():
        raise SystemExit(f"missing {pairs}; draw first")
    remote_pairs = "trec_lora_train_pairs.json"
    remote_adapter = f"lora_adapter_{seed}"
    remote_log = f"lora_train_log_{seed}.json"
    remote_scores = f"score_qwen_elig_lora_{seed}.json"
    log_dest = train_log_for(seed)
    score_dest = adapter_scores_for(seed)
    adapter_dest = adapter_dir_for(seed)
    result_dest = DATA / f"trec_lora_adapter_results_{seed}.json"
    scp_to(ip, pairs, remote_pairs)
    subprocess.check_call(ssh_base(ip) + ["rm", "-f", "/tmp/lora_train.done", "/tmp/lora_collapsed", "/tmp/lora_test.done"])
    print(f"starting train seed {seed}", flush=True)
    start_remote(
        ip,
        "start_lora_train.sh",
        ["logit2_minus_logit1", remote_adapter, remote_log, str(seed)],
    )
    wait_flag(ip, "/tmp/lora_train.done", t0, itype, lambda: scp_from(ip, remote_log, log_dest))
    try:
        scp_from(ip, remote_log, log_dest)
    except subprocess.CalledProcessError:
        print(f"copy train log failed seed {seed}", flush=True)
    collapsed = remote_has(ip, "/tmp/lora_collapsed")
    if collapsed:
        print(f"seed {seed} collapsed; still scoring 2022 once", flush=True)
    print(f"scoring 2022 once seed {seed}", flush=True)
    start_remote(
        ip,
        "start_lora_adapter.sh",
        ["test", remote_adapter, remote_scores, "/tmp/lora_test.done"],
    )
    wait_flag(ip, "/tmp/lora_test.done", t0, itype, lambda: scp_from(ip, remote_scores, score_dest))
    scp_from(ip, remote_scores, score_dest)
    n = score_count(score_dest)
    if n < MIN_SCORES:
        raise SystemExit(f"seed {seed} scores only {n}")
    run_eval(score_dest, f"lora_seed_{seed}", result_dest)
    try:
        copy_adapter(ip, remote_adapter, adapter_dest)
    except subprocess.CalledProcessError:
        print(f"copy adapter failed seed {seed}", flush=True)
    print(f"seed {seed} copied n={n} collapsed={collapsed} spend ${spend(t0, itype):.2f}", flush=True)


def main() -> None:
    if not SSH_KEY.exists():
        raise SystemExit(f"missing {SSH_KEY}")
    if not PACK.exists():
        raise SystemExit(f"missing {PACK}")
    if not EVAL_PAIRS_PATH.exists():
        raise SystemExit("eval pair list missing")
    for seed in SEEDS:
        if not train_pairs_for(seed).exists():
            raise SystemExit(f"missing {train_pairs_for(seed)}")
    key = load_lambda_key()
    lrl.NAME = NAME
    lrl.STATE = STATE
    lrl.HOURLY = HOURLY
    lrl.spend = spend
    lrl.SPEND_CAP = SPEND_CAP
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
        STATE.write_text(
            json.dumps({"instance_id": instance_id, "type": itype, "region": region, "t0": t0}, indent=2),
            encoding="utf-8",
        )
        ip = wait_ip(key, instance_id)
        wait_ssh(ip)
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
        scp_to(ip, CONFIG_PATH, "trec_lora_config.json")
        for sh in ("start_lora_train.sh", "start_lora_adapter.sh"):
            scp_to(ip, STAGE / sh, f"/tmp/{sh}")
            subprocess.check_call(ssh_base(ip) + ["chmod", "+x", f"/tmp/{sh}"])
        print(f"spend so far ${spend(t0, itype):.2f}; two seeds, 2022 scored once each", flush=True)
        if spend(t0, itype) + 12 > SPEND_CAP:
            raise SystemExit("two seeds would likely push past $25; stopping to ask")
        for seed in SEEDS:
            run_one(ip, seed, t0, itype)
        subprocess.check_call(
            [sys.executable, str(here / "trec_lora_seed_summary.py")],
            env={**{k: v for k, v in __import__("os").environ.items()}, "PYTHONIOENCODING": "utf-8"},
        )
        subprocess.check_call(ssh_base(ip) + ["touch", "/tmp/lora_all.done"])
        print(f"copy verified hours {(time.time() - t0) / 3600:.2f} spend ${spend(t0, itype):.2f}", flush=True)
    finally:
        if instance_id:
            try:
                terminate(key, instance_id)
            except Exception as exc:
                print("terminate failed", type(exc).__name__, flush=True)
                raise
            STATE.write_text(
                json.dumps(
                    {
                        "instance_id": instance_id,
                        "type": itype,
                        "region": region,
                        "terminated": True,
                        "hours": round((time.time() - t0) / 3600, 3),
                        "spend": round(spend(t0, itype), 2),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )


if __name__ == "__main__":
    main()
