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
