"""Pairwise LoRA on the v1 eligibility score. Human labels only."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import torch
from peft import LoraConfig, get_peft_model
from torch.nn.functional import logsigmoid
from transformers import AutoModelForCausalLM, AutoTokenizer

PACK_PATH = Path("score_pack.json")
PAIRS_PATH = Path("trec_lora_train_pairs.json")
CONFIG_PATH = Path("trec_lora_config.json")
KEEP_ALIVE = Path("/tmp/keep_alive")
PROGRESS = Path("/tmp/qwen_progress.txt")
QWEN_NAME = "Qwen/Qwen2.5-7B-Instruct"

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


def pair_score(logits, ids: list[int], kind: str, values: torch.Tensor):
    stacked = torch.stack([logits[:, i] for i in ids], dim=1)
    if kind == "logit2_minus_logit1":
        return stacked[:, 2] - stacked[:, 1]
    probs = torch.softmax(stacked.float(), dim=1)
    return (probs * values).sum(dim=1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="lora_adapter")
    ap.add_argument("--log", default="lora_train_log.json")
    ap.add_argument("--score", default="")
    ap.add_argument("--done", default="/tmp/lora_train.done")
    args = ap.parse_args()
    done = Path(args.done)
    if done.exists():
        done.unlink()
    if not torch.cuda.is_available():
        raise SystemExit("CUDA not available")
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    pairs = json.loads(PAIRS_PATH.read_text(encoding="utf-8"))
    score_kind = args.score or cfg.get("score") or "expected_digit"
    gpu = torch.cuda.get_device_name(0)
    progress(f"gpu {gpu} score {score_kind}")
    progress("load Qwen")
    tok = AutoTokenizer.from_pretrained(QWEN_NAME, padding_side="left")
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        QWEN_NAME,
        torch_dtype=torch.float16,
        device_map="cuda",
    )
    lora = LoraConfig(
        r=int(cfg["lora_r"]),
        lora_alpha=int(cfg["lora_alpha"]),
        lora_dropout=float(cfg["lora_dropout"]),
        target_modules=list(cfg["target_modules"]),
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora)
    model.enable_input_require_grads()
    model.gradient_checkpointing_enable()
    model.train()
    ids = digit_ids(tok)
    values = torch.tensor([0.0, 1.0, 2.0, 3.0], device=model.device)
    opt = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=float(cfg["lr"]),
        weight_decay=float(cfg["weight_decay"]),
    )
    jobs = []
    notes = pack["years"]["2021"]["topics"]
    docs = pack["docs"]
    for tid, rows in (pairs.get("topics") or {}).items():
        note = (notes.get(tid) or {}).get("raw_query") or " "
        for row in rows:
            jobs.append((note, row["win"], row["lose"]))
    max_len = int(cfg["max_len"])
    accum = int(cfg["grad_accum"])
    epochs = int(cfg["epochs"])
    max_norm = float(cfg["max_grad_norm"])
    progress(f"jobs {len(jobs)} epochs {epochs} accum {accum}")
    started = time.time()
    step_logs = []
    opt.zero_grad()
    step = 0
    running = 0.0
    running_n = 0
    for epoch in range(epochs):
        for i, (note, win, lose) in enumerate(jobs):
            users = [
                user_text(note, full_criteria(docs.get(win) or {})),
                user_text(note, full_criteria(docs.get(lose) or {})),
            ]
            texts = [
                tok.apply_chat_template(
                    [{"role": "system", "content": ELIG_SYSTEM}, {"role": "user", "content": u}],
                    tokenize=False,
                    add_generation_prompt=True,
                )
                for u in users
            ]
            enc = tok(texts, return_tensors="pt", padding=True, truncation=True, max_length=max_len)
            enc = {k: v.to(model.device) for k, v in enc.items()}
            try:
                try:
                    logits = model(**enc, use_cache=False, logits_to_keep=1).logits[:, -1, :]
                except TypeError:
                    logits = model(**enc, use_cache=False).logits[:, -1, :]
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                progress(f"  oom skip pair {i}")
                continue
            s = pair_score(logits, ids, score_kind, values)
            loss = -logsigmoid(s[0] - s[1]) / accum
            loss.backward()
            running += float(loss.detach() * accum)
            running_n += 1
            if (i + 1) % accum == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm)
                opt.step()
                opt.zero_grad()
                step += 1
                if step % 10 == 0 or step == 1:
                    mean_loss = running / max(running_n, 1)
                    step_logs.append({"step": step, "loss": round(mean_loss, 4), "i": i, "epoch": epoch})
                    progress(f"  step {step} loss {mean_loss:.4f} pair {i + 1}/{len(jobs)}")
                    running = 0.0
                    running_n = 0
                touch()
        if running_n:
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm)
            opt.step()
            opt.zero_grad()
    out = Path(args.out)
    model.save_pretrained(out)
    tok.save_pretrained(out)
    log = {
        "gpu": gpu,
        "score": score_kind,
        "seconds": round(time.time() - started, 1),
        "n_pairs": len(jobs),
        "steps": step_logs,
        "adapter": str(out),
    }
    Path(args.log).write_text(json.dumps(log, indent=2), encoding="utf-8")
    done.write_text("ok\n", encoding="utf-8")
    progress(f"wrote {out} seconds {log['seconds']}")


if __name__ == "__main__":
    main()
