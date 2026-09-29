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

| Method | Same-trait pairs linked (of 29) | Different-trait pairs linked (of 25) |
|---|---:|---:|
| Embeddings | **6.9%** (2) | **4.0%** (1) |
| MeSH | 3.5% (1) | 0% (0) |
| Combined | **10.3%** (3) | **4.0%** (1) |

Against the gate: wrong-link ≤ 5% **cleared**; correct-link ≥ 85% **not cleared**, by a
wide margin.

The script nominated MeSH as "best" because it sorts by lowest wrong-link first. That is
misleading: MeSH almost never links anything. The method the design actually specified is
**combined**, and that is the row to quote.

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
2. **UMLS was not tried.** The plan allowed half a day and then embeddings only. MeSH
   downloaded and parsed in minutes, so the dictionary arm was tested. What failed is
   the connection from drug to class, not the install.

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

## 2026-09-29 — Spike 2 Step 5a: the marker trait is the strong filter, and it justifies continuing

**Decision: the cheap step is still worth building. Do not label the other
three traits until Will approves the ~$10.** The marker trait alone throws out
**23.9%** of trials on average — above the 18.2% per-trait figure that would
make six traits reach 70% if they were all this strong. Combined with the two
already-labelled traits, a perfect filter throws out **39.9%** of the corpus
(the 40% floor, with three traits not six). The six-trait projection moves
from 51.7% to **63.8%**, which is toward 70% and is the plan's test for
whether the remaining labelling is justified.

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
