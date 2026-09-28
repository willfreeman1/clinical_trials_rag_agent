"""Embed the saved trials with OpenAI and score three lookups.

The question is fixed: which trials refuse this fact. The answer key says
a trial refuses it when the label is barred or barred_with_exception.

Lookups:
- word search over the whole eligibility text
- word search over the cannot-join section only
- semantic search with text-embedding-3-small, using the question sentence

If OpenAI reports that the account has no credits, this script stops.
"""

from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np

from keyword_section_check import (
    BRAIN_PATTERNS,
    IMMUNO_PATTERNS,
    JSONL_PATH,
    split_sections,
)
from mini_pilot import load_key

ROOT = Path(__file__).resolve().parents[1]
KEY_PATH = ROOT / "data" / "answer_key.jsonl"
EMB_PATH = ROOT / "data" / "embeddings_openai.npz"
EMB_META_PATH = ROOT / "data" / "embeddings_openai_meta.json"
REPORT_PATH = ROOT / "data" / "search_test_report.json"

MODEL = "text-embedding-3-small"
USD_PER_MILLION = 0.02
REFUSAL = {"barred", "barred_with_exception"}

QUESTIONS = [
    {
        "name": "prior_immunotherapy",
        "label_field": "prior_immunotherapy_classification",
        "patterns": IMMUNO_PATTERNS,
        "question": (
            "Trials that refuse patients who have already received immunotherapy, "
            "a checkpoint inhibitor, or a PD-1, PD-L1, or CTLA-4 drug."
        ),
    },
    {
        "name": "brain_metastases",
        "label_field": "brain_metastases_classification",
        "patterns": BRAIN_PATTERNS,
        "question": (
            "Trials that refuse patients who have brain metastases or "
            "central nervous system metastases."
        ),
    },
]


def load_joined() -> list[dict]:
    trials = {}
    with JSONL_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                trials[row["nct_id"]] = row
    labels = {}
    with KEY_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                row = json.loads(line)
                labels[row["nct_id"]] = row["answer"]
    joined = []
    for nct_id, trial in trials.items():
        if nct_id not in labels:
            continue
        parts = split_sections(trial["eligibility_criteria"])
        joined.append(
            {
                "nct_id": nct_id,
                "whole": trial["eligibility_criteria"],
                "exclusion": parts["exclusion"],
                "answer": labels[nct_id],
            }
        )
    return joined


def embed_batch(api_key: str, texts: list[str]) -> tuple[list[list[float]], int]:
    payload = {"model": MODEL, "input": texts}
    last_error = "unknown error"
    for attempt in range(6):
        request = urllib.request.Request(
            "https://api.openai.com/v1/embeddings",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                body = json.loads(response.read().decode("utf-8"))
            ordered = sorted(body["data"], key=lambda item: item["index"])
            vectors = [item["embedding"] for item in ordered]
            tokens = (body.get("usage") or {}).get("total_tokens") or 0
            return vectors, tokens
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            last_error = f"HTTP {exc.code}: {detail[:500]}"
            lowered = detail.lower()
            if "insufficient_quota" in lowered or "credit_balance_exhausted" in lowered:
                raise SystemExit(
                    "OpenAI has no credits remaining. Stopped. No further calls were made."
                )
            if "maximum context length" in lowered or "max_tokens" in lowered:
                raise SystemExit(last_error)
            if exc.code not in (429, 500, 502, 503):
                raise SystemExit(last_error)
            time.sleep(2**attempt)
        except SystemExit:
            raise
        except Exception as exc:
            last_error = str(exc)
            time.sleep(2**attempt)
    raise SystemExit(last_error)


def embed_texts(api_key: str, texts: list[str], label: str) -> tuple[np.ndarray, int]:
    vectors: list[list[float]] = []
    tokens = 0
    batch: list[str] = []
    batch_chars = 0
    for text in texts:
        if batch and (len(batch) >= 64 or batch_chars + len(text) > 200_000):
            got, used = embed_batch(api_key, batch)
            vectors.extend(got)
            tokens += used
            print(f"{label}: embedded {len(vectors)} of {len(texts)}", flush=True)
            batch, batch_chars = [], 0
        batch.append(text)
        batch_chars += len(text)
    if batch:
        got, used = embed_batch(api_key, batch)
        vectors.extend(got)
        tokens += used
        print(f"{label}: embedded {len(vectors)} of {len(texts)}", flush=True)
    return np.asarray(vectors, dtype=np.float32), tokens


def normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def pattern_hit(text: str, patterns: list) -> bool:
    return any(pattern.search(text) for _, pattern in patterns)


def wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float, float]:
    if total == 0:
        return (float("nan"), float("nan"), float("nan"))
    proportion = successes / total
    z2 = z * z
    denom = 1 + z2 / total
    center = (proportion + z2 / (2 * total)) / denom
    margin = z * math.sqrt((proportion * (1 - proportion) + z2 / (4 * total)) / total) / denom
    return (proportion, max(0.0, center - margin), min(1.0, center + margin))


def score_set(predicted: np.ndarray, truth: np.ndarray) -> dict:
    true_positive = int(np.sum(predicted & truth))
    predicted_count = int(np.sum(predicted))
    truth_count = int(np.sum(truth))
    precision = wilson(true_positive, predicted_count)
    recall = wilson(true_positive, truth_count)
    return {
        "returned": predicted_count,
        "should_return": truth_count,
        "overlap": true_positive,
        "precision": {"point": precision[0], "low": precision[1], "high": precision[2]},
        "recall": {"point": recall[0], "low": recall[1], "high": recall[2]},
    }


def top_mask(scores: np.ndarray, count: int) -> np.ndarray:
    count = max(1, min(count, len(scores)))
    order = np.argsort(-scores)
    mask = np.zeros(len(scores), dtype=bool)
    mask[order[:count]] = True
    return mask


def main() -> None:
    rows = load_joined()
    print(f"joined {len(rows)} trials", flush=True)
    api_key = load_key()
    print("embedding the two question sentences", flush=True)
    query, query_tokens = embed_texts(
        api_key, [item["question"] for item in QUESTIONS], "questions"
    )
    print("embedding whole eligibility texts", flush=True)
    whole, whole_tokens = embed_texts(api_key, [row["whole"] for row in rows], "whole")
    exclusion_inputs = []
    exclusion_is_empty = []
    for row in rows:
        empty = not row["exclusion"].strip()
        exclusion_is_empty.append(empty)
        exclusion_inputs.append("." if empty else row["exclusion"])
    print("embedding cannot-join sections", flush=True)
    exclusion, exclusion_tokens = embed_texts(api_key, exclusion_inputs, "exclusion")
    tokens = query_tokens + whole_tokens + exclusion_tokens
    cost = round(tokens * USD_PER_MILLION / 1_000_000, 4)
    meta = {
        "model": MODEL,
        "trials": len(rows),
        "tokens": tokens,
        "estimated_usd": cost,
        "empty_exclusion_sections": int(sum(exclusion_is_empty)),
        "questions": [item["question"] for item in QUESTIONS],
    }
    np.savez(
        EMB_PATH,
        whole=whole,
        exclusion=exclusion,
        query=query,
        exclusion_is_empty=np.asarray(exclusion_is_empty, dtype=bool),
    )
    EMB_META_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta), flush=True)

    whole_n = normalize(whole)
    exclusion_n = normalize(exclusion)
    query_n = normalize(query)
    empty = np.asarray(exclusion_is_empty, dtype=bool)

    report = {"trials": len(rows), "embedding": meta, "questions": []}
    for index, spec in enumerate(QUESTIONS):
        truth = np.array(
            [row["answer"].get(spec["label_field"]) in REFUSAL for row in rows],
            dtype=bool,
        )
        whole_hits = np.array(
            [pattern_hit(row["whole"], spec["patterns"]) for row in rows],
            dtype=bool,
        )
        exclusion_hits = np.array(
            [
                bool(row["exclusion"].strip()) and pattern_hit(row["exclusion"], spec["patterns"])
                for row in rows
            ],
            dtype=bool,
        )
        whole_scores = whole_n @ query_n[index]
        exclusion_scores = exclusion_n @ query_n[index]
        exclusion_scores = exclusion_scores.copy()
        exclusion_scores[empty] = -1.0
        whole_count = int(np.sum(whole_hits))
        exclusion_count = int(np.sum(exclusion_hits))
        result = {
            "name": spec["name"],
            "question": spec["question"],
            "word_search_whole_text": score_set(whole_hits, truth),
            "word_search_cannot_join_section": score_set(exclusion_hits, truth),
            "semantic_whole_text_same_count_as_word_search": score_set(
                top_mask(whole_scores, whole_count), truth
            ),
            "semantic_cannot_join_section_same_count_as_word_search": score_set(
                top_mask(exclusion_scores, exclusion_count), truth
            ),
        }
        report["questions"].append(result)
        print(json.dumps(result, indent=2), flush=True)

    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
