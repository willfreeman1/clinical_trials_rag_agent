"""Faster Qwen keep/drop on the cheap-pass pack. Pad to batch max, not 1536."""

from __future__ import annotations

import json
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

PACK_PATH = Path("cheap_pass_pack.json")
OUT_PATH = Path("cheap_pass_gpu.json")
KEEP_ALIVE = Path("/tmp/keep_alive")
QWEN_NAME = "Qwen/Qwen2.5-7B-Instruct"
QWEN_BATCH = 32
QWEN_WORDS = ("KEEP", "DROP", "UNSURE")
ELIG_SLICE = 800
MAX_LEN = {"title_cond": 768, "title_cond_slice": 1024}


def touch() -> None:
    try:
        KEEP_ALIVE.write_text("1", encoding="utf-8")
    except OSError:
        pass


def title_cond(row: dict) -> str:
    title = (row.get("title") or "").strip()
    conds = row.get("conditions") or []
    if isinstance(conds, str):
        conds = [conds]
    joined = "; ".join(str(c).strip() for c in conds if str(c).strip())
    parts = [p for p in (title, f"Conditions: {joined}" if joined else "") if p]
    return "\n".join(parts) or " "


def title_cond_slice(row: dict) -> str:
    base = title_cond(row)
    elig = (row.get("eligibility") or "").strip()[:ELIG_SLICE]
    if elig:
        return f"{base}\nEligibility (opening):\n{elig}"
    return base


DOC_FN = {"title_cond": title_cond, "title_cond_slice": title_cond_slice}


def qwen_user(summary: str, doc: str) -> str:
    return (
        "Patient's main problems:\n"
        f"{summary}\n\n"
        "Trial record:\n"
        f"{doc}\n\n"
        "Could this trial conceivably be about this patient's problem?\n"
        "Answer with one word: KEEP, DROP, or UNSURE.\n"
        "KEEP if it might be about any of the patient's main problems, a synonym, a parent condition, or a related disease area.\n"
        "DROP only if it is clearly about a different disease or situation.\n"
        "UNSURE if you cannot tell."
    )


def word_token_ids(tok) -> dict[str, int]:
    out = {}
    for word in QWEN_WORDS:
        for variant in (word, " " + word, word.lower(), " " + word.lower()):
            ids = tok.encode(variant, add_special_tokens=False)
            if ids:
                out.setdefault(word.lower(), ids[0])
                break
    if len(out) < 3:
        raise SystemExit(f"qwen token ids missing: {out}")
    return out


def iter_pairs(pack: dict, doc_name: str):
    fn = DOC_FN[doc_name]
    docs = pack["docs"]
    for year, ypack in pack["years"].items():
        for tid, trow in ypack["topics"].items():
            summary = trow.get("summary") or " "
            for nct in trow["shortlist"]:
                yield year, tid, nct, summary, fn(docs.get(nct) or {})


@torch.no_grad()
def score_qwen(prompts: list[str], tok, model, ids: dict[str, int], max_len: int) -> list[str]:
    out = []
    batch_size = QWEN_BATCH
    i = 0
    names = ["keep", "drop", "unsure"]
    while i < len(prompts):
        batch = prompts[i : i + batch_size]
        texts = []
        for user in batch:
            messages = [
                {
                    "role": "system",
                    "content": "You answer KEEP, DROP, or UNSURE. This is not an eligibility decision.",
                },
                {"role": "user", "content": user},
            ]
            texts.append(
                tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            )
        enc = tok(
            texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=max_len,
        )
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
            print(f"  oom, batch now {batch_size}", flush=True)
            continue
        stacked = torch.stack(
            [logits[:, ids["keep"]], logits[:, ids["drop"]], logits[:, ids["unsure"]]],
            dim=1,
        )
        out.extend(names[j] for j in stacked.argmax(dim=1).tolist())
        i += len(batch)
        if (i // max(batch_size, 1)) % 10 == 0:
            print(
                f"  qwen {i}/{len(prompts)} seq {enc['input_ids'].shape[1]} batch {batch_size}",
                flush=True,
            )
            touch()
    return out


def main() -> None:
    if not torch.cuda.is_available():
        raise SystemExit("CUDA not available")
    print("gpu", torch.cuda.get_device_name(0), flush=True)
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    payload = {}
    if OUT_PATH.exists():
        payload = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    payload.setdefault("seconds", {})
    payload.setdefault("qwen", {})
    payload["qwen_model"] = QWEN_NAME
    payload["qwen_batch"] = QWEN_BATCH
    touch()
    print("load Qwen", flush=True)
    tok = AutoTokenizer.from_pretrained(QWEN_NAME, padding_side="left")
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        QWEN_NAME,
        torch_dtype=torch.float16,
        device_map="cuda",
    )
    model.eval()
    ids = word_token_ids(tok)
    print("token ids", ids, flush=True)
    for doc_name in ("title_cond", "title_cond_slice"):
        t0 = time.time()
        print(f"qwen {doc_name}", flush=True)
        prompts = []
        keys = []
        for year, tid, nct, summary, doc in iter_pairs(pack, doc_name):
            prompts.append(qwen_user(summary, doc))
            keys.append((year, tid, nct))
        words = score_qwen(prompts, tok, model, ids, MAX_LEN[doc_name])
        bucket = payload["qwen"].setdefault(doc_name, {})
        for (year, tid, nct), word in zip(keys, words):
            bucket.setdefault(year, {}).setdefault(tid, {})[nct] = word
        payload["seconds"][f"qwen_{doc_name}"] = round(time.time() - t0, 1)
        OUT_PATH.write_text(json.dumps(payload), encoding="utf-8")
        print(f"qwen {doc_name} done {payload['seconds'][f'qwen_{doc_name}']}s", flush=True)
    print("wrote", OUT_PATH, flush=True)


if __name__ == "__main__":
    main()
