"""Qwen TREC-label prompt on the 411 judged pairs. Token probs plus verbalized p_eligible."""

from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

PACK_PATH = Path("score_pack.json")
PAIRS_PATH = Path("trec_frontier_elig_pairs.json")
OUT_PATH = Path("frontier_elig_qwen_trec.json")
KEEP_ALIVE = Path("/tmp/keep_alive")
DONE_PATH = Path("/tmp/qwen_score.done")
PROGRESS = Path("/tmp/qwen_progress.txt")
QWEN_NAME = "Qwen/Qwen2.5-7B-Instruct"
PAIRS_COMMIT = "99f795c"
MAX_IN = 3072
MAX_NEW = 48
BATCH_START = 8

TREC_SYSTEM = """You assign a TREC Clinical Trials label from the patient description and the trial text.

This is not a decision that the patient qualifies. Do not say the patient can join the trial.

Ignore whether the trial is still recruiting. Ignore where the trial is located.

Labels, as used by the TREC 2021/2022 assessors:

0 = not relevant. The patient is not relevant for the trial in any way.
1 = excluded. The patient has the condition that the trial is targeting and met the inclusion criteria, but one or more exclusion criteria make the patient ineligible.
2 = eligible. The patient met the inclusion criteria and did not meet any exclusion criteria.

Return JSON only, no other text:
{"label": 0, "p_eligible": 0.00}

label is exactly 0, 1, or 2.
p_eligible is your probability that the correct label is 2, from 0 to 1 inclusive, two decimal places."""

LABEL_RE = re.compile(r'"label"\s*:\s*([012])', re.I)
P_RE = re.compile(r'"p_eligible"\s*:\s*([0-9]*\.?[0-9]+)', re.I)


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


def first_token_id(tok, text: str) -> int:
    ids = tok.encode(text, add_special_tokens=False)
    if not ids:
        raise SystemExit(f"no token for {text!r}")
    return ids[0]


def atomic_write(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def parse_gen(text: str) -> tuple[int | None, float | None]:
    lab = None
    p = None
    m = LABEL_RE.search(text or "")
    if m:
        lab = int(m.group(1))
    m = P_RE.search(text or "")
    if m:
        p = max(0.0, min(1.0, float(m.group(1))))
    return lab, p


def needed_jobs(pack: dict, pairs: dict, payload: dict) -> list[tuple[str, str, str, str]]:
    have = payload.get("scores") or {}
    jobs = []
    for year, topics in (pairs.get("years") or {}).items():
        tpack = pack["years"][year]["topics"]
        for tid, bucket in topics.items():
            note = tpack[tid].get("raw_query") or " "
            got = (have.get(year) or {}).get(tid) or {}
            for nct, _lab in bucket:
                if nct in got:
                    continue
                jobs.append((year, tid, nct, note))
    return jobs


@torch.no_grad()
def score_batch(users: list[str], tok, model, label_ids: dict[str, int], batch_size: int):
    out = []
    i = 0
    while i < len(users):
        batch = users[i : i + batch_size]
        texts = [
            tok.apply_chat_template(
                [{"role": "system", "content": TREC_SYSTEM}, {"role": "user", "content": u}],
                tokenize=False,
                add_generation_prompt=True,
            )
            for u in batch
        ]
        enc = tok(texts, return_tensors="pt", padding=True, truncation=True, max_length=MAX_IN)
        enc = {k: v.to(model.device) for k, v in enc.items()}
        try:
            gen = model.generate(
                **enc,
                max_new_tokens=MAX_NEW,
                do_sample=False,
                use_cache=True,
                pad_token_id=tok.pad_token_id,
            )
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            if batch_size == 1:
                raise
            batch_size = max(1, batch_size // 2)
            progress(f"  oom, batch now {batch_size}")
            continue
        prompt_len = enc["input_ids"].shape[1]
        decoded = tok.batch_decode(gen[:, prompt_len:], skip_special_tokens=True)
        prefixes = [t + '{"label": ' for t in texts]
        penc = tok(
            prefixes,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=MAX_IN + 16,
        )
        penc = {k: v.to(model.device) for k, v in penc.items()}
        try:
            try:
                logits = model(**penc, use_cache=False, logits_to_keep=1).logits[:, -1, :]
            except TypeError:
                logits = model(**penc, use_cache=False).logits[:, -1, :]
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            if batch_size == 1:
                raise
            batch_size = max(1, batch_size // 2)
            progress(f"  oom logits, batch now {batch_size}")
            continue
        stacked = torch.stack([logits[:, label_ids[s]] for s in ("0", "1", "2")], dim=1)
        tok_p = torch.softmax(stacked.float(), dim=1).cpu().tolist()
        for text, p3 in zip(decoded, tok_p):
            lab, p_el = parse_gen(text)
            out.append(
                {
                    "label": lab,
                    "p_eligible": p_el,
                    "p_tokens": [round(x, 4) for x in p3],
                    "text": " ".join((text or "").split())[:240],
                }
            )
        i += len(batch)
        touch()
    return out, batch_size


def main() -> None:
    if not torch.cuda.is_available():
        raise SystemExit("CUDA not available")
    gpu = torch.cuda.get_device_name(0)
    progress(f"gpu {gpu}")
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    pairs = json.loads(PAIRS_PATH.read_text(encoding="utf-8"))
    payload = {}
    if OUT_PATH.exists():
        payload = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    payload.setdefault("pairs_commit", PAIRS_COMMIT)
    payload.setdefault("model", QWEN_NAME)
    payload.setdefault("scores", {})
    payload["gpu"] = gpu
    threading.Thread(target=heartbeat, daemon=True).start()
    progress("load Qwen")
    tok = AutoTokenizer.from_pretrained(QWEN_NAME, padding_side="left")
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        QWEN_NAME,
        torch_dtype=torch.float16,
        device_map="cuda",
    )
    model.eval()
    label_ids = {s: first_token_id(tok, s) for s in ("0", "1", "2")}
    jobs = needed_jobs(pack, pairs, payload)
    mem_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
    batch_size = 16 if mem_gb >= 70 else (8 if mem_gb >= 30 else 2)
    progress(f"jobs {len(jobs)} batch {batch_size} mem {mem_gb:.1f}")
    docs = pack["docs"]
    started = time.time()
    for i in range(0, len(jobs), 64):
        chunk = jobs[i : i + 64]
        users = [
            user_text(note, full_criteria(docs.get(nct) or {})) for _y, _t, nct, note in chunk
        ]
        rows, batch_size = score_batch(users, tok, model, label_ids, batch_size)
        for (year, tid, nct, _note), rec in zip(chunk, rows):
            payload["scores"].setdefault(year, {}).setdefault(tid, {})[nct] = rec
        payload["n_scored"] = sum(
            len(t) for y in payload["scores"].values() for t in y.values()
        )
        payload["seconds"] = round(time.time() - started, 1)
        atomic_write(OUT_PATH, payload)
        progress(f"  n={payload['n_scored']} batch={batch_size}")
    DONE_PATH.write_text("ok\n", encoding="utf-8")
    progress(f"wrote {OUT_PATH} n={payload.get('n_scored')}")


if __name__ == "__main__":
    main()
