"""Eligibility prompt v2: CHECK then eligible/ineligible/unsure. Sample only.

Gates: 4424157. 2021/2022, seed 20261001, 30 patients. Discard nothing.
"""

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
OUT_PATH = Path("score_qwen_elig_v2.json")
KEEP_ALIVE = Path("/tmp/keep_alive")
DONE_PATH = Path("/tmp/qwen_score.done")
PROGRESS = Path("/tmp/qwen_progress.txt")
QWEN_NAME = "Qwen/Qwen2.5-7B-Instruct"
THRESHOLDS_COMMIT = "4424157"
MAX_IN = 3072
MAX_NEW = 96
BATCH_START = 4

ELIG_SYSTEM = """You judge whether this patient appears to meet this trial's stated eligibility criteria, using only the patient note and the trial text you are given.

Read all of the trial text. Do not stop after the title or the disease name. Read every inclusion rule and every exclusion rule. Watch for conditions and timing: "already had," "prior," "within the last," "before surgery," "after," "unless," "except," "must have completed," "stable," "no recent change."

Examples of things that often decide the answer (not a complete list): the patient already had the surgery the trial requires to happen later, or has not had a surgery the trial requires already; treatment changed this week (for example steroids doubled) when the trial wants a stable regimen; wrong biomarker; age outside the stated range; a prior drug the trial bars, or a required prior drug the note never mentions; pregnancy, smoking, organ function, or stage/spread that a rule names.

If the disease does not match, the verdict is ineligible.
If the disease matches, do not assume eligible. Check the rules against the note.

Verdict (exactly one of these three words):

- ineligible — the note and the trial text are enough to decide, and the patient does not meet the criteria
- eligible — the note and the trial text are enough to decide, and no criterion appears to fail
- unsure — only when a fact that the trial's stated criteria require is missing from the note

If the fact is in the note, you must choose eligible or ineligible. Do not use unsure to avoid a hard call.

Reply in exactly this form, nothing else:

CHECK: one to three sentences. Say what in the text decided the verdict, or which required fact is missing from the note.
VERDICT: eligible

or VERDICT: ineligible

or VERDICT: unsure

Example (made up — follow the shape only):

CHECK: The trial excludes prior platinum chemotherapy. The note says the patient completed cisplatin last year.
VERDICT: ineligible"""

WORDS = ("ineligible", "unsure", "eligible")
VERDICT_RE = re.compile(r"VERDICT:\s*(eligible|ineligible|unsure)", re.I)


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


def first_token_id(tok, word: str, variant: str) -> int:
    ids = tok.encode(variant, add_special_tokens=False)
    if not ids:
        raise SystemExit(f"no token for {word!r} via {variant!r}")
    return ids[0]


def pick_verdict_ids(tok) -> dict[str, int]:
    schemes = [
        {w: " " + w for w in WORDS},
        {w: w for w in WORDS},
        {w: " " + w.capitalize() for w in WORDS},
        {w: w.upper() for w in WORDS},
    ]
    last = {}
    for scheme in schemes:
        ids = {w: first_token_id(tok, w, scheme[w]) for w in WORDS}
        last = ids
        if len(set(ids.values())) == 3:
            return ids
    return last


def atomic_write(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def load_payload() -> dict:
    if OUT_PATH.exists():
        payload = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    else:
        payload = {}
    payload.setdefault("thresholds_commit", THRESHOLDS_COMMIT)
    payload.setdefault("model", QWEN_NAME)
    payload.setdefault("seconds", 0)
    payload.setdefault("n_scored", 0)
    payload.setdefault("scores", {})
    payload.setdefault("parse_fail", 0)
    return payload


def topic_ids(pack: dict) -> list[tuple[str, str]]:
    wanted = pack.get("sample_topics") or {}
    out = []
    for year, ypack in pack["years"].items():
        allow = set(str(t) for t in (wanted.get(year) or []))
        for tid in ypack["topics"]:
            if tid in allow:
                out.append((year, tid))
    return out


def parse_out(text: str) -> tuple[str, str]:
    check = ""
    m_check = re.search(r"CHECK:\s*(.*?)(?:\nVERDICT:|$)", text, re.I | re.S)
    if m_check:
        check = " ".join(m_check.group(1).split())[:400]
    m = VERDICT_RE.search(text)
    word = (m.group(1).lower() if m else "")
    if word not in WORDS:
        tail = text.strip().split()
        last = tail[-1].strip(".:").lower() if tail else ""
        word = last if last in WORDS else "unsure"
    return word, check


@torch.no_grad()
def score_batch(users: list[str], tok, model, ids: dict[str, int], batch_size: int):
    out: list[dict] = []
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
        enc = tok(
            texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=MAX_IN,
        )
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
        new_ids = gen[:, prompt_len:]
        decoded = tok.batch_decode(new_ids, skip_special_tokens=True)
        # Prefix for verdict logits: generated text up through "VERDICT:"
        prefixes = []
        words = []
        checks = []
        for raw_prompt, gen_text in zip(texts, decoded):
            word, check = parse_out(gen_text)
            words.append(word)
            checks.append(check)
            cut = gen_text
            idx = cut.upper().rfind("VERDICT:")
            if idx >= 0:
                prefixes.append(raw_prompt + cut[: idx + len("VERDICT:")])
            else:
                prefixes.append(raw_prompt + cut.rstrip() + "\nVERDICT:")
        penc = tok(
            prefixes,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=MAX_IN + MAX_NEW,
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
        stacked = torch.stack([logits[:, ids[w]] for w in WORDS], dim=1)
        probs = torch.softmax(stacked.float(), dim=1)
        for word, check, p in zip(words, checks, probs.cpu().tolist()):
            out.append(
                {
                    "word": word,
                    "check": check,
                    "p_ineligible": round(p[0], 4),
                    "p_unsure": round(p[1], 4),
                    "p_eligible": round(p[2], 4),
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
    payload = load_payload()
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
    ids = pick_verdict_ids(tok)
    progress(f"verdict first tokens {ids}")
    if len(set(ids.values())) < 3:
        payload.setdefault("notes", []).append(
            "verdict first tokens collide; ranking still uses p_eligible"
        )
        progress(payload["notes"][-1])
    docs = pack["docs"]
    topics = topic_ids(pack)
    started = time.time()
    batch_size = BATCH_START
    mem_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
    if mem_gb < 30:
        batch_size = 2
    progress(f"topics {len(topics)} batch {batch_size} mem {mem_gb:.1f}GiB")

    for ti, (year, tid) in enumerate(topics):
        trow = pack["years"][year]["topics"][tid]
        note = trow.get("raw_query") or " "
        year_bucket = payload["scores"].setdefault(year, {})
        topic_bucket = year_bucket.setdefault(tid, {})
        needed = [nct for nct in trow["shortlist"] if nct not in topic_bucket]
        if not needed:
            progress(f"skip {year} {tid}")
            continue
        users = [user_text(note, full_criteria(docs.get(nct) or {})) for nct in needed]
        rows, batch_size = score_batch(users, tok, model, ids, batch_size)
        for nct, rec in zip(needed, rows):
            topic_bucket[nct] = rec
            if rec["word"] == "unsure" and not rec["check"]:
                payload["parse_fail"] = int(payload.get("parse_fail") or 0) + 1
        n = sum(len(t) for y in payload["scores"].values() for t in y.values())
        payload["n_scored"] = n
        payload["seconds"] = round(float(payload.get("seconds") or 0) + (time.time() - started), 1)
        started = time.time()
        atomic_write(OUT_PATH, payload)
        progress(f"  elig_v2 {year} {tid} {ti + 1}/{len(topics)} n={n} batch={batch_size}")

    payload["elapsed_sec"] = round(sum([payload.get("seconds") or 0]), 1)
    atomic_write(OUT_PATH, payload)
    DONE_PATH.write_text("ok\n", encoding="utf-8")
    progress(f"wrote {OUT_PATH} n={payload['n_scored']}")


if __name__ == "__main__":
    main()
