# Clinical-trial eligibility retrieval — start here

**Where the project is right now:** spike 1 is finished. Spike 2 is run through the
cheap-filter measurements. Steps 6, 7, 8 and 9 have not been run, and Step 8 is the one
that would measure whether any answer the system gives is correct. Still no service, no
vector database, no agent framework, no container.

**Read `docs/STATUS.md` first** — it has every number measured so far and the decision
that is open. This page tells you what to read and which parts of the older files are
stale.

---

## Read these three files, in this order

| Order | File | Status | What it is |
|---|---|---|---|
| 0 | `docs/STATUS.md` | **CURRENT — read first** | Where the project stands, in plain language: every number measured so far, what is still broken, what has not been measured at all, and the decision to make. |
| 1 | `CONTEXT.md` | **CURRENT** | What the project is for, the medical words, who would use it, and every decision that has been argued and settled. Read all of it. |
| 2 | `SPIKE_2_PLAN.md` | **CURRENT — this is the work** | The seven steps to run, with thresholds. The thresholds are deliberately arbitrary placeholders; they get replaced before each step runs. |
| 3 | `report.md` | **HISTORICAL RECORD** | What spike 1 measured. The measurements are accurate and worth knowing. **Its two closing sections, "What this means" and "Paths discussed after the result", are superseded — do not follow their recommendations.** It carries a note saying so at the top. |

There is no other documentation. `SPIKE_PLAN.md`, the original spike brief, has been
**deleted** because its steps were executed and its architecture assumption turned out
to be wrong. Anything in it that is still true was moved into `CONTEXT.md` or
`SPIKE_2_PLAN.md`. If you find a reference to it anywhere, the reference is stale.

There is no full project brief, on purpose. The spikes decide whether writing one is
worth it.

---

## The design that actually works, in one paragraph

A patient description gets taken apart into separate facts by a large model. Every rule in
every trial has already been read once, in advance, by the same model. **Both sides are
assigned to the same short, fixed list of fact names**, so matching them is exact string
equality rather than any kind of similarity score — that one change lifted realistic
elimination from 23.2% to 40.6%. A three-level prior-therapy hierarchy, used only at
comparison time, then closed the platinum hole and took the realistic figure to **44.7%**.
A fact only throws a trial out on confident evidence; silence and "can't tell" both keep the
trial. A large model then reads the survivors in full. See `docs/STATUS.md` for the
measured numbers and the ceiling that caps them at 54.2%.

---

## What is already on disk

### Data — `data/` is gitignored, so it exists locally only

| File | What it is | Reuse? |
|---|---|---|
| `nsclc_recruiting.jsonl` | The 1,308 recruiting lung-cancer trials, downloaded 2026-09-28 | **Yes. Do not re-download.** |
| `nsclc_recruiting_meta.json` | The API query that produced them | Yes |
| `answer_key.jsonl` | Labels for two facts (immunotherapy, brain), plus verbatim quotes. Four hand edits. | **Yes — core ground truth** |
| `answer_key_markers.jsonl` | The genetic-marker fact, list-shaped, across all trials | **Yes — the strongest filter** |
| `answer_key_*` for platinum, autoimmune, stage | The other three facts | Yes |
| `step2_ceiling.json` | Perfect-rule-finding ceiling, six facts: 54.2% | Yes |
| `step3c_closed_names.jsonl`, `step3c_match_report.json` | Closed-name assignment and the 40.6% figure | Historical — the names-only result |
| `step3d_closed_names.jsonl`, `step3d_match_report.json` | Hierarchy + containment and the 44.7% realistic figure | **Yes — the current result** |
| `therapy_hierarchy.json` | Child → parent for the prior-therapy family | **Yes — inspectable, not buried in code** |
| `step3_report.json`, `step3b_match_report.json` | The two failed free-text matching attempts, 10% and 32% | Historical, but the negatives matter |
| `step4_parse.json`, `step4_check.md` | Patient-description parsing and its hand check | Yes |
| `fake_patients.md`, `fake_patients_draw.json` | The 20 invented patients, seed 20260929 | Yes |
| `answer_key_summary.json` | Label counts, cost, the four edited trial ids | Yes |
| `keyword_report.json` | Word-search counts and the section split | Yes, as a reference |
| `search_test_report.json` | Precision and recall for the four spike-1 lookups | Historical |
| `embeddings_openai.npz`, `embeddings_openai_meta.json` | Whole-document and whole-section vectors from `text-embedding-3-small` | **Superseded.** Spike 2 needs per-bullet vectors, not whole-document ones. |
| `embeddings.npz`, `embeddings_meta.json` | A discarded run with a small local model | **Ignore.** Not the model under test; kept only for the record. |
| `mini_pilot*.json`, `gpt54_pilot*.json` | The five labelling pilot runs on 10 trials | Historical |

### Scripts — `scripts/`

| File | What it does | Reuse? |
|---|---|---|
| `keyword_section_check.py` | Downloads trials, splits inclusion from exclusion, runs word search | **Reuse the download and the section splitter.** The tightened phrase-list logic is superseded — spike 2 needs the broadest possible lists, not tightened ones. |
| `mini_pilot.py` | Holds the shared labelling prompt, and the 10-trial runner | **Reuse the prompt.** It is the standard the answer key was built to. |
| `label_corpus.py` | The full labelling run, six threads, resumable | **Reuse** when labelling more facts |
| `embed_and_search.py` | Whole-document embedding and the spike-1 search test | **Approach superseded.** Reuse only the embedding-cache plumbing. |

### Git

Every step's deciding numbers were committed to `THRESHOLDS.md` *before* the run that
produced them, and `DECISIONS.md` records each outcome including two cases where the
pre-committed reasoning turned out to be wrong. That ordering is visible in the history and
is part of what the project demonstrates. There is still no remote. `data/`, `.env` and
`.specstory/` are gitignored, so the data files above exist locally only.

---

## Things that are true and easy to get wrong

Five mistakes that would cost real time. All of them are explained in `CONTEXT.md`;
this is the short list.

1. **Set `PYTHONIOENCODING=utf-8` and pass `encoding="utf-8"` to every file read and
   write.** The trial text is full of `≥`, `≤` and `×`, which crash a default Windows
   console.
2. **Use word boundaries in every pattern, and check sampled hits.** Searching for the
   abbreviation `ICI` as a plain substring matches 242 of 300 trials; as
   `\bICIs?\b` it matches 10. The difference is *participants*, *toxicity*,
   *immunodeficiency*, *physician*.
3. **Do not match text by similarity at all.** Three attempts failed and are measured:
   whole-document similarity (spike 1), free-text phrase matching (10% recall), and
   free-text matching after tidying the wording (32%). The pairs that should match scored
   *lower* than a pair that should not — brain versus bone spread at 0.86 — so no cutoff
   works. Closed names with exact equality reached 84% recall; a three-level therapy
   hierarchy at comparison time took the mean to 94% and platinum from 37% to 89%. Use that.
4. **A filter's ground truth is every trial with any rule about the fact**, not the
   trials that refuse it. In answer-key terms that is every label except
   `not mentioned` — 750 trials for immunotherapy, 719 for brain metastases. Measuring
   recall against the refusal set instead would test the wrong thing.
5. **A filter may only eliminate on confident evidence.** Silence is a pass. The whole
   argument that the filters narrow multiplicatively depends on this, and it is a
   non-negotiable in `SPIKE_2_PLAN.md`.

## Working practices

- **`THRESHOLDS.md`** — the real threshold for each step, committed **before** that
  step runs. The numbers in the plan are placeholders and are labelled as such.
- **`DECISIONS.md`** — a running log: date, decision, options considered, why, and what
  evidence would reverse it.
- **Track cost from the first API call.** Report spend at the checkpoint.
- **Ask Will** before spending over about $25 in one run, and before changing anything
  in the plan's Non-negotiables list.
- Commit small and often, with explanatory messages.
- You are expected to think, not just type. When the data contradicts an assumption in
  a plan, say so, propose a change, and log it. **Priorities, in order: honest results >
  a working end-to-end system > breadth of features.**
