# Spike 2 — can a complex patient question be narrowed to a readable shortlist?

**Status: CURRENT. This is the work.** Read `README.md` and `CONTEXT.md` before this
file. `report.md` is the first spike's record — its measurements hold, its
recommendations do not.

Written 2026-09-28, after the first spike's report. Nothing in this plan has been run. Still no vector database, no agent framework, no Docker.
Code written here can be thrown away.

**⚠️ Every threshold in this document is arbitrary.** Same as last time: they are
placeholders so the habit stays intact — numbers written down before the run they
apply to. They were picked by guesswork, not by reasoning about what result would
actually change the decision. Before each step runs, Will and the coding agent argue
the real number and commit it to `THRESHOLDS.md`. Git history is the proof it wasn't
moved afterward.

---

## What the first spike settled — do not re-run any of this

- **Off-the-shelf meaning-based search cannot tell a refusal from a requirement.**
  Measured on 1,308 recruiting lung-cancer trials with OpenAI
  `text-embedding-3-small`. Word search beat it on both test facts, both scopes, both
  precision and recall.
- **The mechanism, which is the useful part.** Every eligibility text scored in a
  narrow band (about 0.40 to 0.65) against the question. The spread *inside* the
  refusal group was about 0.10; the gap *between* "requires it" and "refuses it" was
  about 0.01. Scatter inside a group larger than the distance between groups means a
  ranking mixes them. 115 of 168 trials that *require* prior immunotherapy scored
  above the typical refusal.
- **A frontier model reading the text does the job well.** All 1,308 trials, both
  facts, about 8 minutes and $7.26. Four hand edits needed on the brain fact.
- **Word search recall, full text:** 81.2% for immunotherapy, 79.1% for brain
  metastases. Restricting to the cannot-join section raised precision but dropped
  recall to 64.2% and 76.7%.
- **Cost per trial read:** about $0.0055 per trial for two facts, derived from the
  measured token counts. Every cost estimate below scales from this.

**What the first spike did NOT test, and is the reason for this one:** it only ever
asked single-fact questions ("which trials refuse brain metastases"). That is not the
product. A real question is a patient description spanning six or more facts.

---

## What changed in the architecture, and why

The first spike's conclusion — stop the vector database, extract each trial into
columns instead — was right about its own evidence and wrong as a product design,
for two reasons. Columns only answer facts someone decided to extract in advance, and
the space of facts a patient description might mention is open-ended. And a fixed
column schema tuned to lung cancer would not transfer to another disease.

The design this spike tests instead:

**1. Take the question apart first.** Never embed a whole patient description. A
model reads it and emits a structured list of facts, each tagged with what the
patient has, lacks, or measures. Three or four facts usually land on structured
registry fields (disease, recruiting status, age, location) and are free and exact.
The rest are free-text work.

**2. Each fact becomes a timid filter.** A filter judges each trial as *no* (this
trial definitely cannot take this patient) or *keep*. It may only say no on confident
evidence. **A trial that never mentions kidney function has no kidney rule, so
silence is a pass.** Elimination comes mostly from trials *requiring* something the
patient lacks — a different mutation, treatment-naive status, a stricter performance
status.

**3. Filters run in sequence, most eliminative first**, so each one only reads what
survived the last. This is what keeps the cost down: a few hundred reads in total
rather than every fact against every trial.

**4. The frontier model reads whatever survives**, and resolves polarity there.

**Why precision stops mattering and recall becomes everything.** Because the filters
are joined by *and*, they narrow multiplicatively. Six filters each eliminating 30%
leave 1,308 × 0.7⁶ ≈ 154 trials; each eliminating half leaves about 20. Individually
sloppy filters are collectively decisive. But recall compounds the same way, and
against you: 81% recall per fact across six facts leaves only 0.81⁶ = **28%** of
qualifying trials. At 95% per fact it is 74%; at 98% it is **89%**.

So the first spike optimised the wrong direction. The tightened phrase list and the
cannot-join section restriction were precision work. **This architecture needs the
broadest possible phrase lists, no section restriction, recall near 100%, and
precision allowed to be terrible.** The full-text numbers the report treated as the
weaker result (81.2% and 79.1% recall) are the ones that matter.

**Where meaning-based search comes back.** The filters only need to answer "does this
trial have a *rule about* kidney function?" — topic matching, not polarity. Polarity
is resolved later by the model that reads the survivors. Topic matching is what
embeddings are good at, and the configuration is far more favourable than what was
tested: one short fact embedded against one short criteria bullet (~120 characters),
instead of a six-fact question against a 3,581-character document. The first spike's
negative result kills embeddings *for polarity*. It does not settle this.

---

## Scope change to decide in Step 6

At 1,308 lung-cancer trials, brute force — read every trial for every fact, no
filtering — costs about **$21 per question** and takes a few minutes. Affordable for
a task worth $50 or more of a coordinator's time. **So at this scope the filter chain
is an optimisation, not a necessity, and a reviewer will say so.**

At all ~124,000 cancer trials, brute force is roughly **$2,000 per question** and
hours of latency. The filter chain brings it to a few dollars. That is a ~500-fold
reduction and it is what makes the architecture load-bearing instead of decorative.

Step 6 confirms or refutes those numbers with measurements. If they hold, the project
should scope to all cancer trials, with the existing 1,308-trial answer key serving as
the labelled development set inside the larger corpus.

---

## Non-negotiables

Four carried over from the first spike, plus three new ones.

1. **The system never issues an eligibility verdict.** It returns candidate trials
   plus the criterion text a human must check.
2. **No real patient data, ever.** Patient descriptions are fictional or from a
   published research benchmark.
3. **Confidence intervals on every sample under ~200 items.**
4. **Thresholds are committed before the run they apply to** and never edited after.
5. **NEW — filters are recall-first.** A filter may only eliminate a trial on
   confident evidence. Silence is a pass. Any change to this rule needs Will's
   sign-off and a `DECISIONS.md` entry, because the whole conjunction argument
   depends on it.
6. **NEW — no answer-key leakage into phrase lists.** The model that generates a
   fact's phrase list must not see the answer key, the gold trial ids, or any
   measurement of a previous list's recall. Otherwise the recall number in Step 3 is
   meaningless. Generate once, then measure, then stop.
7. **NEW — no number from the answer key gets quoted in the memo until Step 2 is
   done.** The 40-case review is what turns the answer key from an assumption into a
   measured instrument.

---

## Stage 0 — the spike (~4 days)

Ordered so the cheapest kills come first. Steps 1 and 2 need no paid API calls.

### Step 1 — Where do the questions come from, and how many distinct facts are there? (half day, no API cost)

**First, check for an existing benchmark.** The TREC Clinical Trials track (2021 and
2022) used clinician-written synthetic patient case descriptions paired with human
relevance judgments against ClinicalTrials.gov. If those topics and judgment files
are still publicly downloadable, they solve two problems at once: a realistic
question set that Will cannot write himself without domain knowledge, and an
**independent, human-made ground truth** for retrieval that is far stronger than
anything a model can label. Verify whether it exists and is obtainable before writing
questions by hand. Also worth checking: the TREC Precision Medicine track, and any
published clinical-trial-matching benchmark.

If no benchmark is available, build 20 patient descriptions from published case
reports or trial publications rather than inventing clinical detail. Log which route
was taken.

Then the measurement that decides the project's shape: **decompose every question
into its facts, count the distinct facts across all questions, and measure how
concentrated they are.** Report what share of all fact-mentions the 40 most common
distinct facts cover.

*Arbitrary placeholder thresholds:*
- Top 40 facts cover **above 90%** of mentions → this is an extraction-and-filter
  product, retrieval has almost no job, and the project overlaps the NHTSA
  classification work. Stop and reconsider whether it is worth building.
- Top 40 facts cover **below 70%** → the long tail is real, query-time filters are
  necessary, retrieval has a defensible role. Continue.
- In between → continue, but say plainly in the memo that the case is mixed.

### Step 2 — Validate the answer key (90 minutes, no API cost)

Sample **40 trials concentrated on the boundary classes**, not at random: the 22
labelled `both classifications`, the 12 `unclear`, and a sample of
`barred with an exception`. That is where label error lives and it is the set that
defines "real refusal."

Will labels them blind, before seeing GPT-5.4's label for that trial. The question is
reading comprehension — "does this passage say people who already had immunotherapy
are refused?" — not clinical judgment. Genuinely domain-dependent cases (does
leptomeningeal disease count as a brain metastasis) get recorded as unresolvable
rather than forced.

Report agreement with an interval.

*Arbitrary placeholder threshold:* disagreement **above 25%** on the boundary classes
→ rework the labelling prompt and relabel before any answer-key number is quoted.
Below that, note the rate in the memo and carry on.

### Step 3 — Can a generated phrase list reach the recall the conjunction needs? (1 day — the load-bearing test)

**This is the step most likely to kill the architecture.** Everything above assumes a
per-fact filter can reach 95–98% recall.

Ground truth for a filter is *not* the refusal set. It is **every trial that has any
rule about that fact** — in answer-key terms, every label other than `not mentioned`.
That is 750 trials for immunotherapy and 719 for brain metastases.

Method: give a model only the fact name ("prior immunotherapy") and ask it to generate
the broadest useful phrase list, with no sight of the corpus statistics, the answer
key, or any previous attempt's score. Run word search with that list over all 1,308
full texts. Measure recall against the ground-truth set above. Then inspect what was
missed and characterise *why* — the first spike already found two known leak types:
refusals phrased without the word ("no prior systemic therapy") and rules written on
the can-join side as a negation ("No prior immunotherapy", NCT07103395).

Repeat for two further facts that have no answer key — suggest ECOG performance status
and a common organ-function threshold — using a model label as ground truth for those,
which is acceptable when measuring a filter's recall rather than a final answer.

*Arbitrary placeholder thresholds:*
- Recall **below 95%** on a first generated list, and the misses are not obviously
  fixable by a named pattern → the conjunction cannot hold, and the architecture
  fails. Stop and report.
- Recall **below 95%** but the misses fall into two or three nameable patterns → fix
  the generator once, re-measure once, and say in the memo that the list was revised
  after inspection.
- Recall **at or above 98%** across all four facts → the load-bearing assumption
  holds.

### Step 4 — Does the conjunction actually narrow anything? (1 day)

Take 3 patient questions from Step 1. For each, run the filter chain and record the
candidate count after every stage, plus the LLM reads consumed at each stage.

For a true recall figure, a reference answer is needed. If TREC judgments were
obtained in Step 1, use them — that is the strong version. Otherwise, brute-force read
all 1,308 trials for all of that question's facts with the frontier model and treat
that as the reference. **Cost: roughly $21 per question, so about $65 for three. This
exceeds the $25-per-run limit and needs Will's approval before it runs.**

Report: survivors at each stage, total reads, end-to-end recall against the reference,
and how many of the final survivors the reference also calls eligible.

*Arbitrary placeholder thresholds:*
- End-to-end recall **below 70%** → the chain is dropping qualifying trials. Identify
  which filter and whether it is the recall problem from Step 3 or the ordering.
- Final survivor count **above 400** on a six-fact question → the chain is not
  narrowing enough to matter; brute force is competitive and the architecture has no
  job at this scope.
- Total reads **above 1,308** → the chain costs more than reading everything, which
  is an outright failure of the design.

### Step 5 — Do per-bullet embeddings add recall that phrase lists miss? (half day)

Split every eligibility text into individual criteria bullets, keeping a tag for which
section each came from. Embed each bullet. Embed each fact **on its own**, not the
whole question. For each fact, rank bullets by closeness and measure recall of the
same ground-truth set as Step 3, at several cutoffs.

The number that matters is not embedding recall on its own. It is **the union**: how
much recall does adding embeddings buy on top of the generated phrase list, and
specifically does it catch the phrasings the list missed?

*Arbitrary placeholder thresholds:*
- Embeddings add **under 2 points** of recall over the phrase list → drop them. The
  project then has no vector database, and the memo has to say so plainly rather than
  keeping one for the sake of the gap table.
- Embeddings add **5 points or more**, or recover a known leak type from Step 3 →
  they have a real job, and pgvector is justified by measurement.

### Step 6 — Scope and cost model (half day)

Pull counts at the all-cancer scope. Measure how selective the structured filters
really are: for each Step 1 question, how many trials survive disease, status, age and
location filtering out of ~124,000? Then compute, from the measured per-trial read
cost, brute force versus filtered cost per question at both scopes, and estimated
latency at the parallelism the first spike already demonstrated (six threads, 1,308
trials × 2 facts in about 8 minutes).

*Arbitrary placeholder threshold:* if the filtered cost at the all-cancer scope is not
at least **50 times** cheaper than brute force there, the architecture is not earning
its complexity and the project should scope down and say so.

### Step 7 — Memo

`docs/spike2_memo.md`, in the same plain-language style as `report.md`: every number
against the thresholds as committed, with intervals; what the thresholds got wrong in
hindsight; spend; and a recommendation — **go / adjust (and how) / stop**. It must
stand alone for a reader who has seen neither this plan nor the first report, and it
must be a usable portfolio artifact even if the answer is stop.

⛳ **Checkpoint — review before any build work.**

---

## Cost estimate

| Step | Estimated cost |
|---|---:|
| 1 — question set and fact counting | $0 |
| 2 — label review | $0 |
| 3 — phrase-list recall, four facts | ~$2 |
| 4 — filter chain, three questions, with brute-force reference | ~$65 |
| 5 — per-bullet embeddings | ~$1 |
| 6 — scope and cost model | ~$1 |
| **Total** | **~$70** |

Step 4 is nearly the whole bill and needs approval. If Step 1 obtains TREC relevance
judgments, the brute-force reference becomes unnecessary and the total drops to about
**$5**, which is a strong reason to spend real effort on Step 1 before anything else.

---

## What would make Will stop

Written here so it cannot be rationalised away later.

- **Step 1:** the 40 most common facts cover nearly everything real questions ask
  about. The product is extraction plus a structured filter, which re-proves the NHTSA
  classification work and leaves the LLM-engineering gaps open.
- **Step 3:** generated phrase lists cannot reach high recall per fact, and the misses
  have no nameable pattern. The conjunction fails, and with it the narrowing step.
- **Step 4:** the filter chain either drops too many qualifying trials or fails to
  narrow enough for brute force to be beaten.
- **Step 5 alone is not a stop condition.** If embeddings add nothing, the project
  continues without a vector database, and that gap stays open and gets stated
  honestly. Do not keep a vector database that the measurements do not support.

Any of these is a good outcome for four days and under $70.
