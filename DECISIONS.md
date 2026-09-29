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
