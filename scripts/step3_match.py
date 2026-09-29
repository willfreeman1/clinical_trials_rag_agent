"""Spike 2, Step 3: can two wordings of the same trait be linked?

Compares embeddings, MeSH, and MeSH-then-embeddings on the gold pairs in
step3_gold.json. Thresholds are in THRESHOLDS.md, committed before this ran.

Embedding calls are only for gold phrases not already in the Step 1 vector
cache. MeSH download is free.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from step1_analyze import (  # noqa: E402
    EMBED_MODEL,
    VEC_PATH,
    load_key,
    normalise,
)

ROOT = Path(__file__).resolve().parents[1]
GOLD_PATH = Path(__file__).resolve().parent / "step3_gold.json"
MESH_DIR = ROOT / "data" / "mesh"
REPORT_PATH = ROOT / "data" / "step3_report.json"
GOLD_VEC_PATH = ROOT / "data" / "step3_gold_vecs.npz"

INPUT_USD_PER_MILLION = 0.02  # text-embedding-3-small, published price
EMBED_THRESHOLD = 0.85
EMBED_CURVE = (0.75, 0.80, 0.85, 0.90, 0.95)
TREE_MAX_LEVELS = 2


# ---------------------------------------------------------------------------
# MeSH
# ---------------------------------------------------------------------------

def _norm_mesh(text: str) -> str:
    text = (text or "").lower().replace("-", " ").replace("/", " ")
    text = re.sub(r"[\"'.,;:()]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _field_value(line: str) -> str:
    _, _, rest = line.partition(" = ")
    return rest.strip().split("|", 1)[0].strip()


def load_mesh() -> dict | None:
    d_path = MESH_DIR / "d2025.bin"
    c_path = MESH_DIR / "c2025.bin"
    if not d_path.exists() or not c_path.exists():
        return None

    term_to_ids: dict[str, set[str]] = {}
    id_to_trees: dict[str, list[str]] = {}
    id_to_hm: dict[str, list[str]] = {}
    id_to_pa: dict[str, list[str]] = {}
    name_to_id: dict[str, str] = {}

    def add_term(term: str, ui: str) -> None:
        key = _norm_mesh(term)
        if not key:
            return
        term_to_ids.setdefault(key, set()).add(ui)

    def parse(path: Path) -> None:
        rec: dict[str, list[str]] = {}

        def flush() -> None:
            ui = (rec.get("UI") or [None])[0]
            if not ui:
                return
            for mh in rec.get("MH", []):
                add_term(mh, ui)
                name_to_id[_norm_mesh(mh)] = ui
            for nm in rec.get("NM", []):
                add_term(nm, ui)
                name_to_id.setdefault(_norm_mesh(nm), ui)
            for entry in rec.get("ENTRY", []) + rec.get("PRINT ENTRY", []):
                add_term(entry, ui)
            for sy in rec.get("SY", []):
                add_term(sy, ui)
            trees = rec.get("MN") or []
            if trees:
                id_to_trees[ui] = trees
            hms = [_norm_mesh(h.lstrip("*")) for h in rec.get("HM") or []]
            hms = [h for h in hms if h]
            if hms:
                id_to_hm[ui] = hms
            pas = [_norm_mesh(p) for p in rec.get("PA") or []]
            pas = [p for p in pas if p]
            if pas:
                id_to_pa[ui] = pas

        with path.open(encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                line = raw.rstrip("\n")
                if line == "*NEWRECORD":
                    if rec:
                        flush()
                    rec = {}
                    continue
                if " = " not in line:
                    continue
                key, _, _ = line.partition(" = ")
                rec.setdefault(key.strip(), []).append(_field_value(line))
            if rec:
                flush()

    parse(d_path)
    parse(c_path)

    heading_ids = {name: ui for name, ui in name_to_id.items()}
    return {
        "term_to_ids": term_to_ids,
        "id_to_trees": id_to_trees,
        "id_to_hm": id_to_hm,
        "id_to_pa": id_to_pa,
        "heading_ids": heading_ids,
        "n_terms": len(term_to_ids),
        "n_ids": len(id_to_trees) + len(id_to_hm),
    }


LEADING = re.compile(
    r"^(?:a |an |the |prior |previous |history of |known )+"
)


def resolve_mesh(index: dict, phrase: str) -> dict:
    """Map a phrase to MeSH ids. unknown if nothing looks up."""
    candidates = []
    n = _norm_mesh(phrase)
    if n:
        candidates.append(n)
    stripped = LEADING.sub("", n)
    if stripped and stripped not in candidates:
        candidates.append(stripped)
    # carbo/pemetrexed and similar regimens
    parts = [p.strip() for p in re.split(r"[/,]", phrase.lower()) if p.strip()]
    if len(parts) > 1:
        candidates.extend(_norm_mesh(p) for p in parts)

    ids: set[str] = set()
    hit_terms = []
    for cand in candidates:
        found = index["term_to_ids"].get(cand)
        if found:
            ids |= found
            hit_terms.append(cand)
    return {"ids": ids, "hit_terms": hit_terms, "unknown": not ids}


def _trees(index: dict, ids: set[str]) -> list[str]:
    out = []
    for ui in ids:
        out.extend(index["id_to_trees"].get(ui, []))
    return out


def _ancestor_levels(a: str, b: str) -> int | None:
    """How many steps from ancestor a down to descendant b, or None."""
    prefix = a + "."
    if b.startswith(prefix):
        return b[len(prefix):].count(".") + 1
    prefix = b + "."
    if a.startswith(prefix):
        return a[len(prefix):].count(".") + 1
    return None


def _expand(index: dict, ids: set[str], kind: str) -> set[str]:
    """kind is 'hm' (mapped heading) or 'pa' (pharmacological action)."""
    out: set[str] = set()
    field = "id_to_hm" if kind == "hm" else "id_to_pa"
    for ui in ids:
        for name in index[field].get(ui, []):
            hid = index["heading_ids"].get(name)
            if hid:
                out.add(hid)
            extra = index["term_to_ids"].get(name)
            if extra:
                out |= extra
    return out


def mesh_pair(index: dict, phrase_a: str, phrase_b: str) -> str:
    """Return match, no, or unknown.

    Two drugs that only share a broad action like 'antineoplastic agents'
    are not a match — that would link pembrolizumab to carboplatin. A drug
    does match a class the other phrase actually named (pembrolizumab's
    action 'immune checkpoint inhibitors' vs the phrase 'checkpoint inhibitor').
    """
    ra = resolve_mesh(index, phrase_a)
    rb = resolve_mesh(index, phrase_b)
    if ra["unknown"] or rb["unknown"]:
        return "unknown"
    a, b = ra["ids"], rb["ids"]
    if a & b:
        return "match"
    hm_a, hm_b = _expand(index, a, "hm"), _expand(index, b, "hm")
    pa_a, pa_b = _expand(index, a, "pa"), _expand(index, b, "pa")
    # One phrase is the heading the other maps to, or the action it has.
    if (a & hm_b) or (b & hm_a) or (a & pa_b) or (b & pa_a):
        return "match"
    # Ancestor on the named heading, not on a shared broad action.
    trees_a = _trees(index, a | hm_a)
    trees_b = _trees(index, b | hm_b)
    for ta in trees_a:
        for tb in trees_b:
            levels = _ancestor_levels(ta, tb)
            if levels is not None and levels <= TREE_MAX_LEVELS:
                return "match"
    return "no"


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

def embed_new(phrases: list[str], api_key: str) -> tuple[np.ndarray, int]:
    vectors: list[list[float]] = []
    for start in range(0, len(phrases), 512):
        batch = phrases[start : start + 512]
        request = urllib.request.Request(
            "https://api.openai.com/v1/embeddings",
            data=json.dumps({"model": EMBED_MODEL, "input": batch}).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            body = json.loads(response.read().decode("utf-8"))
        vectors.extend(item["embedding"] for item in body["data"])
    matrix = np.asarray(vectors, dtype=np.float32)
    matrix /= np.clip(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-8, None)
    # embedding-3-small bills ~tokens; use a conservative char/4 estimate logged separately
    return matrix, sum(len(p) for p in phrases)


def load_vectors(phrases: list[str]) -> tuple[dict[str, np.ndarray], dict]:
    """Reuse Step 1's cache; embed only phrases it does not already hold."""
    cached = np.load(VEC_PATH, allow_pickle=True)
    cache_terms = list(cached["terms"])
    cache_index = {t: i for i, t in enumerate(cache_terms)}
    cache_vecs = cached["vectors"]

    by_phrase: dict[str, np.ndarray] = {}
    missing = []
    for p in phrases:
        key = normalise(p)
        if key in cache_index:
            by_phrase[p] = cache_vecs[cache_index[key]]
        elif p in by_phrase:
            continue
        else:
            missing.append(p)

    usage = {
        "reused_from_step1": len(phrases) - len(missing),
        "newly_embedded": 0,
        "new_chars": 0,
        "estimated_usd": 0.0,
    }
    if not missing:
        return by_phrase, usage

    if GOLD_VEC_PATH.exists():
        gold = np.load(GOLD_VEC_PATH, allow_pickle=True)
        gold_terms = list(gold["terms"])
        gold_index = {t: i for i, t in enumerate(gold_terms)}
        still = []
        for p in missing:
            if p in gold_index:
                by_phrase[p] = gold["vectors"][gold_index[p]]
            else:
                still.append(p)
        missing = still
        if not missing:
            usage["newly_embedded"] = 0
            return by_phrase, usage

    api_key = load_key()
    matrix, n_chars = embed_new(missing, api_key)
    # persist: merge with any existing gold cache
    old_terms, old_vecs = [], None
    if GOLD_VEC_PATH.exists():
        gold = np.load(GOLD_VEC_PATH, allow_pickle=True)
        old_terms = list(gold["terms"])
        old_vecs = gold["vectors"]
    all_terms = old_terms + missing
    all_vecs = matrix if old_vecs is None else np.vstack([old_vecs, matrix])
    np.savez(GOLD_VEC_PATH, vectors=all_vecs, terms=np.array(all_terms, dtype=object))
    for p, vec in zip(missing, matrix):
        by_phrase[p] = vec

    # published price is per token; ~chars/4 is a ceiling used only for the log
    est_tokens = n_chars / 4
    usage.update({
        "newly_embedded": len(missing),
        "new_chars": n_chars,
        "estimated_usd": round(est_tokens * INPUT_USD_PER_MILLION / 1_000_000, 6),
    })
    return by_phrase, usage


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def decide(method: str, mesh_verdict: str | None, sim: float | None, threshold: float) -> bool:
    if method == "embed":
        return sim is not None and sim >= threshold
    if method == "mesh":
        return mesh_verdict == "match"
    # combined: MeSH first; embeddings only when MeSH cannot resolve a phrase
    if mesh_verdict == "match":
        return True
    if mesh_verdict == "no":
        return False
    return sim is not None and sim >= threshold


def summarise(pairs: list[dict], labeled_as: str, method: str, threshold: float) -> dict:
    hits = sum(1 for p in pairs if p["decisions"][method])
    n = len(pairs)
    return {
        "n": n,
        "linked": hits,
        "share": round(hits / n, 4) if n else None,
        "labeled_as": labeled_as,
        "threshold": threshold if method != "mesh" else None,
    }


def main() -> None:
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    phrases = []
    for bucket in ("same", "different", "related_unclear"):
        for pair in gold[bucket]:
            phrases.append(pair["a"])
            phrases.append(pair["b"])
    # unique, stable order
    seen = set()
    unique = []
    for p in phrases:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    print(f"gold phrases: {len(unique)}")
    print("loading embeddings...")
    vectors, embed_usage = load_vectors(unique)
    print(f"  reused {embed_usage['reused_from_step1']}, "
          f"new {embed_usage['newly_embedded']}, "
          f"est ${embed_usage['estimated_usd']}")

    print("loading MeSH...")
    mesh = load_mesh()
    if mesh is None:
        print("  MeSH files missing. Run scripts/step3_fetch_mesh.py")
        mesh_ok = False
    else:
        print(f"  {mesh['n_terms']} lookup terms")
        mesh_ok = True

    def score_pair(a: str, b: str, threshold: float) -> dict:
        sim = cosine(vectors[a], vectors[b]) if a in vectors and b in vectors else None
        mesh_verdict = mesh_pair(mesh, a, b) if mesh_ok else None
        row = {
            "a": a,
            "b": b,
            "cosine": None if sim is None else round(sim, 4),
            "mesh": mesh_verdict,
            "decisions": {
                "embed": decide("embed", mesh_verdict, sim, threshold),
                "mesh": decide("mesh", mesh_verdict, sim, threshold) if mesh_ok else None,
                "combined": decide("combined", mesh_verdict, sim, threshold) if mesh_ok else None,
            },
        }
        return row

    def eval_at(threshold: float) -> dict:
        same_rows = [score_pair(p["a"], p["b"], threshold) | {"source": p["source"]}
                     for p in gold["same"]]
        diff_rows = [score_pair(p["a"], p["b"], threshold) | {"source": p["source"]}
                     for p in gold["different"]]
        unclear_rows = [score_pair(p["a"], p["b"], threshold) | {"source": p["source"]}
                        for p in gold["related_unclear"]]
        methods = ["embed"] + (["mesh", "combined"] if mesh_ok else [])
        by_method = {}
        for m in methods:
            correct = summarise(same_rows, "same", m, threshold)
            wrong = summarise(diff_rows, "different", m, threshold)
            # mesh "unknown" on a same-trait pair is a miss, not a link — already in summarise
            by_method[m] = {
                "correct_link_share": correct["share"],
                "correct_linked": correct["linked"],
                "correct_n": correct["n"],
                "wrong_link_share": wrong["share"],
                "wrong_linked": wrong["linked"],
                "wrong_n": wrong["n"],
                "clears_wrong_gate": wrong["share"] is not None and wrong["share"] <= 0.05,
                "clears_correct_gate": correct["share"] is not None and correct["share"] >= 0.85,
            }
        mesh_unknown_same = sum(1 for r in same_rows if r["mesh"] == "unknown")
        mesh_unknown_diff = sum(1 for r in diff_rows if r["mesh"] == "unknown")
        return {
            "threshold": threshold,
            "by_method": by_method,
            "mesh_unknown_on_same": mesh_unknown_same,
            "mesh_unknown_on_different": mesh_unknown_diff,
            "same": same_rows,
            "different": diff_rows,
            "related_unclear": unclear_rows,
        }

    primary = eval_at(EMBED_THRESHOLD)
    curve = []
    for t in EMBED_CURVE:
        point = eval_at(t)
        curve.append({
            "threshold": t,
            "by_method": point["by_method"],
        })

    # Best method at the committed operating point, for the gate.
    ranked = sorted(
        primary["by_method"].items(),
        key=lambda kv: (
            kv[1]["wrong_link_share"] if kv[1]["wrong_link_share"] is not None else 1,
            -(kv[1]["correct_link_share"] or 0),
        ),
    )
    best_name, best = ranked[0]

    report = {
        "embed_model": EMBED_MODEL,
        "embed_operating_threshold": EMBED_THRESHOLD,
        "mesh_source": "2025 ASCII d2025.bin + c2025.bin" if mesh_ok else None,
        "mesh_available": mesh_ok,
        "embed_usage": embed_usage,
        "n_same": len(gold["same"]),
        "n_different": len(gold["different"]),
        "primary": {k: v for k, v in primary.items() if k != "same" and k != "different" and k != "related_unclear"},
        "best_method_at_operating_point": best_name,
        "best": best,
        "gates": {
            "wrong_link_max": 0.05,
            "correct_link_min": 0.85,
            "wrong_cleared": best["clears_wrong_gate"],
            "correct_cleared": best["clears_correct_gate"],
        },
        "curve": curve,
        "pairs_at_operating_point": {
            "same": primary["same"],
            "different": primary["different"],
            "related_unclear": primary["related_unclear"],
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    print(f"{'method':<12}{'correct':>10}{'wrong':>10}  vs gates (correct>=85, wrong<=5)")
    for name, stats in primary["by_method"].items():
        flag = []
        flag.append("OK-correct" if stats["clears_correct_gate"] else "MISS-correct")
        flag.append("OK-wrong" if stats["clears_wrong_gate"] else "FAIL-wrong")
        print(f"{name:<12}{stats['correct_link_share']:>9.1%} "
              f"{stats['wrong_link_share']:>9.1%}  {', '.join(flag)}")
    print()
    print(f"best method at cosine {EMBED_THRESHOLD}: {best_name}")
    print(f"  correct-link {best['correct_link_share']:.1%}  "
          f"(gate >= 85%): {'cleared' if best['clears_correct_gate'] else 'NOT cleared'}")
    print(f"  wrong-link   {best['wrong_link_share']:.1%}  "
          f"(gate <= 5%): {'cleared' if best['clears_wrong_gate'] else 'NOT cleared'}")
    if mesh_ok:
        print(f"MeSH unknown on {primary['mesh_unknown_on_same']} of "
              f"{len(gold['same'])} same-trait pairs, "
              f"{primary['mesh_unknown_on_different']} of {len(gold['different'])} different-trait pairs")
    print(f"\nWrote {REPORT_PATH}")


if __name__ == "__main__":
    main()
