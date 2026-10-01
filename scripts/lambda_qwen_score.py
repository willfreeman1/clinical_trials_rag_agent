"""Score shortlisted trials with Qwen2.5-7B. Topical 0-3 then eligibility 0-3.

Standalone for the rented GPU. Resume from score_qwen.json.
Gates: 114cce7. 2021/2022 only. Discard nothing.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

PACK_PATH = Path("score_pack.json")
OUT_PATH = Path("score_qwen.json")
KEEP_ALIVE = Path("/tmp/keep_alive")
DONE_PATH = Path("/tmp/qwen_score.done")
PROGRESS = Path("/tmp/qwen_progress.txt")
QWEN_NAME = "Qwen/Qwen2.5-7B-Instruct"
THRESHOLDS_COMMIT = "114cce7"

TOPICAL_SYSTEM = """You score how topically related a clinical-trial record is to a patient description.

This is not an eligibility decision. Do not say whether the patient can join the trial.
Score only whether the trial is about a disease, procedure, or situation that appears in the description.

score is an integer 0, 1, 2, or 3.
0 = unrelated
1 = weakly related
2 = same disease area or a listed problem
3 = clearly about the main problem in the description

Answer with a single digit: 0, 1, 2, or 3."""

ELIG_SYSTEM = """You judge whether a patient appears to meet a clinical trial's stated eligibility criteria.

This is not a decision that the patient qualifies. Do not say the patient can join the trial. The score is a ranking signal for a human who will read the criteria.

score is an integer 0, 1, 2, or 3.
0 = different disease or situation, or the stated criteria clearly rule this patient out
1 = right disease area, but one or more stated criteria probably fail
2 = right disease area, and the stated criteria look mostly compatible, with real remaining uncertainty
3 = the stated criteria look compatible with the description

If you cannot tell from the text, choose 2. Do not use 0 or 3 to express uncertainty. Uncertainty belongs in the middle of the scale.

Answer with a single digit: 0, 1, 2, or 3."""

ELIG_SLICE = 800
BATCH_START = {"topical_title_cond": 32, "topical_title_cond_slice": 24, "elig_full": 8}
MAX_LEN = {"topical_title_cond": 768, "topical_title_cond_slice": 1024, "elig_full": 4096}
SOFT_BUDGET_SEC = 10 * 3600


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


def title_cond(row: dict) -> str:
    title = (row.get("title") or "").strip()
    conds = "; ".join(cond_list(row))
    parts = [p for p in (title, f"Conditions: {conds}" if conds else "") if p]
    return "\n".join(parts) or " "


def title_cond_slice(row: dict) -> str:
    base = title_cond(row)
    elig = (row.get("eligibility") or "").strip()[:ELIG_SLICE]
    if elig:
        return f"{base}\nEligibility (opening):\n{elig}"
    return base


def full_criteria(row: dict) -> str:
    base = title_cond(row)
    elig = (row.get("eligibility") or "").strip()
    if elig:
        return f"{base}\nEligibility criteria:\n{elig}"
    body = (row.get("text") or "").strip()
    if body:
        return f"{base}\nTrial text:\n{body}"
    return base


DOC_FN = {
    "topical_title_cond": title_cond,
    "topical_title_cond_slice": title_cond_slice,
    "elig_full": full_criteria,
}

ARMS = (
    ("topical_title_cond", TOPICAL_SYSTEM),
    ("topical_title_cond_slice", TOPICAL_SYSTEM),
    ("elig_full", ELIG_SYSTEM),
)


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


def load_payload() -> dict:
    if OUT_PATH.exists():
        payload = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    else:
        payload = {}
    payload.setdefault("thresholds_commit", THRESHOLDS_COMMIT)
    payload.setdefault("model", QWEN_NAME)
    payload.setdefault("seconds", {})
    payload.setdefault("n_scored", {})
    payload.setdefault("arms", {})
    payload.setdefault("notes", [])
    return payload


def topic_ids(pack: dict, sample_only: bool) -> list[tuple[str, str]]:
    wanted = pack.get("sample_topics") or {}
    out = []
    for year, ypack in pack["years"].items():
        tids = list(ypack["topics"])
        if sample_only:
            allow = set(str(t) for t in (wanted.get(year) or []))
            tids = [t for t in tids if t in allow]
        for tid in tids:
            out.append((year, tid))
    return out


@torch.no_grad()
def score_batch(
    users: list[str],
    system: str,
    tok,
    model,
    ids: list[int],
    max_len: int,
    batch_size: int,
) -> tuple[list[list[float]], int]:
    """Return [p0,p1,p2,p3] per prompt and the batch size actually used."""
    out: list[list[float]] = []
    i = 0
    while i < len(users):
        batch = users[i : i + batch_size]
        texts = []
        for user in batch:
            messages = [
                {"role": "system", "content": system},
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
            progress(f"  oom, batch now {batch_size}")
            continue
        stacked = torch.stack([logits[:, did] for did in ids], dim=1)
        probs = torch.softmax(stacked.float(), dim=1)
        out.extend(row.tolist() for row in probs.cpu())
        i += len(batch)
        touch()
    return out, batch_size


def user_text(note: str, doc: str) -> str:
    return f"Patient description:\n{note}\n\nTrial record:\n{doc}\n"


def n_missing(bucket: dict, topics: list[tuple[str, str]], pack: dict) -> int:
    n = 0
    for year, tid in topics:
        have = (bucket.get(year) or {}).get(tid) or {}
        n += sum(1 for nct in pack["years"][year]["topics"][tid]["shortlist"] if nct not in have)
    return n


def main() -> None:
    if not torch.cuda.is_available():
        raise SystemExit("CUDA not available")
    gpu = torch.cuda.get_device_name(0)
    progress(f"gpu {gpu}")
    pack = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    payload = load_payload()
    payload["gpu"] = gpu
    touch()
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
    ids = digit_ids(tok)
    progress(f"digit token ids {ids}")
    docs = pack["docs"]
    started = time.time()
    pairs_done = 0
    sample_elig = False

    for arm_name, system in ARMS:
        bucket = payload["arms"].setdefault(arm_name, {})
        fn = DOC_FN[arm_name]
        max_len = MAX_LEN[arm_name]
        batch_size = BATCH_START[arm_name]
        use_sample = sample_elig if arm_name == "elig_full" else False
        topics = topic_ids(pack, use_sample)
        missing_before = n_missing(bucket, topics, pack)
        progress(
            f"arm {arm_name} topics {len(topics)} missing {missing_before} "
            f"sample={use_sample} max_len={max_len}"
        )
        t0 = time.time()
        scored_this = 0
        for ti, (year, tid) in enumerate(topics):
            trow = pack["years"][year]["topics"][tid]
            note = trow.get("raw_query") or " "
            year_bucket = bucket.setdefault(year, {})
            topic_bucket = year_bucket.setdefault(tid, {})
            needed = [nct for nct in trow["shortlist"] if nct not in topic_bucket]
            if not needed:
                continue
            users = [user_text(note, fn(docs.get(nct) or {})) for nct in needed]
            probs, batch_size = score_batch(
                users, system, tok, model, ids, max_len, batch_size
            )
            for nct, p in zip(needed, probs):
                digit = int(max(range(4), key=lambda i: p[i]))
                cont = sum(i * p[i] for i in range(4))
                topic_bucket[nct] = [digit, round(cont, 4)]
            scored_this += len(needed)
            pairs_done += len(needed)
            if ti % 2 == 0 or ti + 1 == len(topics):
                payload["n_scored"][arm_name] = (
                    int(payload["n_scored"].get(arm_name) or 0) + scored_this
                )
                # n_scored accumulates wrongly if we add scored_this every 2 topics.
                # Recompute from the bucket instead.
                payload["n_scored"][arm_name] = sum(
                    len(t) for y in bucket.values() for t in y.values()
                )
                payload["seconds"][arm_name] = round(
                    float(payload["seconds"].get(arm_name) or 0) + (time.time() - t0),
                    1,
                )
                t0 = time.time()
                atomic_write(OUT_PATH, payload)
                progress(
                    f"  {arm_name} {year} {tid} {ti + 1}/{len(topics)} "
                    f"n={payload['n_scored'][arm_name]} batch={batch_size}"
                )
                scored_this = 0
        payload["n_scored"][arm_name] = sum(
            len(t) for y in bucket.values() for t in y.values()
        )
        payload["seconds"][arm_name] = round(
            float(payload["seconds"].get(arm_name) or 0),
            1,
        )
        payload["elapsed_sec"] = round(time.time() - started, 1)
        atomic_write(OUT_PATH, payload)
        progress(f"arm {arm_name} done n={payload['n_scored'][arm_name]} s={payload['seconds'][arm_name]}")

        if arm_name == "topical_title_cond_slice" and not sample_elig:
            elapsed = time.time() - started
            rate = pairs_done / max(elapsed, 1.0)
            n_elig = n_missing(
                payload["arms"].setdefault("elig_full", {}),
                topic_ids(pack, False),
                pack,
            )
            projected = n_elig / max(rate / 5.0, 0.05)
            if elapsed + projected > SOFT_BUDGET_SEC:
                sample_elig = True
                payload["notes"].append(
                    f"elig_full cut to sample: elapsed {elapsed:.0f}s "
                    f"projected {projected:.0f}s rate {rate:.2f}/s"
                )
                atomic_write(OUT_PATH, payload)
                progress(payload["notes"][-1])

    payload["elapsed_sec"] = round(time.time() - started, 1)
    payload["sample_elig"] = sample_elig
    atomic_write(OUT_PATH, payload)
    DONE_PATH.write_text("ok\n", encoding="utf-8")
    progress(f"wrote {OUT_PATH} elapsed {payload['elapsed_sec']}s")


if __name__ == "__main__":
    main()
