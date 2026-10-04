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
from trec_reader_common import DATA, PAIRS, PROBE_PAIRS, PROBE_READS, PROBE_READS_V2, READS  # noqa: E402
from trec_score_common import PACK  # noqa: E402

SSH_KEY = Path.home() / ".ssh" / "lambda_key"
NAME = "trec-reader-probe"
STAGE = DATA / "lambda_stage"
STATE = DATA / "reader_probe_lambda_state.json"
SPEND_CAP = 25.0
FULL_PAIRS = 1250
PROBE_PAIRS_N = 50
RETRY_SEC = 30
# A10 is the wrong card and the wrong image. Wait for H100/A100.
TYPE_PREF = (
    "gpu_1x_h100_sxm5",
    "gpu_1x_h100_pcie",
    "gpu_1x_a100_sxm4",
    "gpu_1x_a100",
)
VENV_PY = "/home/ubuntu/venv/bin/python"


def wait_name_free(key: str, name: str = NAME) -> None:
    while True:
        listed = api("GET", "/instances", key)
        live = [
            row
            for row in (listed.get("data") or [])
            if row.get("name") == name and row.get("status") not in {"terminated"}
        ]
        if not live:
            return
        if all(row.get("status") == "terminating" for row in live):
            print("waiting for old instance to finish terminating", flush=True)
            time.sleep(10)
            continue
        raise SystemExit(f"already running {live[0].get('id')} status {live[0].get('status')}")


def wait_launch(key: str) -> tuple[str, str, str]:
    ljunk.TYPE_PREF = TYPE_PREF
    started = time.time()
    last = 0.0
    print("waiting for H100/A100 capacity", flush=True)
    while True:
        try:
            return launch(key)
        except SystemExit as exc:
            msg = str(exc)
            low = msg.lower()
            if any(s in low for s in ("capacity", "no gpu", "out of stock", "429")):
                now = time.time()
                if now - last >= 300:
                    print(f"still no H100/A100 after {int((now - started) / 60)} min", flush=True)
                    last = now
                time.sleep(RETRY_SEC)
                continue
            raise


def write_stage_sh(name: str, body: str) -> Path:
    dest = STAGE / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body.replace("\r\n", "\n").encode("utf-8"))
    return dest


def ensure_stack(ip: str) -> None:
    script = write_stage_sh(
        "ensure_reader_stack.sh",
        f"""#!/bin/bash
set -e
export PYTHONIOENCODING=utf-8
if {VENV_PY} -c 'import transformers, torch'; then
  echo STACK_OK
  {VENV_PY} -c 'import transformers, torch; print(transformers.__version__, torch.__version__, torch.cuda.is_available())'
  exit 0
fi
python3 -m venv ~/venv
. ~/venv/bin/activate
pip install -q --upgrade pip
pip install -q torch --index-url https://download.pytorch.org/whl/cu124
pip install -q transformers accelerate
{VENV_PY} -c 'import transformers, torch; print(transformers.__version__, torch.__version__, torch.cuda.is_available())'
""",
    )
    scp_to(ip, script, "/tmp/ensure_reader_stack.sh")
    subprocess.check_call(ssh_base(ip) + ["bash", "/tmp/ensure_reader_stack.sh"])


def start_reader(ip: str, pairs_name: str, out_name: str) -> None:
    script = write_stage_sh(
        "start_reader.sh",
        f"""#!/bin/bash
set -e
export PYTHONIOENCODING=utf-8
export READER_PACK=score_pack.json
export READER_PAIRS={pairs_name}
export READER_OUT={out_name}
cd /home/ubuntu
nohup {VENV_PY} -u lambda_qwen_reader.py > /tmp/reader.log 2>&1 &
echo $!
""",
    )
    scp_to(ip, script, "/tmp/start_reader.sh")
    subprocess.check_call(ssh_base(ip) + ["bash", "/tmp/start_reader.sh"])


def generation_stats(path: Path) -> dict:
    n = 0
    ok = 0
    gens = 0
    coerced = 0
    if path.exists():
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                row = json.loads(line)
                n += 1
                gens += int(row.get("retries") or 0) + 1
                if row.get("schema_ok"):
                    ok += 1
                coerced += len(row.get("coerced_rule_ids") or [])
    return {
        "n": n,
        "schema_ok": ok,
        "generations": gens,
        "generations_per_trial": round(gens / n, 3) if n else 0.0,
        "valid_rate": round(ok / n, 3) if n else 0.0,
        "coerced_rules": coerced,
    }


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
    full = "--full" in sys.argv
    local_pairs = PAIRS if full else PROBE_PAIRS
    local_reads = READS if full else PROBE_READS_V2
    remote_pairs = "trec_reader_pairs.json" if full else "trec_reader_probe_pairs.json"
    remote_out = "trec_reader_reads.jsonl" if full else "trec_reader_probe_reads_v2.jsonl"
    job_name = "trec-reader-full" if full else NAME
    state = DATA / ("reader_full_lambda_state.json" if full else "reader_probe_v2_lambda_state.json")
    need = FULL_PAIRS if full else PROBE_PAIRS_N
    if not SSH_KEY.exists():
        raise SystemExit(f"missing {SSH_KEY}")
    if not PACK.exists() or not local_pairs.exists():
        raise SystemExit("pack or pairs missing; run trec_reader_draw.py")
    key = load_lambda_key()
    ljunk.NAME = job_name
    lrl.NAME = job_name
    lrl.STATE = state
    lrl.HOURLY = HOURLY
    lrl.spend = spend
    lrl.SPEND_CAP = SPEND_CAP
    wait_name_free(key, job_name)
    instance_id = None
    itype = ""
    t0 = time.time()
    try:
        instance_id, itype, region = wait_launch(key)
        t0 = time.time()
        state.write_text(
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
        scp_to(ip, local_pairs, remote_pairs)
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
        ensure_stack(ip)
        start_reader(ip, remote_pairs, remote_out)
        wait_flag(ip, "/tmp/reader.done", t0, itype)
        scp_from(ip, remote_out, local_reads)
        stats = generation_stats(local_reads)
        n = stats["n"]
        hours = (time.time() - t0) / 3600.0
        usd = spend(t0, itype)
        if n < need:
            raise SystemExit(f"{'full' if full else 'probe'} reads only {n}")
        scale = FULL_PAIRS / max(n, 1)
        proj = {
            "mode": "full" if full else "probe_v2",
            "pairs": n,
            "schema_ok": stats["schema_ok"],
            "valid_rate": stats["valid_rate"],
            "generations": stats["generations"],
            "generations_per_trial": stats["generations_per_trial"],
            "coerced_rules": stats["coerced_rules"],
            "hours": round(hours, 3),
            "usd": round(usd, 2),
            "full_pairs": FULL_PAIRS,
            "proj_hours": round(hours * scale, 2),
            "proj_usd": round(usd * scale, 2),
            "type": itype,
            "baseline_valid": "13/50" if not full else None,
        }
        out_proj = DATA / ("trec_reader_full_cost.json" if full else "trec_reader_projection_v2.json")
        out_proj.write_text(json.dumps(proj, indent=2), encoding="utf-8")
        print(json.dumps(proj, indent=2), flush=True)
        if not full and proj["proj_usd"] > 25:
            print("projection over $25; not starting the full pass", flush=True)
    finally:
        if instance_id:
            terminate(key, instance_id)


if __name__ == "__main__":
    main()
