# Thresholds

Committed **before** the run they apply to. Git history is the evidence they were not
moved afterward. If one turns out badly chosen, it gets logged in `DECISIONS.md` and
said plainly in the memo — it does not get edited here after results exist.

---

## Spike 2, Step 1 — concept concentration in the corpus

**Committed 2026-09-28, before any extraction run.** Set by Claude with reasoning
below, not picked arbitrarily. Will may override; an override gets a `DECISIONS.md`
entry.

### What is being measured

How many distinct clinical facts do these trials actually gate on, and how concentrated
is that distribution? This decides whether a fixed set of pre-extracted columns could
cover what real questions ask about (an extraction project, which overlaps the NHTSA
classification work already in the portfolio) or whether the long tail forces filters
built at query time (a retrieval project, which is what the gap table wants).

Measured from the corpus rather than from a question set, because **a fact no trial
gates on cannot eliminate any trial** — if a patient mentions something no trial has a
rule about, every trial passes that filter trivially. So the vocabulary that matters is
defined by the trials, not by the questions. TREC topics are not used here: they span
all diseases, so their fact diversity would mostly reflect disease diversity, and
against a lung-cancer corpus that would produce a misleadingly long tail in the
direction that flatters the project.

### Sample

300 trials drawn from the 1,308 in `data/nsclc_recruiting.jsonl`, random seed
**20260928**. The drawn id list is committed to `data/step1_sample_ids.json` so the run
is reproducible.

### Granularity rules — fixed before the run, because the answer depends on them

The measurement is meaningless without these, and they are the easiest thing to get
wrong.

**Level 1, coarse category.** A closed list of 17. The model must choose from it and may
not invent a category. Concentration at this level is bounded by construction, so the
reportable thing is how the mass distributes, not whether 40 categories suffice.

`disease_or_stage`, `histology_or_subtype`, `biomarker_or_mutation`,
`prior_systemic_therapy`, `prior_local_therapy`, `performance_status`,
`organ_function_lab`, `comorbidity_or_history`, `metastasis_site`, `infection_status`,
`pregnancy_or_contraception`, `concurrent_medication`, `trial_participation`,
`consent_or_compliance`, `demographics`, `measurable_disease`, `other`.

**Level 2, fine concept.** Open vocabulary, but strictly formatted: a short lowercase
noun phrase naming the specific clinical thing being gated on.

- **Name the thing, not the threshold.** "creatinine clearance ≥60" → `creatinine
  clearance`.
- **Name the thing, not the direction.** "No prior immunotherapy" → `prior
  immunotherapy`. This is deliberate and aligns the measurement with the architecture:
  a filter searches for the *topic*, and polarity is resolved later by the model that
  reads the survivors.
- No numbers, no units, no negation words, singular where natural.

**Normalisation after extraction.** The same concept will come back spelled several
ways. Report the concentration curve three ways so the sensitivity is visible: raw
strings; lowercased and punctuation-stripped exact merge; and an embedding-based merge
of near-duplicates at cosine 0.85 and again at 0.90. State in the memo which curve the
decision was read from.

### Thresholds

Read from the **fine-concept** curve, on the exact-merge normalisation, using the share
of all gating criteria covered by the 40 most common concepts.

| Result | Decision |
|---|---|
| Top 40 concepts cover **≥90%** of gating criteria | **Extraction project.** Columns cover nearly everything a question would raise. Retrieval is marginal, the project overlaps NHTSA, and it should stop and be reconsidered. |
| Top 40 cover **70–90%** | **Continue, case is mixed.** The memo must say so plainly rather than claiming retrieval is necessary. |
| Top 40 cover **<70%** | **Retrieval project.** The tail is real, query-time filters are needed, and the gap table's vector database has a defensible justification. |

**Reasoning for 90 and 70, rather than picking round numbers.** A question raises about
six facts, and it is most likely to raise the facts trials most commonly gate on, so
frequency-weighted coverage of the top concepts is a fair proxy for "would columns have
answered this question." At 90% coverage, a six-fact question has a good chance of
being fully covered by columns and the fallback path is rarely exercised, which makes
the retrieval machinery decorative. Below 70%, roughly one fact in three needs
query-time handling, so almost every question exercises the fallback and it is
load-bearing.

**Second reported number, no threshold attached:** the share of trials whose entire
gating set falls inside the top 40 concepts. That is the "a pure column system could
handle this trial" rate. Reported for interpretation, not used as a gate, because it
answers a per-trial question while the decision is per-question.

### Known limits of this measurement, recorded before seeing results

- One model does the extraction. No second-model agreement check and no human check.
  Acceptable because a concentration curve is robust to small per-item error, but it
  means the curve is an estimate, not ground truth.
- 300 of 1,308 trials, so tail concepts appearing once or twice corpus-wide are
  under-sampled. That biases the measured tail **shorter** than reality, which means it
  biases toward the extraction conclusion — the conservative direction for this
  project, which is the right way round.
- Lung cancer only. Concentration in another disease area is unmeasured.

---

## Spike 2, Step 2 — the best a perfect cheap step could do

**Committed 2026-09-29, before the run.** Set by Claude with the arithmetic shown. Will may
override; an override gets a `DECISIONS.md` entry.

### What is being measured

Assume a flawless cheap step and build nothing. For each invented patient and each labelled
trait, use the answer key as a perfect oracle and count how many of the 1,308 trials could be
thrown out. Take the union across the patient's traits, not the sum, so trials thrown out by more
than one trait are not double-counted.

A trial can only be thrown out when a rule settles the matter definitely. Rules written
conditionally — "cannot join unless it was treated and has been stable" — cannot be settled from
a patient description, so they keep the trial no matter how good any model is. That is what puts
a ceiling on the whole idea, and the ceiling is a property of how the rules are written rather
than of any model.

### The partial-run problem

Only two traits are labelled today: previous immunotherapy and cancer spread to the brain. The
plan's threshold is written for six traits. So this run measures **per-trait elimination** and a
**two-trait union**, and the six-trait threshold is evaluated later, after Step 5.

### Thresholds — reasoned, not guessed

If six traits were independent, the share of trials thrown out would be 1 − (1 − x)⁶ where x is
the mean per-trait share. Solving that for the two targets in the plan:

- to reach the **40% floor**: (1 − x)⁶ = 0.60, so x = **8.2%**
- to reach the **70% target**: (1 − x)⁶ = 0.30, so x = **18.2%**

| Mean per-trait elimination across the two labelled traits | Reading |
|---|---|
| **below 8.2%** | Six independent traits could not reach even the 40% floor. Strong signal to stop before spending anything on labelling. |
| **8.2% to 18.2%** | Six traits land between the floor and the target. Continue, but the ceiling is the headline of the write-up, not the model. |
| **above 18.2%** | Six traits could clear the target. Continue. |

**Independence is almost certainly false and the error runs one way.** Restrictive trials tend to
be restrictive on several counts at once, so the same trial gets thrown out by more than one
trait and the union is smaller than the independent projection. So the projection above is an
**upper bound**, and the real six-trait figure will be lower. This run measures the actual
two-trait overlap so the size of that effect is known rather than assumed.

### Also reported, with no threshold attached

- **Per-patient spread**, not just an average. A patient whose cancer has spread to the brain
  faces a very different ceiling from one whose has not.
- **An optimistic ceiling** alongside the pessimistic one, treating conditional refusals as
  though the extra detail were available. The gap between the two answers a design question: if
  the system asked the coordinator two follow-up questions, how much more could it throw out?
- **How much of the corpus is unreachable**, meaning trials that have a rule about a trait but
  state it conditionally.

### Known limits, recorded before results exist

- Two traits of six, so the headline six-trait number cannot be produced yet.
- The answer key has not been human-checked beyond four corrections, so these figures inherit its
  errors. Step 9 addresses that as far as it can be.
- The invented patients are balanced by design rather than realistic in their mix, so no average
  across patients is an estimate of what a real clinic would see.
