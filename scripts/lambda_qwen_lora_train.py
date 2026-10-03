"""Pairwise LoRA on the v1 eligibility score. Human labels only."""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import torch
from peft import LoraConfig, get_peft_model
from torch.nn.functional import logsigmoid
from transformers import AutoModelForCausalLM, AutoTokenizer

PACK_PATH = Path("score_pack.json")
PAIRS_PATH = Path("trec_lora_train_pairs.json")
EVAL_PAIRS_PATH = Path("trec_lora_eval_pairs.json")
CONFIG_PATH = Path("trec_lora_config.json")
KEEP_ALIVE = Path("/tmp/keep_alive")
PROGRESS = Path("/tmp/qwen_progress.txt")
COLLAPSED = Path("/tmp/lora_collapsed")
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


def chat_text(tok, user: str) -> str:
    return tok.apply_chat_template(
        [{"role": "system", "content": ELIG_SYSTEM}, {"role": "user", "content": user}],
        tokenize=False,
        add_generation_prompt=True,
    )


@torch.no_grad()
def score_users(users, tok, model, ids, kind: str, values, max_len: int, batch_size: int = 8):
    probs_out = []
    scalars = []
    i = 0
    while i < len(users):
        batch = users[i : i + batch_size]
        texts = [chat_text(tok, u) for u in batch]
        enc = tok(texts, return_tensors="pt", padding=True, truncation=True, max_length=max_len)
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
            continue
        stacked = torch.stack([logits[:, did] for did in ids], dim=1)
        probs = torch.softmax(stacked.float(), dim=1)
        probs_out.extend(row.tolist() for row in probs.cpu())
        scalars.extend(pair_score(logits, ids, kind, values).detach().float().cpu().tolist())
        i += len(batch)
        touch()
    return probs_out, scalars


def _median(xs: list[float]) -> float | None:
    if not xs:
        return None
    ys = sorted(xs)
    mid = len(ys) // 2
    if len(ys) % 2:
        return float(ys[mid])
    return 0.5 * (ys[mid - 1] + ys[mid])


def probe_dev(tok, model, ids, pack: dict, kind: str, values, max_len: int, baseline: dict | None) -> dict:
    pairs = json.loads(EVAL_PAIRS_PATH.read_text(encoding="utf-8"))
    docs = pack["docs"]
    notes = pack["years"]["2021"]["topics"]
    gold = []
    users = []
    by_tid: dict[str, dict[int, list[int]]] = {}
    for tid, rows in (pairs["dev_2021"]["topics"] or {}).items():
        note = (notes.get(tid) or {}).get("raw_query") or " "
        dest = by_tid.setdefault(tid, {1: [], 2: []})
        for nct, lab in rows:
            users.append(user_text(note, full_criteria(docs.get(nct) or {})))
            gold.append(int(lab))
            dest[int(lab)].append(len(users) - 1)
    model.eval()
    probs, scalars = score_users(users, tok, model, ids, kind, values, max_len)
    model.train()
    digits = [int(max(range(4), key=lambda j: p[j])) for p in probs]
    conts = [sum(j * p[j] for j in range(4)) for p in probs]
    from collections import Counter

    counts = Counter(digits)
    n = len(conts)
    mean = sum(conts) / max(n, 1)
    var = sum((x - mean) ** 2 for x in conts) / max(n, 1)
    std = var ** 0.5
    pos = [c for c, g in zip(conts, gold) if g == 2]
    neg = [c for c, g in zip(conts, gold) if g == 1]
    better = 0.0
    if pos and neg:
        for p in pos:
            for q in neg:
                if p > q:
                    better += 1
                elif p == q:
                    better += 0.5
        auroc = better / (len(pos) * len(neg))
    else:
        auroc = None
    gaps = []
    for dest in by_tid.values():
        wins = dest.get(2) or []
        loses = dest.get(1) or []
        if not wins or not loses:
            continue
        for wi in wins[:20]:
            for lj in loses[:20]:
                gaps.append(float(scalars[wi]) - float(scalars[lj]))
    med_gap = _median(gaps)
    mean_gap = (sum(gaps) / len(gaps)) if gaps else None
    abs_med = _median([abs(g) for g in gaps])
    top_digit, top_n = counts.most_common(1)[0]
    rec = {
        "n": n,
        "n_gaps": len(gaps),
        "digit_counts": {str(k): int(v) for k, v in sorted(counts.items())},
        "top_digit": int(top_digit),
        "top_share": round(top_n / max(n, 1), 4),
        "cont_mean": round(mean, 4),
        "cont_std": round(std, 4),
        "median_gap": None if med_gap is None else round(med_gap, 4),
        "mean_gap": None if mean_gap is None else round(mean_gap, 4),
        "median_abs_gap": None if abs_med is None else round(abs_med, 4),
        "auroc": None if auroc is None else round(float(auroc), 4),
        "score": kind,
    }
    bunch = (top_n / max(n, 1) >= 0.90 and int(top_digit) != 2) or (
        counts.get(1, 0) / max(n, 1) >= 0.70
    )
    gap_dead = med_gap is not None and med_gap <= 0.10
    gap_shrunk = False
    if baseline and baseline.get("median_gap") is not None and med_gap is not None:
        base_gap = float(baseline["median_gap"])
        rec["gap_vs_baseline"] = None if base_gap == 0 else round(med_gap / base_gap, 4)
        if base_gap > 0 and med_gap < 0.25 * base_gap:
            gap_shrunk = True
    rec["collapsed"] = bool(bunch or gap_dead or gap_shrunk)
    rec["collapse_reason"] = (
        "bunch"
        if bunch
        else ("gap_near_zero" if gap_dead else ("gap_shrunk" if gap_shrunk else None))
    )
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="lora_adapter")
    ap.add_argument("--log", default="lora_train_log.json")
    ap.add_argument("--score", default="")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--done", default="/tmp/lora_train.done")
    args = ap.parse_args()
    if args.seed:
        os.environ["PYTHONHASHSEED"] = str(args.seed)
        random.seed(args.seed)
        torch.manual_seed(args.seed)
        torch.cuda.manual_seed_all(args.seed)
    done = Path(args.done)
    if done.exists():
        done.unlink()
    if not torch.cuda.is_available():
        raise SystemExit("CUDA not available")
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    pairs = json.loads(PAIRS_PATH.read_text(encoding="utf-8"))
    score_kind = args.score or cfg.get("score") or "logit2_minus_logit1"
    gpu = torch.cuda.get_device_name(0)
    progress(f"gpu {gpu} score {score_kind} seed {args.seed or 'none'}")
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
    if args.seed:
        random.Random(args.seed).shuffle(jobs)
    max_len = int(cfg["max_len"])
    accum = int(cfg["grad_accum"])
    epochs = int(cfg["epochs"])
    max_norm = float(cfg["max_grad_norm"])
    progress(f"jobs {len(jobs)} epochs {epochs} accum {accum}")
    started = time.time()
    step_logs = []
    probes = []
    probe_at = {max(1, len(jobs) // 4), max(2, len(jobs) // 2)}
    opt.zero_grad()
    step = 0
    running = 0.0
    running_n = 0
    stopped = False
    log_path = Path(args.log)

    def write_log() -> None:
        payload = {
            "gpu": gpu,
            "score": score_kind,
            "lr": float(cfg["lr"]),
            "seconds": round(time.time() - started, 1),
            "n_pairs": len(jobs),
            "steps": step_logs,
            "probes": probes,
            "adapter": args.out,
            "seed": args.seed or None,
            "stopped": stopped,
        }
        log_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if probes:
            last = probes[-1]
            Path(f"lora_probe_{last.get('pair', len(probes))}.json").write_text(
                json.dumps(last, indent=2),
                encoding="utf-8",
            )

    rec0 = probe_dev(tok, model, ids, pack, score_kind, values, max_len, None)
    rec0["pair"] = 0
    probes.append(rec0)
    progress(f"  probe pair 0 {rec0}")
    write_log()

    for epoch in range(epochs):
        if stopped:
            break
        for i, (note, win, lose) in enumerate(jobs):
            users = [
                user_text(note, full_criteria(docs.get(win) or {})),
                user_text(note, full_criteria(docs.get(lose) or {})),
            ]
            texts = [chat_text(tok, u) for u in users]
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
                    write_log()
                touch()
            if (i + 1) in probe_at:
                rec = probe_dev(tok, model, ids, pack, score_kind, values, max_len, probes[0])
                rec["pair"] = i + 1
                probes.append(rec)
                progress(f"  probe pair {i + 1} {rec}")
                write_log()
                if rec.get("collapsed"):
                    stopped = True
                    COLLAPSED.write_text(json.dumps(rec), encoding="utf-8")
                    progress(f"collapsed ({rec.get('collapse_reason')}), stopping")
                    break
        if running_n and not stopped:
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm)
            opt.step()
            opt.zero_grad()
    out = Path(args.out)
    model.save_pretrained(out)
    tok.save_pretrained(out)
    write_log()
    done.write_text("ok\n", encoding="utf-8")
    progress(f"wrote {out} seconds {round(time.time() - started, 1)} stopped={stopped}")


if __name__ == "__main__":
    main()
