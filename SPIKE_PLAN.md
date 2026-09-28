# Clinical-trial eligibility retrieval agent — Feasibility spike plan

**Status:** written 2026-09-28. Nothing built yet. This covers **Stage 0 only** —
the cheap test of whether the project's core bets hold. No LangGraph, no Docker,
no vector database yet. Code written here can be thrown away.

Same shape as `CORPFAM_BUILD_PLAN.md`. Read alongside the gap table below.

**⚠️ Every threshold in this document is arbitrary.** They are placeholders, put
here so the *habit* is right — numbers written down before the run they apply to.
They were picked by guesswork, not by reasoning about what result would actually
change the decision. Before each step runs, Will and the coding agent argue the
real number and commit it to `THRESHOLDS.md`. Git history is the proof it wasn't
moved afterward. Do not treat any number below as settled.

---

## Why this project exists

It closes named gaps found by screening ~20 real job descriptions. The corpus
changed (from Polars documentation to clinical trials); the purpose did not.

| Gap | What closes it |
|---|---|
| Production vector database, chunking, hybrid search, reranking | pgvector on hosted Postgres; measured chunking and retrieval configurations |
| A named agent framework | LangGraph |
| Explicit tool use / function calling | Structured tool schemas the model chooses between, with measured tool-choice accuracy |
| A named eval/observability platform | Langfuse for traces; MLflow for the config registry and promotion gate |
| Schema-constrained structured output | Strict JSON schema for per-claim citations, with a measured violation rate |
| Guardrails: hallucination, prompt injection, unintended actions | Measured refusal behavior, an injection test set, and a hard "never issue an eligibility verdict" rule |
| Self-hosted LLM serving | vLLM in a container for the cheap-model arm, brought up for eval runs and torn down |

**What this project does NOT try to prove** (covered elsewhere in the portfolio,
do not re-prove here): fine-tuning or distillation (NHTSA), a custom-trained
two-tower retriever (paper-reviewer), classical-ML production rigor (NHTSA,
streamflow), graph methods (AML).

---

## What the system is, in one paragraph

A question-answering service over US clinical-trial records that helps someone
screening a patient find candidate trials and, critically, shows **the exact
criterion text** that makes each trial a candidate or not. The hard part is that
everything filterable — age, sex, phase, status, location, disease — is already
structured and already searchable on ClinicalTrials.gov, while everything that
actually decides eligibility — which genetic mutations, which prior treatments
disqualify you, required lab values, performance status, disqualifying
comorbidities — exists only as prose inside one free-text block per trial.

## The frontier-model comparison is deliberately NOT the headline

A browsing frontier model cannot read 300 eligibility sections in one pass, so a
comparison on multi-trial questions would be won by construction. **A comparison
you are guaranteed to win is not evidence.** State that in one sentence and move
on. The real baselines are:

1. **ClinicalTrials.gov's own search** — free, public, and what a coordinator
   actually uses today. This is the baseline to measure against.
2. **Keyword search over criteria text** — the naive version of what we're building.
3. **Cheap self-hosted model vs. expensive frontier model, both on our retrieval** —
   the genuine production decision, and a contest we might lose.

Step 3 below still tests the browsing model, but as a *sanity check on the premise*,
not as the headline result.

---

## Facts already verified (2026-09-28) — do not re-derive

- API: `https://clinicaltrials.gov/api/v2/studies`, free, no key, US government
  public domain. `countTotal=true` returns totals; `fields=` limits the payload.
- **604,566** studies total. **123,589** mention cancer. **1,308** recruiting for
  non-small cell lung cancer (NSCLC).
- Each record has 12 modules. Eligibility lives in `protocolSection.eligibilityModule`.
- The **only** structured eligibility fields are `healthyVolunteers`, `sex`,
  `minimumAge`, `maximumAge`, `stdAges`. Everything clinical is free text in
  `eligibilityCriteria`.
- Across 300 recruiting NSCLC trials: criteria text averages **3,467 characters**,
  maximum **19,471**. Zero records were missing criteria text.
- **The motivating measurement.** Searching those 300 trials for prior-immunotherapy
  terms (immunotherapy, PD-1, PD-L1, checkpoint inhibitor, pembrolizumab,
  nivolumab, atezolizumab), split at the "Exclusion Criteria" header:

  | Term appears | Trials |
  |---|---|
  | Inclusion section only | 55 |
  | Exclusion section only | 49 |
  | Both sections | 38 |
  | Nowhere | 158 |

  So "which trials exclude patients who already had immunotherapy?" returns **142
  keyword hits, of which 49 are right** — about 35% precision. The 55
  inclusion-only trials are the *opposite* of the request. Keyword search is blind
  to negation and to section position. Reproduce this first; it is the project's
  motivating number and it must hold up.
- Windows gotcha: criteria text contains `≥`, `≤`, `×`. Printing to a cp1252
  console raises `UnicodeEncodeError`. Set `PYTHONIOENCODING=utf-8`, and read and
  write every file with `encoding="utf-8"` explicitly.

---

## Setup

- **Repo:** `C:\Users\willf\git_proj\ctgov-eligibility-rag`, pushed to
  `willfreeman1/*`. **Not** inside Google Drive — sync corrupts `.git` folders.
  Keep briefs in Drive, copy the current one into `docs/` in the repo.
- `.env` git-ignored from the first commit. Data directory git-ignored.
- Python version and package manager are your call; log it.
- Decide with Will before Step 1: which frontier model for the browsing arm
  (record its version and stated training cutoff), and which embedding model.

## Working practices

- **`THRESHOLDS.md`** — the real threshold for each step, committed **before**
  that step runs. The placeholders in this document are explicitly not final.
- **`DECISIONS.md`** — running log: date, decision, options considered, why, and
  what evidence would reverse it.
- Commit small and often, with explanatory messages.
- **Cost tracking from the first API call.** Every LLM and embedding call logs
  tokens and dollars. Report spend at the checkpoint.
- **Ask Will** before spending over ~$25 in one run, and before changing anything
  in Non-negotiables.

## Non-negotiables

1. **The system never issues an eligibility verdict.** It returns candidate trials
   plus the specific criterion text a human must verify. Never "this patient
   qualifies." This is a safety rule and a product decision, not a limitation to
   engineer around.
2. **No real patient data, ever.** Test questions describe fictional patients that
   Will writes. Nothing from a real person enters the system at any stage.
3. **Hand-labeling happens blind**, before seeing any model's output on that item.
4. **Confidence intervals on every sample under ~200 items.** A 20-question probe
   has a very wide interval; report it rather than quoting a bare percentage.
5. **Thresholds are committed before the run they apply to**, and never edited
   afterward. If one turns out to be badly chosen, log that in `DECISIONS.md`
   and say so in the memo — do not quietly change it.
6. **The browsing-model arm gets a fair prompt.** Told the corpus, told what a good
   answer looks like, allowed to search repeatedly. No strawman.

## Yours to decide (propose, log, proceed)

Disease-area scope, chunking approach, embedding model, how to structure the
labeling tool, sample sizes within the ranges given, library choices, repo layout.
If a better approach than this plan's shows up, say so.

---

## Stage 0 — the spike (~3 days)

Ordered so the cheapest ways to kill the project come first.

### Step 1 — Reproduce the motivating number, and pick the scope (half day)

Pull the chosen disease area's trials via the API and store them locally. Reproduce
the 142-vs-49 keyword-precision result on the 300 NSCLC records, then check whether
it holds on the wider set and on a second clinical concept. Suggested second
concept: brain metastases, usually an exclusion but sometimes explicitly allowed if
treated and stable.

Decide and log the corpus scope. Starting suggestion: all-status NSCLC, or all
recruiting solid-tumour trials. Report the record count and the total characters of
criteria text.

*Arbitrary placeholder threshold:* if keyword precision for the intended meaning is
**above 70%** on both concepts, the premise is much weaker than assumed — stop and
reconsider before doing anything else.

### Step 2 — Does semantic search handle negation? (1 day — the step most likely to kill this)

**This is the real risk.** Embedding models are known to be weak at negation:
"excludes prior immunotherapy" and "requires prior immunotherapy" embed to nearly
the same place because they share almost all their words. If that weakness holds
here, the project's central retrieval claim fails, and no amount of engineering
rescues it.

Build ground truth first, by hand, blind: take 150 trials and label each for two
concepts — does it exclude prior immunotherapy (yes / no / ambiguous), does it
exclude untreated brain metastases (yes / no / ambiguous). Label before running any
search. The section-split regex may pre-sort candidates to make labeling faster, but
Will's label is the one that counts, and ambiguous cases must be recorded as
ambiguous rather than forced into a binary.

Then measure, on the same labeled set:
- keyword search;
- embeddings over whole criteria blocks;
- embeddings over inclusion and exclusion sections indexed **separately**;
- an LLM reading each retrieved chunk and answering the inclusion-or-exclusion
  question.

Report precision and recall for each, with intervals.

*Arbitrary placeholder thresholds:*
- Embeddings alone within **5 points** of keyword search on the negation questions →
  embeddings are not solving negation. Not fatal, but the architecture must shift to
  section-aware indexing plus an LLM classification pass, and the writeup says so
  plainly.
- Section-aware indexing plus an LLM pass **below 80% precision** → stop. The system
  cannot do its one job.
- If the honest answer is "an LLM reading each trial works, and retrieval adds little
  beyond narrowing the candidate set" — that is a legitimate finding and it reframes
  the project around the cost and latency of the narrowing step. Report it, do not
  bury it.

### Step 3 — Is the premise real? Test the browsing model (half day)

Will writes **20 coordinator-style questions** before any of this runs — realistic
patient screens over fictional patients, weighted toward multi-trial and
negation-heavy cases. Run them through a browsing frontier model with a fair prompt.
Score how many candidate trials it finds that are actually correct, and how many it
asserts that are wrong.

*Arbitrary placeholder threshold:* if the browsing model handles **15 of 20** well,
the premise is weaker than assumed — not fatal, since cost, latency, reproducibility
and auditability all survive, but the writeup must lead with those instead of with
retrieval quality. Report the interval; on n=20 it is very wide.

### Step 4 — Programmatic ground truth: how much is free? (half day)

Test the three proposed free-label sources:

- **Structured fields as labels** — questions about phase, status, age limits.
  Confirm these are answerable and gradeable with no human in the loop.
- **Set-retrieval labels** — the Step 2 labeling pass, reused: every question of the
  form "find trials that exclude X" gets precision and recall for free from one
  labeling session. Confirm this generalizes to a third concept.
- **Structured-versus-text contradictions** — one record already showed
  `minimumAge: 18 Years` while its text said "aged 18-75", so the maximum age exists
  only in prose. Measure how common that pattern is across the corpus. If common, it
  is both a free source of checkable questions and a genuine data-quality finding
  worth reporting.

*Arbitrary placeholder threshold:* if fewer than **300** gradeable questions can be
produced without hand-writing each answer, the eval budget is mostly human time —
say so, and scope the eval set down honestly rather than pretending otherwise.

### Step 5 — Chunking: does the inclusion/exclusion boundary survive? (half day)

At up to 19,471 characters, some criteria blocks must be split. Splitting *across*
the inclusion/exclusion boundary would be catastrophic for exactly the questions this
system exists to answer — a chunk holding the tail of the inclusion list and the head
of the exclusion list is actively misleading.

Measure: how many records exceed a plausible chunk size; how often a naive
fixed-size split crosses the boundary; whether a section-aware splitter (split on the
header first, then within each section, never across) keeps every chunk labeled with
which section it came from. Also check how often the header is formatted unusually
enough to break the regex — real registry text is inconsistent.

*Arbitrary placeholder threshold:* if a section-aware splitter cannot correctly label
**95%** of chunks, fix the parser before building anything else. This is plumbing,
not research — it should just work, and if it doesn't, the whole retrieval layer is
built on sand.

### Step 6 — Feasibility memo

`docs/feasibility_memo.md`, in the plain-language style of the Polars spike memo:
every number from Steps 1–5 against the thresholds as committed, with intervals;
what surprised you; what the thresholds got wrong in hindsight; spend to date; and a
recommendation — **go / adjust (and exactly how) / stop**.

Write it so Will can hand it to a reviewer who has read none of this, and so it
stands on its own as a portfolio artifact even if the answer is "stop."

⛳ **Checkpoint 0 — review before any build work.** Bring: the memo, `THRESHOLDS.md`
with its git history, `DECISIONS.md`, the hand-labeled CSV from Step 2, the 20
questions from Step 3, and spend to date.

---

## Cost estimate for the spike

- ClinicalTrials.gov API: free.
- Embedding a scoped corpus (a few thousand trials): well under $5.
- LLM calls for Steps 2–4 (classification passes, the 20-question browsing arm):
  roughly $10–25 depending on model choice.
- **Total: under $30.** Check current provider pricing before starting; it moves.

## What would make Will stop

Written here so it cannot be rationalized away later:

- Section-aware indexing plus an LLM pass can't reach usable precision on the
  negation questions (Step 2). The system cannot do its one job.
- Keyword search turns out to be fine (Step 1). There is no problem to solve.
- Free ground truth doesn't materialize *and* the browsing model does well
  (Steps 3–4). The project becomes months of hand-labeling for a result nobody
  needs.

Any of those is a good outcome for three days and $30 — the same way CorpFam was.
