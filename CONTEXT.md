# Context — clinical-trial eligibility retrieval

**Status: CURRENT.** Start with `README.md`, then read this, then `SPIKE_2_PLAN.md`.

This file gives you the background the plan assumes: what the project is for, what the
medical words mean, who would use the system, and the history of how it got to this
shape. It is deliberately short. There is **no full project brief, on purpose** — the
spikes decide whether writing one is worth it.

---

## Part 0 — What the project is for

It closes named gaps found by screening about 20 real job descriptions. The corpus has
changed once (from Polars software documentation to clinical trials) and the
architecture has changed once (see Part 2). The purpose has not changed.

| Gap | What would close it |
|---|---|
| Production vector database, chunking, hybrid search, reranking | pgvector on hosted Postgres; measured chunking and retrieval configurations |
| A named agent framework | LangGraph |
| Explicit tool use / function calling | Structured tool schemas the model chooses between, with measured tool-choice accuracy |
| A named eval/observability platform | Langfuse for traces; MLflow for the config registry and promotion gate |
| Schema-constrained structured output | Strict JSON schema for question decomposition and per-claim citations, with a measured violation rate |
| Guardrails: hallucination, prompt injection, unintended actions | Measured refusal behavior, an injection test set, and a hard "never issue an eligibility verdict" rule |
| Self-hosted LLM serving | vLLM in a container for the cheap-model arm, brought up for eval runs and torn down |

**Important:** a gap only counts as closed if the measurements support the component
being there. If the spike shows that meaning-based search adds nothing, the project
ships without a vector database and says so. Do not keep a component to satisfy a row
in this table.

**What this project does NOT try to prove** — these are covered elsewhere in the
portfolio, so do not re-prove them here: fine-tuning or distillation (the NHTSA
project), a custom-trained two-tower retrieval model (the paper-reviewer project),
classical machine-learning production rigor (NHTSA and the streamflow monitor), graph
methods (the anti-money-laundering project).

---

## Part 1 — The domain, in plain words

### What a clinical trial record is

A clinical trial is a study testing a treatment on human volunteers. Every trial run in
the US must be registered on ClinicalTrials.gov, a government website. Each
registration is a long structured record: who is running it, what drug, what disease,
how many patients, where, and **who is allowed to join**.

That last part is the whole project. It is written as two prose lists:

- **Inclusion criteria** — you must match *all* of these to join.
- **Exclusion criteria** — if *any* of these describes you, you cannot join.

The same fact can appear on either list, and it means the opposite thing in each place.
"Previous immunotherapy" on the inclusion list means the trial *wants* patients who had
it; on the exclusion list it means those patients are *barred*. A word search cannot
tell these apart. Spike 1 proved a meaning-based search cannot either.

### The vocabulary you will meet

Shallow definitions, enough to sanity-check your own output. Do not treat them as
clinically authoritative, and do not make clinical judgments.

- **NSCLC** — non-small cell lung cancer, the most common kind of lung cancer. The
  corpus downloaded so far.
- **Stage I–IV** — how far the cancer has spread. Stage I is localized, stage IV has
  spread to distant organs. Stage III is in between and is often split into IIIA and
  IIIB. Trials are usually specific about which stages they accept.
- **ECOG performance status** — a 0-to-5 score for how functional a patient is in daily
  life. 0 means fully active, 1 means able to do light work, 2 means up and about but
  unable to work, higher means increasingly bedbound. Most trials require 0 or 1. You
  will see "ECOG 0-1" constantly.
- **Treatment-naive** — has never been treated for this cancer. The opposite of
  "previously treated" or "pretreated."
- **Line of therapy** — first-line is the initial treatment, second-line is what you
  try after the first stops working. "Second-line or later" is a common requirement.
- **Immunotherapy / checkpoint inhibitor** — a class of cancer drug that releases the
  brakes on the immune system. Whether a patient has already had one is one of the most
  common eligibility questions, which is why it is one of the two test facts.
- **Brain metastases** — cancer that has spread to the brain. Usually an exclusion, but
  often allowed if already treated and stable. That conditional phrasing is why it is
  the second test fact.
- **Mutation names** (EGFR exon 20 insertion, ALK fusion, KRAS G12C, ROS1 fusion) —
  specific genetic changes in the tumour that determine which drugs can work. Trials
  frequently require one specific mutation and exclude others. **This is the single
  most eliminative fact when screening a patient**, because a trial requiring a
  mutation the patient does not have is immediately out.
- **Lab thresholds** — numeric requirements like "absolute neutrophil count ≥2.0 ×
  10⁹/L" or "total bilirubin ≤1.5 × upper limit of normal." Common, numeric, and full
  of symbols that break Windows console encoding.

### Who would use this, and what they ask

Five realistic user types. The **first is the primary target**; the fourth is a good
secondary demo because it needs synthesis across many records.

1. **Trial coordinators and research nurses** at cancer centres, screening a specific
   patient against open trials. A real job done largely by hand today, taking something
   like 30 to 90 minutes per patient.
   *"67-year-old, stage IIIB NSCLC, EGFR exon 20 insertion, ECOG 1, already had
   carboplatin and pemetrexed, creatinine clearance 55 — what's open within 200
   miles?"*
2. **Oncologists**, asking narrower treatment-sequence questions.
   *"Any trials for KRAS G12C lung cancer after progression on sotorasib?"*
3. **Patients and caregivers**, in plain language that does not match the registry's
   vocabulary at all.
   *"My mother's triple-negative breast cancer came back after chemo. Are there any
   studies she could join?"*
4. **Biotech competitive intelligence**, needing aggregation across many records.
   *"Who else is running phase 3 trials with a PD-1 inhibitor in first-line gastric
   cancer, and what primary endpoints are they using?"*
5. **Clinical operations and feasibility teams**, asking about design patterns.
   *"How many trials in this indication require a fresh biopsy at screening rather than
   accepting archival tissue?"*

**Note the shape of question 1, because it drives the whole current architecture:** it
is six or more facts at once, not one. Spike 1 only ever tested single-fact questions.

### How to build the clinical vocabulary — this matters

**Do not write phrase lists from your own knowledge, and do not accept one from a chat
model as final. Mine the actual text, and check every pattern against sampled hits.**

Real numbers from 300 recruiting NSCLC trials. Surface forms for the immunotherapy
concept, counted as documents containing each phrase:

| Phrase | Trials (of 300) |
|---|---|
| immunotherapy | 90 |
| PD-L1 | 60 |
| PD-1 | 45 |
| anti-PD | 38 |
| immune checkpoint | 28 |
| checkpoint inhibitor | 27 |
| CTLA-4 | 18 |
| pembrolizumab | 16 |
| durvalumab | 6 |
| nivolumab | 4 |
| atezolizumab | 3 |

For brain involvement: `brain metasta*` 84, `leptomeningeal` 41, `cns metasta*` 28,
`central nervous system metasta*` 16, `intracranial` 16, and `brain mets` **0** — the
casual abbreviation a person would type never appears in the registry at all.

**The trap, with real numbers.** A naive substring search for the abbreviation `ICI`
(immune checkpoint inhibitor) matches **242 of 300** trials. A word-boundary regular
expression `\bICIs?\b` matches **10**. The difference is words like *participants*,
*immunodeficiency*, *toxicity* and *physician*, which all contain the letters "ici".
That is a 24-fold error from one careless pattern. Use word boundaries, case-sensitive
matching for uppercase abbreviations, and verify every pattern against sampled hits
before trusting a count.

---

## Part 2 — Decision history

These framings look like mistakes if you do not know the reasoning. Each was argued
through and is deliberate. To reverse one, bring evidence and log it in
`DECISIONS.md` — do not simply propose the discarded version back.

### Why this is not a software-documentation project

The original plan was the same engineering project over a Python dataframe library's
documentation and GitHub issues. A one-day spike ran and the data collection worked
fine. It was set aside for one reason: **on a popular, well-documented public library
there is no honest answer-quality win available against a frontier model with web
search.** Three candidate advantages were proposed and each fell — long-tail
obscurity (a browsing model finds well-indexed public answers), retrieving from the
issue archive (most closed issues end in "fixed in PR #107," which matches a question
without answering it), and API-signature precision (a model told the library version
can just fetch the reference page).

Clinical trials were chosen because narrowing there is **structurally** necessary:
answering a six-fact patient question requires consulting hundreds of eligibility
sections, which no browsing model does in one pass.

### Why the frontier-model comparison is not the headline

Because we would win it by construction, and **a comparison you are guaranteed to win
is not evidence** — any reviewer spots that immediately. So a browsing model appears
only as a sanity check on the premise, in one sentence of any writeup. The real
baselines are ClinicalTrials.gov's own search, plain word search, and cheap
self-hosted model versus expensive frontier model on identical narrowing.

What survives regardless of answer quality, and cannot be prompted away: cost per
question, latency, reproducibility (a pinned configuration returns the same passages;
web results change daily), per-claim grounding to a fixed passage, and a controllable
refusal threshold.

### Why the architecture changed after spike 1 — read this one carefully

Spike 1 asked whether meaning-based search could rank refusals above requirements. It
cannot, and the mechanism is measured in `report.md`. Spike 1's own recommendation was
to extract every trial into a fixed set of columns and filter that table instead.
**That recommendation was rejected**, for two reasons: columns only answer facts
somebody chose in advance, and the space of facts a patient description might mention
is open-ended; and a column schema tuned to lung cancer would not transfer to another
disease.

What replaced it:

1. **Take the question apart first.** Never embed a whole patient description. A model
   reads it and emits a structured list of facts, each tagged with what the patient
   has, lacks, or measures. Three or four facts usually land on structured registry
   fields (disease, recruiting status, age, location) and are free and exact.
2. **Each fact becomes a timid filter.** A filter judges each trial as *no* (definitely
   cannot take this patient) or *keep*, and may only say no on confident evidence. **A
   trial that never mentions kidney function has no kidney rule, so silence is a
   pass.** Most elimination comes from trials *requiring* something the patient lacks.
3. **Filters run in sequence, most eliminative first**, so each reads only what
   survived the last. This is what keeps cost down.
4. **A frontier model reads whatever survives** and resolves polarity there.
5. **Pre-extracted columns are a cache, not a schema.** Extract the facts that recur
   so the reading cost is paid once, but never depend on the cache existing; any fact
   without a column falls back to a filter generated at query time.

**The inversion this causes, which is the most important single idea in the project.**
Because the filters are joined by *and*, they narrow multiplicatively: six filters each
eliminating 30% leave 1,308 × 0.7⁶ ≈ 154 trials. So **precision per filter barely
matters.** But recall compounds the same way and against you: 81% recall per fact
across six facts leaves only 0.81⁶ = 28% of qualifying trials. At 95% it is 74%; at
98% it is 89%.

Therefore **spike 1 optimised the wrong direction.** Its tightened phrase list and its
cannot-join-section restriction were precision work. This architecture wants the
broadest possible phrase lists, no section restriction, recall near 100%, and precision
allowed to be terrible. The full-text recall numbers spike 1 treated as the weaker
result (81.2% and 79.1%) are the ones that matter.

### Why meaning-based search is not dead

The filters only need to answer "does this trial have a **rule about** kidney
function?" — topic matching, not polarity. Polarity is resolved later by the model
reading the survivors. Topic matching is what embeddings are good at, and the
configuration is far more favourable than spike 1 tested: one short fact embedded
against one short criteria bullet (about 120 characters), rather than a whole question
against a 3,581-character document. Spike 1 killed embeddings **for polarity**. It did
not settle this, and `SPIKE_2_PLAN.md` Step 5 tests it.

### Why the system must never say a patient qualifies

A wrong eligibility answer wastes a patient's time at best and delays treatment at
worst. The system returns candidate trials plus the exact criterion text a human must
check, and never a verdict. This is not timidity — it is what gives the citation and
refusal machinery a real purpose instead of being a feature built because a job
description mentioned it. Related: no real patient data enters the system at any stage.
Patient descriptions are fictional or come from a published research benchmark.

### Why the thresholds in the plans are labelled arbitrary

Because they are. Deciding stop-or-continue criteria *before* the run is a standing
practice across this portfolio — on a previous project a retrained model looked better
and the pre-written gate rejected it because the confidence intervals overlapped. The
numbers in the spike plans are placeholders that keep the habit intact; the real ones
get argued and committed to `THRESHOLDS.md` before each step, with git history as proof
they were not moved afterward.

---

## Part 3 — Practical notes

- **Encoding.** Criteria text contains `≥`, `≤`, `×`, `µ` and Greek letters. On
  Windows, printing these to a cp1252 console raises `UnicodeEncodeError`. Set
  `PYTHONIOENCODING=utf-8`, and pass `encoding="utf-8"` to every file read and write.
- **The registry text is inconsistent.** Section headers are not always exactly
  "Exclusion Criteria:". Spike 1 measured it: a heading on its own line in 1,234 of
  1,308 trials, the words somewhere in a line in 46, and **no heading at all in 28**.
  Measure parser failures rather than assuming success.
- **The corpus is already downloaded.** 1,308 recruiting NSCLC trials in
  `data/nsclc_recruiting.jsonl`. Do not re-download it. See `README.md` for what else
  is on disk.
- **Ask Will** before spending over about $25 in one run, and before changing anything
  in a plan's Non-negotiables list.
- **Priorities, in order:** honest results > a working end-to-end system > breadth of
  features.
