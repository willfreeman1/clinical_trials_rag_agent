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

**Committed 2026-09-30, before the 40-row sheet was written.** Free. No
API. Will checks English, not medicine.

### Sample

40 rows, seed **20260930**, from `data/answer_key.jsonl` only (the two
traits the original key was built on). Least-sure labels first:

| Bucket | How many |
|---|---:|
| Immunotherapy `unclear` | all 12 |
| Brain `unclear` | all 7 |
| Brain `both_classifications` | all 7 |
| Immunotherapy `both_classifications` | 8 of 22 |
| Immunotherapy `barred_with_exception` | 3 of 87 |
| Brain `barred_with_exception` | 3 of 417 |

This is not a random sample of the key. It is biased toward the labels
the model itself was least sure about, which is the point.

### What Will marks

agree / disagree / needs medical knowledge. The last is unresolvable in
this project. Report all three. The gate uses only the checkable ones
(agree + disagree).

### Threshold

| Measure | Gate |
|---|---|
| Disagree / (agree + disagree) | above **25%** → rework the labelling instructions and redo the key before quoting anything that depends on it |

The share marked needs-medical-knowledge is reported, not gated. That is
the part of the key nobody here can verify.


