# Context for the coding agent — clinical-trial eligibility retrieval

Read this before `SPIKE_PLAN.md`. This file gives you the background the plan
assumes: what the medical words mean, who would use the system, and the history of
how the project got to this shape. It is deliberately short. There is **no full
project brief yet, on purpose** — the spike decides whether writing one is worth it.

---

## Part 1 — The domain, in plain words

### What a clinical trial record is

A clinical trial is a study testing a treatment on human volunteers. Every trial run
in the US must be registered on ClinicalTrials.gov, a government website. Each
registration is a long structured record: who is running it, what drug, what disease,
how many patients, where, and **who is allowed to join**.

That last part is the whole project. It is written as two prose lists:

- **Inclusion criteria** — you must match *all* of these to join.
- **Exclusion criteria** — if *any* of these describes you, you cannot join.

The same fact can appear on either list depending on the trial, and it means the
opposite thing in each place. That is the core difficulty: "previous immunotherapy"
on the inclusion list means the trial *wants* patients who had it; on the exclusion
list it means those patients are *barred*. A word search cannot tell these apart.

### The vocabulary you will meet

These are shallow definitions, enough to sanity-check your own output. Do not treat
them as clinically authoritative, and do not make clinical judgments.

- **NSCLC** — non-small cell lung cancer, the most common kind of lung cancer. The
  suggested starting corpus.
- **Stage I–IV** — how far the cancer has spread. Stage I is localized, stage IV has
  spread to distant organs. Stage III is in between and is often subdivided (IIIA,
  IIIB). Trials are usually specific about which stages they accept.
- **ECOG performance status** — a 0-to-5 score for how functional a patient is in
  daily life. 0 means fully active, 1 means able to do light work, 2 means up and
  about but unable to work, higher means increasingly bedbound. Most trials require
  0 or 1. You will see "ECOG 0-1" constantly.
- **Treatment-naive** — has never been treated for this cancer. The opposite of
  "previously treated" or "pretreated."
- **Line of therapy** — first-line is the initial treatment, second-line is what you
  try after the first stops working. "Second-line or later" is a common requirement.
- **Immunotherapy / checkpoint inhibitor** — a class of cancer drug that releases
  the brakes on the immune system. Whether a patient has already had one is one of
  the most common eligibility questions, which is why the spike uses it as a test
  concept.
- **Brain metastases** — cancer that has spread to the brain. Usually an exclusion,
  but often allowed if already treated and stable. The conditional phrasing is why
  it is the spike's second test concept.
- **Mutation names** (EGFR exon 20 insertion, ALK fusion, KRAS G12C, ROS1 fusion) —
  specific genetic changes in the tumour that determine which drugs can work. Trials
  frequently require one specific mutation and exclude others.
- **Lab thresholds** — numeric requirements like "absolute neutrophil count ≥2.0 ×
  10⁹/L" or "total bilirubin ≤1.5 × upper limit of normal." Common, numeric, and
  full of symbols that break Windows console encoding.

### Who would use this, and what they ask

Five realistic user types. The **first is the primary target**; the fourth is a good
secondary demo because it needs synthesis across many records.

1. **Trial coordinators and research nurses** at cancer centres, screening a specific
   patient against open trials. This is a real job done largely by hand today.
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
   *"How many trials in this indication require a fresh biopsy at screening rather
   than accepting archival tissue?"*

### How to build the clinical vocabulary — this matters

**Do not write synonym lists from your own knowledge, and do not accept one from a
chat model. Mine the actual text.** The seven-term probe in `SPIKE_PLAN.md` was a
quick sanity check, not a finished vocabulary. Count what phrasings genuinely occur
in the corpus, review the frequency table with Will, and commit the resulting term
list to the repo as a versioned artifact.

Real numbers from 300 recruiting NSCLC trials show why. Surface forms for the
immunotherapy concept, counted as documents containing each phrase:

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

And for brain involvement: `brain metasta*` 84, `leptomeningeal` 41, `cns metasta*`
28, `central nervous system metasta*` 16, `intracranial` 16, `brain mets` **0** — the
casual abbreviation a person would type never appears in the registry at all.

**The trap, with real numbers.** A naive substring search for the abbreviation `ICI`
(immune checkpoint inhibitor) matches **242 of 300** trials. A word-boundary regex
`\bICIs?\b` matches **10**. The difference is words like *participants*,
*immunodeficiency*, *toxicity* and *physician*, which all contain the letters "ici".
That is a 24-fold error from one careless pattern. Use word boundaries, case-sensitive
matching for uppercase abbreviations, and verify every pattern against sampled hits
before trusting a count.

---

## Part 2 — Decision history: why the project is shaped this way

Four framings below look like mistakes if you do not know the reasoning. They were
argued through on 2026-09-28 and are deliberate. If you want to reverse one, bring
evidence and log it in `DECISIONS.md` — do not just propose the discarded version
back.

### Why this is not the Polars documentation project

The original plan was the same engineering project over a Python dataframe library's
documentation and GitHub issues. A one-day spike ran and the data collection worked
fine. It was set aside for one reason: **on a popular, well-documented public library
there is no honest answer-quality win available against a frontier model with web
search.** Three candidate advantages were proposed and each fell:

- *Long-tail obscurity* — a browsing model finds well-indexed public answers.
- *Retrieving from the GitHub issue archive* — most closed issues end in "fixed in
  PR #107," which matches a question without answering it. The spike measured only
  ~11% of issues yielding a clean question-answer pair.
- *API-signature precision* — a model told the library version can simply fetch the
  reference page. Not a structural limitation.

Clinical trials were chosen because retrieval there is **structurally** necessary:
answering "which trials exclude prior immunotherapy" requires reading hundreds of
eligibility sections, which no browsing model can do in one pass. The advantage does
not depend on the model being ignorant.

### Why the frontier-model comparison is not the headline

Because we would win it by construction, and **a comparison you are guaranteed to win
is not evidence** — any reviewer spots that immediately. So the browsing model appears
only as a sanity check on the premise (Step 3), in one sentence of the writeup. The
real baselines are ClinicalTrials.gov's own search, plain keyword search, and cheap
self-hosted model versus expensive frontier model on identical retrieval. That last
one is a genuine contest we might lose, which is exactly why it is worth running.

What survives regardless of answer quality, and cannot be prompted away: cost per
query, latency, reproducibility (a pinned configuration returns the same passages;
web results change daily), per-claim grounding to a fixed passage, and a controllable
refusal threshold.

### Why the system must never say a patient qualifies

A wrong eligibility answer wastes a patient's time at best and delays treatment at
worst. The system returns candidate trials plus the exact criterion text a human must
check, and never a verdict. This is not timidity — it is what makes the citation and
refusal machinery have a real purpose instead of being a feature built because a job
description mentioned it. Related: no real patient data enters the system at any
stage. Test questions describe fictional patients that Will writes.

### Why the thresholds in the plan are labelled arbitrary

Because they are. Deciding stop-or-continue criteria *before* the run is a standing
practice across this portfolio — on a previous project a retrained model looked better
and the pre-written gate rejected it because the confidence intervals overlapped. The
numbers in `SPIKE_PLAN.md` are placeholders that keep the habit intact; the real ones
get argued and committed to `THRESHOLDS.md` before each step, with git history as
proof they were not moved afterward.

---

## Part 3 — Practical notes

- **Encoding.** Criteria text contains `≥`, `≤`, `×`, `µ` and Greek letters. On
  Windows, printing these to a cp1252 console raises `UnicodeEncodeError`. Set
  `PYTHONIOENCODING=utf-8`, and pass `encoding="utf-8"` to every file read and write.
- **The registry text is inconsistent.** Section headers are not always exactly
  "Exclusion Criteria:" — expect variants, different capitalisation, missing colons,
  and occasional records where the two lists are not separated at all. Measure how
  often the parser fails rather than assuming it works.
- **Scope small.** Do not index all 604,566 studies. One disease area, a few thousand
  records.
- **Ask Will** before spending over ~$25 in one run, and before changing anything in
  the plan's Non-negotiables list.
- **Priorities, in order:** honest results > a working end-to-end system > breadth of
  features.
