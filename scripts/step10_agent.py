"""Clarifying-question loop in LangGraph. Cap 3 rounds. Simulated coordinator."""

from __future__ import annotations

import time
import uuid
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph

from step10_common import coordinator_answer  # noqa: E402
from step10_logic import apply_answers, rank_questions  # noqa: E402

ROUNDS_CAP = 3
_RUNTIME: dict[str, dict[str, Any]] = {}


class AgentState(TypedDict, total=False):
    run_id: str
    remaining: list[str]
    answers: dict
    asked: list
    round: int
    next_question: str | None
    next_unlocks: int
    extra_discard: list[str]
    stop_reason: str
    log: list


def rank_node(state: AgentState) -> dict:
    ctx = _RUNTIME[state["run_id"]]
    remaining = set(state["remaining"])
    ranked = rank_questions(ctx["patient"], remaining, ctx["by_nct"], ctx.get("found"), state.get("answers"))
    if not ranked or ranked[0][1] <= 0:
        reason = "top_unlocks_zero" if state.get("asked") else "no_live_questions"
        return {"next_question": None, "next_unlocks": 0, "stop_reason": reason}
    question, n = ranked[0]
    return {"next_question": question, "next_unlocks": n, "stop_reason": ""}


def ask_node(state: AgentState) -> dict:
    question = state.get("next_question")
    if not question:
        return {}
    ctx = _RUNTIME[state["run_id"]]
    value = coordinator_answer(ctx["patient"], question)
    asked = list(state.get("asked") or [])
    asked.append({"question": question, "value": value, "unlocks_at_ask": state.get("next_unlocks")})
    answers = dict(state.get("answers") or {})
    answers[question] = value
    return {"asked": asked, "answers": answers, "round": int(state.get("round") or 0) + 1}


def fold_node(state: AgentState) -> dict:
    ctx = _RUNTIME[state["run_id"]]
    remaining = set(state["remaining"])
    applied = apply_answers(
        ctx["patient"], remaining, ctx["by_nct"], state.get("answers") or {}, ctx.get("found")
    )
    new_remaining = remaining - applied["extra_discard"]
    log = list(state.get("log") or [])
    last_q = (state.get("asked") or [{}])[-1].get("question") if state.get("asked") else None
    log.append({
        "round": state.get("round"),
        "question": last_q,
        "n_extra_discard": len(applied["extra_discard"]),
        "n_settled": len(applied["settled"]),
        "n_remaining": len(new_remaining),
    })
    extra = sorted(set(state.get("extra_discard") or []) | applied["extra_discard"])
    stop = state.get("stop_reason") or ""
    if int(state.get("round") or 0) >= ctx["rounds_cap"]:
        stop = stop or "cap"
    if not new_remaining:
        stop = "none_remaining"
    return {
        "remaining": sorted(new_remaining),
        "extra_discard": extra,
        "log": log,
        "stop_reason": stop,
    }


def after_rank(state: AgentState) -> Literal["ask", "end"]:
    if state.get("next_question") and (state.get("next_unlocks") or 0) > 0:
        return "ask"
    return "end"


def after_fold(state: AgentState) -> Literal["rank", "end"]:
    ctx = _RUNTIME[state["run_id"]]
    if int(state.get("round") or 0) >= ctx["rounds_cap"]:
        return "end"
    if not state.get("remaining"):
        return "end"
    return "rank"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("rank", rank_node)
    graph.add_node("ask", ask_node)
    graph.add_node("fold", fold_node)
    graph.set_entry_point("rank")
    graph.add_conditional_edges("rank", after_rank, {"ask": "ask", "end": END})
    graph.add_edge("ask", "fold")
    graph.add_conditional_edges("fold", after_fold, {"rank": "rank", "end": END})
    return graph.compile()


APP = build_graph()


def run_patient(patient: dict, remaining: set[str], by_nct, found=None, rounds_cap: int = ROUNDS_CAP) -> dict:
    run_id = uuid.uuid4().hex
    _RUNTIME[run_id] = {
        "patient": patient,
        "by_nct": by_nct,
        "found": found,
        "rounds_cap": rounds_cap,
    }
    start = time.perf_counter()
    try:
        result = APP.invoke({
            "run_id": run_id,
            "remaining": sorted(remaining),
            "answers": {},
            "asked": [],
            "round": 0,
            "extra_discard": [],
            "log": [],
            "stop_reason": "",
        })
    finally:
        elapsed = time.perf_counter() - start
        _RUNTIME.pop(run_id, None)
    asked = result.get("asked") or []
    extra = result.get("extra_discard") or []
    return {
        "patient_id": patient["id"],
        "rounds": len(asked),
        "asked": asked,
        "answers": result.get("answers") or {},
        "extra_discard": extra,
        "n_extra_discard": len(extra),
        "n_remaining": len(result.get("remaining") or []),
        "stop_reason": result.get("stop_reason") or "completed",
        "elapsed_s": round(elapsed, 4),
        "log": result.get("log") or [],
        "framework": "langgraph",
    }


def compile_note() -> str:
    return (
        "The loop is a LangGraph StateGraph (rank → ask → fold, cap 3). "
        "If one round captures nearly everything, the framework is heavier than the problem."
    )
