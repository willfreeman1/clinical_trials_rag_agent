"""Re-label the 50 mixed-polarity and 20 heuristic-disagree crossing slots.

One named fact per call. Other facts on the same trial are left alone.
Verbatim eligibility substring required; retry on failure. Snapshot first.
"""

from __future__ import annotations

import json
import shutil
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from keyword_section_check import JSONL_PATH  # noqa: E402
from mini_pilot import (  # noqa: E402
    BRAIN_WORDS,
    IMMUNO_WORDS,
    INPUT_USD_PER_MILLION,
    MODEL,
    OUTPUT_USD_PER_MILLION,
    ask_with_verbatim_retry,
    load_key,
    quote_match,
)
from step5_label_markers import MARKER_WORDS, as_list as marker_as_list  # noqa: E402
from step5_label_rest import AUTO_WORDS, PLATINUM_WORDS, as_list  # noqa: E402
from step9_triage import STAGE_MENTION  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TRIAGE = DATA / "step9_triage.json"
YES_NO = DATA / "answer_key.jsonl"
MARKERS = DATA / "answer_key_markers.jsonl"
STEP5B = DATA / "answer_key_step5b.jsonl"
SNAP_YES = DATA / "answer_key_pre_remaining.jsonl"
SNAP_MARK = DATA / "answer_key_markers_pre_remaining.jsonl"
SNAP_5B = DATA / "answer_key_step5b_pre_remaining.jsonl"
LOG = DATA / "step9_relabel70.json"
PROGRESS = DATA / "step9_relabel70_progress.jsonl"
WORKERS = 8

ALLOWED = {
    "required",
    "allowed",
    "allowed_with_exception",
    "barred",
    "barred_with_exception",
    "both_classifications",
    "not_mentioned",
    "unclear",
}

RULES = """You read eligibility criteria from a lung-cancer trial. Do not decide whether any patient qualifies.

Copy one contiguous passage verbatim from the eligibility criteria. Do not quote the trial title. Do not join two criteria. Do not truncate mid-sentence. If inclusion and exclusion disagree about this fact, still quote only one criterion, copied in full. If the passage is about a different fact, treat this fact as not mentioned and leave the quote empty.

A criterion that applies only to a different cancer type, a different cohort, or a different study part does not apply. If the only mention of this fact is scoped that way, treat it as not mentioned.

A word that narrows a bar makes it conditional. If people who have the fact are refused except when the bar is qualified by active, uncontrolled, untreated, symptomatic, or within N months, choose barred_with_exception, not barred.
"""

YES_NO_USE = """Use: required, allowed, allowed_with_exception, barred, barred_with_exception, both_classifications, not_mentioned, unclear.
Choose allowed_with_exception or barred_with_exception by the rule, not by the verb.
"""

SYSTEMS = {
    "prior_immunotherapy": RULES + """
Prior immunotherapy is treatment the person has already received, or that is already underway, when they join this trial. It includes immunotherapy, an immune checkpoint inhibitor, or a drug aimed at PD-1, PD-L1, or CTLA-4. A laboratory result about PD-1 or PD-L1 on the tumor is not a treatment history. Treatment the protocol gives or forbids during the study is not prior immunotherapy.

""" + YES_NO_USE + "Return JSON with keys: prior_immunotherapy_classification, prior_immunotherapy_quote, note.",
    "brain_metastases": RULES + """
Brain metastases are cancer involving the brain or central nervous system, including leptomeningeal disease, intracranial metastases, and carcinomatous meningitis. A sentence about metastatic disease, distant metastases, or stage IV that does not mention the brain, CNS, intracranial disease, or leptomeningeal disease is not a brain-metastases rule.

""" + YES_NO_USE + "Return JSON with keys: brain_metastases_classification, brain_metastases_quote, note.",
    "prior_platinum_chemo": RULES + """
Previous platinum chemotherapy is chemotherapy containing a platinum drug (cisplatin, carboplatin, oxaliplatin, nedaplatin, lobaplatin) that the person received, or was receiving, before joining. Chemotherapy without a platinum drug does not count. A platinum drug the trial itself would administer does not count.

""" + YES_NO_USE + "Return JSON with keys: prior_platinum_chemo_classification, prior_platinum_chemo_quote, note.",
    "autoimmune_disease": RULES + """
Autoimmune disease is a condition in which the immune system attacks the body's own tissue, whether active now or in the past. A family history alone does not count.

""" + YES_NO_USE + "Return JSON with keys: autoimmune_disease_classification, autoimmune_disease_quote, note.",
    "disease_stage": RULES + """
Disease stages the trial accepts: record two lists. allowed_stages holds every stage or descriptive stage-like label the trial accepts (including locally advanced, metastatic, unresectable, early). refused_stages holds every one it excludes. Use the labels the trial uses. Do not translate a description into a numbered stage. If the trial accepts none specifically and excludes none, both lists are empty. Do not infer a stage rule from the title.

stage_condition: a short copy of the qualifying clause when the stage rule is conditional. Empty string when unqualified.
stage_quote: one verbatim passage that supports the lists. Empty string when both lists are empty.

Return JSON with keys: allowed_stages, refused_stages, stage_condition, stage_quote, note. allowed_stages and refused_stages are arrays of strings.
""",
    "driver_mutation": RULES + """
Genetic marker the trial asks for — a specific tumour genetic change the trial demands or excludes.
- required_markers: every specific change the trial demands. Leave empty if it demands none. Use the exact names the trial uses.
- refused_markers: every specific change the trial excludes.
Do not expand a general phrase into variants you were not given.

genetic_marker_condition: a short copy of the qualifying clause when the rule is conditional. Empty string when unqualified.
genetic_marker_quote: one verbatim passage that supports the lists. Empty string when both lists are empty.

Return JSON with keys: required_markers, refused_markers, genetic_marker_condition, genetic_marker_quote, note. required_markers and refused_markers are arrays of strings.
""",
}

YES_NO_FACTS = {
    "prior_immunotherapy": (
        "prior_immunotherapy_classification",
        "prior_immunotherapy_quote",
        IMMUNO_WORDS,
    ),
    "brain_metastases": (
        "brain_metastases_classification",
        "brain_metastases_quote",
        BRAIN_WORDS,
    ),
    "prior_platinum_chemo": (
        "prior_platinum_chemo_classification",
        "prior_platinum_chemo_quote",
        PLATINUM_WORDS,
    ),
    "autoimmune_disease": (
        "autoimmune_disease_classification",
        "autoimmune_disease_quote",
        AUTO_WORDS,
    ),
}

FACT_FILE = {
    "prior_immunotherapy": YES_NO,
    "brain_metastases": YES_NO,
    "prior_platinum_chemo": STEP5B,
    "autoimmune_disease": STEP5B,
    "disease_stage": STEP5B,
    "driver_mutation": MARKERS,
}


def jobs() -> list[dict]:
    payload = json.loads(TRIAGE.read_text(encoding="utf-8"))
    rows = [
        {"nct_id": r["nct_id"], "fact": r["fact"], "harm": r["harm"]}
        for r in payload["check1_crossings"]["rows"]
        if r["harm"] in ("mixed_polarity", "label_differs")
    ]
    if len(rows) != 70:
        raise SystemExit(f"expected 70 crossing jobs, got {len(rows)}")
    return rows


def load_trials(ids: set[str]) -> dict[str, dict]:
    found = {}
    with JSONL_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row["nct_id"] in ids:
                found[row["nct_id"]] = row
    return found


def load_progress() -> dict[tuple[str, str], dict]:
    done = {}
    if not PROGRESS.exists():
        return done
    with PROGRESS.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("answer") and not quotes_still_missing(row.get("checks") or []):
                done[(row["nct_id"], row["fact"])] = row
    return done


def quotes_still_missing(checks: list[str]) -> bool:
    return any("not in the trial text" in c for c in checks)


def make_ask(system: str):
    def ask(api_key: str, record: dict, extra_user: str = "") -> dict:
        user = (
            f"Trial {record['nct_id']}: {record['brief_title']}\n\n"
            f"{record['eligibility_criteria']}"
        )
        user += (
            "\n\nThe quote must be one contiguous verbatim passage. "
            "Do not join two criteria. Do not truncate."
        )
        if extra_user:
            user += "\n\n" + extra_user
        payload = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            body = json.loads(response.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        usage = body.get("usage") or {}
        return {
            "nct_id": record["nct_id"],
            "brief_title": record.get("brief_title"),
            "answer": json.loads(content),
            "usage": {
                "input_tokens": usage.get("prompt_tokens"),
                "output_tokens": usage.get("completion_tokens"),
            },
        }

    return ask


def check_yes_no(class_key: str, quote_key: str, words):
    def check(text: str, answer: dict) -> list[str]:
        problems = []
        classification = answer.get(class_key)
        quote = answer.get(quote_key) or ""
        if classification not in ALLOWED:
            problems.append(f"{class_key} is missing or not a known classification")
            return problems
        if classification == "not_mentioned":
            if quote:
                problems.append("not_mentioned but quote is not empty")
            return problems
        if not quote:
            problems.append("classification set but quote empty")
            return problems
        if quote_match(quote, text) == "missing":
            problems.append(f"{quote_key} is not in the trial text")
            return problems
        if not words.search(quote):
            problems.append("quote does not mention the fact")
        return problems

    return check


def check_stage(text: str, answer: dict) -> list[str]:
    problems = []
    allowed = as_list(answer.get("allowed_stages"))
    refused = as_list(answer.get("refused_stages"))
    answer["allowed_stages"] = allowed
    answer["refused_stages"] = refused
    quote = answer.get("stage_quote") or ""
    if not allowed and not refused:
        if quote:
            problems.append("stage lists are empty but the quote is not empty")
        return problems
    if not quote:
        problems.append("a stage list is non-empty but the quote is empty")
        return problems
    if quote_match(quote, text) == "missing":
        problems.append("stage_quote is not in the trial text")
        return problems
    if not STAGE_MENTION.search(quote):
        problems.append("stage_quote does not mention a stage")
    return problems


def check_marker(text: str, answer: dict) -> list[str]:
    problems = []
    required = marker_as_list(answer.get("required_markers"))
    refused = marker_as_list(answer.get("refused_markers"))
    answer["required_markers"] = required
    answer["refused_markers"] = refused
    quote = answer.get("genetic_marker_quote") or ""
    if not required and not refused:
        if quote:
            problems.append("lists are empty but the quote is not empty")
        return problems
    if not quote:
        problems.append("a list is non-empty but the quote is empty")
        return problems
    if quote_match(quote, text) == "missing":
        problems.append("genetic_marker_quote is not in the trial text")
        return problems
    if not MARKER_WORDS.search(quote):
        problems.append("genetic_marker_quote does not mention a genetic marker")
    return problems


CHECKERS = {
    "prior_immunotherapy": check_yes_no(*YES_NO_FACTS["prior_immunotherapy"]),
    "brain_metastases": check_yes_no(*YES_NO_FACTS["brain_metastases"]),
    "prior_platinum_chemo": check_yes_no(*YES_NO_FACTS["prior_platinum_chemo"]),
    "autoimmune_disease": check_yes_no(*YES_NO_FACTS["autoimmune_disease"]),
    "disease_stage": check_stage,
    "driver_mutation": check_marker,
}


def label_one(api_key: str, record: dict, fact: str) -> dict:
    ask = make_ask(SYSTEMS[fact])
    check = CHECKERS[fact]
    last_error = "unknown error"
    for attempt in range(5):
        try:
            result = ask_with_verbatim_retry(ask, check, api_key, record, max_quote_tries=5)
            result["fact"] = fact
            return result
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            last_error = f"HTTP {exc.code}: {detail}"
            if exc.code not in (429, 500, 502, 503):
                break
            time.sleep(2 ** attempt)
        except Exception as exc:
            last_error = str(exc)
            time.sleep(2 ** attempt)
    return {
        "nct_id": record["nct_id"],
        "fact": fact,
        "answer": None,
        "checks": ["request failed"],
        "error": last_error,
        "usage": {"input_tokens": 0, "output_tokens": 0},
    }


def snapshot() -> None:
    for src, dest in ((YES_NO, SNAP_YES), (MARKERS, SNAP_MARK), (STEP5B, SNAP_5B)):
        if not dest.exists():
            shutil.copyfile(src, dest)
            print(f"snapshot {dest}", flush=True)


def patch_answer(answer: dict, fact: str, fresh: dict) -> None:
    if fact in YES_NO_FACTS:
        class_key, quote_key, _ = YES_NO_FACTS[fact]
        answer[class_key] = fresh.get(class_key)
        answer[quote_key] = fresh.get(quote_key) or ""
        return
    if fact == "disease_stage":
        answer["allowed_stages"] = as_list(fresh.get("allowed_stages"))
        answer["refused_stages"] = as_list(fresh.get("refused_stages"))
        answer["stage_condition"] = fresh.get("stage_condition") or ""
        answer["stage_quote"] = fresh.get("stage_quote") or ""
        return
    if fact == "driver_mutation":
        answer["required_markers"] = marker_as_list(fresh.get("required_markers"))
        answer["refused_markers"] = marker_as_list(fresh.get("refused_markers"))
        answer["genetic_marker_condition"] = fresh.get("genetic_marker_condition") or ""
        answer["genetic_marker_quote"] = fresh.get("genetic_marker_quote") or ""


def old_slice(answer: dict, fact: str) -> dict:
    if fact in YES_NO_FACTS:
        class_key, quote_key, _ = YES_NO_FACTS[fact]
        return {class_key: answer.get(class_key), quote_key: answer.get(quote_key)}
    if fact == "disease_stage":
        return {k: answer.get(k) for k in ("allowed_stages", "refused_stages", "stage_condition", "stage_quote")}
    return {
        k: answer.get(k)
        for k in ("required_markers", "refused_markers", "genetic_marker_condition", "genetic_marker_quote")
    }


def patch_file(path: Path, by_job: dict[tuple[str, str], dict], facts: set[str]) -> int:
    n = 0
    patched = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("answer"):
                for fact in facts:
                    fresh = by_job.get((row["nct_id"], fact))
                    if not fresh or not fresh.get("answer"):
                        continue
                    if quotes_still_missing(fresh.get("checks") or []):
                        continue
                    patch_answer(row["answer"], fact, fresh["answer"])
                    n += 1
            patched.append(row)
    with path.open("w", encoding="utf-8") as handle:
        for row in patched:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return n


def main() -> None:
    work = jobs()
    snapshot()
    trials = load_trials({j["nct_id"] for j in work})
    missing = {j["nct_id"] for j in work} - set(trials)
    if missing:
        raise SystemExit(f"missing trials: {sorted(missing)}")
    retry_failed = "--failed" in sys.argv
    if retry_failed:
        previous = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {"rows": []}
        failed_keys = {
            (r["nct_id"], r["fact"])
            for r in previous.get("rows") or []
            if quotes_still_missing(r.get("checks") or [])
        }
        work = [j for j in work if (j["nct_id"], j["fact"]) in failed_keys]
        done = {}
    else:
        done = load_progress()
    api_key = load_key()
    results = [] if retry_failed else list(done.values())
    lock = Lock()
    todo = [j for j in work if (j["nct_id"], j["fact"]) not in done]
    print(f"jobs={len(work)} already={len(done)} todo={len(todo)} retry_failed={retry_failed}", flush=True)
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {
            pool.submit(label_one, api_key, trials[j["nct_id"]], j["fact"]): j
            for j in todo
        }
        for future in as_completed(futures):
            job = futures[future]
            try:
                row = future.result()
            except Exception as exc:
                row = {
                    "nct_id": job["nct_id"],
                    "fact": job["fact"],
                    "answer": None,
                    "error": str(exc),
                    "checks": ["request failed"],
                }
            row["harm"] = job["harm"]
            with lock:
                results.append(row)
                with PROGRESS.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                print(
                    job["nct_id"],
                    job["fact"],
                    list((row.get("answer") or {}).keys())[:2],
                    row.get("checks"),
                    flush=True,
                )

    by_job = {(r["nct_id"], r["fact"]): r for r in results if r.get("answer")}
    n_yes = patch_file(YES_NO, by_job, {"prior_immunotherapy", "brain_metastases"})
    n_mark = patch_file(MARKERS, by_job, {"driver_mutation"})
    n_5b = patch_file(STEP5B, by_job, {"prior_platinum_chemo", "autoimmune_disease", "disease_stage"})

    log_rows = list(results)
    if retry_failed and LOG.exists():
        previous = json.loads(LOG.read_text(encoding="utf-8"))
        merged = {
            (r["nct_id"], r["fact"]): r
            for r in previous.get("rows") or []
            if not quotes_still_missing(r.get("checks") or [])
        }
        for r in results:
            merged[(r["nct_id"], r["fact"])] = r
        log_rows = list(merged.values())

    in_tok = sum((r.get("usage") or {}).get("input_tokens") or 0 for r in log_rows)
    out_tok = sum((r.get("usage") or {}).get("output_tokens") or 0 for r in log_rows)
    cost = (in_tok * INPUT_USD_PER_MILLION + out_tok * OUTPUT_USD_PER_MILLION) / 1_000_000
    failed = [r for r in log_rows if not r.get("answer") or quotes_still_missing(r.get("checks") or [])]
    log = {
        "n": 70,
        "this_run": len(results),
        "labeled": sum(1 for r in log_rows if r.get("answer")),
        "patched_this_run": n_yes + n_mark + n_5b,
        "failed_or_unverified": len(failed),
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "estimated_usd": round(cost, 4),
        "rows": [
            {
                "nct_id": r["nct_id"],
                "fact": r.get("fact"),
                "harm": r.get("harm"),
                "answer": r.get("answer"),
                "checks": r.get("checks") or [],
                "error": r.get("error"),
            }
            for r in log_rows
        ],
    }
    LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: log[k] for k in log if k != "rows"}, indent=2))
    if failed:
        print("unpatched", [(r["nct_id"], r.get("fact"), r.get("checks")) for r in failed])


if __name__ == "__main__":
    main()
