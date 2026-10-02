"""GPU cheap pass: MedCPT-CE then Qwen2.5-7B keep/drop/unsure.

Run on the Lambda box. Uncertainty keeps. Full criteria is not scored here.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import torch
from transformers import (
    AutoModelForCausalLM,
    AutoModelForSequenceClassification,
    AutoTokenizer,
)

PACK_PATH = Path("cheap_pass_pack.json")
OUT_PATH = Path("cheap_pass_gpu.json")
KEEP_ALIVE = Path("/tmp/keep_alive")
CE_NAME = "ncbi/MedCPT-Cross-Encoder"
QWEN_NAME = "Qwen/Qwen2.5-7B-Instruct"
CE_BATCH = 64
QWEN_BATCH = 8
CE_MAX_LEN = 512
QWEN_MAX_LEN = 1536
ELIG_SLICE = 800
QWEN_WORDS = ("KEEP", "DROP", "UNSURE")


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


def title_body(row: dict) -> str:
    title = (row.get("title") or "").strip()
    body = (row.get("text") or "").strip()
    if title and body:
        return f"{title}\n{body}"
    return title or body or " "


DOC_FN = {
    "title_cond": title_cond,
    "title_cond_slice": title_cond_slice,
    "title_body_512": title_body,
}


def load_ce(device: str):
    tok = AutoTokenizer.from_pretrained(CE_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(CE_NAME).to(device)
    model.eval()
    return tok, model


@torch.no_grad()
def score_ce(pairs: list[list[str]], tok, model, device: str) -> list[float]:
    out = []
    for i in range(0, len(pairs), CE_BATCH):
        batch = pairs[i : i + CE_BATCH]
        enc = tok(
            batch,
            truncation=True,
            padding=True,
            return_tensors="pt",
            max_length=CE_MAX_LEN,
        ).to(device)
        logits = model(**enc).logits
        if logits.ndim == 2 and logits.size(-1) == 1:
            vals = logits.squeeze(-1)
        elif logits.ndim == 2:
            vals = logits[:, -1]
        else:
            vals = logits.squeeze()
        out.extend(vals.float().cpu().tolist())
        if (i // CE_BATCH) % 40 == 0:
            print(f"  ce {min(i + CE_BATCH, len(pairs))}/{len(pairs)}", flush=True)
            touch()
    return [float(x) for x in out]


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


def parse_word(text: str) -> str:
    token = re.sub(r"[^A-Za-z]+", " ", text or "").strip().split()
    if not token:
        return "unsure"
    word = token[0].lower()
    if word == "drop":
        return "drop"
    if word == "keep":
        return "keep"
    if word == "unsure":
        return "unsure"
    blob = " ".join(token[:4]).lower()
    if "drop" in blob:
        return "drop"
    if "keep" in blob:
        return "keep"
    return "unsure"


def load_qwen(device: str):
    tok = AutoTokenizer.from_pretrained(QWEN_NAME, padding_side="left")
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        QWEN_NAME,
        torch_dtype=torch.float16,
        device_map=device,
    )
    model.eval()
    return tok, model


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


@torch.no_grad()
def score_qwen(prompts: list[str], tok, model, device: str) -> list[str]:
    ids = word_token_ids(tok)
    out = []
    for i in range(0, len(prompts), QWEN_BATCH):
        batch = prompts[i : i + QWEN_BATCH]
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
                tok.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )
            )
        enc = tok(
            texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=QWEN_MAX_LEN,
        )
        enc = {k: v.to(model.device) for k, v in enc.items()}
        logits = model(**enc).logits[:, -1, :]
        keep_s = logits[:, ids["keep"]]
        drop_s = logits[:, ids["drop"]]
        unsure_s = logits[:, ids["unsure"]]
        stacked = torch.stack([keep_s, drop_s, unsure_s], dim=1)
        arg = stacked.argmax(dim=1).tolist()
        names = ["keep", "drop", "unsure"]
        out.extend(names[j] for j in arg)
        if (i // QWEN_BATCH) % 20 == 0:
            print(f"  qwen {min(i + QWEN_BATCH, len(prompts))}/{len(prompts)}", flush=True)
            touch()
    return out


def iter_pairs(pack: dict, doc_name: str):
    fn = DOC_FN[doc_name]
    docs = pack["docs"]
    for year, ypack in pack["years"].items():
        for tid, trow in ypack["topics"].items():
            summary = trow.get("summary") or " "
            for nct in trow["shortlist"]:
                yield year, tid, nct, summary, fn(docs.get(nct) or {})


def save(payload: dict) -> None:
    OUT_PATH.write_text(json.dumps(payload), encoding="utf-8")


def main() -> None:
    if not torch.cuda.is_available():
        raise SystemExit("CUDA not available")
    device = "cuda"
    print("gpu", torch.cuda.get_device_name(0), flush=True)
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    started = time.time()
    payload = {
        "gpu": torch.cuda.get_device_name(0),
        "ce_model": CE_NAME,
        "qwen_model": QWEN_NAME,
        "seconds": {},
        "ce": {},
        "qwen": {},
    }
    touch()

    print("load CE", flush=True)
    tok, model = load_ce(device)
    for doc_name in ("title_cond", "title_cond_slice", "title_body_512"):
        t0 = time.time()
        print(f"ce {doc_name}", flush=True)
        pairs = []
        keys = []
        for year, tid, nct, summary, doc in iter_pairs(pack, doc_name):
            pairs.append([summary, doc])
            keys.append((year, tid, nct))
        vals = score_ce(pairs, tok, model, device)
        bucket = payload["ce"].setdefault(doc_name, {})
        for (year, tid, nct), val in zip(keys, vals):
            bucket.setdefault(year, {}).setdefault(tid, {})[nct] = val
        payload["seconds"][f"ce_{doc_name}"] = round(time.time() - t0, 1)
        save(payload)
        print(f"ce {doc_name} done {payload['seconds'][f'ce_{doc_name}']}s", flush=True)
    del model
    del tok
    torch.cuda.empty_cache()

    print("load Qwen", flush=True)
    qtok, qmodel = load_qwen(device)
    for doc_name in ("title_cond", "title_cond_slice"):
        t0 = time.time()
        print(f"qwen {doc_name}", flush=True)
        prompts = []
        keys = []
        for year, tid, nct, summary, doc in iter_pairs(pack, doc_name):
            prompts.append(qwen_user(summary, doc))
            keys.append((year, tid, nct))
        words = score_qwen(prompts, qtok, qmodel, device)
        bucket = payload["qwen"].setdefault(doc_name, {})
        for (year, tid, nct), word in zip(keys, words):
            bucket.setdefault(year, {}).setdefault(tid, {})[nct] = word
        payload["seconds"][f"qwen_{doc_name}"] = round(time.time() - t0, 1)
        save(payload)
        print(f"qwen {doc_name} done {payload['seconds'][f'qwen_{doc_name}']}s", flush=True)
    payload["seconds"]["total"] = round(time.time() - started, 1)
    save(payload)
    print("wrote", OUT_PATH, "elapsed", payload["seconds"]["total"], flush=True)


if __name__ == "__main__":
    main()
