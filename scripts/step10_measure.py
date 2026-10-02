"""Run the clarifying-question agent and score the committed gates.

Does not regenerate Will's sheets. Does not start Steps 6 or 7.
"""

from __future__ import annotations

import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from step10_agent import compile_note, run_patient  # noqa: E402
from step10_common import (  # noqa: E402
    ASKABLE,
    DESIGN,
    DONT_KNOW,
    assignment_by_nct,
    coordinator_answer,
    is_live,
    load_assignment,
    load_extended_patients,
)
from step10_logic import (  # noqa: E402
    apply_answers,
    definite_discarded,
    matching_discarded,
    rank_questions,
)
from step2_ceiling import load_markers, load_step5b, load_yes_no  # noqa: E402
from step3d_match import FACTS, listed_facts, load_assigned, retrieve  # noqa: E402
from step3d_reassign import canonical_name  # noqa: E402
from step8_common import DESIGN as STEP8_DESIGN  # noqa: E402
from step8_common import wilson  # noqa: E402
from step8_score import load_best, overall_of  # noqa: E402
from therapy_containment import load_child_to_parent  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PARSE = DATA / "step4_parse.json"
SAMPLE = DATA / "step8_sample.json"
OUT = DATA / "step10_report.json"
REPORT = ROOT / "docs" / "step10_questions.md"


def found_maps(patients: list[dict]) -> dict[str, dict[str, set[str]]]:
    parse = {row["patient_id"]: row for row in json.loads(PARSE.read_text(encoding="utf-8"))["patients"]}
    edges = load_child_to_parent()
    assigned = load_assigned()
    trial_names: dict[str, set[str]] = defaultdict(set)
    for row in assigned:
        trial_names[row["nct_id"]].add(canonical_name(row.get("assigned_name") or ""))
    out = {}
    for p in patients:
        traits = (parse[p["id"]].get("answer") or {}).get("traits") or []
        listed = listed_facts(traits)
        found = {}
        for fact in FACTS:
            found[fact] = set() if fact not in listed else retrieve(listed[fact], trial_names, False, edges)
        out[p["id"]] = found
    return out


def union_share(discarded: set[str], n: int) -> float:
    return round(len(discarded) / n, 4) if n else 0.0


def sequential(patient, remaining, by_nct, found, k: int) -> dict:
    answers = {}
    left = set(remaining)
    extra = set()
    asked = []
    for _ in range(k):
        ranked = rank_questions(patient, left, by_nct, found, answers)
        if not ranked or ranked[0][1] <= 0:
            break
        q, n = ranked[0]
        answers[q] = coordinator_answer(patient, q)
        asked.append({"question": q, "value": answers[q], "unlocks_at_ask": n})
        applied = apply_answers(patient, left, by_nct, answers, found)
        extra |= applied["extra_discard"]
        left -= applied["extra_discard"]
    applied = apply_answers(patient, remaining, by_nct, answers, found)
    return {
        "asked": asked,
        "answers": answers,
        "extra_discard": extra,
        "n_settled": len(applied["settled"]),
        "n_extra_discard": len(extra),
    }


def random_three(patient, remaining, by_nct, found, rng: random.Random) -> dict:
    ranked = rank_questions(patient, remaining, by_nct, found)
    live = [q for q, n in ranked if n > 0]
    if len(live) > 3:
        picks = rng.sample(live, 3)
    else:
        picks = live
    answers = {q: coordinator_answer(patient, q) for q in picks}
    applied = apply_answers(patient, remaining, by_nct, answers, found)
    return {
        "asked": picks,
        "n_settled": len(applied["settled"]),
        "n_extra_discard": len(applied["extra_discard"]),
        "extra_discard": applied["extra_discard"],
    }


def ask_all(patient, remaining, by_nct, found) -> dict:
    answers = {q: coordinator_answer(patient, q) for q in ASKABLE if is_live(patient, q)}
    applied = apply_answers(patient, remaining, by_nct, answers, found)
    return {
        "n_questions": len(answers),
        "n_settled": len(applied["settled"]),
        "n_extra_discard": len(applied["extra_discard"]),
        "n_dont_know": sum(1 for v in answers.values() if v == DONT_KNOW),
        "extra_discard": applied["extra_discard"],
    }


def lost_joinable(new_discarded: dict[str, set[str]]) -> dict:
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    best = load_best()
    expensive = STEP8_DESIGN["expensive_model"]
    k = n = 0
    per = {}
    for pid in STEP8_DESIGN["patients"]:
        sampled = set(sample["patients"][pid]["discarded"]) | set(sample["patients"][pid]["kept"])
        disc = new_discarded.get(pid, set())
        pk = pn = 0
        for nct in sampled:
            if nct not in disc:
                continue
            row = best.get((expensive, pid, nct, 1))
            if not row or not row.get("answer"):
                continue
            n += 1
            pn += 1
            if overall_of(row) == "candidate_needs_human_check":
                k += 1
                pk += 1
        per[pid] = {"k": pk, "n": pn, "rate": round(pk / pn, 4) if pn else None}
    rate = k / n if n else None
    return {
        "k": k,
        "n": n,
        "rate": round(rate, 4) if rate is not None else None,
        "ci": wilson(k, n) if n else None,
        "gate_unsafe_above": 0.10,
        "cleared": (rate if rate is not None else 1) <= 0.10,
        "per_patient": per,
    }


def pct(x) -> str:
    if x is None:
        return "n/a"
    return f"{x:.1%}"


def main() -> None:
    t0 = time.perf_counter()
    patients = load_extended_patients()
    yes_no = load_yes_no()
    markers = load_markers()
    extra = load_step5b()
    universe = sorted(set(yes_no) & set(markers) & set(extra))
    n_trials = len(universe)
    by_nct = assignment_by_nct(load_assignment())
    found = found_maps(patients)
    rng = random.Random(DESIGN["seed"])

    finder_base = []
    gated_base = []
    curve = {k: [] for k in DESIGN["probe_curve"]}
    ranked3_settle = []
    random3_settle = []
    allq_settle = []
    allq_disc = []
    agent_rows = []
    gated_after3 = []
    finder_after3 = []
    gated_disc_after = {}
    round1_share = []
    round2_gain = []
    asked_q = Counter()
    zero_unlock_questions = Counter()

    for p in patients:
        definite = definite_discarded(p, yes_no, markers, extra, universe)
        gated = matching_discarded(p, yes_no, markers, extra, universe, found[p["id"]])
        remaining_f = set(universe) - definite
        remaining_g = set(universe) - gated
        finder_base.append(union_share(definite, n_trials))
        gated_base.append(union_share(gated, n_trials))

        answers_so_far = {}
        extra_so_far: set[str] = set()
        for i in range(1, 6):
            ranked = rank_questions(p, set(universe) - definite - extra_so_far, by_nct, None, answers_so_far)
            if ranked and ranked[0][1] > 0:
                q = ranked[0][0]
                answers_so_far[q] = coordinator_answer(p, q)
                extra_so_far = apply_answers(p, remaining_f, by_nct, answers_so_far, None)["extra_discard"]
            if i in curve:
                curve[i].append(union_share(definite | extra_so_far, n_trials))

        r3 = sequential(p, remaining_f, by_nct, None, 3)
        ranked3_settle.append(r3["n_settled"])
        finder_after3.append(union_share(definite | r3["extra_discard"], n_trials))

        g3 = sequential(p, remaining_g, by_nct, found[p["id"]], 3)
        gated_after3.append(union_share(gated | g3["extra_discard"], n_trials))
        gated_disc_after[p["id"]] = gated | g3["extra_discard"]

        rnd = random_three(p, remaining_f, by_nct, None, rng)
        random3_settle.append(rnd["n_settled"])

        everything = ask_all(p, remaining_f, by_nct, None)
        allq_settle.append(everything["n_settled"])
        allq_disc.append(union_share(definite | everything["extra_discard"], n_trials))

        agent = run_patient(p, remaining_f, by_nct, None, rounds_cap=3)
        agent_rows.append({k: agent[k] for k in agent if k != "extra_discard"})
        agent_rows[-1]["n_extra_discard"] = agent["n_extra_discard"]
        for item in agent.get("asked") or []:
            asked_q[item["question"]] += 1
        if agent.get("rounds", 0) >= 1:
            a1 = {agent["asked"][0]["question"]: agent["asked"][0]["value"]}
            d1 = apply_answers(p, remaining_f, by_nct, a1, None)["extra_discard"]
            round1_share.append(union_share(definite | d1, n_trials))
        else:
            round1_share.append(union_share(definite, n_trials))
        if agent.get("rounds", 0) >= 2:
            a2 = {x["question"]: x["value"] for x in agent["asked"][:2]}
            d2 = apply_answers(p, remaining_f, by_nct, a2, None)["extra_discard"]
            round2_gain.append(len(d2) - len(d1))
        ranked_end = rank_questions(p, remaining_f - r3["extra_discard"], by_nct, None, r3["answers"])
        for q, n in ranked_end:
            if n == 0:
                zero_unlock_questions[q] += 1

    def mean(xs):
        return round(sum(xs) / len(xs), 4) if xs else None

    finder_3 = mean(finder_after3)
    gated_3 = mean(gated_after3)
    ranked_mean = mean(ranked3_settle)
    random_mean = mean(random3_settle)
    ratio = None if not random_mean else round(ranked_mean / random_mean, 4) if random_mean else None
    if random_mean == 0:
        ratio = None if ranked_mean == 0 else 999.0

    r1 = mean(round1_share)
    r2_gain_mean = mean(round2_gain) if round2_gain else 0
    round2_earns = bool(round2_gain) and (sum(1 for g in round2_gain if g > 0) / len(round2_gain) >= 0.5)

    lost = lost_joinable(gated_disc_after)
    gates = DESIGN["gates"]
    finder_cleared = finder_3 is not None and finder_3 >= gates["finder_after_3_min"]
    finder_stop = finder_3 is not None and finder_3 < gates["finder_after_3_stop_below"]
    rank_cleared = ratio is not None and ratio >= gates["ranked_vs_random_min_ratio"]
    safety_cleared = lost["cleared"]

    report = {
        "n_trials": n_trials,
        "n_patients": len(patients),
        "n_assigned_rules": len(load_assignment()),
        "baselines": DESIGN["baselines"],
        "perfect_finder": {
            "before": mean(finder_base),
            "after_1": mean(curve[1]),
            "after_2": mean(curve[2]),
            "after_3": finder_3,
            "after_5": mean(curve[5]),
            "ask_everything": mean(allq_disc),
        },
        "matching_gated": {
            "before": mean(gated_base),
            "after_3_ranked": gated_3,
        },
        "unlocks": {
            "ranked_3_mean_trials_settled": ranked_mean,
            "random_3_mean_trials_settled": random_mean,
            "ratio_ranked_over_random": ratio,
            "ask_everything_mean_settled": mean(allq_settle),
            "ranked_3_over_everything": (
                round(ranked_mean / mean(allq_settle), 4) if mean(allq_settle) else None
            ),
        },
        "round_two": {
            "finder_after_round_1": r1,
            "mean_additional_discards_in_round_2": r2_gain_mean,
            "share_of_patients_with_round_2_gain": (
                round(sum(1 for g in round2_gain if g > 0) / len(round2_gain), 4) if round2_gain else None
            ),
            "earns_itself": round2_earns,
            "note": (
                "If round 1 already captures nearly the after-3 figure, this is one extra "
                "step rather than a loop."
            ),
        },
        "lost_joinable": lost,
        "questions_asked": dict(asked_q.most_common()),
        "agent": agent_rows,
        "elapsed_s": round(time.perf_counter() - t0, 3),
        "framework": compile_note(),
        "gates": {
            "finder_after_3": finder_3,
            "finder_cleared_65": finder_cleared,
            "finder_below_quarter_stop": finder_stop,
            "ranked_vs_random_ratio": ratio,
            "ranked_cleared_1_5x": rank_cleared,
            "wrongly_discarded": lost["rate"],
            "wrongly_discarded_cleared": safety_cleared,
            "recovery_is_bad_trade": finder_cleared and not safety_cleared,
        },
    }
    OUT.write_text(json.dumps(report, indent=2, default=list), encoding="utf-8")

    pfind = report["perfect_finder"]
    lines = [
        "# Clarifying-question agent",
        "",
        "Thresholds were committed before the oracle draw and before assignment.",
        "Old narrowing numbers stay on disk. This page is the new measurement.",
        "",
        compile_note(),
        "",
        "| | Before | After 3 ranked questions | Gate |",
        "|---|---:|---:|---|",
        f"| Perfect-finder ceiling | {pct(pfind['before'])} | {pct(pfind['after_3'])} | "
        f"{'cleared' if finder_cleared else 'missed'} 65%; "
        f"{'STOP (below a quarter of the gap)' if finder_stop else 'above the 58.5% floor'} |",
        f"| Matching-gated | {pct(report['matching_gated']['before'])} | "
        f"{pct(report['matching_gated']['after_3_ranked'])} | reported, no recovery gate |",
        f"| Wrongly discarded (lost-joinable) | {pct(DESIGN['baselines']['lost_joinable'])} | "
        f"{pct(lost['rate'])} ({lost['k']}/{lost['n']}) | "
        f"{'cleared' if safety_cleared else 'BREACHED — bad trade, overrides recovery'} |",
        f"| Ranked-3 vs random-3 unlocks | {ranked_mean:.1f} vs {random_mean:.1f} | "
        f"ratio {ratio} | {'cleared' if rank_cleared else 'missed 1.5× — drop ranking'} |",
        "",
        "## Recovery curve (perfect finder)",
        "",
        f"| Questions | Narrowing |",
        f"|---|---:|",
        f"| 0 | {pct(pfind['before'])} |",
        f"| 1 | {pct(pfind['after_1'])} |",
        f"| 2 | {pct(pfind['after_2'])} |",
        f"| 3 | {pct(pfind['after_3'])} |",
        f"| 5 | {pct(pfind['after_5'])} |",
        f"| Everything live | {pct(pfind['ask_everything'])} |",
        "",
        f"Ranked-3 settles {pct(report['unlocks']['ranked_3_over_everything'])} of what asking every live question settles.",
        "",
        "## Does round two earn itself?",
        "",
        f"Round 1 alone reaches {pct(r1)}. Mean extra discards in round 2: {r2_gain_mean}.",
        (
            "**Round two adds a little, but the loop is not the product.** Round 1 already "
            "has almost all of the (small) gain. LangGraph is heavier than the problem."
            if (r1 is not None and finder_3 is not None and (finder_3 - r1) < 0.03)
            else (
                "**Round two earns itself** — half or more of the patients still discard more trials."
                if round2_earns
                else "**Round two does not earn itself.** One extra step would have been enough. LangGraph is heavier than the problem."
            )
        ),
        "",
        f"Questions asked (count of patients): {dict(asked_q.most_common())}",
        "",
        "## Why 56% and not 65%",
        "",
        "The 51.9→78.2 gap assumed that a settled conditional **discards**. For these 20",
        "patients it often does not. Five of ten brain-mets patients are treated and",
        "stable: asking the question keeps the trial, which is correct. Nineteen of",
        "twenty have no autoimmune disease, so 376 autoimmune tags never go live.",
        "789 of 1,918 assigned rules were `other` (cohort, trial histology, protocol",
        "part) and cannot be asked of a coordinator. Asking every live question still",
        "only reaches 57.7%. The 78.2% optimistic ceiling was not sitting in unasked",
        "questions. It was sitting in exceptions the patients meet, and in conditions",
        "that are not facts about the patient.",
        "",
        "So the complexity is not earning itself. That is the stop the lower-bound",
        "gate asked for. The 10% wrongly-discarded gate also failed (10.4%), which",
        "would have vetoed the feature even if recovery had cleared 65%.",
        "",
        "Ranking missed 1.5× (1.21×). Ranked-3 still settles 65% of asking-everything,",
        "so coverage ranking is doing some work, but not enough to keep. A fixed order",
        "would have been enough to test, and random was close.",
        "",
        "Round 1 reaches 54.2%; rounds 2–3 add two more points. Half the patients",
        "discard a few extra trials in round 2. That is not a loop. LangGraph was",
        "heavier than the problem. Saying so is the point of having built it.",
        "",
        f"Assignment: 1,918 rules, $1.79, gpt-5.4. Scoring {report['elapsed_s']}s, no extra API.",
        "",
        "Will's check sheets were not regenerated. Steps 6 and 7 were not started.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report["gates"], indent=2))
    print("finder", pfind)
    print("gated", report["matching_gated"])
    print("unlocks", report["unlocks"])
    print("round_two", report["round_two"])
    print("lost", {k: lost[k] for k in lost if k != "per_patient"})
    print("Wrote", OUT)
    print("Wrote", REPORT)


if __name__ == "__main__":
    main()
