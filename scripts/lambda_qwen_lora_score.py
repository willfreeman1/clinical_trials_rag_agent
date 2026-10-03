"""Score judged 1-and-2 pairs with the v1 eligibility prompt. Base or adapter."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

PACK_PATH = Path("score_pack.json")
PAIRS_PATH = Path("trec_lora_eval_pairs.json")
KEEP_ALIVE = Path("/tmp/keep_alive")
PROGRESS = Path("/tmp/qwen_progress.txt")
QWEN_NAME = "Qwen/Qwen2.5-7B-Instruct"
MAX_LEN = 3072

ELIG_SYSTEM = """You judge whether a patient appears to meet a clinical trial's stated eligibility criteria.

This is not a decision that the patient qualifies. Do not say the patient can join the trial. The score is a ranking signal for a human who will read the criteria.

score is an integer 0, 1, 2, or 3.
0 = different disease or situation, or the stated criteria clearly rule this patient out
1 = right disease area, but one or more stated criteria probably fail
2 = right disease area, and the stated criteria look mostly compatible, with real remaining uncertainty
3 = the stated criteria look compatible with the description

If you cannot tell from the text, choose 2. Do not use 0 or 3 to express uncertainty. Uncertainty belongs in the middle of the scale.

Answer with a single digit: 0, 1, 2, or 3."""


def touch() -> None:
    try:
        KEEP_ALIVE.write_text("1", encoding="utf-8")
    except OSError:
        pass


def heartbeat(done: Path) -> None:
    while not done.exists():
        touch()
        time.sleep(60)


def progress(msg: str) -> None:
    print(msg, flush=True)
    try:
        PROGRESS.write_text(msg + "\n", encoding="utf-8")
    except OSError:
        pass


def cond_list(row: dict) -> list[str]:
    raw = row.get("conditions") or []
    if isinstance(raw, str):
        return [raw] if raw.strip() else []
    return [str(c).strip() for c in raw if str(c).strip()]


def full_criteria(row: dict) -> str:
    title = (row.get("title") or "").strip()
    conds = "; ".join(cond_list(row))
    parts = [p for p in (title, f"Conditions: {conds}" if conds else "") if p]
    base = "\n".join(parts) or " "
    elig = (row.get("eligibility") or "").strip()
    if elig:
        return f"{base}\nEligibility criteria:\n{elig}"
    body = (row.get("text") or "").strip()
    return f"{base}\nTrial text:\n{body}" if body else base


def user_text(note: str, doc: str) -> str:
    return f"Patient description:\n{note}\n\nTrial record:\n{doc}\n"


def digit_ids(tok) -> list[int]:
    out = []
    for i in range(4):
        found = None
        for variant in (str(i), " " + str(i)):
            ids = tok.encode(variant, add_special_tokens=False)
            if len(ids) == 1:
                found = ids[0]
                break
        if found is None:
            raise SystemExit(f"digit {i} is not a single token")
        out.append(found)
    return out


def atomic_write(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def jobs_for(pack: dict, pairs: dict, split: str, have: dict) -> list[tuple[str, str, str, str]]:
    blocks = []
    if split in ("all", "dev"):
        blocks.append(("2021", pairs["dev_2021"]["topics"]))
    if split in ("all", "test"):
        blocks.append(("2022", pairs["test_2022"]["topics"]))
    out = []
    for year, topics in blocks:
        tpack = pack["years"][year]["topics"]
        for tid, rows in topics.items():
            note = tpack[tid].get("raw_query") or " "
            got = (have.get(year) or {}).get(tid) or {}
            for nct, _lab in rows:
                if nct not in got:
                    out.append((year, tid, nct, note))
    return out


@torch.no_grad()
def score_batch(users, tok, model, ids, batch_size):
    out = []
    i = 0
    while i < len(users):
        batch = users[i : i + batch_size]
        texts = [
            tok.apply_chat_template(
                [{"role": "system", "content": ELIG_SYSTEM}, {"role": "user", "content": u}],
                tokenize=False,
                add_generation_prompt=True,
            )
            for u in batch
        ]
        enc = tok(texts, return_tensors="pt", padding=True, truncation=True, max_length=MAX_LEN)
        enc = {k: v.to(model.device) for k, v in enc.items()}
        try:
            try:
                logits = model(**enc, use_cache=False, logits_to_keep=1).logits[:, -1, :]
            except TypeError:
                logits = model(**enc, use_cache=False).logits[:, -1, :]
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            if batch_size == 1:
                raise
            batch_size = max(1, batch_size // 2)
            progress(f"  oom, batch now {batch_size}")
            continue
        stacked = torch.stack([logits[:, did] for did in ids], dim=1)
        probs = torch.softmax(stacked.float(), dim=1)
        out.extend(row.tolist() for row in probs.cpu())
        i += len(batch)
        touch()
    return out, batch_size


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--split", choices=("all", "dev", "test"), default="all")
    ap.add_argument("--adapter", default="")
    ap.add_argument("--pairs", default="trec_lora_eval_pairs.json")
    ap.add_argument("--done", default="/tmp/lora_score.done")
    args = ap.parse_args()
    out_path = Path(args.out)
    done = Path(args.done)
    if done.exists():
        done.unlink()
    if not torch.cuda.is_available():
        raise SystemExit("CUDA not available")
    gpu = torch.cuda.get_device_name(0)
    progress(f"gpu {gpu} split {args.split} adapter {args.adapter or 'none'}")
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    pairs_path = Path(args.pairs)
    pairs = json.loads(pairs_path.read_text(encoding="utf-8"))
    payload = {}
    if out_path.exists():
        payload = json.loads(out_path.read_text(encoding="utf-8"))
    payload.setdefault("scores", {})
    payload["model"] = QWEN_NAME
    payload["prompt"] = "v1_ELIG_SYSTEM_DIGIT"
    payload["adapter"] = args.adapter or None
    payload["gpu"] = gpu
    threading.Thread(target=heartbeat, args=(done,), daemon=True).start()
    progress("load Qwen")
    tok = AutoTokenizer.from_pretrained(QWEN_NAME, padding_side="left")
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        QWEN_NAME,
        torch_dtype=torch.float16,
        device_map="cuda",
    )
    if args.adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, args.adapter)
    model.eval()
    ids = digit_ids(tok)
    jobs = jobs_for(pack, pairs, args.split, payload["scores"])
    mem_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
    batch_size = 16 if mem_gb >= 70 else (8 if mem_gb >= 30 else 2)
    progress(f"jobs {len(jobs)} batch {batch_size} mem {mem_gb:.1f}")
    docs = pack["docs"]
    started = time.time()
    for i in range(0, len(jobs), 64):
        chunk = jobs[i : i + 64]
        users = [user_text(note, full_criteria(docs.get(nct) or {})) for _y, _t, nct, note in chunk]
        probs, batch_size = score_batch(users, tok, model, ids, batch_size)
        for (year, tid, nct, _note), p in zip(chunk, probs):
            digit = int(max(range(4), key=lambda j: p[j]))
            cont = sum(j * p[j] for j in range(4))
            payload["scores"].setdefault(year, {}).setdefault(tid, {})[nct] = [digit, round(cont, 4)]
        payload["n_scored"] = sum(len(t) for y in payload["scores"].values() for t in y.values())
        payload["seconds"] = round(time.time() - started, 1)
        atomic_write(out_path, payload)
        progress(f"  n={payload['n_scored']} batch={batch_size}")
    done.write_text("ok\n", encoding="utf-8")
    progress(f"wrote {out_path} n={payload.get('n_scored')}")


if __name__ == "__main__":
    main()
