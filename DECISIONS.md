# Decisions

Running log. Each entry: the date, the decision, what was considered, why, and what
evidence would reverse it.

---

## 2026-09-28 — Spike 2 Step 1: the corpus is not coverable by a fixed column schema

**Decision: continue. This is a retrieval project, not an extraction project.**

### What was run

`scripts/step1_concepts.py` then `scripts/step1_analyze.py`. GPT-5.4 read 300 trials
drawn from the 1,308 with seed 20260928 (ids in `data/step1_sample_ids.json`) and listed
every distinct clinical fact each trial's criteria gate on, at the two granularity
levels fixed in `THRESHOLDS.md` before the run. 300 of 300 succeeded, no failures.

- **13,033 facts, 43.4 per trial.** Far more than expected.
- **5,578 distinct concept strings** after lowercase-and-punctuation normalisation.
- Cost **$6.72**, against an estimate of about $3.

### The numbers

Share of all gating criteria covered by the most common concepts, at five
normalisations. Concept strings were embedded and near-duplicates merged greedily in
frequency order, so the commonest phrasing becomes each cluster's representative.

| Normalisation | Clusters | Top 10 | Top 20 | **Top 40** | Top 80 | Top 160 |
|---|---:|---:|---:|---:|---:|---:|
| Exact merge only | 5,578 | 9.3% | 14.7% | **21.7%** | 29.2% | 37.2% |
| Cosine 0.90 | 4,700 | 9.5% | 15.0% | **22.5%** | 30.6% | 39.9% |
| Cosine 0.85 | 4,026 | 9.8% | 15.6% | **24.0%** | 32.8% | 43.0% |
| Cosine 0.80 | 3,324 | 11.5% | 17.5% | **26.2%** | 36.4% | 47.9% |
| Cosine 0.75 | 2,631 | 13.5% | 20.3% | **30.0%** | 41.9% | 54.4% |

Discriminating categories only (dropping consent, pregnancy testing, demographics and
other boilerplate every trial carries): 9,288 facts, 31.0 per trial, **top 40 = 24.6%**.

**Trials whose entire gating set falls inside the top 40 concepts: 0 of 300.** Mean
share of a single trial's gating set inside the top 40: 25.6%.

### Against the committed threshold

`THRESHOLDS.md` set: ≥90% → extraction project, stop; 70–90% → continue, case mixed;
<70% → retrieval project. The measured value is **24%**, and the gate is cleared on
every normalisation variant by a wide margin.

### Two disclosures

1. **The nominated curve was the wrong one, and it did not matter.** The threshold said
   to read the decision from the exact-merge curve. That normalisation turned out to be
   nearly useless — it collapsed only 11 of 5,589 raw strings, so it measured phrasing
   variety as much as fact variety. `measurable disease` and `measurable lesion`,
   `informed consent` and `written informed consent`, `non-small cell lung cancer` and
   `nsclc` all survived as separate entries. The embedding merges were run as the
   threshold document also specified, and every variant lands in a 22–30% band, so the
   decision is unchanged. Recording the flaw rather than editing the threshold.
2. **Cost overran the estimate by 2.2×** ($6.72 against ~$3), because trials gate on
   43 facts each rather than the handful assumed. Still inside the $25 limit. Any future
   per-trial extraction should be budgeted from the 43-facts figure.

Minor: the model emitted a category outside the closed list 3 times in 13,033
(`prior_supportive_care`). Left as-is; 0.02% and it does not affect any curve.

### What this settles, and what it does not

**Settled: the strong extraction claim is dead.** You cannot pre-extract every trial
into a fixed set of columns and answer questions by filtering that table. No trial in
the sample — not one — has its gating set covered by even the 40 commonest concepts, and
the tail does not close: 160 concepts still reach only 43%. This is the claim spike 1's
report recommended, and it is now measured to be false.

**Not settled: whether the *filters* need the tail.** This measurement counts facts
**trials gate on**. A filter only has to cover the facts **a question raises**, and a
patient description raises maybe six, which are likely drawn from the common head
(age, stage, histology, mutation, performance status, prior therapy, a lab value — all
inside the top 40). The remaining trial-side criteria get resolved by the model reading
the survivors, not by a filter. So the frequency-weighted proxy named in `THRESHOLDS.md`
is weaker than that document claimed, and this result does not by itself prove that
query-time filter generation is necessary.

That gap is what Step 1b answers, by counting the oncology topics in the TREC 2021–2022
sets and measuring which facts real patient descriptions actually raise.

**Consistent with the current architecture.** Pre-extracted columns as a cache for
recurring facts, query-time filters for anything without a column, and a frontier model
reading whatever survives. The result rules out dropping the reading step, which is what
that design already assumes.

### What would reverse this

Step 1b finding that real patient descriptions draw almost entirely from the top 40
concepts. That would mean columns can supply every filter a question needs, the tail
measured here never gets exercised, and the extraction reading of spike 1 is right after
all for the filtering stage even though it is wrong for the corpus as a whole.

---

## 2026-09-29 — Spike 2 Step 2: the ceiling clears the floor but misses the target

**Decision: continue, and the ceiling is the headline of the write-up, not the model.**

### What was run

`scripts/step2_ceiling.py` — arithmetic over `data/answer_key.jsonl` and
`data/fake_patients_draw.json`. No API calls, no cost. Assumes a flawless filter and builds
nothing: for each of the 20 invented patients and each of the two labelled traits, it uses the
answer key as a perfect oracle and counts how many of the 1,308 trials could be thrown out, then
takes the union across traits.

Thresholds were committed in `68559b7`, before this ran.

### The numbers

| | Result |
|---|---|
| Mean per-trait share thrown out | **11.4%** (range 3.6% to 19.8%) |
| Two traits combined, mean | **22.0%** (range 16.4% to 27.1%) |
| Same, if conditional refusals could be resolved | **37.7%** |
| Projection to six traits, if independent | **51.7%** |
| Trials stating the brain rule conditionally | **417 of 1,308 — 31.9%** |
| Trials stating the immunotherapy rule conditionally | 87 of 1,308 — 6.7% |

Per-trait detail: a patient who has had immunotherapy trips 19.8% of trials; one who has not
trips 12.8%. A patient whose cancer has spread to the brain trips 9.5%; one whose has not trips
3.6%.

### Against the committed threshold

The threshold was: below 8.2% per trait → stop; 8.2% to 18.2% → continue but the ceiling is the
story; above 18.2% → the target is reachable.

**Measured 11.4%, which lands in the middle band.** Six traits project to 51.7% — comfortably
above the 40% floor, well short of the 70% target that would make the full cancer registry
cheap. At 50% elimination, cost per patient at cancer scope falls from about $10 to about $5.
Real, but not transformative.

### One disclosure: my pre-registered reasoning was wrong in a way that favours the project

The committed threshold document argued that because restrictive trials tend to be restrictive on
several counts at once, the same trial would be thrown out by more than one trait, so the
independent projection would be an **upper** bound and the real six-trait figure lower.

Measured, the opposite is true. Observed overlap was **230 trial-slots against 279 predicted by
independence — a ratio of 0.82.** The two traits co-occur *less* than chance, so the 51.7%
projection is if anything slightly conservative. Recording this rather than editing the
threshold. It does not change the decision, but it does mean the argument I used to justify the
threshold was not sound, and the write-up should not repeat it.

### The measurement's own limits

- **Only four distinct outcomes exist.** Both traits are yes-or-no and the answer key is fixed, so
  there are exactly 2 × 2 = 4 possible results and the 20 patients produced only four distinct
  union values (16.4%, 21.4%, 23.1%, 27.1%). For *this* measurement, 20 patients carried no more
  information than 4 would. The apparent per-patient spread is the balanced design showing
  through, not a finding. More patients will matter for later steps; they did not matter here.
- **The strongest trait is not in this measurement.** The two labelled traits are mid-strength.
  Step 1 found that one particular genetic-marker requirement is mentioned by roughly a third of
  trials, so for a patient lacking that marker it could throw out on its own more than twice what
  either measured trait does. Until Step 5 labels it, 11.4% is a floor on the mean, not an
  estimate.
- Inherits any errors in the answer key, which no human has checked beyond four corrections.

### The most useful finding, which was not the headline number

**Nearly a third of all trials — 417 of 1,308 — state their brain-metastases rule conditionally**,
and those cannot be thrown out from a patient description no matter how good any model is. That
is the ceiling made concrete, and it is a property of how the rules are written rather than of any
model.

But the same fact is a product idea. Resolving conditional refusals lifts two-trait elimination
from 22.0% to **37.7%** — nearly double. Those conditions are mostly about whether the brain
lesions were treated and have been stable, which is one or two follow-up questions to the
coordinator. **So "ask two clarifying questions" is worth roughly as much as adding several more
traits.** That belongs in the design, and it is the kind of finding worth reporting whatever
happens to the rest of the project.

### What would reverse this

Step 5 labelling the genetic-marker trait and finding it throws out far more than 11.4%, which
would push the six-trait projection toward or past 70% and make the cheap step clearly worth
building. That is the single most informative thing left to measure, and it argues for
prioritising the marker trait over the three plain yes-or-no ones.

---

## 2026-09-29 — Environment: Python 3.11 venv, not Anaconda 3.9

**Decision: create `.venv` on the Python 3.11.9 already on PATH, and do not install into
Anaconda base.**

The plan checked this machine on 2026-09-29 and found Anaconda 3.9.12 as the base interpreter.
That is still there, but it is not what `python` resolves to: PATH python is 3.11.9, and 3.13.x
is also installed. Several libraries Step 7 needs have dropped 3.9. Putting the spike on 3.11
now avoids rebuilding the environment later, and 3.11 is new enough for current
`transformers` / `torch` wheels without being 3.13, whose wheels are still patchy.

Pinned in `requirements.txt`: `numpy==2.1.3` only, until Step 7. Verified inside the venv:
Python 3.11.9, numpy 2.1.3.

### What would reverse this

Step 7's chosen starting model or trainer refusing to install on 3.11. Then recreate the venv
on whichever version actually works, and log it.

---

## 2026-09-29 — Spike 2 Step 3: matching misses the traps; it does not mix up different traits

**Decision: continue.** The cheap step will miss differently-worded rules, which makes the
shortlist bigger rather than wrong. Matching is not good enough to be a load-bearing filter
on its own. That is what the committed gate said to do with a correct-link rate under 85%.

Thresholds were committed in `6c1cf87`, before this ran. Cost: one embedding batch of 17
short phrases, about **$0.000001**. MeSH 2025 ASCII downloaded free (2026 ASCII was
discontinued). UMLS was not used; it needs a licence this machine does not have.

### What was run

`scripts/step3_dump_clusters.py` then `scripts/step3_match.py`, against the gold pairs in
`scripts/step3_gold.json`. Three methods: embeddings at cosine 0.85, MeSH, and MeSH-then-
embeddings. The wording groups Step 1 never saved are now in `data/step3_wording_groups.json`.

### The numbers, at the committed operating point (cosine 0.85)

Wilson 95% intervals. The plan requires a range on any sample under about 200.
At n=29 / n=25 almost nothing is distinguishable: 3 of 29 and 0 of 25 overlap.

| Method | Same-trait (of 29) | 95% CI | Different-trait (of 25) | 95% CI |
|---|---:|---|---:|---|
| Embeddings | 6.9% (2) | 1.9–22.0% | 4.0% (1) | 0.7–19.5% |
| MeSH | 3.5% (1) | 0.6–17.2% | 0% (0) | 0–13.3% |
| Combined | **10.3% (3)** | **3.6–26.4%** | **4.0% (1)** | **0.7–19.5%** |

Against the gate: wrong-link ≤ 5% **cleared on the point estimate**; the interval
runs to 20%, so that clearance is not established. Correct-link ≥ 85% **not
cleared**, even at the top of the interval.

**Retracted: "best method = MeSH."** MeSH linked 1 of 29 correctly and 0 of 25
wrongly. It wins a wrong-link ranking by barely matching anything. A method that
never matches never makes a mistake. Never select on the error gate alone;
require a minimum recall first. Combined is the method the design specified, and
it is the row to quote. No method here cleared a usable recall.

### What actually linked, and what did not

The two embedding hits at 0.85 were English inflection and abbreviation: `brain metastasis` /
`brain metastases` (cosine 0.95) and `cns metastases` / `central nervous system metastases`
(0.85). The one MeSH hit was `rheumatoid arthritis` / `autoimmune disease`, which is the
hierarchy doing the one job we wanted it for.

Everything the invented patients were built to test **missed**:

| Pair | Cosine | MeSH |
|---|---:|---|
| carbo/pemetrexed ↔ platinum-based chemotherapy | 0.53 | unknown |
| carboplatin ↔ platinum-based chemotherapy | 0.63 | unknown |
| pembrolizumab ↔ immunotherapy | 0.47 | no (both terms found, not connected) |
| pembrolizumab ↔ checkpoint inhibitor | 0.34 | unknown (`checkpoint inhibitor` is not a heading; `immune checkpoint inhibitors` is) |
| PD-1 agent ↔ prior immunotherapy | 0.38 | unknown |
| cerebral metastases ↔ brain metastases | 0.80 | unknown |
| CNS metastases ↔ brain metastases | 0.76 | unknown |
| ILD ↔ interstitial lung disease | 0.40 | unknown |
| nsclc ↔ non-small cell lung cancer | 0.64 | unknown (abbreviation not in MeSH as `nsclc`) |

The one wrong link at 0.85 is the trap Step 1 already documented: **`brain metastases` /
`bone metastases` at cosine 0.8608.** Combined inherits it, because MeSH could not resolve
`bone metastases` and so fell through to embeddings. Step 1's cosine-0.85 merge still joins
those two; that is now written down in the wording-groups file rather than being an anecdote.

### The curve, so this is not an artefact of 0.85

No point on the curve reaches 85% correct-link. Loosening embeddings *does* pick up a few
near-paraphrases (`cerebral` / `brain` mets at 0.80), and it blows the wrong-link gate on
the way:

| Cosine | Embeddings correct | Embeddings wrong |
|---:|---:|---:|
| 0.75 | 24% | **16%** |
| 0.80 | 14% | **12%** |
| 0.85 | 7% | 4% |
| 0.90 | 3% | 0% |

Drug-to-class never appears on this curve. Those pairs sit at 0.34–0.63. There is no
threshold that catches `pembrolizumab` as immunotherapy without first catching a pile of
things that are not.

### Two disclosures about the dictionary arm

1. **Exact lookup, not a failure to download.** MeSH loaded 947,905 terms including
   supplementary drug names. `pembrolizumab`, `carboplatin`, `immunotherapy`, `brain
   metastases` all resolved. The hierarchy still did not treat pembrolizumab as
   immunotherapy, and `carbo` in `carbo/pemetrexed` did not look up so the slash-split
   only found pemetrexed. A looser lookup (token-subset of headings) was not run after
   seeing this; it would be a different method.
2. **MeSH is the easier substitute, not "a medical dictionary."** It returned
   `unknown` on 21 of 29 same-trait pairs. Drug-to-family hierarchies are what UMLS
   has and MeSH largely lacks. The record is: the freely downloadable substitute was
   tested and failed. It is not: a medical dictionary does not help. UMLS needs a
   licence this machine does not have; that remains an open option, not a result.

### What this means for the cheap step

A binary "are these two phrases the same trait" matcher cannot be how candidate lines are
found. Word-index overlap will still catch a trial that uses the same words the patient
used. It will not catch a trial that says `platinum-based chemotherapy` when the patient
said `carbo/pemetrexed`. That is a recall hole, and the committed reading of that hole is:
the shortlist gets bigger, later stages spend more, the system does not throw out a
joinable trial *by this mechanism*. The bone/brain mix-up *is* that mechanism, and at 0.85
it is sitting just over the line.

### What would reverse this

A matcher that links drug-to-class without linking brain-to-bone — for example UMLS with
the actual hierarchy, or a short curated synonym list checked against sampled hits, not
invented from memory. Either would have to be measured on this same gold file, which stays
frozen.

---

## 2026-09-29 — Spike 2 Step 4: the big model can take the descriptions apart

**Decision: continue.** Script-flagged fails were 18 of 20; that is the alias
matcher, not the model. Reading the English against the list already written
under each patient, **2 of 20** fail the four counted mistakes. The gate is
more than 2 → revise once. 2 is not more than 2, so the instructions stay as
they were. Will should still skim `data/step4_check.md` — the plan assigned
him that reading, and a different call on the two borderline patients would
flip the gate.

Thresholds were committed in `4597f41`, before this ran. Cost **$0.13**
(9,859 in, 7,082 out).

### What was run

`scripts/step4_parse.py` — `gpt-5.4`, the 20 descriptions from
`data/fake_patients.md`, output shape as in the plan. Check sheet:
`data/step4_check.md`.

### Against the four counted mistakes

Counted by reading, not by the script. The script required exact name aliases
and treated "cancer type = adenocarcinoma" as a missed histology; it is not.

| Patient | Call | Why |
|---|---|---|
| P02 | **miss** | Description says metastatic adenocarcinoma. No disease-stage row; metastatic was folded into a yes_no named "metastatic adenocarcinoma". |
| P03 | **miss** | Description says "excellent performance status". No performance-status row at all. |
| The other 18 | pass | Every inventory trait the description actually states is present, with the right kind for numbers vs categories. |

Direction or a number in the name: **none**. Number labelled as a category or
the reverse: **none**. True inventions (a trait the description does not
state): **none**. Extra rows that *are* in the description — steroids, SRS,
methotrexate, frailty, ART — were flagged by the script as inventions and are
not.

Negative traps held: P07 "never had immunotherapy — declined it" and P11
"neither platinum nor a checkpoint agent" both came back `does_not_have`, not
`has`.

Drug-to-class, which Step 3 could not do: `carbo/pemetrexed` → previous
platinum chemotherapy (P01), `pembrolizumab` / `a PD-1 agent` / `durvalumab` /
`nivolumab` / `atezolizumab` → previous immunotherapy, `CNS metastases` and
`cerebral metastases` → cancer spread to the brain. The big model does this
when it sees the whole sentence. Embeddings and MeSH, looking at the two
phrases alone, do not.

### One shape issue that is not a counted fail, and should be said

On several patients a one_of_many trait came back as yes_no: "adenocarcinoma
/ has" instead of "histology / value / adenocarcinoma" (P04, P06, P16), and
"ALK rearrangement / has" instead of "genetic marker / value / ALK fusion"
(P10). That is not "a number labelled as a category", so it does not trip the
committed fourth mistake. It *does* lose the exclusivity the cheap step needs
for markers. If Will counts it as a fail, P10 (and maybe P03's "targetable
alteration / does_not_have") push the set over 2 of 20 and the instructions
get one revision. Left as 2 of 20 pending that call.

### What would reverse this

Will reading the check sheet and counting more than 2 of 20. Then one prompt
revision, focused on forcing one_of_many for histology and markers, and a
second run of the same 20.

---

## 2026-09-29 — Spike 2 Step 4 revised once: marker kind is fixed, 4 of 20 fail

**Decision: continue.** Will counted P02, P03, and P10 — three of twenty, over
the threshold of two. The prompt was revised once, as the plan permits
(committed in `0031555` before this run). Re-read of all 20: **4 of 20** fail.
The post-revision gate is more than 4 → stop. 4 is not more than 4.

Cost **$0.17** (16,859 in, 8,632 out).

### What the revision changed

Two instruction fixes, nothing else:

1. One-of-many fields use fixed names: `tumour genetic marker`, `disease stage`,
   `histology`, `sex`. The specific value goes in the value slot.
2. The tumour genetic marker is always `one_of_many`, never `yes_no`. "No
   marker found" is the value `none`. One worked example of each.

### Against the four counted mistakes, by reading

The load-bearing fail from the review is gone. P03 is now
`tumour genetic marker / one_of_many / none`. P10 is now
`tumour genetic marker / one_of_many / ALK fusion`. Every patient who stated a
marker, or stated that none was found, used that shape.

| Patient | Call | Why |
|---|---|---|
| P02 | **miss** | Still no disease-stage row. "Metastatic adenocarcinoma" is in the description. |
| P09 | **direction in name** | Extra row `untreated brain lesion`. |
| P10 | **direction in name** | Extra row `brain metastases treated`. Marker kind is now correct. |
| P18 | **direction in name** | Extra row `brain metastases untreated`. |
| The other 16 | pass | Fixed names used; marker kind correct; no invented traits; numbers stayed numbers. |

The three extra-row fails are the treated/untreated detail the threshold
document said was optional to record. Recording it is fine; putting
"untreated" in the *name* is not.

Negative traps still hold (P07, P11, P13, P17, P19, P20). Drug-to-class still
holds. P12 now lifts rheumatoid arthritis to `autoimmune condition`.

### Disclosed, not counted

Five patients stated an age in shorthand (`67F`, `53M`, …) and omitted an age
row (P01, P02, P03, P07, P12). Pass 1 did not count those as fails, and age is
a number trait stage 2 ignores. If they are counted, the set goes over 4 and
the plan says stop. Left uncounted, and said here so that call can be reversed
without re-running.

The script's 16 "fails" are mostly that alias bug (`age` matching the letters
inside `disease stage`) plus extras that are in the description (steroids,
frailty, ART). Reading is the count.

### What would reverse this

Counting the age omissions, or counting any further shape problem on a
re-read, so the set is more than 4 of 20. Then the plan says stop.

---

## 2026-09-29 — Spike 2 Step 5a: the marker trait is the strong filter, and it justifies continuing

**Decision: the cheap step is still worth building. Do not label the other
three traits until Will approves the ~$10.** The marker trait alone throws out
**23.9%** of trials on average — above the 18.2% per-trait figure that would
make six traits reach 70% if they were all this strong. Combined with the two
already-labelled traits, a *perfect* filter — one that finds every rule —
throws out **39.9%** of the corpus (the 40% floor, with three traits not six).
The six-trait projection moves from 51.7% to **63.8%**, which is toward 70%
and is the plan's test for whether the remaining labelling is justified.

**These are best-case ceilings, not predictions.** They assume every rule is
found. How good simply reading everything is has not been measured; that is
Step 8. Do not quote 39.9% or 63.8% as what the system would do.

Thresholds for this decision were already in the Step 2 section, plus the
Step 5a section committed in `af4c473` before labelling. Cost **$6.36**
(1,662,093 in, 146,776 out). Estimate was ~$4.

### What was run

`scripts/step5_label_markers.py` on all 1,308 trials, then
`scripts/step2_ceiling.py` re-run with three traits. New labels:
`data/answer_key_markers.jsonl`. Existing two-trait key not touched.

| | |
|---|---|
| Labelled | 1,308 / 1,308, none failed |
| Quote-check flagged | 151 (11.5%; the two-trait key was 353 / 27%) |
| Trials that require some marker | **442 (33.8%)** — matches Step 1's "roughly a third" |
| Trials that refuse some marker | 382 |
| No marker rule (silence, a pass) | 610 |
| Rule is conditional | 206 (15.7%) |

### Ceiling with three traits

| | Two-trait partial | Three-trait re-run |
|---|---:|---:|
| Mean per-trait throw-out | 11.4% | **15.6%** |
| Marker trait alone | — | **23.9%** (16.7%–29.4%) |
| Union across measured traits | 22.0% | **39.9%** (34.5%–44.4%) |
| Same, if conditionals resolved | 37.7% | 57.0% |
| Projection to six independent traits | 51.7% | **63.8%** |

Against the committed band: 15.6% is still between 8.2% and 18.2%, so the
ceiling remains the headline, not the model. The marker did the job this step
existed for: it is more than twice either of the first two traits, and it
nearly doubles the union.

By patient marker, pessimistic throw-out on that trait alone:

| Patient marker | Share thrown out |
|---|---:|
| ALK fusion (P10) | 29.4% |
| no driver (13 patients) | 24.6% |
| EGFR L858R / exon 19 deletion | 22.2% |
| KRAS G12C (P19) | 16.7% |

A patient with no identified driver is refused by every trial that demands one,
which is the commonest reason this trait eliminates anything. A KRAS G12C
patient loses fewer trials because more of the marker-specific studies are
KRAS studies.

### Two caveats

1. **151 quotes failed the substring check**, mostly two passages stitched
   together. The lists may still be right. Same class of flag as the original
   key, at a lower rate. Not guessed into different lists.
2. **Marker matching for the ceiling uses gene-token overlap**, as written in
   THRESHOLDS.md before the labels existed (`EGFR L858R` satisfies a required
   list containing `EGFR mutation`). A tighter exact-string match would throw
   out fewer trials and would understate a perfect filter.

### What would reverse this

The other three traits being labelled and the six-trait union not moving
materially past 40%, which would mean the marker was the whole story and
further labelling was wasted. That is why they wait on approval rather than
running tonight.

---

## 2026-09-29 — Step 3b: matching on general terms does not recover the ceiling

**Decision: matching loses most of the ceiling. The approach needs rethinking.**
Combined recall is **32.2%** (below the 60% gate). Wrongly-picked-up is
**0.9%** (well under 20%). The matching-gated union is **10.2%**, against a
perfect-oracle ceiling of **39.9%**. Those are ceilings under this matcher,
not predictions of end-to-end accuracy.

Thresholds were committed in `73e9cc6`, before normalisation. Cost about
**$1.10** to turn 2,167 quotes into subjects (750 immuno, 719 brain, 698
marker), plus a few cents to embed 764 terms.

### What was run

`scripts/step3b_normalise.py` then `scripts/step3b_match.py`. The model was
not told which fact a quote belonged to, and was not given the patient field
names. Patient queries came from the revised Step 4 output.

| Arm (at cosine 0.80) | Mean recall | Wrongly picked up |
|---|---:|---:|
| Word overlap | **32.2%** | 0.9% |
| Embeddings | 1.2% | 0.0% |
| Combined | **32.2%** | 0.9% |

By fact, combined (= word, because embeddings added nothing):

| Fact | Recall | Wrongly picked up |
|---|---:|---:|
| Immunotherapy | 32.5% | 0.0% |
| Brain metastases | 48.4% | 2.7% |
| Tumour genetic marker | 15.8% | 0.0% |

Embeddings at every sweep point (0.70–0.90) stay below 7% mean recall.
`previous immunotherapy` vs `immunotherapy` is cosine **0.73**. `cancer
spread to the brain` vs `brain metastases` is **0.53**. `tumour genetic
marker` vs `EGFR mutation` is **0.52**. The one pair that clears 0.80 is a
specific value against its gene: `EGFR L858R` vs `EGFR mutation` (0.83).
Normalising both sides to "general terms" did not move them into the same
neighbourhood. Word overlap is the whole combined arm.

### Why marker recall is 16%

A patient with value `none` queries `tumour genetic marker` and `none`.
Neither shares a token with `EGFR mutation` or `ALK fusion`. Those patients
are exactly the ones the perfect oracle throws out the most (24.6%), and
matching finds none of those rules. Patients who carry a named marker match
some same-gene trials and still miss the rest.

### The matching-gated ceiling

| | Perfect oracle | After matching |
|---|---:|---:|
| Union mean | 39.9% | **10.2%** (2.3–16.8%) |
| Mean per-trait | 15.6% | 4.7% |
| Six-trait projection | 63.8% | 25.1% |

Matching finds about a quarter of the rules the oracle uses. The cheap step,
as currently matched, cannot throw out most of what a perfect filter could.

### What this suggests, which is not a result

The take-apart step already uses *fixed* names (`tumour genetic marker`,
`cancer spread to the brain`). This measurement asked the trial side for any
ordinary general term, on purpose, so it could not just copy those names.
The miss is that those two vocabularies are not the same. Forcing the
trial-side subject onto the same closed names would make matching a string
equals and is a different method — not run here, not scored.

UMLS is still untested. Steps 6 and 7 stay on hold: a trained small model
does not fix a matching hole that sits *before* the judge.

### What would reverse this

A matcher that puts both sides on the same closed names, or a dictionary
that links `tumour genetic marker` to `EGFR mutation` without linking brain
to bone, measured on this same quote set.

---

## 2026-09-29 — Step 5b: six-trait ceiling is 54.2%; matching still loses most of it

**Decision: the perfect-oracle ceiling with six traits is 54.2% — above the
40% floor, short of 70%.** Matching-gated, it is **23.2%**. The cheap step
as currently matched still cannot deliver the ceiling. Steps 6 and 7 stay on
hold.

Thresholds were committed in `6c9da99` before labelling. Cost **$9.26** to
label (1,852,214 in, 308,955 out) plus **$1.19** to normalise 2,216 new
quotes. One trial failed (NCT07560111, HTTP 520). Quote-check flagged 683
of 1,307 (52%), mostly stitched stage quotes. 1,196 trials have an allowed
stage list; 744 of those lists are conditional, so stage is often unreachable
from a plain description.

### Perfect-oracle ceiling, six traits

| Trait | Mean throw-out | Notes |
|---|---:|---|
| Tumour genetic marker | 23.8% | Still the strongest |
| Disease stage | 17.3% | 57% of trials state the rule conditionally |
| Immunotherapy | 16.3% | |
| Platinum chemotherapy | 12.6% | |
| Brain metastases | 6.5% | 32% conditional |
| Autoimmune disease | **0.6%** | 316 of 1,307 are barred-with-exception |
| **Union** | **54.2%** (46–64%) | |
| Optimistic union | 79.0% | |
| Independent six-trait projection from the new mean (12.9%) | 56.2% | Close to the measured union |

These are best-case ceilings assuming every rule is found. They are not what
the system would do. Reading everything is still unmeasured (Step 8).

Autoimmune adds almost nothing to a timid filter: the common rule is
conditional. Stage looks useful until more than half the rules carry a
condition. The marker is still doing the heavy work; the other five together
lift the union from 39.9% to 54.2%.

### Matching-gated, six facts

Combined recall **58.1%**, wrongly-picked-up **10.1%**. Recall is just under
the 60% rethink gate. Mean FPR clears 20%, but brain FPR is **45.5%** —
because the patient name `cancer spread to the brain` shares the token
`cancer` with nearly every newly indexed stage quote. Adding facts to a
shared word-overlap index made a name that was safe on three facts unsafe on
six. Marker recall is still 23%. Autoimmune recall is 92% on the one patient
who has the trait listed (P12); that is n=1.

| | Perfect oracle | After matching |
|---|---:|---:|
| Three-trait union | 39.9% | 10.2% |
| Six-trait union | 54.2% | **23.2%** (12–32%) |

### What this does to the architecture question

The write-once-and-look-up design Will prefers still needs both sides on the
same closed names. Unconstrained general terms do not match, and a shared
word index over mixed facts is one generic token away from swamping a fact.
A trained small model (Steps 6–7) does not sit in front of that hole.

### What would reverse this

Closed-name normalisation on the trial side, measured on these same quotes,
lifting matching-gated union toward the 54% oracle without a 45% brain FPR.

---

## 2026-09-29 — Step 3c: closed names recover most of the ceiling

**Decision: matching is workable once both sides use the same fixed names.**
Mean recall is **84.2%** (the 60–85% band). Wrongly-picked-up is **0.03%**.
The matching-gated union is **40.6%**, against a 54.2% perfect-oracle
ceiling and a 23.2% figure under unconstrained general terms. Quote 40.6%,
not 54.2%. These are still ceilings under this matcher, not predictions.
Reading everything is still Step 8.

Thresholds were committed in `c1b190d`, before assignment. Cost **$2.36**
(426,135 in, 86,365 out) to name 4,383 quotes.

### What was run

`scripts/step3c_closed_names.py` then `scripts/step3c_match.py`. The model
was not told which fact a quote belonged to. Patient queries came from the
revised Step 4 output, name only — never the value. Matching is exact
equality of names. No word index, no embeddings.

| Fact | Recall | Wrongly picked up |
|---|---:|---:|
| Tumour genetic marker | 99.9% | 0.2% |
| Autoimmune disease | 99.4% | 0.0% |
| Brain metastases | 93.9% | 0.0% |
| Disease stage | 93.3% | 0.0% |
| Immunotherapy | 81.4% | 0.0% |
| Platinum chemotherapy | **37.2%** | 0.0% |
| **Mean** | **84.2%** | **0.03%** |

Assignment agreed with the source field on 86.1% of quotes (3,773 of
4,383). 419 came back `other`.

### The two bugs are closed

- **No-marker.** Marker recall is 99.9%. Every none-marker patient who
  actually listed the trait retrieves the same 321 trials the oracle
  throws out. Querying the name `tumour genetic marker`, not the value
  `none`, is the whole fix.
- **Word-flooding.** Brain wrongly-picked-up is 0.0%, down from 45.5%.
  There is no shared token bag, so `cancer` in the patient name cannot
  hit a stage quote.

### Why the mean is 84% and not 99%

Platinum. 284 of 545 platinum quotes were assigned `other`. They are
generic prior-therapy sentences — "no prior systemic treatment", "any
prior chemotherapy" — that never say platinum. The answer key treats
those as platinum rules because chemotherapy includes platinum. The
assigner, not told the question is about platinum, refuses to invent
that implication. Five of six facts clear 81%. Platinum is 37% and
pulls the mean into the workable band rather than past 85%.

The other drag on the *gated* number is take-apart, not matching. Six
of twenty parses omitted `tumour genetic marker` (P01, P06, P08, P11,
P14, P20). Those patients cannot throw out on the strongest trait.
If every patient queried every always-on fact, the gated union would
be **48.6%**. The official number uses the Step 4 output, as committed,
and is 40.6%.

| | Perfect oracle | General terms (3b) | Closed names (3c) |
|---|---:|---:|---:|
| Six-trait union | 54.2% | 23.2% | **40.6%** |
| Same, if take-apart listed every fact | 54.2% | — | 48.6% |

### What this does to the architecture

Write-once-and-look-up is now the design to prefer. Matching by exact
name works. The leftover holes are (1) take-apart missing a listed
trait, and (2) a quote that names a broader class than the fact. A
trained small model (Steps 6–7) does not sit in front of either hole,
and still stays on hold.

A write-once pass that assigns the closed name *while labelling* would
not have the platinum miss: the labeler already decided those sentences
are platinum rules. That is a different measurement — how accurate the
label is — not a matching measurement.

### What would reverse this

Re-running with names assigned at labelling time and finding the gated
union still far below 54%, which would mean implication and take-apart
are the real ceiling and closed-name matching was not the missing piece.
Or counting the 84.2% mean as a fail because it is just under 85% —
the committed band calls that workable, and says to quote the gated
number.

---

## 2026-09-30 — Step 3d: containment closes the platinum hole

**Decision: keep the hand-written hierarchy. Do not install UMLS for this.**
Platinum recall is **88.8%**, from 37.2%, against a 70% gate. Matching-gated
six-fact narrowing is **44.7%**, from 40.6%, against a 54.2% perfect-oracle
ceiling. Quote 44.7%. UMLS remains a separate test: generalising beyond these
field names.

Thresholds were committed in `f93ce2c`, hierarchy and comparison logic in
`739dd4f`, both before re-assignment. Cost **$0.79** (parse $0.04 + 1,338
quotes $0.76). No embeddings. Steps 6 and 7 stay on hold.

### What was run

Two names added to the closed list: `previous chemotherapy (any kind)` and
`previous systemic anticancer treatment (any kind)`. Hierarchy in
`therapy_hierarchy.json`. Containment at comparison time only; neither side
is rewritten. Re-assigned platinum-source, immunotherapy-source, and
then-`other` quotes (1,338). Copied the other four facts' names and re-scored
them. Five vague-history patients (V01–V05) parsed with the extended names.

### Against the committed gates

| Measure | Gate | Result |
|---|---|---|
| Platinum recall | ≥70%, from 37.2% | **88.8%** (485 of 546) |
| Every other fact's recall | drop ≤3 points | none dropped; immuno **+6.3** |
| Wrongly-picked-up, any fact | <20% | max **6.4%** (platinum) |
| Vague-history patients vs platinum-named rules | 0% | **0 of 845** pairs |
| Six-fact narrowing | must rise from 40.6% | **44.7%** (25.3–54.8%) |

Recovering all 284 generic-chemotherapy sentences was estimated at about 89%.
88.8% is that recovery, not a near-miss against 70%.

### Which numbers moved, and which did not

| Fact | Recall 3c → 3d | Wrongly picked up 3c → 3d |
|---|---:|---:|
| Platinum chemotherapy | 37.2% → **88.8%** | 0.0% → **6.4%** |
| Immunotherapy | 81.4% → **87.7%** | 0.0% → **4.1%** |
| Brain metastases | 93.9% → 94.2% | 0.0% → 0.0% |
| Disease stage | 93.3% → 93.4% | 0.0% → 0.0% (n=101 negatives; Wilson 0.0–3.7%) |
| Tumour genetic marker | 99.9% → 99.9% | 0.2% → 0.3% |
| Autoimmune disease | 99.4% → 99.6% | 0.0% → 0.0% |
| **Mean** | 84.2% → **93.9%** | 0.03% → **1.8%** |

Brain, stage, marker, and autoimmune did not move in any way that matters.
They were re-scored because comparison changed; exact name equality is
unchanged for facts outside the hierarchy. The small recall ticks are
re-assignment of a handful of `other` quotes, not containment.

Immunotherapy recall rose because an immunotherapy patient sits inside a ban
on any systemic treatment. That is case 2, the same direction as platinum.

Wrongly-picked-up rose because the shared parent also matches the *other*
child. A platinum patient now retrieves some immunotherapy-source sentences
assigned `previous systemic anticancer treatment (any kind)`, and the
reverse. That is expected, it is under 20%, and it is why a method that
matched nothing would still look perfect on this gate alone. Do not read
the 6.4% without the 88.8%.

### The original 20 are not a vague-history case

None of P01–P20 parsed at a broader therapy level without also naming a
specific drug or class. Case 3 was untested there. Stated, not papered over.
It is tested on V01–V05.

### Price of the safety valve

On the original 20, **zero** trials are now kept as can't-tell that a
both-directions comparison would have narrowed. Those patients are the
narrower side, so case 3 does not arise.

On the five vague-history patients, **169 platinum-named trials per patient**
are kept as can't-tell (845 patient–trial pairs). Wrongly-picked-up on those
pairs is 0%. A trial that bars platinum specifically is not applied to a
note that only says "chemotherapy" or "systemic therapy". That is the
visible cost of not promoting the trial's rule up.

Immunotherapy is not under chemotherapy. A patient who had only
immunotherapy is not caught by a chemotherapy ban; 36 immunotherapy-source
quotes assigned `previous chemotherapy (any kind)` do not match an
immunotherapy query.

### What this does to the architecture

Write-once-and-look-up still holds. The leftover matching hole was a missing
rung on a three-level ladder, not a need for UMLS, embeddings, or a trained
retriever. Steps 6–7 stay on hold. The remaining drag on the gated number is
take-apart: six of twenty parses still omit `tumour genetic marker`. If
every patient queried every always-on fact, the gated union would be
**51.9%**, next to 44.7% official and 54.2% oracle.

### What would reverse this

Finding that a coordinator's real notes are usually as vague as V01–V05,
so the 44.7% (measured on named drugs) overstates operational narrowing, and
the 169 kept platinum-named trials per vague patient become the typical
case. Or a later UMLS test beating 44.7% on a vocabulary this hierarchy
cannot name — that is the generalisation question, not this hole.

---

## 2026-09-30 — Step 8: the reader is measurable; 44.7% stands

**Decision: do not withdraw the 44.7% narrowing figure.** On trials the
filter discarded, gpt-5.4 called the patient a candidate **6.3%** of the
time (38 of 600), under the 10% unsafe gate. There is still no overall
accuracy number, and there should not be: acceptances are unverifiable
with a six-fact key.

Thresholds and the model pair were committed in `aebee10` before any
sample or read. Cheap arm is **gpt-5.4-mini**, not Qwen3. Cost about
**$18** across both models (plus a few dollars of duplicate calls from
restarting at 32 workers). 3,040 reads, six patients, 100 discarded + 150
kept each, plus 20 pairs twice.

### Against the committed gates (expensive model is the reference)

| Measure | Gate | gpt-5.4 | gpt-5.4-mini |
|---|---|---:|---:|
| Discarded trials called a candidate | >10% withdraws 44.7% | **6.3%** (38/600) | 10.8% (65/600) |
| Quotes missing from the trial text | >5% is fabrication | **1.2%** (54/4,516) | 7.7% (283/3,692) |
| Agreement on verifiable key exclusions | <85% investigate | **87.0%** (663/762) | 81.6% (622/762) |
| Cheap vs expensive on measurement 1 | no gate | — | **+4.5 points** |

Doctors in published work on this task agreed with each other 64–70% on
per-rule questions. 87% is not a human ceiling; 81.6% on mini is not
automatically poor. Mini still fails the two gates that were written for
a production reader.

### What else moved

- **Per patient, expensive, lost-joinable (n=100, Wilson):** P12 1.0%
  (0.2–5.5%), P02 and P09 3.0% (1.0–8.5%), P01 5.0% (2.2–11.2%), **P03
  and V01 13.0% (7.8–21.0%)**. The pooled 6.3% hides two patients over
  the 10% line. V01 is the vague-history case.
- **Same-rule given an exclusion:** 73.6% expensive, 64.0% mini. The
  reader often excludes, but not always citing the fact the key used.
- **Extra exclusions the six facts miss:** 352 expensive, 384 mini, on
  kept trials. A 20-row sheet is in `docs/step8_will_check.md` for Will.
  Reading comprehension only.
- **Not enough information** is used, not avoided. Highest on previous
  immunotherapy (45.9% of that fact's rules) and tumour genetic marker
  (34.1%) for gpt-5.4 — the facts that are often conditional.
- **Consistency, 20 pairs, Wilson:** expensive 15% changed (5.2–36.1%);
  mini 5% (0.9–23.6%). n=20 is too small to prefer mini on stability.
- **Off-topic quotes** (in the trial, but keyword-miss for the claimed
  six facts): 586 expensive. Not in the 5% gate. Open facts are 1,238.
- **Cost / time per patient, pass 1:** gpt-5.4 about **$2.36** and 5.5 s
  mean per read; mini about **$0.65** and 2.3 s. Wall clock at 32 workers
  was minutes, not an hour.

Quotes that appear after whitespace normalisation count as present, same
as the answer-key checker.

### What this does to the architecture

The cheap filter's discarded pile is mostly not full of joinable trials,
if gpt-5.4 is the reference full-read. Mini is not a drop-in reader: it
fabricates more, agrees with the key less, and sits on the wrong side of
the 10% lost-joinable line. Steps 6–7 stay on hold; a trained judge has
little to win if the expensive reader is the one you ship, and mini is
not close enough that training is the next cost win.

Qwen3 on Lambda is still unmeasured. Mini failing does not prove Qwen
would fail.

### What would reverse this

Will's 20 extra-exclusion rows disagreeing often enough that measurement
4 is invention rather than extra work. Or P03/V01's 13% lost-joinable
holding up on a larger discarded sample, which would mean the pooled 6.3%
is the wrong summary for those patient types. Or Qwen matching gpt-5.4
on measurement 1 at GPU-hour prices.

---

## 2026-09-30 — Will agrees 20/20 on extra-exclusion quotes

**Decision: measurement 4 is extra work the six facts miss, not invention.**
Will marked agree on all 20 rows in `docs/step8_will_check.md`. Those rows
were gpt-5.4 only. Mini produced 384 extra exclusions on the same kept
stratum; they were not hand-checked.

---

## 2026-09-30 — Step 9 sample redesigned before any of the 40 were scored

**Decision: audit definite labels (`barred` / `required`), not the
least-sure ones.** The 40-row sheet in `docs/step9_will_check.md` is
superseded. **None of those 40 rows had been scored.** No results were
seen. Goalposts were not moved.

The old sample had no consequences: `unclear`, `both_classifications`,
and `barred_with_exception` all keep the trial. A wrong label there
cannot change 44.7%, 6.3%, or any other number. `unclear` also cannot
be verified from a single quote.

What can cause harm is a wrong `barred` or `required`: the system
discards a trial a patient could have joined, permanently. Those labels
had never been audited.

Replacement, committed in THRESHOLDS.md before either new run: (1)
mechanical recategorisation of the 52% quote flags, D+E gate 5%; (2) 30
consequential rows weighted by narrowing, disagreement bands under 5% /
5–10% / above 10% read against the 6.3% lost-joinable figure.

### Task 1 result (same day)

4,384 quote-slots. Originally flagged 1,353. Among those: A 619 (45.8%),
B 3, C 675 (49.9%), D 13, E 43. **D+E = 57 / 4,384 = 1.3%**, under 5%,
next to Step 8's 1.2% missing-quote rate. The 52% was stitching and
word-lists, not fabrication. 334 platinum C-flags are generic
chemotherapy/systemic sentences; the platinum word list was not widened
to hide that.

## 2026-09-30 — Step 9 three mechanical quote checks

### What was run

Free, scripted, no human. Thresholds (name any non-zero crossing or
E-discard in full, not as a percentage) committed in THRESHOLDS.md
before this ran. The 30-row consequential sheet was not touched. No
row was re-labelled. Steps 6 and 7 were not started.

### Check 1 — stitched quotes that mix the two lists

**282.** Not zero. Named in `docs/step9_three_checks.md`: 254 trials,
mostly stage (118) and marker (79). One example in full:
`NCT07103395` immunotherapy quote joins an inclusion "no prior
immunotherapy" sentence to an exclusion "prior anti-PD-1" sentence.
57 stitched quotes sat on the 46 loose-heading or 28 no-heading
trials and were reported as unresolvable, not as clean.

### Check 2 — unsupported quotes that actually discarded a trial

**441 patient–trial pairs, from 34 labels.** That is a count of bad
citations, not of wrong labels. Triage is in the next section.

### Check 3 — split of the 675 word-list misses

| Sub-bucket | n | of 675 |
|---|---:|---:|
| C1 hierarchy parent | 410 | 60.7% |
| C2 missing spelling | 130 | 19.3% |
| C3 unrelated | 135 | 20.0% |

C1 only on the prior-therapy family (299 platinum, 111 immunotherapy).
C1 is large: independent evidence that trials state rules broader
than the labelled fact, corroborating the hierarchy.

C2 missing spellings worth widening later: `advanced`, `metasta` for
stage; `ICI` / hyphenation of PD-L1; `auto-immune`; drug names
`durvalumab`, `tislelizumab`, `cemiplimab`. Not done here — no
re-label without a further DECISIONS entry.

**D+E+C3 = 192 / 4,384 = 4.4%**, under the committed 5% support gate
(D+E alone was 1.3%). Remaining C3 is real: brain labels on
"metastatic disease" with no brain word; immuno/platinum labels on
"treatment-naïve", which sits above the written hierarchy and was
not absorbed into C1.

### What this does not settle

The 30-row human sheet on consequential labels is still outstanding.
282 crossings and 441 E-discards were not folded into a disagreement
rate; they sit next to it. No overall accuracy figure.


## 2026-09-30 — Step 9 30-row check: the gate was breached

**This was not a human audit.** Will could not judge the 30 rows —
nearly all need medical knowledge he does not have. Claude judged
them instead, and pulled the source trial text for the doubtful ones.
The plan called for a human check and did not get one. What follows
is a second-model agreement check: it bounds careless error, not
the kind where two models misread the same convention identically.
Do not describe Step 9 as a human audit in the write-up.

### The result

| | Rows |
|---|---:|
| Agree | 22 |
| Disagree | 4 |
| Borderline — label stronger than the quote warrants | 3 |
| Can't judge from the quote alone | 1 |

**4 of 29 checkable = 13.8%.** The committed gate was: above 10% →
re-examine the 6.3% lost-joinable figure before quoting it.
**Breached.** Counting the three borderlines it is 24%.

Every one of the four errs in the same direction: wrongly discarding
a trial. None wrongly keeps one. That is the direction that costs
patients.

### The cause: a criterion scoped to a different cancer, read as general

Three of the four are basket trials. The labeller read a criterion
written for another tumour type and applied it as if it applied to
lung.

- `NCT07064018` — genetic marker **required**. The marker is attached
  only to the pancreatic arm; the lung arm needs none.
- `NCT04282044` — platinum **required**. The quote literally reads
  "Subjects with Ovarian cancer must have received... a platinum-based
  regimen."
- `NCT07444814` — stage **required**. The quote is the trial's title,
  not a criterion, and the eligibility text states no stage
  requirement at all.
- `NCT05766800` — platinum **barred**. A lung-only trial whose
  exclusion is about prior treatment for thymic epithelial tumour.
  Same shape: a criterion about another disease read as general.

The three borderline rows are a different convention: a bar narrowed
by a qualifier ("active central nervous system metastases", "active
autoimmune disease", platinum "planned to start") labelled as a
plain unconditional bar.

### What this does to the numbers

6.3% was measured against this key. The 10% gate on lost-joinable
is breached as a *reason to re-examine*, not yet as a new figure.
Scoping re-label is **held** until the 34-label triage (below) is
read. A missing quote is not a wrong label.


## 2026-09-30 — missing quote ≠ wrong label; triage of 34 and 282

**Decision: 441 is a citation-quality finding, not 441 lost trials.**
The worked example is the CorpFam shape — right verdict, invented
source — and sharper here because a valid sentence was sitting in
the eligibility text. The evidence layer caught it.

### The 34 labels that discarded someone

Search of eligibility, not of the quoted string.

| Verdict | Labels |
|---|---:|
| Supported — wrong citation only | 22 |
| Unsupported — no stage (or other) sentence in eligibility | 12 |
| Ambiguous | 0 |

NCT06868485 is supported: eligibility says "Documented EGFR mutation."
The model cited the title anyway.

The 12 unsupported are all `disease_stage` / `required`, inferred
from the title, with no stage language in the criteria. They
discarded **212** patient–trial pairs:

- 19 patients each: NCT06943521, NCT03193567, NCT05363319,
  NCT05902988, NCT06737107, NCT06775678, NCT06281678, NCT04977453,
  NCT06896422, NCT07117890, NCT07241039
- 3 patients (P08, P14, P20): NCT06983743

Those 12 are real lost trials. They were not re-labelled here.
Ids and patients are in `docs/step9_triage.md`.

### The 282 crossings

| Outcome | n |
|---|---:|
| Same direction (redundant, like NCT07103395) | 142 |
| Fact named on only one list (other piece is padding) | 56 |
| Mixed polarity — stitch can flip the label | 50 |
| Stored label vs piece heuristic disagreed | 20 |
| No piece names the fact | 14 |

**50** is the harm-pattern count, not 282. NCT07103395 is both-bar:
inclusion "no prior immunotherapy" and exclusion "prior anti-PD-1"
point the same way. Mixed-polarity ids are in the triage doc.
Some of those 50 are cohort/basket scoping, which is still held.

### Hierarchy top level

Added `previous anticancer therapy of any kind` above systemic.
C1/C2/C3 re-run: C1 **410 → 433**, C3 **135 → 112**, C2 130.
D+E+C3 **4.4% → 3.9%**. 23 treatment-naïve rows moved into C1
where they belong. Brain C3 stayed 37.

### 37 brain-on-metastatic-disease re-label

$0.14. Snapshot `data/answer_key_pre_brain37.jsonl`. 32 of 37
became `not_mentioned` (the quote was spread-anywhere, not brain).
5 had a real brain/CNS sentence and were re-cited. Immuno labels
untouched.

### Citation rule going forward

Labeller must emit a verbatim eligibility substring. Reject and
retry up to twice if it quotes the title or anything else. Wired
into the three labelling scripts. Does not re-run the corpus.

### Still held

Scoped basket re-label, qualifier convention applied to the key,
and downstream re-score of 54.2% / 44.7% / 6.3%. The 12
unsupported stage labels are the next small re-label if we
continue, not a wholesale key rewrite. Steps 6 and 7 not started.

---

## 2026-09-30 — Remaining list done; quote 43.0% next to 44.7%

**Decision: the qualifier convention is adopted.** A word that narrows
a bar (`active`, `uncontrolled`, `untreated`, `symptomatic`, `within N
months`) makes it `barred_with_exception`, which keeps the trial.
Applied to 147 yes/no quotes (immuno 12, brain 34, platinum 9,
autoimmune 92). The headline fell. That is correct behaviour, not a
regression.

**Decision: do not withdraw the narrowing figure.** Lost-joinable on
the corrected matching-gated discarded set is **5.6%** (32/569), under
the 10% gate. 43.0% stands. Previous reports stay on disk.

### What was run, in the committed order

1. Twelve title-inferred stage labels cleared. Mechanical. 212 wrong
   discards among the 20 patients.
2. Seventy mixed-polarity / heuristic-disagree slots re-labelled.
   gpt-5.4, ~$0.97. All 70 quotes are a verbatim eligibility substring.
3. Qualifier pass, above.
4. Free scope count. **281 of 1,307** (21.5%) list a named cancer other
   than lung on `conditions`. **308 quotes / 231 trials** name another
   cancer. The 34 missing-quote labels were not a basket problem; the
   corpus is. Wholesale scoping re-label is still held — this is the
   size that would justify it.
5. Re-score into `*_after_fix.json`. Ceiling **54.2% → 51.9%**.
   Matching-gated **44.7% → 43.0%**. Lost-joinable **6.3% → 5.6%**.
   Will sheet not regenerated.

### What would reverse it

Lost-joinable above 10% on the corrected discarded set would withdraw
43.0%. A scoped basket re-label of the 231 other-cancer-quote trials
would be the next key change, not another mechanical pass on the 12.

---

## 2026-09-30 — Clarifying questions do not recover the ceiling

**Decision: do not ship the clarifying-question agent.** Three ranked
questions take the perfect-finder ceiling from **51.9% to 56.0%**,
below the 58.5% stop line (a quarter of the 51.9→78.2 gap). Matching-
gated goes 43.0% → 48.0%. Wrongly discarded goes **5.6% → 10.4%**,
over the 10% gate, which overrides recovery. Asking every live
question still only reaches 57.7%.

The 78.2% optimistic figure assumed a settled conditional discards.
For these patients it often keeps: treated-and-stable brain mets,
no autoimmune disease on 19/20, and 789 of 1,918 assigned rules
were `other` (cohort / trial histology / protocol part). Those points
were not sitting in unasked questions.

Ranking missed 1.5× (1.21×). Drop it. Round 1 already has 54.2% of
the 56.0%; LangGraph is heavier than the problem, and the write-up
says so rather than retrofitting a framework justification.

Thresholds, seed **202609303**, and the oracle field draw were
committed before assignment. Assignment cost **$1.79**. Will sheets
untouched. Steps 6 and 7 not started.

### What would reverse it

A patient sample where most people with brain mets fail the
exception, and where wrongly-discarded stays under 10% at ≥65%
narrowing. That is a different clinic, not a better ranker.

---

## 2026-09-30 — Sparse-input asking recovers facts and fails safety

**Decision: do not ship fact-recovery asking.** The previous test
measured condition-resolution on complete notes (prize 5.8 points).
This one measures recovering the six facts when the note is incomplete
(prize 0% → 43.0%, or 50.2% listed perfectly).

**79.0% / 78.2% is retired from this project's vocabulary.** It assumed
every conditional discards. Many keep. It is not reachable under any
design.

280 configurations, seed **202609304**, random subsets of size k=0..6,
two draws per patient per k. Notes leak-checked (0/280 first drafts).
Parsed with the Step 4 parser. Checklist baseline in discard-power
order. Agent: same order, stop after observed increment < 2pp.

| Measure | Result | Gate |
|---|---|---|
| k=0, 1, 2 after 3 questions | 45.0%, 47.6%, 48.9% | cleared half-gap to 43.0% |
| Agent vs 6-question checklist | 49.8% vs 50.2%, 2.96 questions | cleared |
| Stopping within one of right stop | 100% (by construction on this policy) | cleared 70% |
| Wrongly discarded | **11.4%** (66/581 unique pairs) | **BREACHED — overrides recovery** |

On trials the original 43.0% system already discarded, the reader still
agrees (4.6%). The breach is the extra discards from a complete fact
list: 41.5% of originally-kept trials the agent now throws away are
still candidates according to the reader. The 10% gate held at 43.0%
and fails at 50.2%.

A two-line note parses more reliably than a full one (recall 100% at
k=0, 71% at k=6). The parser never invented a fact.

Sparsity is synthetic. Upper bound on real coordinator input, which
this project does not have.

Cost $1.56. Will sheets untouched. No further condition-resolution
work. Steps 6 and 7 not started.

### What would reverse it

Wrongly discarded under 10% on the agent's discarded set at this
recovery, on real coordinator notes rather than stripped complete
ones. A better ranker is not the gap.

---

## 2026-09-30 — TREC snapshot exists; do not assign at TREC scale yet

**Decision: TREC 2021/2022 is usable as the scoreboard.** Both years
share one April 27, 2021 ClinicalTrials.gov dump, still downloadable
from trec-cds.org (`2021_data/ClinicalTrials.2021-04-27.part1–5.zip`,
all five HEAD 200, ~1.71 GB). Use that text, not the live registry.

125 patient descriptions (75 + 50). 71,226 judgments. 48,714 unique
NCT IDs. Relevance: 0 not relevant, 1 excluded, 2 eligible.

Live API sample (450 IDs, 150 per level, seed 202609305): 100% still
resolve at every level. That does not decide usability; the snapshot
does. The 70% per-level gate was for the no-snapshot case.

**Do not start TREC-scale concept assignment on a frontier model.**
Judged pool at gpt-5.4 is about $5,100; the snapshot ~$40k. Cheap
hosted is still too much. **Self-hosted batch on a rented GPU, once,
then tear down** is the path if the lung API gate clears. Gene-symbol
matching is not replaced by UMLS. scispaCy has no concept is-a.
No Metathesaurus for the lung test.

Gates: THRESHOLDS.md commits **03d95b5** (retrievability) and
**a2dfda5** (UMLS corrections). Write-up:
`docs/trec_retrievability.md`.

### What would reverse it

The five zip parts disappearing and a later live-API sample falling
below 70% retrievable at any relevance level — then TREC is not the
scoreboard.

---

## 2026-09-30 — UMLS API lung pass is not a vocabulary result

**Decision: do not proceed to TREC assignment or a RxNorm/MeSH
download.** The REST run resolved **13 of 3,390** quotes (miss
99.62%). Mean recall 94.4% / false pickup 3.7% is the six-name
matcher with a 13-quote overlay. Stage false pickup rose to 11.4%
(was 0.0%) on those hits. Marker matching was left untouched
(99.9%). scispaCy unused. No Metathesaurus.

The lookup must be a **short subject phrase**, not the eligibility
sentence. That is Will's prompt, then the API. Until miss rate is
low, the 84% / 5% gates are not measuring UMLS.

### What would reverse it

Quote (or extracted-phrase) miss rate low enough that most
retrieve decisions are CUI + is-a, and mean recall still ≥84%
with mean false pickup ≤5%, marker row still the existing matcher.

---

## 2026-09-30 — UMLS does not cover this corpus's vocabulary

**Decision: stop. UMLS cannot supply the vocabulary. The six-name
approach stays. Generalising needs a different answer.**

Looked up all **5,578** distinct Step 1 `concept` phrases
(`data/step1_concepts.jsonl`) via the UMLS REST API. No download. No
new extraction. No TREC. Gates committed in **107c1e2** before the
lookups. Gene-symbol matching was not replaced.

| Measure | Result | Gate |
|---|---|---|
| Coverage by occurrence | **56.4%** (7,351 / 13,033) | STOP below 60% |
| Coverage of distinct phrases | 30.5% (1,700 / 5,578) | reported; 76.7% of phrases appear once |
| Excluding biomarker/mutation | 58.4% | still below 60% |
| Resolution precision (name agreement) | **66.2%** (1,125 / 1,700) | BREACHED below 90% |

Labs, infection, pregnancy, demographics, and performance status resolve
often (82–98% of occurrences). The categories this dictionary was meant
to own do not: prior systemic therapy 15.2%, disease or stage 57.6%,
comorbidity 64.6%, concurrent medication 47.4%. Common misses include
`absolute neutrophil count`, `written informed consent`,
`leptomeningeal disease`, `prior immunotherapy`, `stage iv nsclc`.

When a phrase does resolve, string agreement against the canonical name
is 66.2%. Claude review of the 575 disagreements (`docs/step13_umls_disagreements.md`):
many are true synonyms the automatable check is too strict on, and many
are genuine wrongs — `measurable disease` → Newcastle disease virus
antibody, `non-squamous nsclc` → squamous NSCLC, `ecog` →
electrocorticogram, `her2 amplification` → amplification not detected.
A generous re-score still leaves polarity flips and unrelated CUIs well
above 10%.

Write-up: `docs/step13_umls_coverage.md`. JSON:
`data/step13_umls_coverage.json`.

---

## 2026-09-30 — TREC hybrid retrieval: 2021/2022 match the papers; 2023 does not

**Decision: stop on the written gate.** Eligible recall at 6% of
the judged pool is **91.6%** (2021) and **91.4%** (2022), and
**65.4%** (2023). The gate is below 70% → stop and diagnose. The
two reproduction checks passed: hybrid beat BM25 and MedCPT alone;
LLM keywords beat the raw note.

Stages 1–2 only. Judged pool as the collection. 2021/2022: 27 April
2021 dump. 2023: 8 May 2023 dump. No trial text to an LLM. No
six-name code. MedCPT article vectors from a rented A10, then
terminated. Truncation to 512 tokens, same as TrialGPT.

2023 is a different query: questionnaire fields, not admission
notes. Mean 315 eligible and 604 relevant trials per topic. 6% of
that collection is 1,026 rows, enough to hold every eligible trial,
so 65% is a miss, not a short list. BM25 is almost the whole
hybrid; MedCPT loses to words. The papers that exceed 90% were
measured on 2021/2022.

On those two years, keyword + `text-embedding-3-small` is as good
as MedCPT (91.8% / 90.3%). The earlier whole-note embedding miss
was the query shape.

Write-up: `docs/trec_hybrid_retrieval.md`. Do not start the reader
or a reranker from the 2023 number.

### What would reverse it

A 2023 keyword prompt that lifts eligible recall at 6% to ≥70%
without breaking 2021/2022, or a decision to score the gate only
on the note-shaped years the papers used. Neither is claimed here.

---

## 2026-09-30 — The conditions field does not replace retrieval

**Decision: keep keyword hybrid as the first stage on 2021/2022.
Do not treat the free `conditions` field as the retriever. Do not
start a reranker from this measurement.**

Gates committed in **9ffa03b** before any match rate. 2023 not
run. Disease term = first already-generated keyword. Strict =
normalised equality. Loose = strict or substring either way or
token overlap. Comparison is at matched depth *k* (the filter's
retained count for that patient). Combination = loose filter,
then the same BM25 + MedCPT + RRF inside the survivors.

| Year | Loose recall | Hybrid @ *k* | Gap | Mean *k* | Reading |
|---|---:|---:|---:|---:|---|
| 2021 | 62.3% | 73.3% | 11.0 pts | 994 | more than 10 worse |
| 2022 | 49.2% | 62.2% | 13.0 pts | 581 | more than 10 worse |

Empty `conditions`: 7 / 26,162 and 3 / 26,585. Zero patients with
zero loose matches. The field is usable and still loses.

The 604,566 → 1,308 NSCLC query is a single-disease cut. TREC
notes are multi-problem admission notes. Eligible trials are often
for a second problem (ESRD note, *C. diff* trials), a synonym
with no shared token (`Depression` vs `major depressive
disorder`, `Stroke` vs `Cerebrovascular Accident`), or a parent
heading (Kallmann → hypogonadism). Retrieval is reading the rest
of the note. The field, given one string, is not.

Combo @ 6% of the pool is 62.2% / 49.2% — the filter's ceiling —
against hybrid 91.1% / 91.2%. It does not beat both.

Write-up: `docs/trec_condition_baseline.md`. JSON:
`data/trec/trec_condition_baseline.json`.

### What would reverse it

A conditions match — still one disease term, still no trial text
to an LLM — coming within 3 points of hybrid at matched depth on
both years. A synonym list that closed the 11–13 point gap would
be a different method, not this baseline.

---

## 2026-09-30 — Reranking the shortlist is not earning itself

**Decision: stop. Do not ship a reranker. Do not start a reader
or a trained ranker from this lift.**

Gates committed in **44878a7** before any score. 2023 not run.
Shortlist = keyword hybrid, top 6%. Arms: MedCPT-CE, MS MARCO
MiniLM-L-12, `gpt-4o-mini` (2021, top 200, raw note), and the
unre-ranked hybrid. Query: keywords and raw note on the
cross-encoders. Documents: 512-token `[title, body]` truncation.
Chunk-and-max skipped (MedCPT truncated pass was 74 minutes on
an A10; the written start budget was 25 minutes).

| 2021 arm | R@10 eligible | NDCG@10 | P@10 eligible |
|---|---:|---:|---:|
| Hybrid (no rerank) | 5.7% | 39.9% | 28.5% |
| `gpt-4o-mini` raw, top 200 | **9.0%** | 51.0% | 38.4% |
| MedCPT-CE keywords | 8.2% | 49.3% | 36.9% |
| MedCPT-CE raw note | 8.1% | 47.8% | 34.8% |
| MS MARCO keywords | 4.2% | 29.7% | 22.8% |
| MS MARCO raw note | 3.0% | 25.5% | 18.9% |

Best 2021 Recall@10 is 9.0%, below doubling (11.4%) and below
17%. Full-shortlist recall stayed 91.6% / 91.4% on every
cross-encoder arm.

The medical cross-encoder beat the generic one. The raw note
did not beat keywords. Both were the open questions from
retrieval, and both land the other way here.

Write-up: `docs/trec_rerank.md`. JSON:
`data/trec/trec_rerank_results.json`.

### What would reverse it

A reranker — same shortlist, same years, no 2023 — with 2021
eligible Recall@10 above 17%, full-depth recall still 91.6% /
91.4%. Below 11.4% the stop stands.

---

## 2026-10-01 — The shortlist is 91% junk; cheap fusion does not clean it

**Decision: do not replace unweighted RRF. Do not start a reader
from this.**

Task 1 gates **697d808**. The 144 / 91% guess holds.

| 2021, mean of 1,570 | Count | Share |
|---|---:|---:|
| Eligible (2) | 67 | 4.3% |
| Excluded (1) | 73 | 4.7% |
| Judged not relevant (0) | 143 | 9.1% |
| Unjudged for this patient | 1,287 | 82.0% |
| Disease-relevant (1+2) | 140 | 8.9% |
| Junk (0 + unjudged) | 1,430 | 91.1% |

Excluded recall at 6% is 92.1%, eligible 91.6%. Retrieval does
not distinguish "right disease, cannot join" from "can join."
The leftover is unjudged-for-this-patient, clustered on generic
keywords.

Tasks 2 and 3 gates **c178dc4**. Best official 2021 Recall@10
**6.3%** (IDF + section), from 5.7%, under +3 points. Full
shortlist recall stayed 91.6% / 91.4%. Full-collection IDF
probe dropped it to 89.8% / 90.1% and is rejected.

Write-up: `docs/trec_shortlist_diagnosis.md`,
`docs/trec_shortlist_fix.md`.

### What would reverse it

A reorder of this same shortlist, no discards, 2021 Recall@10
at least 8.7%, full-depth still 91.6% / 91.4%. A new first
stage that raises Recall@10 without dropping 6% recall would
be a different method and would need its own gates.

### What would reverse it

A later lookup of these same 5,578 phrases — not a new extraction —
reaching ≥60% occurrence coverage **and** ≥90% name-agreement
precision, without replacing gene-symbol matching. Below 60% the
six-name system stays. Between 60% and 85% would have been partial
(literal-phrase fallback for the miss share). Neither happened.

---

## 2026-10-01 — Cheap topical pass does not earn a pipeline slot

**Decision: do not filter the 1,570. Do not run full scale. Do not
start the per-criterion reader from this.**

Gates `b3431c6`, before any keep/drop score. 30 patients, seed
20261001, 2021/2022 only. Question: could this trial conceivably be
about this patient's problem? Unsure keeps.

No candidate hit both ≥90% disease-relevant recall and ≤50%
retention.

| Arm | Best recall | Best retention at that point | Gate |
|---|---:|---:|---|
| Lexical first keyword | 63.5% | 20.0% | reject recall |
| MedCPT-CE, logit > 0 | 13.0% | 1.7% | reject recall |
| Qwen2.5-7B | 96.6% | 61.7% | fail retention |
| gpt-4o-mini | 88.7% | 50.7% | mixed recall |

Mini with an eligibility-slice keeps 41.7% (retention clears) at
86.0% recall (still mixed). Qwen with the slice is 92.6% / 51.5%.
A KEEP-only probe (unsure drops; not the gate) gets retention down
to 23–32% and recall to 79–85%. Still no joint window.

MedCPT-CE at logit > 0 keeps almost nothing. A threshold sweep
finds no cut that hits both bars. Extra trial text does not open
one. The 110M encoder is not a free topical filter on this
shortlist.

Hosted mini was run. The reader's 10.8% wrongly-discarded figure
was not used as a reason to skip it.

Cost on the sample: mini **$2.61**; Qwen on an A100 SXM about
**$1.53**; A10 for CE (and a failed Qwen start) under a dollar.
Wall-clock is in `docs/trec_cheap_pass.md`.

The question is not mis-posed. Qwen keeps 97% of disease-relevant
rows from title+conditions. The two bars cannot be met together.

### What would reverse it

A keep/drop on this same 30-patient sample, 2021/2022 only, with
disease-relevant recall ≥90% **and** retention ≤50%, measured
before seeing a new operating point. Changing the unsure-keeps
rule after seeing scores is not a reversal; it is a new gate.

---

## 2026-10-01 — Shallow-depth recall hid the first page; three stops are three different mistakes

**Decision: keep the original gates on disk. Do not treat the 17%
recall@10 stop as a physical impossibility, and do not flip
reranking to a pass. Fusion still failed the first page. Cheap-pass
retention stays a cost finding, not a 10-in-20 finding.**

Recompute from stored rankings. No new run. 2023 not touched.
Write-up: `docs/trec_precision.md`.

2021 eligible-trial counts: mean 74.3, **median 62**, min 6, max 203.
One patient has fewer than 10 eligible trials; nine have fewer than
20. 2022: mean 78.8, median 59.5, min 10, max 306.

Recall@10 ceiling, mean of per-patient min(1, 10/n): **24.7%** (2021),
not 10/76 = 13%. Precision@20 ceiling: **95.1%**. Will's 50% of 20 is
52.6% of that ceiling — almost 50% of perfect. The mean-n error was
on recall, not precision.

Product bar (≥10 eligible in top 20), 2021, 75 patients, possible
for 74/75:

| Arm | Patients meeting the bar |
|---|---|
| Keyword hybrid | **9/75** |
| Best rerank (`gpt-4o-mini` top 200) | **22/75** |
| MedCPT-CE keywords | 20/75 |
| MS MARCO keywords | 9/75 |

Best rerank: 3.8 eligible in 10, 7.6 in 20. Hybrid: 2.9 and 5.2.
“9.0% recall ≈ 7 of 10” was mean-recall × mean-n. The on-disk P@10
was already 38%.

Three stops, three kinds:

1. **Reranking.** The 17% recall@10 gate sits *below* the real
   ceiling (24.7%), so it was not impossible. It was the wrong
   target. On the product bar the stage still fails (22/75, 30% of
   those for whom 10-in-20 is possible). Do not flip to a pass.
2. **Weighted fusion + section ranking.** +3 recall points was
   achievable and stiff. Stored P@10 does not move (28.5% → 28.4%).
   Genuine fail on the first page.
3. **Cheap pass.** 50% retention was a cost sketch. On the 30-patient
   sample the first page barely moves (hybrid 6/30 at 10-in-20; mini
   slice 7/30; CE as a filter hurts). Reader-cost finding stands;
   it is not a 10-in-20 finding.

Aggregation: macro mean of per-patient precision, plus the patient
count for the product bar. Fusion per-patient lists were not saved,
so 10-in-20 is not scored for those arms.

### What would reverse the product reading of rerank

On these same 75 2021 patients, a reorder of the existing shortlist
that puts ≥10 eligible trials in the top 20 for a large majority of
the 74 for whom that is possible. 22/75 is not that.






---

## 2026-10-01 — Qwen was never tested as a reranker; the free preview says it should be

**Decision: run Qwen2.5-7B as a scoring reranker on the full shortlist,
with a continuous score, against `gpt-4o-mini` extended to the same
depth. Do not put Qwen in the pipeline on the strength of this preview.**

### The gap

Qwen2.5-7B was run once, in the cheap-pass experiment, and asked a
**keep / unsure / drop** question. That is a filter. It was never asked
a scoring question, so the reranking run compared `gpt-4o-mini` and two
cross-encoders and left the free model out of the stage where the paid
model won. That is an omission in the experiment design, not a result.

### What was recomputed

No run. The three existing labels were sorted into blocks — keep, then
unsure, then drop — ties broken by the fused rank, on the 30-patient
cheap-pass sample. `scripts/trec_qwen_preview.py`,
`docs/trec_qwen_preview.md`.

Equivalent depth, as a multiple of the baseline's own equivalent depth
at the same N (the baseline row is calibration: plateaus in its recall
curve make every arm look negative if read against N):

| Arm | 2021 @500 | 2022 @500 |
|---|---:|---:|
| `gpt-4o-mini` top 200 | 1.00x (capped) | not run |
| MedCPT-CE keywords | **0.93x** | 0.95x |
| MedCPT-CE raw note | 1.05x | 1.24x |
| Qwen three buckets | **1.90x** | 1.39x |
| Qwen three buckets + slice | 1.75x | **1.49x** |

Qwen is the only arm still working at depth 500. MedCPT-CE on keywords
is *worse than not reordering*. `gpt-4o-mini`'s 1.00x is by
construction — it scored 200 trials and past that it is the baseline.

Qwen loses at depths 10 and 20, as three buckets predict: hundreds of
trials tie inside `keep` and fall back to fused order.

### Why this changes the reading of the reranking run

The original run measured the paid model only where it was strong — the
top 200. Qwen, handicapped to three buckets and asked the wrong
question, beats it everywhere past depth 100. The conclusion "the cheap
paid model is the best reranker" was an artefact of the depth each arm
was given.

It does not reverse the product stop. 22/75 on the 10-in-20 bar stands.

### What the next run must separate

A continuous score should raise the **shallow** numbers, by breaking
ties inside the keep block. It should *not* be expected to raise the
depth-500 numbers, where the win already comes from block separation.
If the write-up credits a continuous score with the deep win, that is a
misattribution.

### Open question this preview raises

Reranking exists only because the eligibility read was assumed
expensive. If Qwen can judge eligibility directly on all 1,570 trials
for a few dollars, a separate topical reranking stage has no purpose —
the eligibility judgement is itself the ranking, which is what TrialGPT
does. That has not been tested and should be tested before the
reranking stage is built out.

### What would reverse this

A continuous-score Qwen run on all 125 patients that does not beat
`gpt-4o-mini` at the same depth. 15 patients per year and three buckets
is a reason to run the test, not a result.

---

## 2026-10-01 — Qwen topical scoring earns a slot; a single eligibility score does not delete it

**Decision: keep a topical reordering stage. Default ranker is
Qwen2.5-7B, title+conditions+800-char eligibility slice, continuous
0–3 score. Do not delete that stage in favour of a single cheap
eligibility score. Do not start Run 3 from this entry. Do not start
the per-criterion reader from this.**

Gates were committed in `114cce7` before any 0–3 score. 2023 not
touched. Shortlist stays 1,570 / 1,595.

### What ran

- Qwen topical 0–3 on all 125 patients, two documents, digit and
  continuous. Same scale wording as `trec_rerank_llm.py`.
- `gpt-4o-mini` extended to the full shortlist, both years, same
  prompt and `trial_article[:1200]` as the original arm. $8.996.
  Reused the 2021 top-200 scores.
- Qwen eligibility 0–3 on full criteria, 30-patient sample (seed
  20261001). Cut from 125 because the remaining GPU time projected
  past the 8-hour budget. 47,475 pairs, not 197,500.
- A100 SXM4, 6.36 hours, ~$12. No OOM.

### Run 1 (all 125) — equivalent depth at 200

| Arm | 2021 | 2022 |
|---|---:|---:|
| baseline | 1.00x | 1.00x |
| mini_full | 2.01x | 2.41x |
| Qwen title+cond, continuous | 2.39x | 2.32x |
| **Qwen slice, continuous** | **2.73x** | **2.77x** |
| MedCPT-CE raw | 1.33x | 1.31x |

Best topical is **≥ 1.20×** on 2021 and **≥ 1.10×** on 2022. The
stage earns a slot. MedCPT-CE is still below 1.10× at 500 (0.92×
on 2021): it fades, as before.

P@20, 2021: baseline 26.0%, mini 38.0%, Qwen slice continuous
**47.9%**. 10-in-20: 9/75 → 23/75 (mini) → **37/75**. Product bar
still fails (74 possible).

Continuous vs digit, slice, P@20: +5.4 points on 2021, +3.1 on
2022. The continuous-score bet wins at the page. Depth 200/500
barely moves, as the gate said it should not be credited.

Mini vs Qwen at 200: mini / Qwen = 2.01 / 2.73 = **0.74**. Mini
does not keep the stage. Extending it past 200 *did* beat the
stitched 1.00× of the original top-200 run. Qwen is still better.

### Run 2 vs Run 1 (matched 30-patient sample)

| Arm | 2021 @200 | 2022 @200 | 2021 P@20 | 2022 P@20 |
|---|---:|---:|---:|---:|
| best topical (slice) | 2.41x | 2.24x | 44.3% | 53.3% |
| best eligibility (continuous) | 2.16x | 1.86x | **48.7%** | **58.0%** |

Eligibility is **2.16×** baseline at 200 on 2021 — not ≤ 1.05× —
so a single score *can* rank. It loses the reader budget to
topical on both years. It wins P@20 by more than 3 points on both
years. That is the written **split**. Do not delete.

Run 2 read the full criteria and still lost at 200, so this is
not "more text won." The eligibility question is the better first
page and the worse 200-deep list.

### What this does not decide

- Fine-tuning Qwen. That is Run 3, still a go/no-go (~$14).
- Whether a per-criterion read would rank better than either
  single score. The cheap score is not the wrong instrument; it
  just does not beat topical at the reader budget.
- The product bar. 37/75 is not 74/75.

---

## 2026-10-01 — Qwen topical scoring earns a slot; a single eligibility score does not delete it

**Decision: keep a topical reordering stage. Default ranker is
Qwen2.5-7B, title+conditions+800-char eligibility slice, continuous
0–3 score. Do not delete that stage in favour of a single cheap
eligibility score. Do not start Run 3 from this entry. Do not start
the per-criterion reader from this.**

Gates were committed in `114cce7` before any 0–3 score. 2023 not
touched. Shortlist stays 1,570 / 1,595.

### What ran

- Qwen topical 0–3 on all 125 patients, two documents, digit and
  continuous. Same scale wording as `trec_rerank_llm.py`.
- `gpt-4o-mini` extended to the full shortlist, both years, same
  prompt and `trial_article[:1200]` as the original arm. $8.996.
  Reused the 2021 top-200 scores.
- Qwen eligibility 0–3 on full criteria, 30-patient sample (seed
  20261001). Cut from 125 because the remaining GPU time projected
  past the 8-hour budget. 47,475 pairs, not 197,500.
- A100 SXM4, 6.36 hours, ~$12. No OOM.

### Run 1 (all 125) — equivalent depth at 200

| Arm | 2021 | 2022 |
|---|---:|---:|
| baseline | 1.00x | 1.00x |
| mini_full | 2.01x | 2.41x |
| Qwen title+cond, continuous | 2.39x | 2.32x |
| **Qwen slice, continuous** | **2.73x** | **2.77x** |
| MedCPT-CE raw | 1.33x | 1.31x |

Best topical is **≥ 1.20×** on 2021 and **≥ 1.10×** on 2022. The
stage earns a slot. MedCPT-CE is still below 1.10× at 500 (0.92×
on 2021): it fades, as before.

P@20, 2021: baseline 26.0%, mini 38.0%, Qwen slice continuous
**47.9%**. 10-in-20: 9/75 → 23/75 (mini) → **37/75**. Product bar
still fails (74 possible).

Continuous vs digit, slice, P@20: +5.4 points on 2021, +3.1 on
2022. The continuous-score bet wins at the page. Depth 200/500
barely moves, as the gate said it should not be credited.

Mini vs Qwen at 200: mini / Qwen = 2.01 / 2.73 = **0.74**. Mini
does not keep the stage. Extending it past 200 *did* beat the
stitched 1.00× of the original top-200 run. Qwen is still better.

### Run 2 vs Run 1 (matched 30-patient sample)

| Arm | 2021 @200 | 2022 @200 | 2021 P@20 | 2022 P@20 |
|---|---:|---:|---:|---:|
| best topical (slice) | 2.41x | 2.24x | 44.3% | 53.3% |
| best eligibility (continuous) | 2.16x | 1.86x | **48.7%** | **58.0%** |

Eligibility is **2.16×** baseline at 200 on 2021 — not ≤ 1.05× —
so a single score *can* rank. It loses the reader budget to
topical on both years. It wins P@20 by more than 3 points on both
years. That is the written **split**. Do not delete.

Run 2 read the full criteria and still lost at 200, so this is
not "more text won." The eligibility question is the better first
page and the worse 200-deep list.

### What this does not decide

- Fine-tuning Qwen. That is Run 3, still a go/no-go (~$14).
- Whether a per-criterion read would rank better than either
  single score. The cheap score is not the wrong instrument; it
  just does not beat topical at the reader budget.
- The product bar. 37/75 is not 74/75.
---

## 2026-10-02 — Eligibility prompt v2 did not raise true positives

**Decision: do not replace the v1 eligibility prompt. Keep the
stored `elig_full_cont` arm as the eligibility score. Do not
start Run 3 from this entry. Do not start the per-criterion
reader from this.**

Gates were committed in `4424157` before any v2 score. Same 30
patients (seed **20261001**), same shortlist, same Qwen2.5-7B,
full criteria. Prompt and scoring both changed: written CHECK,
then `eligible` / `ineligible` / `unsure`, rank by P(eligible).
Not a matched model comparison. The question was whether joinable
trials (label 2) rose on the first page.

### What ran

47,475 pairs. Started on A100 (3 patients), finished on H100
PCIe batch 8. About 7 hours of scoring time across both cards.
H100 attach poller copied 47,475 scores and terminated via the
API.

### Against the committed gate

| | v1 continuous | v2 P(eligible) |
|---|---:|---:|
| 2021 P@20 | **48.7%** | 34.0% |
| 2022 P@20 | **58.0%** | 38.3% |
| 2021 10-in-20 | **7/15** | 5/15 |
| 2022 10-in-20 | **9/15** | 5/15 |
| 2021 @200 | 2.16x | 1.16x |
| 1-vs-2 AUROC | 0.745 | 0.60 |

2021 P@20 is **below** 48.7% and 10-in-20 did not rise. That is
the written **do not replace** row. Unsure was 35-39% of judged
1+2 (not the >50% dump). The word "eligible" hit 224/958 label-2
pairs on 2021 and 233/1085 on 2022. Most pairs were called
ineligible.

The stricter prompt made the model pickier, not more accurate
on the page. v1 stays the eligibility score if we need one.
Topical slice continuous remains the default ranker.

---

## 2026-10-02 — GPT-5.4 beats Qwen on 1-vs-2; the TREC prompt does not help

**Decision: there is a real model-size gap (AUROC 0.83 vs 0.72).
Do not adopt the TREC-worded prompt. If a fine-tune is tried
later, use human TREC labels, not GPT answers.**

411 judged pairs, prompts and IDs in `99f795c` before any score.
GPT-5.4 $1.75. Qwen TREC run on an A10, ~$0.23. Total about $2.
P@20 was not computed.

GPT-5.4 AUROC 0.828 / 0.829 on v1 and TREC. Qwen v1 0.722.
Qwen TREC 0.647. Both models said “not relevant” on ~170–190
of the 411 pairs under the TREC prompt. Details:
`docs/trec_frontier_elig.md`. The system does not say a
patient qualifies.

---

## 2026-10-02 — Untrained eligibility beats topical; first LoRA collapsed

**Decision: the 0.749 untrained v1 number on all 50 2022
patients is the result. Do not treat the first adapter’s 0.700
as a measurement of fine-tuning. Prompt format matched; the
scoring harness with the adapter off is what produced 0.749;
the second loss curve was never copied. The first run parked
on the coin-flip loss 0.693.**

Whether a lower learning rate can train without collapsing is
still open. Whether eligibility should replace the topical
slice as the default ranker is a separate decision (first page
vs depth 200 vs cost). Details: `docs/trec_lora_elig.md`.
The system does not say a patient qualifies.
