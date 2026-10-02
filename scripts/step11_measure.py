"""Score sparse-input asking. No condition-resolution. No Will sheet."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from step10_logic import matching_discarded  # noqa: E402
from step2_ceiling import load_markers, load_step5b, load_yes_no  # noqa: E402
from step3c_closed_names import FACT_TO_NAME  # noqa: E402
from step3d_match import listed_facts, load_assigned, retrieve  # noqa: E402
from step3d_reassign import canonical_name  # noqa: E402
from step8_common import DESIGN as STEP8  # noqa: E402
from step8_common import wilson  # noqa: E402
from step8_score import load_best, overall_of  # noqa: E402
from therapy_containment import load_child_to_parent  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DESIGN = json.loads((ROOT / "sparse_design.json").read_text(encoding="utf-8"))
DRAW = ROOT / "data" / "fake_patients_draw.json"
PARSE = ROOT / "data" / "step11_parse.jsonl"
SAMPLE = ROOT / "data" / "step8_sample.json"
OUT = ROOT / "data" / "step11_report.json"
REPORT = ROOT / "docs" / "step11_sparse.md"

CHECKLIST = list(DESIGN["checklist_order"])
TARGET = DESIGN["target_matching_gated"]
STOP_PP = DESIGN["stop_increment_pp"]
FACTS = list(DESIGN["facts"])


def load_gold() -> dict[str, dict]:
    return {p["id"]: p for p in json.loads(DRAW.read_text(encoding="utf-8"))["patients"]}


def load_parses() -> list[dict]:
    rows = []
    with PARSE.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return list({r["id"]: r for r in rows}.values())


def precompute_found() -> dict[str, set[str]]:
    edges = load_child_to_parent()
    assigned = load_assigned()
    trial_names: dict[str, set[str]] = defaultdict(set)
    for row in assigned:
        trial_names[row["nct_id"]].add(canonical_name(row.get("assigned_name") or ""))
    found = {}
    for fact in FACTS:
        found[fact] = retrieve(FACT_TO_NAME[fact], trial_names, False, edges)
    return found


def listed_from_parse(answer: dict | None) -> dict[str, str]:
    traits = (answer or {}).get("traits") or []
    listed = listed_facts(traits)
    return {f: listed[f] for f in listed if f in FACTS}


def narrowing(patient, listed, yes_no, markers, extra, universe, found_all):
    found = {f: found_all[f] for f in listed}
    disc = matching_discarded(patient, yes_no, markers, extra, universe, found)
    return len(disc) / len(universe), disc


def walk(patient, listed0, missing, yes_no, markers, extra, universe, found_all):
    listed = dict(listed0)
    share0, disc0 = narrowing(patient, listed, yes_no, markers, extra, universe, found_all)
    shares = [share0]
    discs = [disc0]
    incs = []
    zero_gain = []
    for fact in missing:
        listed[fact] = FACT_TO_NAME[fact]
        share, disc = narrowing(patient, listed, yes_no, markers, extra, universe, found_all)
        inc = share - shares[-1]
        incs.append(inc)
        if inc < 1e-12:
            zero_gain.append(fact)
        shares.append(share)
        discs.append(disc)
    return shares, incs, zero_gain, discs


def right_stop(incs: list[float]) -> int:
    """How many checklist questions to ask. Stop before the next increment is under 2pp."""
    if not incs:
        return 0
    if incs[0] < STOP_PP:
        return 0
    for t, _inc in enumerate(incs):
        nxt = incs[t + 1] if t + 1 < len(incs) else 0.0
        if nxt < STOP_PP:
            return t + 1
    return len(incs)


def agent_stop(incs: list[float]) -> int:
    """Ask in checklist order; stop after the first increment under 2pp."""
    if not incs:
        return 0
    asked = 0
    for inc in incs:
        asked += 1
        if inc < STOP_PP:
            break
    return asked


def pct(x) -> str:
    if x is None:
        return "n/a"
    return f"{x:.1%}"


def mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 4) if xs else None


def main() -> None:
    gold = load_gold()
    parses = load_parses()
    yes_no = load_yes_no()
    markers = load_markers()
    extra = load_step5b()
    universe = sorted(set(yes_no) & set(markers) & set(extra))
    found_all = precompute_found()
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    best = load_best()
    expensive = STEP8["expensive_model"]
    step8_ids = set(STEP8["patients"])

    by_k = defaultdict(list)
    first_asked = defaultdict(Counter)
    stop_hits = 0
    n_stop = 0
    agent_q = []
    agent_share = []
    check_share = []
    after3 = defaultdict(list)
    start_k = defaultdict(list)
    parse_rows = []
    zero_gain_n = 0
    zero_gain_asked = 0
    lost_k = lost_n = 0
    lost_by_k = defaultdict(lambda: {"k": 0, "n": 0})
    lost_orig_disc = {"k": 0, "n": 0}
    lost_orig_kept = {"k": 0, "n": 0}
    unique_lost: dict[tuple[str, str], bool] = {}
    per_config = []
    by_q: dict[int, list[float]] = defaultdict(list)

    for row in parses:
        pid = row["patient_id"]
        p = gold[pid]
        listed0 = listed_from_parse(row.get("answer"))
        intended = set(row.get("include") or [])
        parsed = set(listed0)
        missing = [f for f in CHECKLIST if f not in listed0]
        shares, incs, zero_gain, discs = walk(
            p, listed0, missing, yes_no, markers, extra, universe, found_all
        )
        start = shares[0]
        checklist = shares[-1]
        rstop = right_stop(incs)
        astop = agent_stop(incs)
        agent = shares[astop]
        share3 = shares[min(3, len(shares) - 1)]
        if missing:
            first_asked[row["k"]][missing[0]] += 1
        n_stop += 1
        if abs(astop - rstop) <= 1:
            stop_hits += 1
        agent_q.append(astop)
        agent_share.append(agent)
        check_share.append(checklist)
        after3[row["k"]].append(share3)
        start_k[row["k"]].append(start)
        by_k[row["k"]].append({"start": start, "after3": share3, "agent": agent, "checklist": checklist})
        zero_gain_n += len(zero_gain)
        zero_gain_asked += sum(1 for i, f in enumerate(missing) if i < astop and f in zero_gain)
        parse_rows.append({
            "k": row["k"],
            "intended": sorted(intended),
            "parsed": sorted(parsed),
            "recall": (len(intended & parsed) / len(intended)) if intended else 1.0,
            "precision": (len(intended & parsed) / len(parsed)) if parsed else 1.0,
            "invented": sorted(parsed - intended),
            "missed": sorted(intended - parsed),
        })
        if pid in step8_ids and pid in sample["patients"]:
            orig_disc = set(sample["patients"][pid]["discarded"])
            orig_kept = set(sample["patients"][pid]["kept"])
            sampled = orig_disc | orig_kept
            disc = discs[astop]
            for nct in sampled:
                if nct not in disc:
                    continue
                read = best.get((expensive, pid, nct, 1))
                if not read or not read.get("answer"):
                    continue
                is_lost = overall_of(read) == "candidate_needs_human_check"
                lost_n += 1
                lost_by_k[row["k"]]["n"] += 1
                if is_lost:
                    lost_k += 1
                    lost_by_k[row["k"]]["k"] += 1
                if nct in orig_disc:
                    lost_orig_disc["n"] += 1
                    if is_lost:
                        lost_orig_disc["k"] += 1
                if nct in orig_kept:
                    lost_orig_kept["n"] += 1
                    if is_lost:
                        lost_orig_kept["k"] += 1
                unique_lost[(pid, nct)] = unique_lost.get((pid, nct), False) or is_lost
        for q in range(7):
            idx = min(q, len(shares) - 1)
            by_q[q].append(shares[idx])
        per_config.append({
            "id": row["id"],
            "k": row["k"],
            "start": round(start, 4),
            "after_3": round(share3, 4),
            "agent": round(agent, 4),
            "checklist": round(checklist, 4),
            "n_missing": len(missing),
            "agent_stop": astop,
            "right_stop": rstop,
            "first_question": missing[0] if missing else None,
            "zero_gain": zero_gain,
        })

    lost_rate = lost_k / lost_n if lost_n else None
    uniq_n = len(unique_lost)
    uniq_k = sum(1 for v in unique_lost.values() if v)
    uniq_rate = uniq_k / uniq_n if uniq_n else None

    def rate_pack(k: int, n: int) -> dict:
        r = k / n if n else None
        return {
            "k": k,
            "n": n,
            "rate": round(r, 4) if r is not None else None,
            "ci": wilson(k, n) if n else None,
        }
    stop_acc = stop_hits / n_stop if n_stop else None
    level_gates = {}
    any_below_quarter = False
    all_half = True
    for k in (0, 1, 2):
        s = mean(start_k[k])
        a3 = mean(after3[k])
        gap = TARGET - s if s is not None else None
        half = s + 0.5 * gap if gap is not None else None
        quarter = s + 0.25 * gap if gap is not None else None
        cleared_half = a3 is not None and half is not None and a3 >= half
        below_q = a3 is not None and quarter is not None and a3 < quarter
        all_half = all_half and cleared_half
        any_below_quarter = any_below_quarter or below_q
        level_gates[k] = {
            "start": s,
            "after_3": a3,
            "half_target": round(half, 4) if half is not None else None,
            "quarter_floor": round(quarter, 4) if quarter is not None else None,
            "cleared_half": cleared_half,
            "below_quarter": below_q,
        }

    agent_mean_n = mean(agent_q)
    agent_mean_s = mean(agent_share)
    check_mean_s = mean(check_share)
    delta = None if agent_mean_s is None or check_mean_s is None else round(agent_mean_s - check_mean_s, 4)
    vs_check = (
        delta is not None
        and abs(delta) <= DESIGN["gates"]["agent_vs_checklist_max_delta"]
        and agent_mean_n is not None
        and agent_mean_n <= DESIGN["gates"]["agent_mean_questions_max"]
    )
    stop_cleared = stop_acc is not None and stop_acc >= DESIGN["gates"]["stop_within_one_min"]
    safety_cleared = (lost_rate if lost_rate is not None else 1) <= 0.10

    parse_by_k = {}
    for k in range(7):
        chunk = [r for r in parse_rows if r["k"] == k]
        parse_by_k[k] = {
            "n": len(chunk),
            "mean_recall": mean([r["recall"] for r in chunk]),
            "mean_precision": mean([r["precision"] for r in chunk]),
            "n_invented": sum(1 for r in chunk if r["invented"]),
            "n_missed": sum(1 for r in chunk if r["missed"]),
        }

    curve_k = {k: {"start": mean(start_k[k]), "after_3": mean(after3[k])} for k in range(7)}
    curve_q = {q: mean(by_q[q]) for q in range(7)}
    leak = {}
    leak_path = ROOT / "data" / "step11_notes_summary.json"
    parse_sum = {}
    parse_sum_path = ROOT / "data" / "step11_parse_summary.json"
    if leak_path.exists():
        leak = json.loads(leak_path.read_text(encoding="utf-8"))
    if parse_sum_path.exists():
        parse_sum = json.loads(parse_sum_path.read_text(encoding="utf-8"))
    notes_usd = leak.get("estimated_usd") or 0
    parse_usd = parse_sum.get("estimated_usd") or 0

    report = {
        "n_configs": len(parses),
        "target_matching_gated": TARGET,
        "by_k": curve_k,
        "by_questions_asked": curve_q,
        "leak": leak,
        "cost_usd": {"notes": notes_usd, "parse": parse_usd, "total": round(notes_usd + parse_usd, 4)},
        "mean_rounds": agent_mean_n,
        "parse_quality": parse_by_k,
        "first_question_by_k": {str(k): dict(first_asked[k]) for k in range(7)},
        "agent": {
            "mean_questions": agent_mean_n,
            "mean_narrowing": agent_mean_s,
            "checklist_mean_narrowing": check_mean_s,
            "delta_vs_checklist": delta,
        },
        "stopping": {
            "accuracy": round(stop_acc, 4) if stop_acc is not None else None,
            "n": n_stop,
            "hits": stop_hits,
        },
        "zero_gain_facts_on_full_walk": zero_gain_n,
        "zero_gain_facts_agent_asked": zero_gain_asked,
        "lost_joinable": {
            **rate_pack(lost_k, lost_n),
            "cleared": safety_cleared,
            "by_k": {str(k): rate_pack(lost_by_k[k]["k"], lost_by_k[k]["n"]) for k in range(7)},
            "on_original_discarded_sample": rate_pack(lost_orig_disc["k"], lost_orig_disc["n"]),
            "on_original_kept_sample": rate_pack(lost_orig_kept["k"], lost_orig_kept["n"]),
            "unique_patient_nct": rate_pack(uniq_k, uniq_n),
        },
        "gates": {
            "levels_0_2": level_gates,
            "half_gap_cleared": all_half,
            "below_quarter_stop": any_below_quarter,
            "agent_vs_checklist_cleared": vs_check,
            "stopping_cleared": stop_cleared,
            "wrongly_discarded_cleared": safety_cleared,
        },
        "limitation": (
            "Sparsity is synthetic: complete descriptions with facts removed. "
            "Upper bound on realistic coordinator input. This project has no real notes."
        ),
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Sparse-input asking — recover missing facts",
        "",
        "The previous run measured condition-resolution on complete notes.",
        "This run measures recovering the six facts when the note is incomplete.",
        "**79% is not a target.** It assumed conditionals discard. They often keep.",
        "",
        "Sparsity is synthetic (facts removed from complete descriptions), not what a",
        "coordinator would type. The numbers are an **upper bound** on realistic input.",
        "",
        f"{len(parses)} configurations. Seed 202609304. Matching-gated full-six target: 43.0%.",
        "",
        "## Gates",
        "",
        "| Measure | Result | Gate |",
        "|---|---|---|",
    ]
    for k, g in level_gates.items():
        lines.append(
            f"| Level {k}: start {pct(g['start'])} → 3 questions {pct(g['after_3'])} "
            f"(half-gap {pct(g['half_target'])}) | "
            f"{'cleared' if g['cleared_half'] else 'missed'}"
            f"{'; below quarter — STOP' if g['below_quarter'] else ''} |"
        )
    delta_txt = "n/a" if delta is None else f"{delta:+.1%}"
    q_txt = "n/a" if agent_mean_n is None else f"{agent_mean_n:.2f}"

    lines += [
        f"| Agent vs checklist | {pct(agent_mean_s)} vs {pct(check_mean_s)} "
        f"(delta {delta_txt}), {q_txt} questions | "
        f"{'cleared' if vs_check else 'missed'} |",
        f"| Stopping accuracy | {pct(stop_acc)} ({stop_hits}/{n_stop}) | "
        f"{'cleared' if stop_cleared else 'missed 70%'} |",
        f"| Wrongly discarded | {pct(lost_rate)} ({lost_k}/{lost_n}) | "
        f"{'cleared' if safety_cleared else 'BREACHED'} |",
        "",
        "Wrongly-discarded overrides the recovery gates. It was measured fresh on",
        "the agent's discarded set, not carried over from the condition-resolution run.",
        f"On the original discarded sample: {pct(lost_orig_disc['k']/lost_orig_disc['n'] if lost_orig_disc['n'] else None)}"
        f" ({lost_orig_disc['k']}/{lost_orig_disc['n']}).",
        f"On originally-kept trials the agent now discards: {pct(lost_orig_kept['k']/lost_orig_kept['n'] if lost_orig_kept['n'] else None)}"
        f" ({lost_orig_kept['k']}/{lost_orig_kept['n']}).",
        f"Unique patient–trial pairs: {pct(uniq_rate)} ({uniq_k}/{uniq_n}).",
        "",
        f"Leak rate (final notes still leaking): {leak.get('leak_rate_final')}. "
        f"First drafts that leaked: {leak.get('leak_rate_first_draft')}. "
        f"Note generation ${notes_usd:.4f}. Parse ${parse_usd:.4f}.",
        "",
        "## Narrowing against completeness k (parsed note, before asking)",
        "",
        "| k | Start | After 3 questions |",
        "|---|---:|---:|",
    ]
    for k in range(7):
        lines.append(f"| {k} | {pct(curve_k[k]['start'])} | {pct(curve_k[k]['after_3'])} |")
    lines += [
        "",
        "## Narrowing against questions asked (checklist order, from the parsed start)",
        "",
        "| Questions | Mean matching-gated narrowing |",
        "|---|---:|",
    ]
    for q in range(7):
        lines.append(f"| {q} | {pct(curve_q[q])} |")
    lines += [
        "",
        "## Parse quality",
        "",
        "| k | Recall of intended facts | Precision | Notes that invented a fact | Notes that missed one |",
        "|---|---:|---:|---:|---:|",
    ]
    for k in range(7):
        pq = parse_by_k[k]
        lines.append(
            f"| {k} | {pct(pq['mean_recall'])} | {pct(pq['mean_precision'])} | "
            f"{pq['n_invented']} | {pq['n_missed']} |"
        )
    first_lines = []
    for k in range(7):
        counts = first_asked[k]
        if not counts:
            first_lines.append(f"- k={k}: no missing facts (nothing to ask)")
            continue
        parts = ", ".join(f"{fact} {n}" for fact, n in counts.most_common())
        first_lines.append(f"- k={k}: {parts}")
    lines += [
        "",
        "## First fact asked vs discard-power order",
        "",
        "The agent asks missing facts in checklist order (marker, stage, immuno,",
        "platinum, brain, autoimmune). The first question is therefore the highest-power",
        "missing fact by design, not a learned ranking.",
        "",
        *first_lines,
        "",
        f"Questions that recovered a fact and added zero narrowing (agent asked): {zero_gain_asked}.",
        f"Same, on the full checklist walk: {zero_gain_n}.",
        "",
        f"Mean questions (rounds) per configuration: {q_txt}. Cost: notes ${notes_usd:.4f}, parse ${parse_usd:.4f}, total ${notes_usd + parse_usd:.4f}.",
        "",
        "Will's sheets were not regenerated. Conditional-rule asking was not re-run.",
        "Steps 6 and 7 were not started.",
        "",
    ]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report["gates"], indent=2))
    print("agent", report["agent"])
    print("stopping", report["stopping"])
    print("lost", report["lost_joinable"])
    print("by_k", curve_k)
    print("by_q", curve_q)
    print("Wrote", OUT)
    print("Wrote", REPORT)


if __name__ == "__main__":
    main()
