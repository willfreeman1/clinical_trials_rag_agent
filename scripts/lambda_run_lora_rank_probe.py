"""Score two 2022 patients with the saved adapter. Project cost. Copy off, terminate."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lambda_common import api, load_lambda_key  # noqa: E402
import lambda_run_lora as lrl  # noqa: E402
from lambda_run_lora import start_remote, terminate, wait_flag  # noqa: E402
import lambda_run_lora_junk as ljunk  # noqa: E402
from lambda_run_lora_junk import HOURLY, launch, spend  # noqa: E402
from lambda_run_rerank import scp_from, scp_to, ssh_base, wait_ip, wait_ssh, write_unix  # noqa: E402
from trec_lora_common import (  # noqa: E402
    RANK_CONFIG,
    RANK_PROBE_PAIRS,
    RANK_SCORES,
    SEED_C,
    adapter_dir_for,
    adapter_scores_for,
)
from trec_score_common import DATA, PACK  # noqa: E402

SSH_KEY = Path.home() / ".ssh" / "lambda_key"
NAME = "trec-lora-rank-probe"
STAGE = DATA / "lambda_stage"
STATE = DATA / "lora_rank_probe_state.json"
FULL_N = 79750
SPEND_CAP = 12.0


def score_count(path: Path) -> int:
    if not path.exists() or path.stat().st_size < 200:
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    return sum(len(t) for y in (data.get("scores") or {}).values() for t in y.values())


def main() -> None:
    if not SSH_KEY.exists():
        raise SystemExit(f"missing {SSH_KEY}")
    if not PACK.exists() or not RANK_PROBE_PAIRS.exists():
        raise SystemExit("pack or probe pairs missing")
    adapter = adapter_dir_for(SEED_C)
    if not adapter.exists():
        raise SystemExit(f"missing adapter {adapter}")
    key = load_lambda_key()
    ljunk.NAME = NAME
    lrl.NAME = NAME
    lrl.STATE = STATE
    lrl.HOURLY = HOURLY
    lrl.spend = spend
    lrl.SPEND_CAP = SPEND_CAP
    listed = api("GET", "/instances", key)
    for row in listed.get("data") or []:
        if row.get("name") == NAME and row.get("status") not in {"terminated", "terminating"}:
            raise SystemExit(f"already running {row.get('id')} status {row.get('status')}")
    if adapter_scores_for(SEED_C).exists() and not RANK_SCORES.exists():
        shutil.copy2(adapter_scores_for(SEED_C), RANK_SCORES)
    start_n = score_count(RANK_SCORES)
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
            (here / "lambda_start_lora_adapter.sh", STAGE / "start_lora_adapter.sh"),
        ):
            write_unix(src, dest)
        scp_to(ip, STAGE / "deadman_lora.sh", "/tmp/deadman.sh")
        subprocess.check_call(ssh_base(ip) + ["chmod", "+x", "/tmp/deadman.sh"])
        subprocess.check_call(ssh_base(ip) + ["bash", "-lc", "nohup /tmp/deadman.sh >/tmp/deadman.log 2>&1 &"])
        scp_to(ip, STAGE / "lambda_setup_lora.sh", "/tmp/lambda_setup_lora.sh")
        subprocess.check_call(ssh_base(ip) + ["bash", "/tmp/lambda_setup_lora.sh"])
        scp_to(ip, STAGE / "lambda_qwen_lora_score.py", "lambda_qwen_lora_score.py")
        scp_to(ip, PACK, "score_pack.json")
        scp_to(ip, RANK_PROBE_PAIRS, "trec_lora_rank_probe_pairs.json")
        if RANK_SCORES.exists():
            scp_to(ip, RANK_SCORES, "score_qwen_elig_lora_rank.json")
        scp_to(ip, STAGE / "start_lora_adapter.sh", "/tmp/start_lora_adapter.sh")
        subprocess.check_call(ssh_base(ip) + ["chmod", "+x", "/tmp/start_lora_adapter.sh"])
        subprocess.check_call(
            [
                "scp",
                "-i",
                str(SSH_KEY),
                "-o",
                "StrictHostKeyChecking=accept-new",
                "-r",
                str(adapter),
                f"ubuntu@{ip}:lora_adapter",
            ]
        )
        print("scoring probe patients 1 and 2", flush=True)
        score_t0 = time.time()
        start_remote(
            ip,
            "start_lora_adapter.sh",
            [
                "test",
                "lora_adapter",
                "score_qwen_elig_lora_rank.json",
                "/tmp/lora_probe.done",
                "trec_lora_rank_probe_pairs.json",
            ],
        )
        wait_flag(
            ip,
            "/tmp/lora_probe.done",
            t0,
            itype,
            lambda: scp_from(ip, "score_qwen_elig_lora_rank.json", RANK_SCORES),
        )
        scp_from(ip, "score_qwen_elig_lora_rank.json", RANK_SCORES)
        n = score_count(RANK_SCORES)
        new = max(0, n - start_n)
        secs = max(1.0, time.time() - score_t0)
        rate = new / secs
        remain = max(0, FULL_N - n)
        hours = remain / rate / 3600 if rate else 99
        dollars = hours * HOURLY.get(itype, 1.79)
        cfg = json.loads(RANK_CONFIG.read_text(encoding="utf-8"))
        proj = {
            "adapter_seed": cfg["adapter_seed"],
            "gpu": itype,
            "probe_new_scores": new,
            "probe_seconds": round(secs, 1),
            "pairs_per_sec": round(rate, 3),
            "already_on_disk": n,
            "remaining": remain,
            "projected_score_hours": round(hours, 2),
            "projected_score_usd": round(dollars, 2),
            "probe_spend": round(spend(t0, itype), 2),
            "under_25": dollars + spend(t0, itype) < 25,
        }
        (DATA / "trec_lora_rank_projection.json").write_text(json.dumps(proj, indent=2), encoding="utf-8")
        print(json.dumps(proj, indent=2), flush=True)
        subprocess.check_call(ssh_base(ip) + ["touch", "/tmp/lora_all.done"])
        print(f"probe copied n={n} spend ${spend(t0, itype):.2f}", flush=True)
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
