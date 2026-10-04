"""Score the rule-by-rule reader on locked TREC pairs. GPU worker.

Resumable JSONL. Stores raw model text. Does not drop flagged quotes.
The system does not say a patient qualifies.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

ROOT = Path(__file__).resolve().parents[1]
if (ROOT / "reader").exists():
    sys.path.insert(0, str(ROOT))
else:
    sys.path.insert(0, str(Path.cwd()))

from reader.judge import read_trial  # noqa: E402

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

PACK_PATH = Path(os.environ.get("READER_PACK", "score_pack.json"))
PAIRS_PATH = Path(os.environ.get("READER_PAIRS", "trec_reader_probe_pairs.json"))
OUT_PATH = Path(os.environ.get("READER_OUT", "trec_reader_probe_reads.jsonl"))
KEEP_ALIVE = Path("/tmp/keep_alive")
DONE_PATH = Path("/tmp/reader.done")
PROGRESS = Path("/tmp/qwen_progress.txt")
QWEN_NAME = "Qwen/Qwen2.5-7B-Instruct"
MAX_IN = 6144
MAX_NEW = 2048


def touch() -> None:
    try:
        KEEP_ALIVE.write_text("1", encoding="utf-8")
    except OSError:
        pass


def heartbeat() -> None:
    while not DONE_PATH.exists():
        touch()
        time.sleep(60)


def progress(msg: str) -> None:
    print(msg, flush=True)
    try:
        PROGRESS.write_text(msg + "\n", encoding="utf-8")
    except OSError:
        pass


def load_done() -> set[str]:
    done = set()
    if not OUT_PATH.exists():
        return done
    with OUT_PATH.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("nct_id"):
                done.add(f"{row.get('patient_id')}::{row['nct_id']}")
    return done


def jobs(pairs: dict, pack: dict) -> list[dict]:
    docs = pack["docs"]
    notes = {}
    for tid, trow in (pack.get("years") or {}).get("2022", {}).get("topics", {}).items():
        notes[str(tid)] = trow.get("raw_query") or ""
    out = []
    for tid, rows in (pairs.get("topics") or {}).items():
        note = notes.get(str(tid)) or ""
        for row in rows:
            nct = row["nct_id"] if isinstance(row, dict) else row[0]
            doc = docs.get(nct) or {}
            out.append(
                {
                    "patient_id": str(tid),
                    "nct_id": nct,
                    "note": note,
                    "title": doc.get("title") or "",
                    "eligibility": doc.get("eligibility") or "",
                    "label": row.get("label") if isinstance(row, dict) else None,
                }
            )
    return out


def main() -> None:
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    pairs = json.loads(PAIRS_PATH.read_text(encoding="utf-8"))
    pending = [j for j in jobs(pairs, pack) if f"{j['patient_id']}::{j['nct_id']}" not in load_done()]
    progress(f"reader pending={len(pending)} out={OUT_PATH}")
    threading.Thread(target=heartbeat, daemon=True).start()

    tok = AutoTokenizer.from_pretrained(QWEN_NAME, trust_remote_code=True)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "left"
    model = AutoModelForCausalLM.from_pretrained(
        QWEN_NAME,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    model.eval()

    def complete(system: str, user: str) -> str:
        text = tok.apply_chat_template(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            tokenize=False,
            add_generation_prompt=True,
        )
        enc = tok(text, return_tensors="pt", truncation=True, max_length=MAX_IN)
        enc = {k: v.to(model.device) for k, v in enc.items()}
        with torch.no_grad():
            gen = model.generate(
                **enc,
                max_new_tokens=MAX_NEW,
                do_sample=False,
                use_cache=True,
                pad_token_id=tok.pad_token_id,
            )
        new = gen[0, enc["input_ids"].shape[1] :]
        return tok.decode(new, skip_special_tokens=True)

    t0 = time.time()
    n_done = 0
    with OUT_PATH.open("a", encoding="utf-8") as fh:
        for job in pending:
            started = time.perf_counter()
            result = read_trial(
                job["patient_id"],
                job["nct_id"],
                job["note"],
                job["title"],
                job["eligibility"],
                complete,
            )
            rec = result.to_dict()
            rec["label"] = job.get("label")
            rec["elapsed_s"] = round(time.perf_counter() - started, 3)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            n_done += 1
            if n_done == 1 or n_done % 5 == 0:
                rate = n_done / max(time.time() - t0, 1)
                progress(
                    f"reader {n_done}/{len(pending)} "
                    f"{rec['elapsed_s']}s last "
                    f"{rate:.3f}/s schema_ok={rec['schema_ok']}"
                )
    DONE_PATH.write_text("1", encoding="utf-8")
    progress(f"reader done {n_done} seconds={time.time() - t0:.1f}")


if __name__ == "__main__":
    main()
