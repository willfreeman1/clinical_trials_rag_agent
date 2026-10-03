"""Score the saved 1e-5 adapter on sampled junk. No retraining. Copy off, terminate."""

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
    launch,
    spend,
    start_remote,
    terminate,
    wait_flag,
)
from lambda_run_rerank import scp_from, scp_to, ssh_base, wait_ip, wait_ssh, write_unix  # noqa: E402
from trec_lora_common import ADAPTER_LR1E5, JUNK_PAIRS_PATH, JUNK_SCORES  # noqa: E402
from trec_score_common import DATA, PACK  # noqa: E402

SSH_KEY = Path.home() / ".ssh" / "lambda_key"
SSH_NAME = "paper-reviewer-project"
NAME = "trec-lora-junk"
STAGE = DATA / "lambda_stage"
STATE = DATA / "lora_junk_lambda_state.json"
MIN_SCORES = 6000


def score_count(path: Path) -> int:
    if not path.exists() or path.stat().st_size < 200:
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    return sum(len(t) for y in (data.get("scores") or {}).values() for t in y.values())


def main() -> None:
    if not SSH_KEY.exists():
        raise SystemExit(f"missing {SSH_KEY}")
    if not PACK.exists():
        raise SystemExit(f"missing {PACK}")
    if not JUNK_PAIRS_PATH.exists():
        raise SystemExit("junk pair list missing; run trec_lora_junk_draw.py")
    if not ADAPTER_LR1E5.exists():
        raise SystemExit(f"missing adapter {ADAPTER_LR1E5}")
    key = load_lambda_key()
    lrl.NAME = NAME
    lrl.STATE = STATE
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
        scp_to(ip, JUNK_PAIRS_PATH, "trec_lora_junk_pairs.json")
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
                str(ADAPTER_LR1E5),
                f"ubuntu@{ip}:lora_adapter",
            ]
        )
        print("scoring saved adapter on junk sample", flush=True)
        start_remote(
            ip,
            "start_lora_adapter.sh",
            [
                "test",
                "lora_adapter",
                "score_qwen_elig_lora_junk.json",
                "/tmp/lora_junk.done",
                "trec_lora_junk_pairs.json",
            ],
        )
        wait_flag(
            ip,
            "/tmp/lora_junk.done",
            t0,
            itype,
            lambda: scp_from(ip, "score_qwen_elig_lora_junk.json", JUNK_SCORES),
        )
        scp_from(ip, "score_qwen_elig_lora_junk.json", JUNK_SCORES)
        n = score_count(JUNK_SCORES)
        if n < MIN_SCORES:
            raise SystemExit(f"junk scores only {n}")
        subprocess.check_call(
            [sys.executable, str(here / "trec_lora_junk_eval.py")],
            env={**{k: v for k, v in __import__("os").environ.items()}, "PYTHONIOENCODING": "utf-8"},
        )
        subprocess.check_call(ssh_base(ip) + ["touch", "/tmp/lora_all.done"])
        print(f"copy verified n={n} hours {(time.time() - t0) / 3600:.2f} spend ${spend(t0, itype):.2f}", flush=True)
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
