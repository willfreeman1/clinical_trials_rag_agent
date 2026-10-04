"""Probe the reader on two 2022 patients. Copy off, project, terminate.

No full pass from this script. Stop and ask if the projection heads
past about $25.
The system does not say a patient qualifies.
"""

from __future__ import annotations

import json
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
from trec_reader_common import DATA, PROBE_PAIRS, PROBE_READS  # noqa: E402
from trec_score_common import PACK  # noqa: E402

SSH_KEY = Path.home() / ".ssh" / "lambda_key"
NAME = "trec-reader-probe"
STAGE = DATA / "lambda_stage"
STATE = DATA / "reader_probe_lambda_state.json"
SPEND_CAP = 25.0
FULL_PAIRS = 1250
PROBE_PAIRS_N = 50


def reads_count(path: Path) -> int:
    if not path.exists():
        return 0
    n = 0
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                n += 1
    return n


def main() -> None:
    if not SSH_KEY.exists():
        raise SystemExit(f"missing {SSH_KEY}")
    if not PACK.exists() or not PROBE_PAIRS.exists():
        raise SystemExit("pack or probe pairs missing; run trec_reader_draw.py")
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
    instance_id = None
    itype = ""
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
        here = Path(__file__).parent
        root = here.parent
        subprocess.check_call(ssh_base(ip) + ["mkdir", "-p", "reader"])
        scp_to(ip, write_unix(here / "lambda_qwen_reader.py", STAGE / "lambda_qwen_reader.py"), "lambda_qwen_reader.py")
        scp_to(ip, PACK, "score_pack.json")
        scp_to(ip, PROBE_PAIRS, "trec_reader_probe_pairs.json")
        for name in (
            "__init__.py",
            "schema.py",
            "split_rules.py",
            "verify_quote.py",
            "prompt.py",
            "aggregate.py",
            "judge.py",
        ):
            scp_to(ip, root / "reader" / name, f"reader/{name}")
        env = (
            "export PYTHONIOENCODING=utf-8 READER_PACK=score_pack.json "
            "READER_PAIRS=trec_reader_probe_pairs.json "
            "READER_OUT=trec_reader_probe_reads.jsonl"
        )
        subprocess.check_call(
            ssh_base(ip)
            + [
                "bash",
                "-lc",
                f"{env}; nohup python3 -u lambda_qwen_reader.py > /tmp/reader.log 2>&1 &",
            ]
        )
        wait_flag(ip, "/tmp/reader.done", t0, itype)
        scp_from(ip, "trec_reader_probe_reads.jsonl", PROBE_READS)
        n = reads_count(PROBE_READS)
        hours = (time.time() - t0) / 3600.0
        usd = spend(t0, itype)
        if n < PROBE_PAIRS_N:
            raise SystemExit(f"probe reads only {n}")
        scale = FULL_PAIRS / max(n, 1)
        proj = {
            "probe_pairs": n,
            "probe_hours": round(hours, 3),
            "probe_usd": round(usd, 2),
            "full_pairs": FULL_PAIRS,
            "proj_hours": round(hours * scale, 2),
            "proj_usd": round(usd * scale, 2),
            "type": itype,
        }
        (DATA / "trec_reader_projection.json").write_text(
            json.dumps(proj, indent=2), encoding="utf-8"
        )
        print(json.dumps(proj, indent=2), flush=True)
        if proj["proj_usd"] > 25:
            print("projection over $25; not starting the full pass", flush=True)
    finally:
        if instance_id:
            terminate(key, instance_id)


if __name__ == "__main__":
    main()
