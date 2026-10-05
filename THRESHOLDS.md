# Thresholds

Committed **before** the run they apply to. Git history is the evidence they were not
moved afterward. If one turns out badly chosen, it gets logged in `DECISIONS.md` and
said plainly in the memo — it does not get edited here after results exist.

---

## How to read this file

This is the project's record of deciding what would count as success **before**
seeing any result. Each section was written and committed first; the measurement
it describes came afterwards, in a later commit.

**Verifying that, rather than taking it on trust:**

```bash
git log --follow --oneline THRESHOLDS.md
```

Every commit message here begins with a word like *lock*, *commit* or *record*,
and names what was being fixed in advance. Comparing those dates against the
commits that added the corresponding results in `docs/` shows the ordering.

Some later runs were locked in machine-readable form instead of prose, in
`scripts/*_config.json` — the model, the random seeds, the exact patient and pair
lists, and what was deliberately out of scope. Same convention, same ordering.

**This header was added after the fact for readability. Nothing below it has been
changed.**

### Where each published result was pre-registered

| Result | Locked in |
|---|---|
| Search keeping 91.6% / 91.4% of eligible trials at 6% of the collection | *TREC hybrid retrieval*, line 1545 |
| Re-ranking the shortlist, including two cross-encoders that failed | *TREC reranking the shortlist*, line 1696 |
| What the shortlist actually contains, and three fixes that went nowhere | line 1796 onward |
| The cheap disease-relevance pass | *cheap topical pass*, line 1932 |
| Whether a re-ordering stage earns its place | line 2029 |
| The eligibility prompt rewrite that made things worse | line 2219 |
| Adapter against the default ranker, 50 held-out patients | line 2377 |
| The rule-by-rule reader — 7.6% of rules settled, 3.75% fabricated quotes | line 2419 |
| Fine-tuning settings, seeds and training pairs | `scripts/trec_lora_config.json` |
| The pre-registered cutoff replication on a year never used in the sweep | `scripts/trec_lora_rank_2021_config.json` |
| GPT-5.4 against the fine-tuned model on identical pairs | `scripts/trec_gpt_vs_adapter_config.json` |
| The reader's design, scope and exclusions | `scripts/trec_reader_config.json` |

Sections before line 1545 belong to an earlier phase of the project on a
lung-cancer slice of the registry. That work produced the first measurement of
how often a model invents a supporting quote, but it is not the work the README
describes, and nothing in it is needed to follow the published results.

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

---

## Spike 2, Step 3 — can two wordings of the same trait be linked?

**Committed 2026-09-29, before any matching run.** Set from the plan's guessed
gates. Will may override; an override gets a `DECISIONS.md` entry.

### What is being measured

The cheap step has to recognise that a patient's wording and a trial's wording
name the same trait, without treating two different traits as the same. The
second error is the one that can throw out a joinable trial. The first error
only makes the shortlist bigger.

Three methods, compared on the same pairs:

1. **Embeddings** — `text-embedding-3-small`, the model already used in Step 1,
   cosine similarity, match at or above the operating threshold.
2. **MeSH** — the National Library of Medicine's medical subject headings,
   freely downloadable, with the synonym list and the hierarchy that should
   connect a specific drug to its class. UMLS is preferred in the plan but
   needs a licence; if MeSH cannot be installed in half a day, this arm is
   recorded as failed and embeddings run alone.
3. **Combined** — MeSH first; embeddings only when MeSH cannot resolve at
   least one of the two phrases. A MeSH "no" is a no, not a fallback.

### Gold pairs

The pairs are in `scripts/step3_gold.json`, committed with this document. They
were written before any matching scores existed.

**Same-trait pairs** come from two places that do not depend on embeddings:

- The wording-trap table already written at the end of `data/fake_patients.md`,
  plus a few extra surface forms of those same traps (a drug name vs the class
  the table says it should recover).
- English-only variants anyone can check by reading: an abbreviation and its
  expansion, a plural and a singular, a phrase and the same phrase with a
  filler word (`written informed consent` / `informed consent`).

They do **not** come from Step 1's embedding clusters. Scoring embeddings
against those clusters would make method 1 look perfect by construction.

**Different-trait pairs** are the dangerous ones, not a random sample of
unrelated phrases (random unrelated phrases are easy and would flatter every
method):

- Near-string confusions: `brain metastases` / `bone metastases` (the merge
  Step 1 already documented as a mistake), `hepatitis b` / `hepatitis c`,
  `pleural effusion` / `pericardial effusion`, `nsclc` / `small cell lung cancer`.
- Crossed traps: a wording that should recover trait A, paired with trait B
  (`pembrolizumab` / `platinum-based chemotherapy`, `carbo/pemetrexed` /
  `prior immunotherapy`).
- Same-category but different fact: `EGFR mutation` / `ALK fusion`,
  `pregnancy` / `pregnancy test`.

A small **related-unclear** list is scored and reported but is **not** read
against the gate — pairs a reader could honestly argue either way
(`measurable disease` / `measurable lesion`). Putting them in the gate would
let a wording dispute look like a method failure.

### Operating threshold for embeddings

Match if cosine ≥ **0.85**. That is the merge threshold Step 1 already used, so
this step tests the setting the project has actually been relying on, not a
new one chosen to look better. The same pairs are also scored at 0.75, 0.80,
0.90 and 0.95 and reported as a curve; those points are not the gate.

### Thresholds — guessed, as the plan labelled them

Read from the hand-specified gold in `scripts/step3_gold.json`.

| Result on the best of the three methods | Decision |
|---|---|
| Wrongly linking different-trait pairs **> 5%** | Matching is the weak point. Stop building the rest of the cheap step until this is fixed. |
| Correctly linking same-trait pairs **< 85%** | The cheap step will miss rules. That makes the shortlist bigger, not wrong. Note it and continue. |
| Wrong-link ≤ 5% and correct-link ≥ 85% | Matching is good enough to build on. |

The gate is read from the **best** method, because the cheap step will use one
method, not an average of three.

### Also reported, with no threshold attached

- The wording groups Step 1's cosine-0.85 merge actually produced, written to
  `data/step3_wording_groups.json` this time (they were never saved before).
- Whether that merge still joins `bone metastases` to `brain metastases`.
- How many gold phrases MeSH cannot resolve at all.
- Tokens and dollars for the embedding calls this step makes.

### Known limits, recorded before results exist

- The same-trait set is small and tilted toward the traps in the invented
  patients, which is the matching problem the cheap step actually faces, not a
  sample of all 5,578 concept strings.
- MeSH 2025 ASCII is used if it downloads; 2026 ASCII was discontinued. A
  one-year lag in a synonym list is a limitation, not a reason to skip the arm.
- No UMLS licence is on this machine. If the hierarchy in MeSH is too coarse
  to connect a drug to its class, that is a finding about MeSH, not about
  "a medical dictionary" in the abstract.

---

## Spike 2, Step 4 — can the big model take a patient description apart?

**Committed 2026-09-29, before any parse run.** Set from the plan's guessed
gates. Will may override; an override gets a `DECISIONS.md` entry.

### What is being measured

Everything downstream assumes a patient description can be turned into a clean
list of traits: a name with no direction and no number in it, a situation, and
one of three kinds (`yes_no`, `one_of_many`, `number`). Nothing has tested
that. Step 1 pulled traits out of trials, which is the opposite direction.

Each of the 20 invented descriptions in `data/fake_patients.md` is sent to
`gpt-5.4` with the output shape in the plan. Will then checks all 20 against
the structured answers already written under each description, counting four
kinds of mistake separately. That check is careful reading of English against
a list. It needs no medical knowledge.

### Expected traits, fixed before the run

Every description states these, so a missing one is a miss:

- age — `number`
- disease stage — `one_of_many`
- histology — `one_of_many`
- genetic marker the tumour carries (including "none" / wild type) — `one_of_many`
- performance status score — `number`
- creatinine clearance — `number`
- prior lines of therapy — `number`
- previous platinum chemotherapy — `yes_no`
- previous immunotherapy — `yes_no`
- cancer spread to the brain — `yes_no`

And, only when the description actually states them: autoimmune disease, interstitial
lung disease, hepatitis B, hepatitis C, HIV, major surgery, pleural effusion.
A comorbidity the description does not mention is not a miss if omitted, and is
an invention if added.

Treated-versus-untreated brain metastases is extra detail on that trait, not a
separate required row. Recording it is fine; dropping it is not one of the four
counted mistakes.

`one_of_many` records the value the patient has, not the values they lack.
Number traits stay `number` even though the cheap step will later ignore them.

### The four mistakes, counted per patient

- **Missed** a trait the description states (from the list above).
- **Invented** a trait the description does not state.
- **Put a direction or a number into the name** — "must have had chemotherapy"
  rather than "previous chemotherapy"; a digit or a comparison in the name.
- **Wrong kind** — a number trait labelled `yes_no` or `one_of_many`, or the
  reverse.

A patient is a **fail** if they have a miss or an invention. Direction-in-name
and wrong-kind are counted separately and also make that patient a fail, because
both break the search step.

### Thresholds — guessed, as the plan labelled them

| Result | Decision |
|---|---|
| Miss or invent (or either of the other two mistakes) in **more than 2 of 20** patients | Fix the instructions once, measure once more, and say in the write-up that they were revised. |
| Still more than **4 of 20** after that one revision | Stop. |

### Also reported, with no threshold attached

- Tokens and dollars.
- Whether drug names were recovered as the class (`carbo/pemetrexed` → previous
  platinum chemotherapy). That is the wording problem Step 3 just measured; it
  is not a fourth gate here, but a miss of platinum on P01 is still a miss.
- Names that are close but not identical to the list above, which Will settles
  by reading. The script flags, it does not judge.

### Known limits, recorded before results exist

- 20 invented descriptions, written with traps on purpose, so this is harder
  than a templated note and easier than a real chart.
- One model, one prompt. No second-model agreement.

---

## Spike 2, Step 5a — label the genetic-marker trait only

**Committed 2026-09-29, before the labelling run.** The gate this run is
read against is already in the Step 2 section above (8.2% per trait to clear
the floor, 18.2% to reach the target). This section only records what is
being labelled and that the other three traits wait on the re-measurement.

### What is being labelled

One list-shaped trait across all 1,308 trials, in a new file
`data/answer_key_markers.jsonl`, so the existing two-trait key is not
touched.

Per trial: `required_markers` (list), `refused_markers` (list),
`genetic_marker_condition` (string or empty), `genetic_marker_quote`, `note`.
Empty lists and an empty quote mean the trial states no marker rule.

Instructions extend the existing labelling prompt's rules (a lab result is
not a treatment history; a drug the trial itself gives is not something the
patient had before) and add the marker definition from the plan. Same model,
`gpt-5.4`. Same quote check, adapted: a non-empty list needs a quote that
appears in the trial text and mentions a marker; empty lists need an empty
quote.

### What happens after the run, before any more labelling

Re-run Step 2 with three traits (immunotherapy, brain, markers). The
committed Step 2 table still decides:

| Mean per-trait elimination | Reading |
|---|---|
| below 8.2% | Stop. |
| 8.2% to 18.2% | Continue, ceiling is the headline. Whether the other three traits get labelled depends on whether the marker moved the six-trait projection toward 70%. |
| above 18.2% | Continue, including the other three traits. |

If the marker trait does not lift the projection enough to change that
picture, the other three traits are **not** labelled. That is the cheap
exit in the plan.

### Known limits, recorded before results exist

- Claude wrote the marker definition; Will cannot check it medically. If a
  labelled row is internally inconsistent (quote does not mention a marker
  that appears in a list), it is flagged, not guessed into a different list.
- Marker matching for the Step 2 re-run will be string overlap plus shared
  gene tokens (EGFR, ALK, KRAS, ROS1, BRAF, MET, RET, NTRK, HER2), because a
  perfect filter would know `EGFR L858R` satisfies a required list that says
  `EGFR mutation`. That rule is written down here before the labels exist.

---

## Spike 2, Step 3b — matching once both sides are in general terms

**Committed 2026-09-29, before any normalisation or matching run.** Suggested
by Will; argued below where this document disagrees.

### Why this is a new measurement

Step 3 tested raw hard cases (drug name to family) and found the pairs that
should match score 0.34–0.63 while brain/bone scores 0.86. No cutoff works.
But the take-apart step already does that translation, once per patient. The
untested question is whether matching works once *both* sides are written in
general terms.

### What is being measured

1. The big model turns each non-empty answer-key quote for the three labelled
   facts (immunotherapy, brain, marker) into a short general-term subject:
   no direction, no number, class over specific drug. It is not told which
   fact the quote came from, and it is not given the patient field names, so
   it cannot just copy a closed list.
2. The patient side is the revised Step 4 output.
3. Three matching arms, scored on the same pairs:
   - **Word overlap** — after lowercase, split on non-letters, drop
     `{the,a,an,of,to,for,on,in,and,or,with,by,from,into,as,at,is,are}`, keep
     tokens of length ≥ 4 or in `{cns,alk,hiv,met,ret,egfr,kras,ros1,braf,her2,pd1,pdl1}`.
     Match if the intersection is non-empty.
   - **Embeddings** — `text-embedding-3-small`, match at cosine ≥ **0.80**.
     Sweep 0.70, 0.75, 0.80, 0.85, 0.90 is reported; 0.80 is the gate. 0.85
     was Step 3's un-normalised operating point and sat above cerebral/brain
     (0.80) and below bone/brain (0.86). Once both sides are general, 0.80 is
     the lowest cutoff that still has a chance to catch a near-paraphrase;
     bone/brain risk is left to the wrongly-picked-up number.
   - **Combined** — either arm matches.

A patient query is the trait **name**, and for `one_of_many` also the
**value**. A trial is retrieved for that query if any of its normalised
subjects (from any of the three facts) matches any of those strings. Ground
truth is free: a trial has a rule about a fact iff its answer-key verdict is
anything other than `not_mentioned` (for markers: either list non-empty).

- **Recall** — of trials that have a rule about this fact, what share is
  retrieved.
- **Wrongly-picked-up rate** — of trials that have no rule about this fact,
  what share is retrieved anyway.

The headline is not recall × ceiling. That is an approximation. The headline
is the **matching-gated ceiling**: re-run the Step 2 oracle, but a trial is
thrown out only if the oracle would throw it out *and* matching retrieved it
for that trait. Report that next to the 39.9% perfect-oracle ceiling. The
difference is the real state of the project.

The gated number uses **combined** at the committed 0.80. It is a ceiling
under this matcher, not a prediction of end-to-end accuracy. Reading
everything is still Step 8.

### Thresholds

| Result on combined, at 0.80, mean across the three facts | Decision |
|---|---|
| Recall **below 60%** | Matching loses most of the ceiling. The approach needs rethinking. |
| Recall **60–85%** | Workable. Quote the matching-gated ceiling, not the perfect-oracle ceiling. |
| Recall **above 85%** | Matching is not the bottleneck. |
| Wrongly-picked-up **above 20%** | Too noisy. The judging step gets swamped and the brain/bone risk is live. |

Per-fact numbers are also reported. The gate is read from the mean, because
the cheap step has to work on every fact, and from the matching-gated union
as the headline.

### Known limits, recorded before results exist

- Only three facts are labelled, so only three can be matched. Step 5b adds
  three more and this measurement is re-run.
- Quote-check failures (stitched quotes) still go into normalisation; a bad
  quote can produce a bad subject.
- Trials with no quote on any of the three facts can never be retrieved, so
  they pull the wrongly-picked-up rate down. That is the operational number
  (those trials are silent in the index), and it is said here rather than
  hidden.

---

## Spike 2, Step 5b — label stage, platinum, and autoimmune

**Committed 2026-09-29, before the labelling run.** Approved after the marker
trait moved the six-trait projection from 51.7% to 63.8%. Run after Step 3b
because matching on general terms may change what three more facts are worth.

### What is being labelled

One request per trial, three traits, new file
`data/answer_key_step5b.jsonl`. Same model, `gpt-5.4`. Same quote-check idea.

- **previous platinum chemotherapy** — the eight-way classification and a
  quote, same shape as the immunotherapy trait.
- **autoimmune disease** — the same eight-way shape.
- **disease stages** — list-shaped, like markers: `allowed_stages`,
  `refused_stages`, `stage_condition`, `stage_quote`. Record the trial's own
  labels, including descriptive ones (`locally advanced`, `metastatic`). Do
  not translate a description into a numbered stage.

Definitions are those in the plan. A platinum drug the trial itself would
give is not prior platinum. A family history is not an autoimmune disease.

### Stage matching for the six-trait ceiling, written before labels exist

Patient `disease_stage` is thrown out when, and only when:

- `stage_condition` is empty (else keep), and
- `allowed_stages` is non-empty and the patient's stage is not in that list,
  or `refused_stages` is non-empty and the patient's stage is in that list.

"In the list" means substring match after lowercase, plus: patient `IV`
matches a list item containing `metastatic` or `stage 4` / `stage iv`;
patient `IIIB` matches `iiib`, `iii-b`, or `iii b`. No other translations.

### After the run

Re-run the perfect-oracle ceiling with six traits, and the matching-gated
ceiling with whatever Step 3b subjects exist plus newly normalised quotes
for these three facts. The 8.2% / 18.2% per-trait gates still decide. The
Step 3b recall gates still decide for matching.

---

## Spike 2, Step 3c — matching by exact equality on a closed name list

**Committed 2026-09-29, before any closed-name assignment or matching run.**
This is the rethink named after Step 3b: put both sides on the same fixed
names, then match by string equality. The two known matching bugs are
closed in the same method, not by a new matcher.

### Why this is a new measurement

Step 3b asked the trial side for any ordinary general term and found that
those terms do not sit in the same neighbourhood as the patient-side names.
Marker recall was 16–23% because a patient with value `none` queries
`tumour genetic marker` and `none`, which share no token with `EGFR
mutation`. Brain wrongly-picked-up hit 45.5% because a shared word index
let `cancer` in `cancer spread to the brain` hit nearly every stage quote.

Neither hole needs embeddings, a dictionary, or a trained model:

- **No-marker.** Retrieval asks "does this trial have a rule about this
  fact?", not "does the patient's value appear in the subject." The value
  is for the later throw-out, not for matching. A patient whose marker is
  `none` still queries the name `tumour genetic marker`.
- **Word-flooding.** There is no shared token bag. A trial is retrieved
  for a fact only when its assigned name equals that fact's name.

### What is being measured

1. The big model reads each non-empty answer-key quote for the six labelled
   facts (~4,383 sentences) and assigns it to exactly one name from this
   closed list, or `other`:

   - `previous immunotherapy`
   - `cancer spread to the brain`
   - `tumour genetic marker`
   - `previous platinum chemotherapy`
   - `autoimmune disease`
   - `disease stage`
   - `other`

   It is not told which fact the quote was labelled as. Direction and
   value are not re-extracted. Batch ~20 quotes per request.

2. The patient side is the revised Step 4 output, mapped onto the same
   six names (`autoimmune condition` → `autoimmune disease`;
   `tumor genetic marker` → `tumour genetic marker`). The query is the
   name only. The value is never a query string.

3. **One matching arm: exact equality of names.** A trial is retrieved
   for a patient fact if any of its assigned names equals that fact's
   name. `other` retrieves nothing.

Ground truth is unchanged: a trial has a rule about a fact iff its
answer-key verdict is anything other than `not_mentioned` (for markers
and stage: either list non-empty).

- **Recall** — of trials that have a rule about this fact, what share is
  retrieved.
- **Wrongly-picked-up rate** — of trials that have no rule about it, what
  share is retrieved anyway.

The headline is the **matching-gated ceiling** under this matcher, next
to the 54.2% six-trait perfect-oracle ceiling. A trial is thrown out only
if the oracle would throw it out *and* exact-name matching retrieved it
for that trait. That is a ceiling under this matcher, not a prediction
of end-to-end accuracy. Reading everything is still Step 8.

### Thresholds

Same bands as Step 3b, because the decision question is the same.

| Result, mean across the six facts | Decision |
|---|---|
| Recall **below 60%** | Matching still loses most of the ceiling. Closed names did not fix it. |
| Recall **60–85%** | Workable. Quote the matching-gated ceiling, not the perfect-oracle ceiling. |
| Recall **above 85%** | Matching is not the bottleneck. |
| Wrongly-picked-up **above 20%** | Too noisy. Assignment is putting quotes on the wrong name. |

Per-fact numbers are also reported. Also reported, no gate: the share of
quotes whose assigned name matches the source fact (assignment accuracy),
and the share of rule-trials that have no quote at all (a ceiling on
recall that no matcher can beat).

### Known limits, recorded before results exist

- The model sees the quote, not the source field, so assignment error is
  a real miss. Using the source field as the name would make recall
  perfect by construction and would not measure matching.
- Stitched quotes (one sentence covering two facts) get one name. That
  can miss the second fact.
- Trials with a rule but an empty quote cannot be retrieved.
- Only the six labelled facts are on the list. A quote about something
  else should come back `other`.

---

## Spike 2, Step 3d — containment over a hand-written prior-therapy hierarchy

**Committed 2026-09-30, before any re-assignment, extra patients, or rescoring.**
Closes the platinum hole without UMLS. UMLS is a separate test: generalising
beyond these field names. Embeddings are not used. Steps 6 and 7 stay on hold.

### Why

Closed-name assignment recalled 81–99.9% of rules on five facts and **37.2%**
on previous platinum chemotherapy. 284 of 545 platinum-source sentences say
"no prior chemotherapy" or "no prior systemic treatment" and never name
platinum. The assigner had no broader name to file them under, so it returned
`other`. That is a missing label, not a matching failure.

The fix is **containment at comparison time**. Neither side is rewritten to a
different level. The hierarchy is consulted only to ask whether one level
contains the other.

| | Patient's fact | Trial's rule | Result |
|---|---|---|---|
| 1 | same level | same level | ordinary comparison |
| 2 | narrower | broader | rule applies — the patient's case sits inside the ban |
| 3 | broader | narrower | **can't tell → keep the trial** |
| 4 | unrelated | unrelated | no match → keep the trial |

Case 2 is the platinum hole and is safe: a patient who had platinum sits
inside a ban on any chemotherapy. Case 3 must not narrow: a trial that bars
platinum specifically cannot be applied when all we know is the patient had
some chemotherapy. Promoting the trial's rule up to chemotherapy would
exclude people who had a different kind of chemotherapy.

Immunotherapy sits under systemic anticancer treatment and **not** under
chemotherapy. Those two broader levels stay distinct.

### What is being measured

1. Two names are added to the closed list: `previous chemotherapy (any kind)`
   and `previous systemic anticancer treatment (any kind)`.
   `previous platinum chemotherapy` and `previous immunotherapy` stay as they
   are. The hierarchy is a committed JSON file, not logic buried in code.
2. Re-assign only: quotes whose answer-key source is platinum or
   immunotherapy, plus every quote currently assigned `other`. The other four
   facts' assigned names are copied forward unchanged, then **re-scored**,
   because comparison changed.
3. Five extra invented descriptions with vague treatment history and no
   named drug. These test case 3. The original 20 are checked first; if none
   of them is a vague-history case, that is stated, not papered over.
4. No embeddings. No UMLS. Verdicts (required, barred, barred-with-condition)
   still come from the answer key.

Recall and wrongly-picked-up are defined as in Step 3c. The headline is still
the matching-gated six-fact narrowing rate on the original 20 patients, next
to 40.6% (names alone) and 54.2% (perfect finder).

Also reported, no gate until seen: how many trials are now kept as can't-tell
that a both-directions containment would have narrowed. That is the price of
the safety valve.

### Thresholds

| Measure | Gate |
|---|---|
| Platinum recall | must reach **70%**, from 37.2%. Recovering all 284 sentences would give about 89%, so 70% is a real bar with headroom. |
| Every other fact's recall | must not fall by more than **3 points** versus Step 3c. |
| Wrongly-picked-up, any fact | stays **under 20%**. |
| Wrongly-picked-up on the 5 vague-history patients, for trials whose assigned name is `previous platinum chemotherapy` | must be **0%**. Narrowing a vague-history patient on a platinum-specific rule is a wrong narrowing. |
| Matching-gated six-fact narrowing on the original 20 | should **rise** from 40.6%. If it falls, stop and say so. |

Wilson 95% intervals on any sample under 200. Do not select on the
wrongly-picked-up gate alone.

### Known limits, recorded before results exist

- The original 20 were written with named drugs on purpose. Case 3 is
  untested there unless a vague-history patient is found on a re-read.
- Containment is only defined for the prior-therapy family. Brain, marker,
  stage, and autoimmune stay exact name equality.
- Re-assigning `other` quotes from the four untouched facts can still attach
  a therapy name to a sentence that was never about therapy. That would show
  up as wrongly-picked-up.
- UMLS is not part of this run.

---

## Spike 2, Step 8 — measure the reader, not overall accuracy

**Committed 2026-09-30, before any sample was drawn or any trial was sent
to a reader.** The $20 spend is approved. Steps 6 and 7 stay on hold.

### Why this is not an accuracy number

The answer key covers six facts. A trial has about 43 rules. Exclusions
on those six facts are verifiable: if the key says a trial bars previous
immunotherapy and the patient had it, that trial excludes them. Acceptances
are not: if none of the six facts excludes the patient, the other 37 rules
might. The key cannot confirm an acceptance.

So this step does **not** produce an overall accuracy figure. It measures
four things that are each verifiable, and reports them separately.

In published work on this task, doctors agreed with each other only
**64–70%** of the time on per-rule eligibility questions. Do not treat 90%
as a human ceiling, and do not read a figure in the 80s as poor.

### Models under test — decided before the run

Two models, not three.

| Role | Model | Price |
|---|---|---|
| Expensive | `gpt-5.4` | $2.50 / $15 per million tokens |
| Cheap | `gpt-5.4-mini` | $0.75 / $4.50 per million tokens |

**Not Qwen3 on a Lambda GPU this run.** That is a self-hosted serving
question (vLLM, GPU-hours, a different cost model) and there is no serving
stack in this repo. It stays a follow-up: if mini reads nearly as well as
5.4, Qwen is how you go cheaper still; if mini is much worse, that does
not prove Qwen would fail, and the write-up must say so.

**Not all three.** The $20 envelope and the two-day window are sized for
one cheap/expensive pair on the same sample. Mini is the sharp cheap
comparator because it already failed the related labelling task in spike 1
(bone counted as brain; a concurrent drug counted as prior immunotherapy).
This measurement asks whether that failure repeats on a full patient-vs-trial
read.

Same sample, same prompt, both models. The gap on measurement 1 is a cost
decision, not a pass/fail.

### What is being measured

1. **Does narrowing lose joinable trials?** Among trials the Step 3d
   matching-gated filter discarded, how often does the reader call the
   patient a candidate (`candidate_needs_human_check`)? The full read is
   the reference. No external ground truth. This is the number that can
   withdraw the 44.7% figure.
2. **Does the reader fabricate?** Every judgment that is not "not enough
   information" must carry a word-for-word quote. Check mechanically that
   the quote appears in that trial's eligibility text (exact, or the same
   normalised-whitespace match used on the answer key). Also flag quotes
   that appear in the trial but do not mention the claimed fact, using the
   existing keyword lists for the six labelled facts; open facts are
   reported separately and are not in the 5% gate.
3. **Does the reader agree with the key where the key is authoritative?**
   On sampled trials the six-fact key definitely excludes this patient
   (unconditional bar or unmet requirement, not a conditional), does the
   reader exclude them? Same-rule agreement (the excluding quote is about
   the same fact the key used) is reported next to that, not gated on its
   own.
4. **Does the reader catch exclusions the six facts miss?** Kept trials
   where the key does not exclude and the reader does. Sample 20 for Will.
   The check is: does the quoted sentence plainly say what the model
   claims. Not a medical judgment.

Also reported, no gate: cost and elapsed time per patient for both models;
the "not enough information" rate per fact; consistency on 20 pairs run
twice (how often the overall verdict changes).

### Sample

Six patients, seed **20260930**. Four cells of prior-immunotherapy × brain
metastases, one extra original-20 patient, one vague-history patient.

| Patient | Immuno | Brain | Why this one |
|---|---|---|---|
| P01 | no | yes, untreated | cell (no, yes) |
| P02 | no | no | cell (no, no); HIV; CrCl 37 |
| P03 | yes | yes, treated/stable | cell (yes, yes); conditional brain |
| P12 | yes | no | cell (yes, no); autoimmune, ILD |
| P09 | yes | yes, untreated | extra; EGFR; untreated vs P03's treated |
| V01 | vague chemo, no drug named | no | the safety-valve case; not in the original 20 |

Per patient, without replacement, from the Step 3d matching-gated discarded
and kept sets on the 1,307-trial universe:

- **100** discarded (measurement 1)
- **150** kept (what production would send the reader)

If a patient has fewer than 100 discarded, take all of them and say so.
20 consistency pairs: 10 discarded + 10 kept from P01's sample, read a
second time by each model.

Do not read all 1,307 for anyone.

### Reader output

Per relevant rule: `excludes_this_patient` / `does_not_exclude` /
`not_enough_information`; a verbatim quote; one sentence of reasoning.
Overall: `definitely_excluded` / `candidate_needs_human_check` /
`never_eligible`. The system never says the patient qualifies.
"Not enough information" is a correct answer. It is not penalised.

A discarded trial counts as a lost joinable trial only when overall is
`candidate_needs_human_check`. `never_eligible` and `definitely_excluded`
are not lost joinables.

### Thresholds

| Measure | Gate |
|---|---|
| Discarded trials the reader calls a candidate | above **10%** → narrowing is unsafe and the 44.7% figure must be withdrawn |
| Quotes that do not appear in the trial text | above **5%** → fabrication problem; headline finding either way |
| Agreement with the key on verifiable exclusions | below **85%** → reader or key is wrong; investigate before reporting anything |
| Cheap vs expensive on measurement 1 | **no gate.** Report the gap. |

Wilson 95% intervals on any sample under 200. Do not produce an overall
accuracy figure.

### Known limits, recorded before results exist

- Acceptances are unverifiable. A "candidate" call on a kept trial is not
  scored as correct or incorrect.
- The 10% lost-joinable gate uses the expensive model as the reference
  full-read. The cheap model is compared to it, not used to withdraw 44.7%
  on its own, unless the write-up says otherwise after seeing the gap.
- Mini failing does not settle Qwen3. That limitation is in the model
  table above.
- Will's 20-row check is reading comprehension, not medicine.
- Conditional key exclusions (`barred_with_exception`, marker/stage
  conditions) are not in the verifiable-exclusion set.

---

## Spike 2, Step 9 — check the answer key as far as reading can

**SUPERSEDED 2026-09-30, before any of the 40 rows were scored.** The
sample was the key's least-sure labels (`unclear`, `both_classifications`,
`barred_with_exception`). Those labels keep the trial, so a wrong one
cannot change any number in the project. Replaced by the section below.
The 40-row sheet in `docs/step9_will_check.md` is kept as a record, marked
superseded. No results were seen. Goalposts were not moved.

---

## Spike 2, Step 9 (revised) — audit support, then audit definite labels

**Committed 2026-09-30, before the quote-flag recategorisation and before
the 30-row consequential sample was drawn.** Free.

### Task 1 — mechanical quote flags (no human)

The six-fact labelling run flagged 52% of Step 5b trials. Recategorise
every flagged quote into:

| Bucket | Meaning |
|---|---|
| A | Stitched: two or more real passages from the same trial joined |
| B | Whitespace, markdown, or punctuation only |
| C | Real passage; word-list spelling miss |
| D | Paraphrased — close, not a quote |
| E | Absent — no such text in that trial |

A, B, and C are checker or stitching artifacts. D and E are real support
problems. Residual flag rate = (D + E) / all checked quote-slots.

Step 8 found 1.2% of reader quotes missing. D+E should land near 1–2%.
If much higher, the labelling prompt differs from the reader prompt and
that difference gets written down.

| Measure | Gate |
|---|---|
| (D + E) / all checked quote-slots | above **5%** → the key has a support problem; affected rows need re-labelling before numbers that rest on them are quoted |

### Task 2 — 30 consequential rows for Will

Only `barred` and `required`. Weight by contribution to narrowing:

| Fact | Rows |
|---|---:|
| Tumour genetic marker | 8 |
| Disease stage | 8 |
| Previous platinum chemotherapy | 5 |
| Previous immunotherapy | 5 |
| Cancer spread to the brain | 3 |
| Autoimmune disease | 1 |

Within each fact, split barred / required in proportion to how many of
each exist. Seed **202609301**. Drawn trial ids committed before the
sheet is generated. Model notes live in a separate file, not on the
sheet.

The question: does this quote say that the trial bars / requires this
thing? agree / disagree / needs medical knowledge.

Reasoned from Step 8's 6.3% lost-joinable against a 10% gate. Errors in
barred/required add to that same figure.

| Disagreement / checkable (agree + disagree) | Reading |
|---|---|
| Under **5%** | Definite labels hold. Quote the numbers as they stand. |
| **5–10%** | Note it. Add it to the lost-joinable discussion: 6.3% plus label error is the honest figure. |
| Above **10%** | Definite labels are unreliable enough to matter. Re-examine 6.3% before quoting it. |

Needs-medical-knowledge is reported as a limitation, not gated.

For every disagreement: record what the label should be, then check
whether that trial was discarded for any of the 20 invented patients.

---

## Spike 2, Step 9 — three mechanical quote checks

**Committed 2026-09-30, before any of the three checks ran.** Free. No
human. Does not touch the 30-row consequential sheet.

These are not pass/fail numbers. If the count is non-zero, it is named
in full. Do not fold a small count into a percentage.

| Check | If non-zero |
|---|---|
| Stitched quotes that mix the can-join list and the cannot-join list | Finding. Report trial ids and facts, plus one example in full. Unresolvable splits (loose heading or no heading) are reported separately, not counted as clean. |
| Bucket E (`barred` / `required`) labels that actually discarded a trial for any of the 20 patients | Finding. Name patient, trial, fact, label, and the quote that does not exist. |

Check 3 splits word-list misses into C1 (hierarchy parent), C2 (synonym), C3 (unrelated). C1 is only defined for the prior-therapy family. C3 is added to D+E and re-checked against the committed 5% support gate.

---

## Spike 2, Step 9 — gate breached; scoped re-label then re-score

**Committed 2026-09-30, before the scope-detector ran, before any
re-labelling, and before any downstream number was re-scored.**

The 30-row check was a second-model agreement check, not a human
audit (DECISIONS.md). 4 of 29 checkable rows disagreed (13.8%),
above the 10% band. Every disagreement was a wrongful discard.
Cause: a criterion scoped to another tumour type, read as general.

Previous headline numbers stay in the record. They are not
overwritten. Both sets go in the write-up, with this reason.

### Task 1 — size the basket-trial population (free)

No gate. Report: how many of 1,307 trials list more than one cancer
type in `conditions`; how many of the 30 sampled rows came from
those trials; how many quotes anywhere in the key name a cancer
other than lung, per fact. The scope-detector is mechanical.

### Task 2 — close the title-as-quote hole in bucket E (free)

`NCT07444814`'s stage quote is the trial title and is not in the
eligibility text. It should have been bucket E and was not. Find
why, close that hole, re-run bucket E, report the corrected D+E.
The 1.3% figure is not to be quoted until this is understood.

### Task 3 — re-label with a scoping instruction

Add, in substance: a criterion explicitly scoped to a tumour type,
cohort, or study part other than this patient's does not apply.
"Subjects with ovarian cancer must have had platinum" is not a
platinum requirement for a lung-cancer patient. Record
`not_mentioned` unless the trial states the same rule for this
patient's tumour type.

Re-label every trial the Task 1 detector flagged, plus a random
sample of 100 unflagged trials (seed **202609302**) to test whether
the error also occurs where the detector does not fire. If it does
at a material rate, widen the re-label to the whole corpus and say
so.

Cost is about $0.012 per trial. A few hundred trials is a few
dollars. Stop and ask if spend would exceed **$25**.

Do not re-run the 30-row sheet with a model and call it
verification. If a fresh sample is judged by a model, label it as
such.

### Task 4 — qualifier convention

A qualifier that narrows a bar makes it conditional. Words such as
active, uncontrolled, untreated, symptomatic, within N months push
a `barred` rule to `barred_with_exception`, not `barred`.

Why: the design errs toward keeping trials. A qualifier means we
cannot be certain the patient falls inside the bar, and certainty
is the standard for discarding.

Adopting this will move rules into the conditional bucket, which
**lowers the ceiling and lowers the 44.7% headline**. That is
correct behaviour, not a regression. Report it that way.

### Task 5 — re-score, in this order

1. Perfect-finder ceiling (was 54.2%).
2. Matching-gated narrowing (was 44.7%).
3. Step 8 lost-joinable (was 6.3%), re-scored against the corrected
   key. The 10% gate still applies, unchanged. If the corrected
   figure exceeds 10%, the narrowing figure is withdrawn pending
   investigation.

Write new report files. Leave the previous JSON reports on disk.

### Citation rule going forward

The labeller must emit a quote that is a verbatim substring of the
eligibility text (normalised whitespace allowed). If it is not, reject
and retry up to twice. Do not quote the trial title. This closes the
class NCT06868485 showed: right label, invented source.

### Brain C3 re-label (37 rows)

Re-label only the 37 brain slots whose quote names metastatic disease
and never the brain. A sentence about spread anywhere is not a
brain-metastases rule. Immuno labels on those trials are left alone.
Snapshot the yes/no key first. Do not start the scoped basket re-label.

---

## Spike 2, Step 9 — remaining list before the numbers can be trusted

**Committed 2026-09-30, before the 12 stage labels were cleared, before
the 70 crossings were re-labelled, before the qualifier convention was
applied, and before any of 54.2% / 44.7% / 6.3% was re-scored.**

A missing quote is not a wrong label. The 12 title-inferred stage
requirements are wrong labels. The 70 mixed-polarity / heuristic-disagree
crossings are small enough to re-label directly. Then one policy call,
one free count, one re-score. Do not re-score with known errors still
in the data.

Previous headline numbers stay on disk. Both sets go in the write-up.

### 1. Twelve known-wrong stage labels

Clear `allowed_stages`, `refused_stages`, `stage_quote`, and
`stage_condition` on these twelve trials. The eligibility text states
no stage rule; the label was inferred from the title. Mechanical. No
model. These 12 caused 212 wrong discards among the 20 patients.

### 2. Seventy crossing rows

Re-label the 50 mixed-polarity stitches and the 20 where the polarity
check disagreed with the stored label. Model. Verbatim eligibility
substring required; retry on failure. A criterion scoped to another
tumour type, cohort, or study part does not apply.

### 3. Qualifier convention

A word that narrows a bar makes it conditional. `active`,
`uncontrolled`, `untreated`, `symptomatic`, and `within N months` on a
`barred` quote push the label to `barred_with_exception`, which keeps
the trial.

This will **lower the ceiling and the 44.7% headline**. That is
correct behaviour, not a regression. A smaller number that discards
fewer joinable trials is the better system.

Applied to the four yes/no facts after the 12 and the 70 are fixed.

### 4. Scope count (free)

How many of 1,307 trials list more than one cancer type in
`conditions`. How many quotes in the key name a cancer other than
lung, per fact. No gate. This sizes whether a wider basket re-label
is worth it.

### 5. Re-score, in this order

1. Perfect-finder ceiling (was 54.2%).
2. Matching-gated narrowing (was 44.7%).
3. Step 8 lost-joinable (was 6.3%), against the corrected key, using
   existing reads. The 10% gate is unchanged. If the corrected figure
   exceeds 10%, the narrowing figure is withdrawn pending investigation.

Write `*_after_fix.json`. Leave the previous JSON reports in place.
Do not regenerate the Will extra-exclusion sheet.

---

## Spike 2 — clarifying-question agent

**Committed 2026-09-30, before the patient records were extended, before
conditional rules were assigned to questions, and before any recovery
number existed.**

About half the rules are conditional. That is what caps the ceiling at
51.9% instead of 78.2% (the 79.0% figure was the same gap before the
remaining-list fixes). Those points are locked in questions nobody asked.
This step asks them.

Until now, "can't tell" always kept the trial. Once a question is
answered, a rule can discard. This feature trades safety for narrowing.
The wrongly-discarded gate does **not** move.

### Closed vocabulary

Do not generate a fresh question per rule. Assign each conditional rule
to one or more names from the fixed list in `questions_design.json`,
the same way quotes were assigned to six field names. A rule may tag
several names from that list (treated *and* stable four weeks) but
must not invent a 401st wording.

Ask for a **value**, not yes-or-no. Different trials set 2 weeks, 4
weeks, 8 weeks, 3 months on the same condition. The coordinator answers
once; each trial is compared against its own stored threshold. An
answer never settles a rule with a different threshold.

Numeric comparison happens once per question, not once per trial.

### Ranking

Rank per patient. A question only counts on pairs where the condition
is live (the patient's situation actually interacts with the rule).
Brain questions are worthless for a patient with no brain involvement.

Score = how many currently-unsettled live trials list that question.
Do not peek at the oracle answer when ranking.

### Loop

LangGraph, capped at **3 rounds**. Each round: narrow, rank, ask the
current top question, fold the value in. Stop early if the top question
unlocks zero remaining trials.

The simulated coordinator answers from the extended structured record.
Where that record has no value, it returns "don't know", which keeps
the trial.

### Oracle extension (free, before assignment)

Seed **202609303**, in `questions_design.json`. Existing fields on the
20 patients stay unchanged. Only new fields are drawn. Written to
`data/fake_patients_questions.json` and committed before any assignment
or recovery number.

### Gates (must exist before the run)

Current matching-gated narrowing is 43.0%. Current perfect-finder
ceiling is 51.9%. Optimistic ceiling (conditionals treated as if
settled against the patient) is 78.2%. Half of that 26.3-point gap is
13.15 points → **65.0%**. A quarter is 6.6 points → **58.5%**.

| Measure | Gate |
|---|---|
| Perfect-finder narrowing after 3 ranked questions | must reach **65.0%** (half the 51.9→78.2 gap) |
| Same, lower bound | below **58.5%** (a quarter of the gap) → the complexity is not earning itself; report and stop |
| Wrongly discarded | under **10%**. Unchanged. Overrides everything above. Measured as lost-joinable on existing Step 8 reads against the new matching-gated discarded set (questions included). If this exceeds 10%, the recovery figure is a bad trade even if it clears 65%. |
| Ranked 3 questions vs 3 random ones | ranked must **settle at least 1.5× as many trials** (mean across 20 patients). Random draws from questions that have at least one live trial for that patient. If ranked fails this, drop the ranking and ask a fixed order. |

### Also measure, no gate

- Recovery curve at 1, 2, 3, and 5 ranked questions (5 is a probe past the cap).
- Ranked-3 against asking every live question. If ranked-3 gets most of the way, the ranking is doing real work.
- Does round two earn itself? If round 1 captures nearly everything, this is one extra step, not a loop, and the write-up says so. Do not retrofit a LangGraph justification.
- Questions that unlock zero trials, per patient.
- Cost, rounds, and elapsed time per patient.
- Matching-gated narrowing after 3 ranked questions (operational number). No separate recovery gate; the 65% gate is on the perfect-finder arm, which is where the 51.9→78.2 gap lives.

### Do not

- Generate a fresh question per rule.
- Let an answer settle a rule with a different threshold.
- Relax the 10% wrongly-discarded gate for any amount of recovery.
- Regenerate Will's check sheets.
- Start Steps 6 or 7.

---

## Spike 2 — sparse-input asking (recover missing facts)

**Committed 2026-09-30, before the 280 subsets were scored, before any
note was generated, and before any recovery number existed.**

The previous clarifying-question run measured condition-resolution on
complete descriptions. The prize was 5.8 points, and 41% of those
conditions are about the trial's own structure. That test does not
answer what asking is worth when the note is incomplete.

**Retire 79.0% / 78.2% optimistic-as-discard from this project's
vocabulary.** It assumed every conditional resolves as a discard. Many
resolve in the patient's favour and keep the trial. It is not reachable
under any design. Do not use it as a target, a gap, or a ceiling.

This run measures fact recovery. With none of the six facts, matching-
gated narrowing is near zero. With all six it is **43.0%**. That range
is the prize. Age, sex, disease (NSCLC), and setting come free from
registry structure and are always in the note. They are not one of the
six.

Do not resolve conditional rules in this run.

### Configurations

Seed **202609304**. For each of 20 patients and each completeness
k = 0..6, two random subsets of size k from the six facts.
**280 configurations.** Random subsets, not a fixed ladder. Subsets
are in `sparse_configs.json`, committed before generation.

Six facts, checklist order (measured discard power):

1. tumour genetic marker (`driver_mutation`)
2. disease stage
3. previous immunotherapy
4. previous platinum chemotherapy
5. cancer spread to the brain
6. autoimmune disease

### Notes and parse

The large model writes a short coordinator-style note containing only
the subset (plus the free fields). Mechanical leak check: no excluded
fact's value may appear in the note. Reject and regenerate on failure.
Report the leak rate.

Parse each note with the existing Step 4 parser. Do not construct the
fact list by hand. Do not write a Will check sheet.

### Agent vs checklist

The baseline is a **fixed checklist** in the order above, asking every
fact the note does not already contain. The agent must beat it on
*fewer questions for the same narrowing* and *knowing when to stop*.
A checklist of the three highest-value facts is already close to
optimal on order, so the edge is stopping, not a clever permutation.

Right stop: the last question after which the next adds **less than 2
percentage points** of matching-gated narrowing (checklist order among
missing facts). Agent stop is observed increment < 2 points, or no
facts left.

### Gates (must exist before the run)

Matching-gated full-six figure is **43.0%**. Starting narrowing at
level k is measured from the parsed note, not from the intended subset.

| Measure | Gate |
|---|---|
| At levels 0, 1, and 2: matching-gated after 3 checklist-order questions | must reach **half the gap** from that level's starting narrowing to 43.0% |
| Same, lower bound | below **a quarter of the gap** at any of 0–2 → asking isn't earning itself; report and stop |
| Agent vs full 6-question checklist | agent mean narrowing within **2 points** of the checklist, while asking **3 or fewer** questions on average |
| Stopping accuracy | agent stop within one question of the right stop on **≥70%** of the 280 configurations |
| Wrongly discarded | under **10%**. Unchanged. Overrides everything above. Measure fresh on the agent's discarded set using existing Step 8 reads. Last time's 10.4% was condition-resolution; this may differ. |

### Also report, no gate

- Narrowing against completeness k, and against number of questions asked.
- Which facts the agent asks first at each k, vs discard-power order.
- Questions that recovered a fact but changed narrowing by zero.
- Parse quality at low k (listed facts vs intended subset).
- Cost and rounds per configuration.

### Limitations (must appear in the write-up)

Sparsity is synthetic: complete descriptions with facts removed, not
what a coordinator would type. The result is an **upper bound** on
realistic input. The honest fix is real coordinator notes, which this
project does not have.

### Do not

- Use a fixed stripping order.
- Skip the leak check.
- Do any further work on resolving conditional rules.
- Relax the 10% wrongly-discarded gate.
- Quote 79% / 78.2% as a target.
- Start Steps 6 or 7.
- Regenerate Will's check sheets.

---

## Spike 2 — UMLS vocabulary (TREC scoreboard, lung diagnostic)

**Committed 2026-09-30, before any ClinicalTrials.gov live-API
probe, before any UMLS file was installed, and before any concept
was assigned.** Snapshot existence is checked from the TREC track
pages first; live-API rates do not decide usability if that dump
is still downloadable.

The six hand-written names work on lung cancer. The mechanism —
assign both sides to the same fixed vocabulary, then match by exact
identifier — does not depend on those names. It depends on there
being a fixed vocabulary. UMLS is that vocabulary. The lung slice
stays as the diagnostic bench. TREC 2021/2022 is the scoreboard.
They do different jobs. Do not discard the lung slice. Do not start
Steps 6 or 7.

### Task A — TREC retrievability (blocker)

Judgments refer to trials as they existed in 2021–2022. If a large
share cannot be retrieved, the scoreboard is holed.

**Check for an archived snapshot first.** TREC distributed an
April 27, 2021 ClinicalTrials.gov dump. If that collection is still
downloadable, it is the correct corpus and the live-API rate does
not decide usability.

If **no** archived snapshot exists:

| Measure | Gate |
|---|---|
| Unique judged NCT IDs retrievable from the current ClinicalTrials.gov API, **at each relevance level** (0 not relevant, 1 excluded, 2 eligible) | **≥70% at every level**. Below 70% at any level → stop, TREC is not the scoreboard, revert to the lung slice |
| Skew | Report retrievable fraction **per relevance level**, not only overall. Eligible gone / irrelevant remaining is a biased leftover even at a decent overall rate |

Sample at least a few hundred judged identifiers if the snapshot is
absent. Do not start TREC-scale concept assignment until this
section has a result and the cost estimate below is agreed.

### Task B — local UMLS, half a day

Install and query locally. The REST API is rate-limited and too
slow for bulk assignment. Need: phrase → CUI; is-a hierarchy;
drug-to-class (RxNorm / ATC). Restrict by semantic type
(diseases/syndromes, findings, pharmacologic substances, drug
classes, therapeutic procedures, lab results) and by source
(SNOMED CT, RxNorm, MeSH). Report how many concepts survive.
If setup fights past half a day, stop and record it.

### Task C — six constraints (already bitten once)

1. The model never emits a CUI. It extracts a subject phrase;
   UMLS resolves it. Invented identifiers are the same failure as
   invented quotes.
2. One subject concept per rule, not every concept in the sentence.
   Flooding is how brain matching hit 45.5% false pickup.
3. Containment is required on day one. Patient carboplatin vs trial
   platinum-based chemotherapy are different CUIs; is-a is what
   joins them.
4. Direction rule unchanged: same→same is normal comparison;
   patient narrower / trial broader → rule applies; patient broader
   / trial narrower → can't tell, keep; unrelated → keep. Never
   promote or demote either side.
5. Lookup miss → keep the literal phrase and match on the string.
   Report the miss rate. Do not drop the rule.
6. Extraction prompt is disease-agnostic. No hard-coded field list.
   Will rewrites this prompt; coordinate, do not duplicate.

### Task D — lung-slice diagnostic (before TREC)

Same 20 patients, same 1,307 trials, same answer key as the
six-name system. Compare recall and false pickup directly.

Six-name mean recall after the hierarchy fix: **93.9%**.

| Result | Decision |
|---|---|
| Mean recall **≥84%** (within 10 points of 93.9%) | Acceptable. Hand-written names were tuned on this slice. Proceed to TREC |
| Mean recall **below 84%** | Not ready. Diagnose before going near TREC |
| False-pickup rate **above 5%** | Vocabulary restriction too loose. Tighten semantic types and re-run |

Report per fact, not only the mean. Genetic marker was 99.9% and is
the strongest filter; loss there matters most.

Do not start TREC-scale assignment before this gate has a result.

### Cost (bring to Will; do not start)

After Task A reports the judged pool size, estimate assignment cost
at frontier-model rates (~43 rules/trial, gpt-5.4). Options: a
cheap model for assignment, or assign only rules relevant to facts
the patients mention. Do not start TREC-scale assignment until the
estimate is agreed.

### Do not

- Let the model output identifiers.
- Assign more than one subject concept per rule.
- Change the direction rule.
- Discard the lung slice.
- Start Steps 6 or 7.
- Start TREC-scale concept assignment before Task A, Task D, and
  the cost agreement.

---

## Spike 2 — UMLS corrections (2026-09-30, before the lung API run)

**Committed before any UMLS REST call and before any Metathesaurus
download.** The brief is not a wholesale swap of the six-name matcher.

### Do not download the full Metathesaurus unless smaller options fail

Order: (1) scispaCy bundled subset — only if it has concept is-a;
(2) UMLS REST API for the lung-slice gate; (3) standalone RxNorm +
MeSH if the API test passes and we need a local index; (4) SNOMED CT
only if those two are insufficient; (5) full Metathesaurus +
MetamorphoSys last. External disk is fine for raw files. Query a
small SQLite index on the internal drive, not the external disk.

### scispaCy check (do this first)

If the bundled KB has no concept-to-concept is-a, it cannot do
containment and is unused. The Semantic Network type tree is not a
substitute. Do not install it as a hierarchy.

### Gene symbols stay as they are

Do **not** put `driver_mutation` through UMLS. It is 99.9% recall on
plain gene-symbol / closed-name matching and is the strongest filter.
UMLS coverage of specific variants (EGFR L858R, ALK fusion, KRAS G12C)
is thin. Trading the best component for the weakest is forbidden.
UMLS is for diseases, comorbidities, drugs and drug classes, and lab
tests — the parts a hand-written list cannot enumerate.

### Lung-slice gate still holds, via the API

Same 20 patients, 1,307 trials, same answer key. Mean recall ≥84%
(within 10 points of 93.9%). False pickup ≤5%. Report per fact.
Markers reported from the existing matcher, not from UMLS.

A few thousand lookups. No bulk download. Lookup miss → keep the
literal phrase and match on the string (degrade to current behaviour;
do not drop the rule). Report the miss rate.

### TREC assignment is not a frontier-model bill

Do not spend ~$5,100 (judged pool) or ~$40,000 (snapshot) on gpt-5.4.
Cheap hosted (~$1,500) is still too much. Shrinking to 30 of 125
topics harms the scoreboard. Keyword-filter-then-assign is
chicken-and-egg. **Self-hosted batch on rented GPU, once, then
tear down** is the affordable path and is the resume gap that now
has a real job. Do not start that job until the lung API gate
clears. Cost it then.

### Still do not

- Let the model emit CUIs.
- Assign more than one subject per rule.
- Change the direction rule.
- Replace gene-symbol matching.
- Start Steps 6 or 7.
- Start TREC-scale assignment.

---

## Spike 2 — UMLS corrections (2026-09-30, before the lung API run)

**Committed before any UMLS REST call and before any Metathesaurus
download.** The brief is not a wholesale swap of the six-name matcher.

### Do not download the full Metathesaurus unless smaller options fail

Order: (1) scispaCy bundled subset — only if it has concept is-a;
(2) UMLS REST API for the lung-slice gate; (3) standalone RxNorm +
MeSH if the API test passes and we need a local index; (4) SNOMED CT
only if those two are insufficient; (5) full Metathesaurus +
MetamorphoSys last. External disk is fine for raw files. Query a
small SQLite index on the internal drive, not the external disk.

### scispaCy check (do this first)

If the bundled KB has no concept-to-concept is-a, it cannot do
containment and is unused. The Semantic Network type tree is not a
substitute. Do not install it as a hierarchy.

### Gene symbols stay as they are

Do **not** put `driver_mutation` through UMLS. It is 99.9% recall on
plain gene-symbol / closed-name matching and is the strongest filter.
UMLS coverage of specific variants (EGFR L858R, ALK fusion, KRAS G12C)
is thin. Trading the best component for the weakest is forbidden.
UMLS is for diseases, comorbidities, drugs and drug classes, and lab
tests — the parts a hand-written list cannot enumerate.

### Lung-slice gate still holds, via the API

Same 20 patients, 1,307 trials, same answer key. Mean recall ≥84%
(within 10 points of 93.9%). False pickup ≤5%. Report per fact.
Markers reported from the existing matcher, not from UMLS.

A few thousand lookups. No bulk download. Lookup miss → keep the
literal phrase and match on the string (degrade to current behaviour;
do not drop the rule). Report the miss rate.

### TREC assignment is not a frontier-model bill

Do not spend ~$5,100 (judged pool) or ~$40,000 (snapshot) on gpt-5.4.
Cheap hosted (~$1,500) is still too much. Shrinking to 30 of 125
topics harms the scoreboard. Keyword-filter-then-assign is
chicken-and-egg. **Self-hosted batch on rented GPU, once, then
tear down** is the affordable path and is the resume gap that now
has a real job. Do not start that job until the lung API gate
clears. Cost it then.

### Still do not

- Let the model emit CUIs.
- Assign more than one subject per rule.
- Change the direction rule.
- Replace gene-symbol matching.
- Start Steps 6 or 7.
- Start TREC-scale assignment.





---

## Spike 2 — UMLS coverage of Step 1 phrases (before lookup)

**Committed 2026-09-30, before any of the 5,578 Step 1 phrases
were looked up.** No Metathesaurus download. No new extraction.
No TREC. Gene-symbol / marker matching stays as it is.

Phrases are the short `concept` strings in `data/step1_concepts.jsonl`
(the 5,578 distinct noun phrases), not eligibility sentences.

### Gates

| Measure | Gate |
|---|---|
| Coverage by **occurrence** | below **60%** → UMLS cannot supply this corpus's vocabulary. Report and stop. Six-name approach stays. |
| Coverage by occurrence | **60–85%** → partial. Usable with literal-phrase fallback. Write-up says what share falls back. |
| Resolution precision (automatable: input phrase vs returned canonical name) | below **90%** of resolved phrases → resolution too noisy to match on, regardless of coverage |

Also report, no gate: coverage of **distinct** phrases; both numbers
broken down by the existing Step 1 categories. Biomarker/mutation
coverage is reported but is **not** a reason to replace gene-symbol
matching.

Disagreements from the automatable check are listed for Claude to
review. Do not send them to Will.

### Do not

- Download the Metathesaurus.
- Start TREC assignment.
- Put `biomarker_or_mutation` through UMLS as a replacement for
  gene-symbol matching.
- Start Steps 6 or 7.

---

## Spike 2 — TREC hybrid retrieval, stages 1–2 only (before any run)

**Committed 2026-09-30, before keyword generation, before MedCPT
encoding, before any recall number.** This replaces the six-name
narrowing measurement as the thing under test. The six-name code
stays on disk as a measured negative. Do not call it from this run.

Stages 1 and 2 only: an LLM reads the **patient note** and writes
search keywords; each keyword is retrieved with BM25 and with
MedCPT; the lists are fused with reciprocal rank fusion
(`1 / (60 + rank)`). No reader. No reranker. No ranking stage.
No LLM call sees trial text.

Collection is the **judged pool** for that year, same as TrialGPT
and TrialMatchAI. Unjudged counts as irrelevant. 2021 and 2022 use
the 27 April 2021 ClinicalTrials.gov dump. 2023 uses a later dump
— confirm the date from the track page and write it down; do not
assume it is the 2021 dump.

MedCPT (PubMed search logs) is out of domain here. TrialGPT used
it anyway. Note the mismatch. Cross-encoder is downloaded and not
run (that is a later stage).

### Reproduction checks (implementation, not research)

If either fails, the run is wrong. Fix it before reporting.

| Check | If it fails |
|---|---|
| Hybrid beats BM25 alone **and** MedCPT alone | Fusion is misimplemented |
| LLM-generated keywords beat the raw patient note | The keyword prompt is bad; rewrite it |

### Research gate

| Measure | Gate |
|---|---|
| Recall of **eligible** trials (label 2) at **6% of collection** | **≥85%** is the same league as the papers. **Below 70%** → stop and diagnose. Two papers independently exceed 90%. |

Also report, no gate: recall of eligible and of relevant (labels 1+2)
at depths 10, 20, 50, 100, 200, 500, and as a share of collection
size, each year. Ablations: raw note vs keywords; BM25 vs MedCPT vs
hybrid; MedCPT vs `text-embedding-3-small`.

### Do not

- Use the six-name vocabulary, closed-name matching, containment
  hierarchy, or the fact-extraction prompt.
- Build the reader, the reranker, or the ranking stage.
- Send trial text to a hosted LLM.
- Start Steps 6 or 7.
- Delete the narrowing record.

---

## Spike 2 — TREC condition-field baseline (2021/2022 only)

**Committed 2026-09-30, before any condition-field match rate or
matched-depth recall.** 2023 stays stopped. This asks whether the
free ClinicalTrials.gov `conditions` field already does the
retrieval step's job. Keyword hybrid reached 91.6% / 91.4%
eligible recall at 6% of the judged pool; BM25 alone was 87.8% /
88.5%; recall at 10 was 5.7% / 7.4%. Eligible trials are nearly
by definition trials for the patient's condition. The same field
already cut the live registry from 604,566 trials to 1,308 in one
query at the start of this project.

### Years and collection

2021 and 2022 only. Same judged pool, same 27 April 2021 dump,
same already-generated keywords (`data/trec/keywords.json`). Do
not touch 2023. Do not regenerate keywords. Do not use the
six-name vocabulary or anything from the narrowing work.

### Disease term

The **first keyword** in that list. The keyword prompt asked for
terms most important first; that first item is treated as the
patient's condition. Later keywords (symptoms, drugs, procedures)
are not used for the filter. They are used only for the
keyword-retrieval comparison and the combination arm, same as the
previous hybrid run.

### Matching strengths

The field is inconsistently populated (the same cancer appears as
`NSCLC`, `Lung Neoplasms`, and `Carcinoma, Non-Small-Cell Lung`).

- **Strict** — lowercase, punctuation stripped to spaces; any
  `conditions` string equals the disease term.
- **Loose** — strict, or substring either way, or token overlap
  after dropping `{the,a,an,of,to,for,on,in,and,or,with,by,from,
  into,as,at,is,are}` and tokens shorter than 2 characters.

No embeddings. No ranking on the filter arms. A trial with an
empty `conditions` field cannot match.

### What is reported

Per patient and in aggregate, for each matching strength:

- trials retained (count and share of the judged pool)
- share of eligible trials (label 2) among those retained

A filter does not rank. Compare at **matched depth**: if the
filter retains *k* trials for that patient, report keyword-hybrid
eligible recall at depth *k* next to the filter's eligible
recall. Aggregate is the mean of those per-patient pairs.

Also one combination, nearly free: **loose filter first**, then
the same keyword hybrid (BM25 + MedCPT, RRF) inside what
survives. Report that combination's eligible recall at the same
depths as the previous hybrid run, including 6% of the original
collection.

Wilson 95% intervals on any sample under 200. Do not invent an
overall accuracy. Never say a patient qualifies.

### Empty or unmatchable

Report, before reading the recall numbers as a product claim:

- share of pool trials whose `conditions` field is empty
- share of eligible trials whose `conditions` field is empty
- share of patients for whom the filter retains zero trials

An empty or unmatchable field is the failure mode that makes the
field unusable regardless of recall.

### Thresholds — read after the run

Compare the filter's eligible recall to keyword-hybrid recall at
matched depth. Read from **loose** as the operational filter
(strict is reported so the synonym problem is visible). Apply the
same table per year.

| Result | Reading |
|---|---|
| Condition filter alone comes within **3 points** of retrieval at matched depth | Retrieval is not earning itself. Say so plainly; it is a database query with extra steps |
| Filter is more than **10 points** worse | Retrieval is doing real work beyond disease matching. Report which patients the filter loses and why |
| Anything between | Report both, and report the filter's retained-trial count, since a cheaper filter at similar recall is still the better first stage |

### Do not

- Touch 2023.
- Build the reranker. This decides what it sits on top of.
- Use the six-name vocabulary or anything from the narrowing work.
- Start Steps 6 or 7.
- Send trial text to a hosted LLM.

---

## Spike 2 — TREC reranking the shortlist (2021/2022 only)

**Committed 2026-09-30, before any rerank score or Recall@10.**
2023 stays stopped. Reranking reorders the already-retrieved
shortlist. It discards nothing. Nothing can be lost.

Keyword hybrid put 91.6% / 91.4% of eligible trials in 6% of the
pool (1,570 / 1,595 slots) and only 5.7% / 7.4% in the top 10.
A coordinator reading ten sees almost nothing. This step asks
whether a second model can move eligible trials to the top.

### Years, shortlist, and what is not being built

2021 and 2022 only. Same judged pool, same 27 April 2021 dump,
same keywords, same keyword-hybrid first stage (BM25 + MedCPT,
RRF, `RETRIEVE_N=1000` per keyword). The shortlist is the top
6% of that ranking per year. Do not regenerate keywords. Do not
touch 2023. Do not use the six-name vocabulary. This is not the
reader: polarity and conditional rules stay criterion-by-criterion
with a quote. Never say a patient qualifies. Do not invent an
overall accuracy.

### Arms

| Arm | What it is |
|---|---|
| 1 | `ncbi/MedCPT-Cross-Encoder`, already downloaded. Score each shortlisted trial against the patient, sort by score |
| 2a | `cross-encoder/ms-marco-MiniLM-L-12-v2` — a general-purpose reranker, not medical. The generic embedding beat MedCPT at retrieval (91.8% vs 88.0%); do not assume the medical cross-encoder wins here |
| 2b | `gpt-4o-mini` scoring topical relevance, not eligibility. 2021 only, top 200 of the shortlist only |
| 3 | No reranking: the current keyword-hybrid order |

Arm 2 is two alternatives because the brief asked for at least
one, named a language-model depth cap, and flagged the medical-
vs-generic question as open. Cross-encoder arms rerank the full
shortlist. The language-model arm cannot; compare every arm at
depth 200 so that comparison is matched. Report the cross-encoders
at both depths.

### Query and document text

Query side, both, on the cross-encoder arms: the raw patient note,
and the already-generated summary plus keyword list joined as one
string. One query string per patient, not a per-keyword pass (that
would be 25× the GPU bill). The raw note was the worst retrieval
query (58%) because the disease term was diluted into one vector.
A cross-encoder reads both texts together, so dilution may not
apply. That is an open question, not a preference.

Document side: start with the same truncation retrieval used —
one `[title, body]` pair, 512 tokens. A typical trial is 3,581
characters, so the tail of eligibility is dropped. Write that
down. If GPU time remains after the truncated pass, also run
chunk-and-take-max-score (overlapping 512-token windows, title
prefixed, keep the max). If that pass is skipped, say so.

The language-model arm uses the raw note (the open query-shape
question) and the same truncated trial text. Score is a 0–3
topical-relevance integer. The prompt must not ask whether the
patient is eligible.

### Depths and metrics

Recall of eligible trials (label 2) at 10, 20, 50, 100, 200 —
the headline. NDCG@10 using labels 0 / 1 / 2 (unjudged = 0).
Precision at 10 for eligible (label 2), and also for relevant
(labels 1+2). Wilson 95% intervals on any sample under 200.

The 0.81 NDCG figure in the literature is on 2023, which is not
run. Do not treat this NDCG as a comparison to that number.

### Thresholds — read after the run

Read from **2021** Recall@10 of eligible trials, best arm. 5.7%
is that year's unre-ranked top 10.

| Measure | Gate |
|---|---|
| Recall at 10, best arm, 2021 | must at least triple from 5.7%, so **above 17%**. Below doubling (**11.4%**) → reranking is not earning itself; report and stop |
| Recall at the full shortlist depth after reranking that whole shortlist | must be unchanged at **91.6% / 91.4%**. Reordering cannot change recall at full depth — if it moves, there is a bug |
| Which arm wins | **no gate.** Report it. The medical specialist losing again is a real possibility and worth stating either way |

2022 Recall@10 is reported the same way (baseline 7.4%; double =
14.8%; triple = 22.2%) but the written stop is the 2021 row.

### Honest limitation, written before scores exist

MedCPT's cross-encoder was trained to judge whether a PubMed
article answers a search query — not whether a patient is eligible
for a trial. MS MARCO MiniLM was trained on web search. The cheap
model is scoring topical relevance. Expect better topical
ordering, not eligibility reasoning.

### Do not

- Touch 2023.
- Use the six-name vocabulary or anything from the narrowing work.
- Start Steps 6 or 7.
- Let the language-model arm claim eligibility.
- Leave a paid GPU running after scores are copied off. Terminate
  via the API, not shutdown.

---

## Spike 2 — what is in the TREC shortlist (2021/2022 only)

**Committed 2026-10-01, before any shortlist composition count.**
2023 stays stopped. Nobody has looked inside the 1,570. This
diagnoses it. Tasks 2 (weighted fusion) and 3 (section-aware
ranking) wait on the result. They are not run from this commit.

### What is being counted

Same keyword-hybrid shortlist already on disk
(`data/trec/rerank_shortlists.json`): 2021 depth 1,570, 2022
depth 1,595. TREC labels, per patient:

| Bucket | Meaning |
|---|---|
| Eligible | label 2 |
| Excluded | label 1 — right condition, trips an exclusion |
| Judged not relevant | label 0 for this patient |
| Unjudged | in the year's judged pool, no label for this patient |

Unjudged-for-this-patient is not "outside the collection." The
collection is the year's judged pool. A trial judged for another
patient, and not this one, is unjudged here and counted as
irrelevant in the published retrieval numbers.

Also report, free:

- Retrieval rate of excluded trials at 6% of collection, next to
  eligible recall at the same depth. Same rate means fusion does
  not distinguish "right disease, cannot join" from "can join."
- Whether judged-0 and unjudged rows in the shortlist cluster on
  particular keywords. Measured from each keyword's BM25 top-1000
  (the same per-keyword lists fusion used). No new LLM call. No
  MedCPT re-encode.

Wilson 95% intervals on any sample under 200. Do not invent an
overall accuracy. Never say a patient qualifies. Nothing is
discarded.

### The estimate under test

2021 qrels are 67.7% / 16.8% / 15.5% (0 / 1 / 2). If excluded
trials are retrieved at the same ~91.6% rate as eligible, a
typical shortlist would hold about **144** disease-relevant
trials (label 1+2) and about **91%** junk (label 0 + unjudged).
That is arithmetic from pool proportions, not a measurement.

### Decision — read after the count, before any fusion or
section work

| Result | Decision |
|---|---|
| Junk (label 0 + unjudged) is the **majority** of the shortlist, and disease-relevant (1+2) is in the neighbourhood of the 144 / 9% guess | Retrieval is imprecise. There is cheap headroom. Commit gates for tasks 2 and 3, then run them |
| Excluded (label 1) is the **majority**, or disease-relevant (1+2) is the majority | Retrieval did its job. Further filtering is reading. **Do not run** tasks 2 or 3 |
| Anything else, including a mix that is not junk-majority | The estimate was wrong. Say so. Follow the diagnosis rather than the written tasks. Do not run 2 or 3 just because they are on the page |

### Do not

- Touch 2023.
- Run weighted fusion or section ranking from this commit.
- Discard any trial.
- Build a reader or a trained ranker.
- Use the six-name vocabulary.
- Start Steps 6 or 7.

---

## Spike 2 — weighted fusion and section ranking (2021/2022 only)

**Committed 2026-10-01, before any new ranking score.** Task 1
(`697d808`) found the 144 / 91% estimate holds: 2021 mean
shortlist is 140 disease-relevant (8.9%) and 1,430 junk (91.1%).
Excluded recall at 6% is 92.1%, next to eligible 91.6%. Junk is
mostly unjudged-for-this-patient, and it clusters on generic
keywords (`hypertension`, `nausea`, `pain`, `genetic disorder`).
That is the premise for these two cheap reorderings. 2023 stays
stopped.

### What is being changed

The official arms **reorder the existing 1,570 / 1,595**. They
do not drop a trial and they do not pull a new set. Full-shortlist
eligible recall must stay **91.6% / 91.4%**. If it moves, there
is a bug.

A full-collection IDF-RRF is run as a **probe only**, because
freezing the set may be the wrong framing if the junk arrived
through fusion. The probe is allowed to pick a different 1,570.
If its eligible recall at 6% **falls**, it is rejected. If it
rises, say that the written invariance was leaving headroom. The
probe is not the gate.

Nothing is discarded. No reader. No trained ranker. No six-name
vocabulary. No trial text to a hosted LLM.

### Arms

| Arm | What it does |
|---|---|
| Baseline | Current unweighted RRF order |
| 2a | RRF, each keyword's lists (BM25 and MedCPT) weighted by the **rarest-token IDF** of that keyword. `idf = log((N+1)/(df+1))`. Unweighted RRF is the published TrialGPT fusion; this is a departure and must be labelled as such if it helps |
| 2b | Sum of BM25 scores across keywords, not ranks. Uses the retrieval scores rather than RRF |
| 3a | Unweighted RRF, then a **multiplier** on a keyword's contribution when that keyword matches the exclusion section only (0.25). Inclusion-only unchanged. Both-sections 0.75. Unsplit: no penalty. Down-rank, never drop |
| 3b | Unweighted RRF, **tie-break**: at equal fusion score, inclusion-only hits before exclusion-only |
| 2+3 | 2a weights plus 3a's exclusion multiplier |

Section split reuses `split_sections` from `scripts/keyword_section_check.py`.

### Thresholds

Headline is eligible recall at 10 and 20. 2021 baseline: **5.7%**
and **10.7%**. Read from the best official (reorder) arm, 2021.

| Measure | Gate |
|---|---|
| Recall at 10, 2021 | must beat 5.7%. Below 5.7% → the change hurts; stop. Under **8.7%** (+3 points) → not a pipeline change; report and do not replace unweighted RRF. **11.4%** would be the doubling reranking missed |
| Recall at 20, 2021 | reported. Same reading at +3 points (13.7%) and at double (21.4%), no separate stop |
| Full-shortlist recall, official arms | **91.6% / 91.4%** unchanged |
| Which arm wins | no gate. Report it. If 3 does nothing, the lists are not the cheap signal. If 2 does nothing, generic keywords are not the cheap signal |

Wilson 95% intervals on any sample under 200. Do not invent an
overall accuracy. Never say a patient qualifies.

### Do not

- Touch 2023.
- Discard a trial.
- Build a reader or a trained ranker.
- Use the six-name vocabulary.
- Start Steps 6 or 7.

---

## Spike 2 — cheap topical pass on the shortlist (2021/2022 only)

**Committed 2026-10-01, before any keep/drop score.** 2023 stays
stopped. The 1,570-trial shortlist is 91% junk. Reading it all is
about $11 per patient; reading the ~140 disease-relevant trials
is about $1. This pass asks a weaker question than eligibility:
**could this trial conceivably be about this patient's problem?**
Uncertainty keeps the trial. It is not the reader. Mini failing
the reader's 10% wrongly-discarded gate does not transfer here
and is not a reason to skip the hosted arm.

### Sample, then winner

30 patients, seed **20261001**, 15 from 2021 and 15 from 2022,
drawn from the existing shortlist topics and written to
`data/trec/cheap_pass_sample.json` before any model sees a pair.
The drawn topic ids are listed below so they sit in this commit
even though `data/` is gitignored. Compare candidates on that
sample. Run **one** winner on all 125 topics only if a candidate
clears the gates below on the sample. Wilson 95% intervals (n=30).

Sample topic ids (drawn with seed 20261001, still before any score):

- 2021: 13, 18, 21, 23, 25, 27, 30, 31, 36, 37, 47, 51, 55, 70, 74
- 2022: 10, 20, 21, 22, 23, 24, 25, 28, 29, 32, 35, 37, 41, 42, 50

### Query and document text

Query is the already-generated **one-sentence summary** of the
main problems, not the full keyword list. Generic keywords
(`hypertension`, `abdominal pain`) are how the junk got in;
replaying them would ask the pass to keep that junk.

Document text, two official options, full criteria not the
default:

| Name | What the pass sees |
|---|---|
| `title_cond` | title + conditions field |
| `title_cond_slice` | those plus the first 800 characters of eligibility |
| `title_body_512` | retrieval's 512-token `[title, body]` truncation — **subset only**, to see what extra context buys. Not used at full scale unless it is the only way a candidate clears |

### Candidates

| # | What | Cost story |
|---|---|---|
| 0 | Lexical: first keyword, loose match on title+conditions (the free conditions-field test, now as a filter on the 1570). Fourth candidate because the diagnosis says the junk is other diseases | free |
| 1 | `ncbi/MedCPT-Cross-Encoder`. Keep if logit **> 0**, committed before seeing scores. A sweep is reported and is not the gate. Rerank failure does not apply: that was ordering by eligibility |
| 2 | `Qwen/Qwen2.5-7B-Instruct` (7–8B class) on a rented GPU. Keep / drop / unsure; unsure keeps. Shut the card down via the API. Qwen3's thinking mode would spend GPU on a keep/drop token; this is the same size class without that |
| 3 | `gpt-4o-mini`, same keep / drop / unsure rule | hosted, known price |

The cheap-reader failure (10.8% wrongly discarded) was
per-criterion eligibility. This is topical. Run arm 3.

### What is counted

On the existing shortlist only. Disease-relevant = TREC labels
**1 or 2**. Junk = label 0 or unjudged for this patient.

- **Recall** = share of disease-relevant shortlist trials kept
- **Retention** = share of the 1,570 / 1,595 kept
- Also report eligible-only (label 2) recall, and the product
  with retrieval's 91.6% / 91.4% as end-to-end eligible recall
  **among trials this pass could have seen**. Do not invent an
  overall accuracy. Never say a patient qualifies.

Cost and wall-clock per patient, including GPU time.

### Thresholds — why these numbers

The project's wrongly-discarded line is 10%. Losing 10% of
disease-relevant trials in this pass leaves end-to-end eligible
recall 91.6% × 90% ≈ **82%**. That is the most this pass may
eat of the retrieval win. Losing 20% leaves ≈73% and has given
back too much of first-stage recall.

Keeping more than half the shortlist does not pay for a pipeline
slot: 785 trials is still about $5.50 of reading.

| Measure | Gate |
|---|---|
| Disease-relevant recall, on the sample | **≥90%**. Below **80%** → that candidate is rejected (stops being an acceptable trade). 80–90% is mixed; do not ship it as the default pass |
| Retention | **≤50%** of the shortlist. If a candidate cannot cut at least half, it is not earning its place even at 90% recall |
| Winner | among sample candidates that clear both bars, the one with the **lowest retention**, then the lowest cost. If none clear both, **do not** run full scale; say so |
| Full-scale, if run | same two bars, now on all 125 topics. Eligible recall at 6% of collection after this pass is reported; it will be below 91.6% / 91.4% by construction wherever recall is not 100%, and that is not a bug |

### Do not

- Touch 2023.
- Start the per-criterion reader.
- Feed full eligibility text by default.
- Discard trials anywhere except this pass.
- Use the six-name vocabulary.
- Leave a paid GPU running. Terminate via the API.

---

## Spike 2 — does a reordering stage earn its place? (2021/2022 only)

**Committed 2026-10-01, before any 0–3 topical or eligibility score.**
2023 stays stopped. The shortlist stays 1,570 / 1,595. Nothing is
discarded. This replaces the earlier assumption that reranking is a
stage worth building. Run 1 (topical score) and Run 2 (eligibility
score) are in competition. Run 3 (frontier vs Qwen vs human) is
**not** started from this commit.

The original rerank gates (Recall@10 ≥ 17%) stay in this file as
committed history. They are not the gates for this run. That target
asked for a share of a long tail. This run asks a cost question:
which ordering gets more eligible trials into a fixed reading budget.

### Why the binary delete is the wrong gate

"If Run 2 beats Run 1, delete the topical stage" has one number
deciding one of two futures. Three outcomes are live, and the third
is the one this project keeps missing:

| Outcome | What it means |
|---|---|
| Run 2 wins the reader budget **and** does not lose the first page | Delete topical reordering. The eligibility score is the ranker. TrialGPT's shape. |
| Run 2 cannot rank (no better than the unreordered shortlist at the reader budget) | A single cheap eligibility score is the wrong instrument. Do not delete topical reordering on this evidence. The architecture question becomes whether only a per-criterion read can rank on eligibility. That finding outranks the horse race. |
| Split: one arm wins the first page, the other wins the reader budget | Do not delete. They have different jobs. Write that down. |

A second confound is committed here so it cannot be explained away
after the numbers exist. Run 2 reads the **full** eligibility
section. Run 1 reads title+conditions, or those plus 800 characters
of eligibility. If Run 2 wins, that is not automatically "the
eligibility question won." It may be "more text won." There is no
third arm (topical prompt + full criteria) in this budget. The
write-up may claim the question won only if Run 2 also beats Run 1's
slice arm by enough that length alone is an unlikely explanation.

A continuous score is judged at depths 10 and 20, where ties inside
a coarse bucket fall back to search order. It does **not** get
credit for a depth-200 or depth-500 win. Those depths are already
won or lost by block separation.

### Years, shortlist, models, prompts

2021 and 2022, all 125 patients, same keyword-hybrid shortlist
already on disk. Do not regenerate keywords. Do not touch 2023.
Do not re-run MS MARCO MiniLM. Full-shortlist eligible recall must
stay **91.6% / 91.4%**. If it moves, there is a bug.

| Arm | Model | Question | Document |
|---|---|---|---|
| baseline | none | fused search order | — |
| qwen_topical_digit / `_cont` | Qwen2.5-7B-Instruct | topical 0–3, **same wording** as `scripts/trec_rerank_llm.py` (not eligibility). Output format is a single digit so token probabilities can be read; the scale definitions are not rewritten | `title_cond`, and `title_cond_slice` (800 chars) |
| mini_full | gpt-4o-mini | same topical prompt as the original mini arm, JSON batches | same document as that arm: `trial_article[:1200]`. Reuse the existing 2021 top-200 scores; score the rest of the shortlist and all of 2022 |
| qwen_elig_digit / `_cont` | Qwen2.5-7B-Instruct | eligibility 0–3 against the stated criteria. New instructions. Uncertainty lands in the middle of the scale (use 2, not 0 or 3). No written reasoning. No per-criterion loop | title + conditions + **full** eligibility |

Query is the raw patient note for every language-model arm. Digit
and continuous are separate eval arms. Continuous = expected value
of the four answer tokens from the softmax of those four logits.

If Run 2's GPU time looks like a bad overrun, cut **patients**, not
shortlist depth. Depth is the thing being tested. Prefer a 30-patient
full-depth sample (seed **20261001**, the cheap-pass sample) over a
shallow pass on 125.

### What is counted

Headline is **equivalent depth**, as a multiple of the baseline's
own equivalent depth at the same N. The baseline row is calibration,
not a result. Flat stretches in the baseline recall curve make every
arm look worse than it is if you read against N.

Equivalent depth at N: reading N trials in this order finds as many
eligible (label 2) trials as reading how many in the fused order.
Report the mean of per-patient ratios, and the mean of per-patient
raw depths. Both years.

Also report, not as the delete-gate:

- Eligible recall at 10, 20, 50, 100, 200, 500, and full shortlist
- Precision at 10 and 20 (macro mean of per-patient), to slot into
  `docs/trec_precision.md`
- Patients with ≥10 eligible in the top 20 (the product bar)
- Machine time and dollars per arm

Accuracy of the eligibility digit against TREC labels is optional
and **must not veto** a ranking result. A model that is
systematically too harsh, in the same direction, ranks fine.

Wilson 95% intervals on any sample under 200. Do not invent an
overall accuracy. Never say a patient qualifies.

### Thresholds — read after Run 1 and Run 2, not after a preview

Two reading budgets, committed because they are different jobs:

- **Page budget N=20.** What a coordinator sees. Also P@20.
- **Reader budget N=200.** What you would send to a per-criterion
  reader if that reader still existed. N=500 is reported as the deep
  check. It is not the delete-gate: the Qwen-bucket preview already
  won there from three-way block separation, and a continuous score
  is not expected to move it.

**Run 1 earns a topical-reordering slot** if the best topical arm
(Qwen digit, Qwen continuous, or mini; either document) is
**≥ 1.20×** baseline equivalent depth at 200 on 2021, and is not
below **1.10×** on 2022. Below **1.10×** on 2021: topical scoring
does not earn a stage. 1.20× is "about 17% fewer trials to read for
the same eligible catch." The 15-patient preview was 1.65–1.79× at
200; if 125 patients land under 1.20×, the sample overstated it.

**Continuous vs digit** is decided at N=20 only. Continuous wins
that bet if it beats the matching digit arm's P@20 by **≥ 2
points** (0.40 eligible in 20). No credit at 200 or 500.

**Mini vs Qwen, topical, same depth.** If mini's equivalent depth
at 200 is **≥ 1.15×** Qwen's best topical arm, the paid model still
wins the stage. If Qwen is within 10% of mini at 200 (ratio
**≥ 0.90**), Qwen is the default topical ranker because it is free
at inference.

**Run 2 vs Run 1 — three outcomes, not two.** Compare Run 2's best
arm (digit or continuous) to Run 1's best topical arm.

| Result | Decision |
|---|---|
| Run 2's equivalent-depth multiple at 200 is **≥** Run 1's on 2021; 2022 is not more than **5% relative** worse than Run 1; and P@20 is not worse than Run 1 by more than **3 points** | Delete the topical stage. Eligibility score is the ranker |
| Run 2's equivalent-depth multiple at 200 is **≤ 1.05×** baseline on 2021 | Single-score eligibility cannot rank. Do not delete topical reordering on this evidence. Say that a cheap eligibility score may be the wrong instrument, and that the per-criterion read is now the open design, not a luxury for the last page |
| Split: Run 2 wins 200 (or 500) and Run 1 wins P@20 by more than 3 points, or the reverse | Do not delete. They have different jobs |
| Tie at 200 (within 5% relative) | Keep the cheaper inference (both Qwen arms are free). Report the tie. Do not invent a preference for keeping the stage |

"Beats" at 200 is the higher mean equivalent-depth multiple. There
is no extra 1.15× margin between Run 1 and Run 2. That would bake
in a preference for keeping a stage this run is allowed to delete.

If the two years disagree on the 200 ranking (2021 deletes, 2022
does not, or the reverse), do not delete. Report the split.

### Run 3 is a separate go/no-go

Not started from this commit. Budget about $14. Combined with
Runs 1 and 2 that is about $36, above the $25 ask-first line.
Check in after Runs 1 and 2. Suggested sample if it runs: 30
patients (seed **20261001**), each patient's top 200 in the **Run 2
eligibility order**, ~6,000 pairs. Frontier model scores the same
eligibility question. Both models are measured against NIST labels
(71,226 judgements), not against each other.

Gates for Run 3, written now so they cannot be fitted to the gap:

- Fine-tuning Qwen is worth considering only if the frontier
  advantage would change the pipeline: **≥ 8 more patients** over
  the 10-in-20 bar than Qwen, **or** equivalent depth at 200
  **≥ 1.20×** Qwen's on that sample.
- Label-1 vs label-2 separation is reported as AUROC (and as recall
  of label 2 among judged 1+2 at the score threshold that keeps
  half of them). If **both** models are **≤ 0.60 AUROC** on that
  distinction, the ceiling is low; do not fine-tune Qwen to close a
  gap neither model can use. Retrieval is already blind here
  (excluded 92.1% vs eligible 91.6%).
- Agreement with humans (accuracy / QWK on judged pairs) is
  reported and does not veto a ranking result.

Optional last, only if Runs 1 and 2 finish under budget: MedCPT-CE
chunk-and-max in half precision on a better card than the A10.
About 30 minutes and $1. Drop it without ceremony if anything
above overruns. Do not hold Runs 1–2 for it.

### Cost and machine

Runs 1 and 2 together are about $32 (Qwen ~$16, mini ~$10, Run 2
the rest). That is the authorized envelope for this commit. Prefer
H100 then A100 when the options are within a few dollars. Stop and
ask if a run overruns its estimate by tens of dollars. Copy scores
off the rented machine before any terminate. Terminate via the API,
not shutdown. `PYTHONIOENCODING=utf-8` and `encoding="utf-8"` on
every file read and write.

### Do not

- Touch 2023.
- Re-run MS MARCO MiniLM.
- Discard a trial. The shortlist stays 1,570 / 1,595.
- Start the per-criterion reader.
- Start Run 3 from this commit.
- Credit a continuous score with a depth-500 win.
- Use the six-name vocabulary.
- Leave a paid GPU running. Terminate via the API.
- Say a patient qualifies.

---

## Spike 2 — eligibility prompt v2 on the 30-patient sample (2021/2022 only)

**Committed 2026-10-02, before any v2 eligibility score.**
2023 stays stopped. Same shortlist, nothing discarded. This is a
prompt-and-output-shape change on the **same 30 patients** (seed
**20261001**) as the first eligibility arm. It is not a matched
model comparison: the question, the labels, and the written check
all changed. The thing we are allowed to ask is whether **true
positives** went up — joinable trials (human label 2) higher in
the list, especially on the first page.

### What changed

Same model (`Qwen/Qwen2.5-7B-Instruct`), same full eligibility
text, same raw patient note. New instructions: read the whole
block; hunt timing and specifics; written CHECK then a verdict
word. Verdict is `ineligible` / `eligible` / `unsure`. Unsure
**only** when a fact the trial's stated criteria require is
missing from the note. If the fact is in the note, it must pick
eligible or ineligible.

Ranking number is **P(eligible)** from the three verdict tokens
after `VERDICT:`, not a typed decimal and not a 0–3 digit. The
written word is reported for accuracy; it does not veto ranking.

Do not reuse the old topical prompt. Do not reuse the old
"if unsure, choose 2" line.

### What is counted

Same 30 patients, full shortlist depth. Both years.

- Eligible hits and macro P@10 / P@20 vs the stored
  `elig_full_cont` arm on **this same sample**
- Equivalent depth at 20, 200, 500 (baseline calibration row)
- 10-in-20 count
- Verdict mix: eligible / ineligible / unsure
- Among judged pairs: share of label 2 called eligible (true
  positive rate of the word); share of label 1 called eligible;
  label-1-vs-2 AUROC on P(eligible)
- Machine time and dollars

Accuracy of the word does not veto a ranking lift. Wilson on
n=30.

### Thresholds — read after this run

Compare to stored `qwen_elig_full_cont` on the same 30
(2021 P@20 **48.7%**, 2022 P@20 **58.0%**; 2021 10-in-20 **7/15**).

| Result | Decision |
|---|---|
| 2021 P@20 is **≥ 2 points** above 48.7% (so **≥ 50.7%**), and 2022 is not more than 2 points worse than 58.0% | The prompt helped the first page. Keep v2 as the eligibility prompt |
| 2021 P@20 is **≤ 48.7%** and 10-in-20 does not rise | The prompt did not help true positives on the page. Do not replace v1 on this evidence |
| Split (one year up, one down, or only 10-in-20 moves) | Report. Do not replace v1 |
| Unsure is **> 50%** of judged disease-relevant (label 1+2) pairs | The model is still dumping. Say so even if P@20 rises |
| P(eligible) AUROC on judged 1 vs 2 is **≥ 0.80** (v1 continuous was **0.745**) | Say loudly: the 1-vs-2 gap moved |

Equivalent depth at 200 is reported. It is not the replace-gate
for this run: we are asking about true positives on the page.

### Cost

Written CHECK on 30 × ~1,570 is slower than a single digit.
Budget about 4–10 hours on H100/A100, about $8–20. Prefer H100
then A100. Stop and ask if it looks like tens of dollars over
that. Copy scores off; terminate via the API.

### Do not

- Touch 2023.
- Discard a trial.
- Start Run 3 from this commit.
- Start the per-criterion reader.
- Leave a paid GPU running. Terminate via the API.
- Say a patient qualifies.

---

## Spike 2 — eligibility prompt v2 on the 30-patient sample (2021/2022 only)

**Committed 2026-10-02, before any v2 eligibility score.**
2023 stays stopped. Same shortlist, nothing discarded. This is a
prompt-and-output-shape change on the **same 30 patients** (seed
**20261001**) as the first eligibility arm. It is not a matched
model comparison: the question, the labels, and the written check
all changed. The thing we are allowed to ask is whether **true
positives** went up — joinable trials (human label 2) higher in
the list, especially on the first page.

### What changed

Same model (`Qwen/Qwen2.5-7B-Instruct`), same full eligibility
text, same raw patient note. New instructions: read the whole
block; hunt timing and specifics; written CHECK then a verdict
word. Verdict is `ineligible` / `eligible` / `unsure`. Unsure
**only** when a fact the trial's stated criteria require is
missing from the note. If the fact is in the note, it must pick
eligible or ineligible.

Ranking number is **P(eligible)** from the three verdict tokens
after `VERDICT:`, not a typed decimal and not a 0–3 digit. The
written word is reported for accuracy; it does not veto ranking.

Do not reuse the old topical prompt. Do not reuse the old
"if unsure, choose 2" line.

### What is counted

Same 30 patients, full shortlist depth. Both years.

- Eligible hits and macro P@10 / P@20 vs the stored
  `elig_full_cont` arm on **this same sample**
- Equivalent depth at 20, 200, 500 (baseline calibration row)
- 10-in-20 count
- Verdict mix: eligible / ineligible / unsure
- Among judged pairs: share of label 2 called eligible (true
  positive rate of the word); share of label 1 called eligible;
  label-1-vs-2 AUROC on P(eligible)
- Machine time and dollars

Accuracy of the word does not veto a ranking lift. Wilson on
n=30.

### Thresholds — read after this run

Compare to stored `qwen_elig_full_cont` on the same 30
(2021 P@20 **48.7%**, 2022 P@20 **58.0%**; 2021 10-in-20 **7/15**).

| Result | Decision |
|---|---|
| 2021 P@20 is **≥ 2 points** above 48.7% (so **≥ 50.7%**), and 2022 is not more than 2 points worse than 58.0% | The prompt helped the first page. Keep v2 as the eligibility prompt |
| 2021 P@20 is **≤ 48.7%** and 10-in-20 does not rise | The prompt did not help true positives on the page. Do not replace v1 on this evidence |
| Split (one year up, one down, or only 10-in-20 moves) | Report. Do not replace v1 |
| Unsure is **> 50%** of judged disease-relevant (label 1+2) pairs | The model is still dumping. Say so even if P@20 rises |
| P(eligible) AUROC on judged 1 vs 2 is **≥ 0.80** (v1 continuous was **0.745**) | Say loudly: the 1-vs-2 gap moved |

Equivalent depth at 200 is reported. It is not the replace-gate
for this run: we are asking about true positives on the page.

### Cost

Written CHECK on 30 × ~1,570 is slower than a single digit.
Budget about 4–10 hours on H100/A100, about $8–20. Prefer H100
then A100. Stop and ask if it looks like tens of dollars over
that. Copy scores off; terminate via the API.

### Do not

- Touch 2023.
- Discard a trial.
- Start Run 3 from this commit.
- Start the per-criterion reader.
- Leave a paid GPU running. Terminate via the API.
- Say a patient qualifies.

---

## Adapter vs topical slice as the default ranker — 2022, 50 patients

**Committed before any full-shortlist adapter score.** No pass/fail
thresholds. The write-up answers replace / layer / stay out from the
numbers and the cost, not from a pre-set gate.

### Adapter

Seed **20261007**. Median of the three 1e-5 seeds (0.770, 0.773,
0.793) and closest to the mean 0.779. Not the 0.793 seed. Config:
\scripts/trec_lora_rank_config.json\.

### Patients

All 50 from 2022. Not the 30-patient sample (15 of those are 2021
tuning patients). 2023 is not used. Shortlist stays 1,595. Nothing
discarded.

### Arms

- Fused shortlist order (baseline, calibration)
- Topical slice continuous (current default; already on disk)
- Adapter eligibility, continuous expected digit
- Adapter eligibility, digit (reported, not the headline score)
- Topical first, then adapter on the top N, for N in 50, 100, 200,
  300, 500

### What is reported

P@10 and P@20; equivalent depth at 20, 200, 500 as a multiple of
the baseline's own equivalent depth at the same N; patients with
at least 10 joinable trials in the top 20; full-shortlist recall;
patient-resampled intervals on P@10 and P@20; machine time and
dollars.

A rate probe on patients 1 and 2 is scored first. The full 50
starts only if the projection stays near or under about \.

The system does not say a patient qualifies.

---

## Rule-by-rule reader — 2022, top 25, no pass/fail

**Committed before any reader score exists.** We want to know how
it does. A number invented beforehand adds nothing.

### What is locked

- Patients: all 50 from 2022. Not 2021. Not 2023.
- Trials: the top 25 of the topical-slice continuous ranking, the
  cutoff that already replicated. 1,250 pairs.
- Model: Qwen2.5-7B-Instruct, self-hosted. No frontier model.
- Prompt, schema, retries, rule split, and both aggregation rules:
  `scripts/trec_reader_config.json`, `reader/`.
- Pair IDs: `scripts/trec_reader_pairs.json`.

### What is reported

- Agreement with TREC labels under **any_hard_fail** and
  **net_balance**. If they disagree on the headline, that is the
  finding.
- Joinable-versus-excluded AUROC on the same 1-versus-2 basis as
  the 0.779 scorer.
- Quote check: raw flag rate, bucket shares (A–E), and D+E as the
  honest fabrication rate. Earlier work treated above **5%** as a
  support problem and measured **1.3%**. That is the reference,
  not a new gate.
- A 50-to-100 row sample for Will to hand-check.
- Cost.

No per-rule accuracy. TREC labels are per trial. TrialGPT's 87.3%
used paid clinicians on 1,015 judgements. There are none here.

### Probe

Patients 1 and 2, 25 trials each. Project the full 50. Stop and
ask if it heads past about $25. Copy reads off. Terminate via
the API.

The system does not say a patient qualifies.

### Amendment — 4 Oct 2026, after the 13/50 probe

**13 of 50 is not accuracy.** It is the share of trials whose
JSON passed the validator on the first probe, while the model
was returning empty quotes. Do not score that run against TREC
labels. Do not quote it as model performance.

**The guardrail worked.** Thirty-seven replies were rejected
rather than stored as judgements. That belongs in the method as
a positive.

Diagnosis, from the stored raw text, no GPU:

- Not `MAX_NEW = 2048`. No failure sat at or near 2,048 output
  tokens. The longest failure was 1,390 tokens. Failures were
  not concentrated in high-rule-count trials. One 45-rule trial
  passed. One 2-rule trial failed.
- 27 of 37 last replies failed because `met` or `not_met` had an
  empty quote (145 `not_met`, 16 `met`). Five had an empty
  `quote_source`. Four were broken JSON. One invented a
  `rule_id`. The model treated a silent note as `not_met`.
- All 37 used three greedy retries. The retry pasted the previous
  JSON. Same failure, wasted generations.

Two rules that lived in the same place and are not the same:

1. **Quote guardrail (never loosen).** If a quote is offered, it
   must actually exist in the named source. That is what measures
   fabrication. `verify_quote.py` is unchanged.
2. **Output contract (this was wrong).** Requiring every `met` and
   `not_met` to carry a quote is unsatisfiable for absence
   judgements. A silent note has no span to cite.

That contract is the same principle CONTEXT.md already locked:
a filter may only eliminate on confident evidence; silence is a
pass. `not_met` means the note positively fails the rule, and
that always has a quote. A rule the note is silent about is
`not_enough_information`.

Amendment:

- Prompt restates that rule. This is consistency with a settled
  project rule, not a workaround.
- If the model still returns `met` or `not_met` with no quote,
  convert that row to `not_enough_information`, flag
  `coerced_to_nei`, and count it. Do not retry that case.
- One targeted repair remains, only for broken JSON or leftover
  schema errors (unknown `rule_id`, quoted row with no
  `quote_source`). It names only the failed rule IDs and does
  not paste the previous reply.
- No rule-batching. That was the truncation design. This was
  not truncation.
- No grammar-constrained decoding. The worker is
  `transformers.generate`, not vLLM.
- `MAX_NEW` stays 2,048.

Write-up note: the output contract required evidence for every
negative judgement, but judgements grounded in absence have no
span to cite, so the contract was unsatisfiable for a whole
class of cases.

Re-probe patients 1 and 2 on the same 50 trials. If the
projection is under about $25, run the 1,250. If not, stop.

The system does not say a patient qualifies.

### Amendment — 4 Oct 2026, compatible-unless-contradicted

The 0.59 AUROC used an aggregation stricter than the TREC 2022
assessors. They judged compatibility, not proof: a sufficient
amount of information may suggest eligibility, and the notes are
deliberately 5 to 10 sentences. **Committed before any new
combination of the stored per-rule verdicts.** No new model
calls. No pass/fail.

Third rule, reported beside the first two:

- **compatible_unless_contradicted.** Excluded if any exclusion
  fires or any inclusion is positively failed. Otherwise
  compatible. Unsettled rules get no vote. Silence never
  excludes.
- Unsplit rules: `u_not` is a contradiction, `u_met` is a
  confirmation, same as the first two rules. Five trials (0.4%)
  had exclusion language inside an unsplit block.
- Score, locked: one contradiction puts the trial at most 0.05
  (divided by the number of contradictions; confirms add a
  little inside that band). No contradiction: 0.50 + 0.50 ×
  (confirms / n). `not_enough_information` is zero either way.

Report AUROC with a patient interval, the verdict counts,
precision with any agreement (compatible is a weaker claim),
and the share of rules a TREC note can settle.

The system does not say a patient qualifies.

### Amendment — 4 Oct 2026, GPT-5.4 vs 0.779 on the same pairs

**Committed before any new GPT call.** No pass/fail.

Question: on the same 2022 judged joinable-versus-excluded
pairs as the 0.779 adapter mean, what is GPT-5.4's AUROC?

- Pairs: `scripts/trec_lora_eval_pairs.json` `test_2022`,
  copied not redrawn. 6,249 pairs, 2,635 excluded, 3,614
  joinable, all 50 patients.
- Prompt: `v1_ELIG_SYSTEM_DIGIT` only. Not the TREC-label
  prompt.
- Score: expected digit from token logprobs. Fallback: the
  typed digit.
- Reuse stored v1 scores from the 411-pair run when the
  topic and trial match.
- Interval: patient bootstrap, 5,000 draws, seed 20261004.
- Spend cap $20. Expected $12–15. Stop and ask if the cap
  is hit.
- Not 2021, not 2023, not a first-page score, not overall
  accuracy.

Compare beside 0.779 (mean of seeds 20261003 / 06 / 07) and
untrained Qwen 0.749. This is not a decision that a patient
qualifies.

