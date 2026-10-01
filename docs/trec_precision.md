# Precision, ceilings, and the 10-in-20 bar (2021/2022 only)

Recomputed from stored shortlists and scores. No new retrieval, GPU, or API run.
2023 was not touched. Original gates in `THRESHOLDS.md` are not edited.

Aggregation is the **macro mean of per-patient precision**: each patient is one
screening job. Micro-averaging would let patients with 200 eligible trials
dominate. The number that matches the product requirement is not that mean;
it is a **count of patients** with at least 10 eligible trials in the top 20.

## Eligible trials per patient (the distribution, not the mean)

Label 2 in the judged pool. This is independent of any ranker.

- **2021** (n=75): mean 74.3, median 62.0, min 6, p10 14.4, p25 36.5, p75 113.0, p90 142.2, max 203
- **2022** (n=50): mean 78.8, median 59.5, min 10, p10 13.9, p25 25.0, p75 116.8, p90 145.6, max 306

2021 patients with fewer than 10 eligible trials: **1/75**. Fewer than 20: **9/75**.
2022: **0/50** under 10, **10/50** under 20.

Will's bar (≥10 eligible in a top 20) is even possible for **74/75** patients in 2021 and **50/50** in 2022. The rest do not have 10 gold
eligible trials at all. Retrieval then leaves **74/75** (2021) and **49/50** (2022) with at least 10 eligible
inside the 6% shortlist — the most a reranker of that shortlist can show.

Disease-relevant (labels 1+2) 2021: mean 154.5, median 153.0, min 13, p10 50.0, p25 78.0, p75 207.5, p90 268.8, max 351.
2022: mean 139.5, median 116.0, min 14, p10 29.9, p25 57.5, p75 191.8, p90 305.0, max 398.

The mean of 76 would have been a reasonable headline for 2021. It still hides
the tails. Do not convert a mean recall into a count by multiplying by 76.
That is how “9.0% recall@10 ≈ 7 of 10” was obtained, and it is not what
macro-recall times mean-n equals. **Mean eligible hits in the top 10 is
already on disk as P@10 × 10.** For keyword hybrid that is 2.9 of 10, not 7.

## Ceilings, per patient then averaged

Recall ceiling at depth k is min(1, k / n_eligible). Precision ceiling is
min(1, n_eligible / k). Average after, not before.

| Year | Depth | Mean recall ceiling | Mean precision ceiling | Naive 10-or-20 / mean-n |
|---|---:|---:|---:|---:|
| 2021 | 10 | 24.7% | 99.5% | 13.5% |
| 2021 | 20 | 41.4% | 95.1% | 26.9% |
| 2021 | 50 | 73.5% | 83.6% | 67.3% |
| 2022 | 10 | 28.4% | 100.0% | 12.7% |
| 2022 | 20 | 46.0% | 93.2% | 25.4% |
| 2022 | 50 | 72.2% | 78.0% | 63.5% |

2021 recall@10 ceiling is **not** 13%. 13% is 10/76. The mean of per-patient
ceilings is higher because 1/n is convex and because some patients have few
eligible trials (ceiling 100%). The triple-recall gate of 17% sits **below**
the real 2021 recall@10 ceiling — so that gate was not physically impossible.
It was still the wrong target: it asked for a share of a long tail, not for
what a coordinator sees on the first page.

Precision@20 ceiling is **95.1%** in 2021, not ~85%. Only 9/75 patients have
fewer than 20 eligible trials, so the “ceiling is far below 100%” worry is a
five-point effect here, not a fifteen-point one. Will's 50% of 20 is therefore
**52.6% of the mean achievable P@20**, which is almost the same as 50% of
perfect. The dangerous conversion was on **recall** (13.5% naive vs 24.7%
real), not on precision.

## Ranking configurations (full 2021 / 2022)

Counts are mean eligible (label 2) or disease-relevant (1+2) in the top N.
Share is macro P@N. “Of ceiling” is mean(P / P_ceiling) per patient.

### 2021 (75 patients)

| Arm | elig@10 | P@10 | of ceil | elig@20 | P@20 | of ceil | elig@50 | P@50 | rel@10 | rel@20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| kw_hybrid | 2.85 | 28.5% | 28.5% | 5.20 | 26.0% | 27.2% | 11.65 | 23.3% | 5.97 | 11.01 |
| llm_raw_top200 | 3.84 | 38.4% | 38.5% | 7.56 | 37.8% | 39.9% | 16.60 | 33.2% | 7.27 | 13.85 |
| medcpt_ce_keywords | 3.69 | 36.9% | 36.9% | 6.71 | 33.5% | 35.2% | 13.76 | 27.5% | 7.11 | 12.88 |
| medcpt_ce_raw | 3.48 | 34.8% | 34.9% | 6.56 | 32.8% | 34.5% | 14.43 | 28.9% | 6.99 | 12.91 |
| msmarco_ce_keywords | 2.28 | 22.8% | 22.8% | 4.13 | 20.7% | 21.3% | 9.25 | 18.5% | 4.12 | 7.55 |
| msmarco_ce_raw | 1.89 | 18.9% | 18.9% | 3.27 | 16.3% | 16.8% | 6.53 | 13.1% | 3.56 | 6.49 |

### 2022 (50 patients)

| Arm | elig@10 | P@10 | of ceil | elig@20 | P@20 | of ceil | elig@50 | P@50 | rel@10 | rel@20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| kw_hybrid | 3.86 | 38.6% | 38.6% | 7.22 | 36.1% | 37.4% | 15.74 | 31.5% | 5.92 | 11.16 |
| medcpt_ce_keywords | 5.08 | 50.8% | 50.8% | 9.16 | 45.8% | 47.7% | 18.36 | 36.7% | 7.12 | 13.34 |
| medcpt_ce_raw | 4.82 | 48.2% | 48.2% | 8.04 | 40.2% | 42.0% | 17.24 | 34.5% | 6.74 | 12.22 |
| msmarco_ce_keywords | 2.64 | 26.4% | 26.4% | 4.76 | 23.8% | 24.8% | 10.72 | 21.4% | 3.88 | 7.36 |
| msmarco_ce_raw | 1.36 | 13.6% | 13.6% | 2.50 | 12.5% | 13.2% | 5.34 | 10.7% | 2.56 | 4.64 |

## The product bar: ≥10 eligible in the top 20

2021 is the 75-patient set the requirement was stated on. 2022 is the other
admission-note year. Cheap-pass arms were only scored on the 30-patient sample;
they are in a later section, not mixed into 75.

| Year | Arm | Patients with ≥10 eligible in top 20 | Possible (n_elig ≥ 10) | Of those possible |
|---|---|---:|---:|---:|
| 2021 | kw_hybrid | 9/75 | 74/75 | 12.2% |
| 2021 | llm_raw_top200 | 22/75 | 74/75 | 29.7% |
| 2021 | medcpt_ce_keywords | 20/75 | 74/75 | 27.0% |
| 2021 | medcpt_ce_raw | 18/75 | 74/75 | 24.3% |
| 2021 | msmarco_ce_keywords | 9/75 | 74/75 | 12.2% |
| 2021 | msmarco_ce_raw | 7/75 | 74/75 | 9.5% |
| 2022 | kw_hybrid | 13/50 | 50/50 | 26.0% |
| 2022 | medcpt_ce_keywords | 24/50 | 50/50 | 48.0% |
| 2022 | medcpt_ce_raw | 18/50 | 50/50 | 36.0% |
| 2022 | msmarco_ce_keywords | 6/50 | 50/50 | 12.0% |
| 2022 | msmarco_ce_raw | 1/50 | 50/50 | 2.0% |

Wilson 95% on 2021 keyword-hybrid meet rate: 12.0% [6.4%, 21.3%] (n=75).
Best 2021 rerank (`llm_raw_top200`): 29.3% [20.2%, 40.4%] (n=75).

## Weighted fusion and section ranking

Weighted-fusion / section arms did not persist per-patient ranked lists. P@20, P@50, and the 10-in-20 bar cannot be reconstructed without re-running fusion. Stored P@10 and recall@k are copied here.

Stored P@10 eligible (already computed at the time; not a new run):

| Year | Arm | P@10 eligible | Recall@10 | Recall@20 |
|---|---|---:|---:|---:|
| 2021 | baseline | 28.5% | 5.7% | 10.7% |
| 2021 | idf_rrf | 27.3% | 5.6% | 10.5% |
| 2021 | bm25_sum | 28.5% | 6.3% | 10.8% |
| 2021 | section_mult | 29.3% | 6.2% | 11.4% |
| 2021 | section_tie | 28.5% | 5.7% | 10.7% |
| 2021 | idf_section | 28.4% | 6.3% | 11.3% |
| 2021 | probe_idf_full | 27.3% | 5.6% | 10.5% |
| 2022 | baseline | 38.6% | 7.4% | 13.3% |
| 2022 | idf_rrf | 41.4% | 8.3% | 13.5% |
| 2022 | bm25_sum | 38.0% | 7.0% | 12.6% |
| 2022 | section_mult | 39.8% | 7.7% | 13.7% |
| 2022 | section_tie | 38.6% | 7.4% | 13.3% |
| 2022 | idf_section | 41.8% | 8.6% | 13.3% |
| 2022 | probe_idf_full | 41.4% | 8.3% | 13.5% |

P@10 barely moves. Baseline 2021 is 28.5%; best official (`idf_section`) is
28.4%. The +3-point **recall** gate was a different unit from the first page.
The 10-in-20 bar cannot be scored for these arms without re-running fusion.

## Cheap pass (30-patient sample only)

These arms **filter** the hybrid shortlist, then the remaining trials keep
hybrid order. Top 20 after a filter is “the first 20 survivors,” not a new
ranker. Sample seed 20261001, 15+15.

| Arm | n | elig@10 | P@10 | elig@20 | P@20 | ≥10 in top 20 | possible |
|---|---:|---:|---:|---:|---:|---:|---:|
| cheap_hybrid_sample | 30 | 3.53 | 35.3% | 6.43 | 32.2% | 6/30 | 30/30 |
| cheap_lexical_title_cond | 30 | 3.97 | 39.7% | 7.23 | 36.2% | 8/30 | 30/30 |
| cheap_ce_title_cond | 30 | 2.57 | 25.7% | 3.30 | 16.5% | 2/30 | 30/30 |
| cheap_ce_title_cond_slice | 30 | 2.97 | 29.7% | 4.13 | 20.7% | 4/30 | 30/30 |
| cheap_ce_title_body_512 | 30 | 2.63 | 26.3% | 3.43 | 17.2% | 2/30 | 30/30 |
| cheap_qwen_title_cond | 30 | 3.57 | 35.7% | 6.60 | 33.0% | 6/30 | 30/30 |
| cheap_qwen_title_cond_slice | 30 | 3.80 | 38.0% | 6.87 | 34.3% | 6/30 | 30/30 |
| cheap_mini_title_cond | 30 | 3.93 | 39.3% | 7.27 | 36.3% | 7/30 | 30/30 |
| cheap_mini_title_cond_slice | 30 | 4.13 | 41.3% | 7.37 | 36.8% | 7/30 | 30/30 |

If a cheap pass only drops the tail, the first page does not move. If it drops
junk that sat in the top 20, P@20 rises. Retention and first-page quality are
different questions — that is why a 50% keep rule was the wrong gate for this
product bar.

## Is precision the right lens?

For “of 20 shown, 10 eligible,” **yes**, and the honest form is the patient
count, not mean P@20. Mean precision still hides patients with 5 eligible
trials (who can never hit 10 in 20) and patients with 200 (who pull the mean).

Recall@k is the wrong gate when k is far below n_eligible. It is still the
right gate for the first stage at 6% of the collection, where the list is
long enough to hold almost every eligible trial. Do not use one number for
both jobs.

Disease-relevant hits (labels 1+2) are reported because an excluded trial
is still a coordinator glance. They are not the product bar. Will asked for
eligible.

## Which conclusions change

Three different mistakes. They do not share a verdict.

### 1. Reranking — wrong gate, not an automatic pass

2021 mean recall@10 ceiling is 24.7%, so 17% was
achievable in principle. It was still the wrong target. The conversion
“9.0% of a 13% ceiling ≈ 7 of 10” is false. Keyword hybrid puts
**2.9 eligible in the top 10** (P@10 28.5%,
28.5% of the precision ceiling). Best rerank
(`llm_raw_top200`) puts **3.8 in 10**
(P@10 38.4%, 38.5% of ceiling)
and **7.6 in 20**.

Product bar, 2021, 75 patients: hybrid 9/75 have ≥10
eligible in the top 20 (possible for 74/75).
Best rerank: 22/75
(of possible, 29.7%).
That is a lift, not a pass on “at least 10 of 20 for a coordinator.”
The 17% recall stop should be retired as misspecified. The product stop
**does not flip**. MS MARCO still hurts the first page.

### 2. Weighted fusion + section ranking — still a genuine fail on the first page

The +3-point recall@10 gate was achievable (ceiling 24.7%,
target 8.7%). Stored P@10 does not move (28.5% baseline → 28.4% best official).
A coordinator reading ten sees the same list. Real fail, different kind:
the method did not change the page. 10-in-20 was not persisted; unchanged
P@10 is enough to say it would not have cleared Will's bar.

### 3. Cheap pass — 50% retention was arbitrary; the first page is mixed

Retention is a reader-cost sketch, not a product number. On the 30-patient
sample, unfiltered hybrid already has **6/30** with ≥10 eligible in top 20
(mean 6.4 eligible in 20). Mini + slice is 7/30 (7.4 in 20). Lexical is 8/30.
Qwen is unchanged at 6/30. MedCPT-CE as a filter **hurts** the first page
(2–4/30) because logit > 0 drops eligible trials out of the head. A 50%
keep rule would not have distinguished those outcomes. The 90%/50% joint
window is still true as a **reader-cost** statement. It is not the 10-in-20
statement. None of these filters puts 10 eligible in the top 20 for most
patients. Do not promote a cheap pass from retention or from a one-patient
lift on this sample.

JSON: `data/trec/trec_precision.json`. No overall accuracy.
The system does not say a patient qualifies.

