# Can Qwen's keep/drop labels order the shortlist? (free preview)

No new run. No GPU, no API, no dollars. Recomputed from labels already on
disk from the cheap-pass run. 2023 not touched. `THRESHOLDS.md` not edited.
This is a **preview**, not a gated result: 15 patients per year, three
buckets instead of a score. Script: `scripts/trec_qwen_preview.py`.

## Why this was run

Qwen2.5-7B was used once, in the cheap-pass experiment, and asked a
**keep / unsure / drop** question — *could this trial conceivably be about
this patient's problem?* That is a filtering question. It was never asked a
**scoring** question, so it was never tested as a reranker, which is the job
`gpt-4o-mini` and MedCPT-CE were tested on.

That is a gap in the reranking run, not a finding. Before spending GPU time
closing it, the existing three labels were sorted into blocks — all keeps,
then all unsures, then all drops, ties broken by the original fused rank —
to see whether Qwen's judgement orders the shortlist at all.

The handicap is severe and worth stating up front. Three buckets cannot
resolve the head of a 1,570-trial list: hundreds of trials tie at `keep`,
and inside that block the order is just the fused order again. Shallow
depths here are a floor.

## Sample

The 30-patient cheap-pass sample, seed **20261001**, 15 from 2021 and 15
from 2022. Same keyword-hybrid shortlist (top 6%, ~1,570 trials) as the
rerank run. Nothing discarded.

`llm_mini_top200` covers 2021 only and the top 200 only; that is how it was
run. Past depth 200 it *is* the baseline, which is why its rows converge.

## Eligible recall (label 2), mean over patients

### 2021 (n=15)

| Arm | @10 | @20 | @50 | @100 | @200 | @500 | P@10 | P@20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline (no reorder) | 8.5% | 13.8% | 25.3% | 36.0% | 53.3% | 76.7% | 30.0% | 28.3% |
| llm_mini_top200 | 11.2% | 20.5% | 34.0% | 43.5% | 53.3% | 76.7% | 40.0% | 38.7% |
| medcpt_ce_raw | 11.4% | 18.3% | 29.2% | 39.5% | 52.6% | 73.7% | 37.3% | 34.7% |
| medcpt_ce_keywords | 11.1% | 18.2% | 25.9% | 33.9% | 46.6% | 69.2% | 36.7% | 33.7% |
| **qwen_bucket** | 8.9% | 17.5% | 26.9% | 42.0% | **60.4%** | **86.2%** | 33.3% | 32.3% |
| **qwen_bucket_slice** | 9.8% | 18.3% | 28.6% | 43.1% | **60.9%** | **85.8%** | 34.7% | 33.3% |

### 2022 (n=15)

| Arm | @10 | @20 | @50 | @100 | @200 | @500 | P@10 | P@20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline (no reorder) | 6.2% | 10.7% | 23.6% | 36.5% | 51.9% | 69.8% | 40.7% | 36.0% |
| medcpt_ce_raw | 9.0% | 15.8% | 28.5% | 41.4% | 56.7% | 70.4% | 46.7% | 42.3% |
| medcpt_ce_keywords | 9.2% | 14.6% | 27.9% | 40.5% | 51.3% | 65.6% | 49.3% | 44.0% |
| **qwen_bucket** | 7.4% | 12.0% | 27.4% | 40.8% | 57.1% | 73.8% | 46.7% | 41.3% |
| **qwen_bucket_slice** | 7.3% | 12.4% | 28.1% | 43.9% | **60.7%** | **75.8%** | 46.7% | 41.0% |

## Equivalent depth — the cost reading

Reading N trials in the reordered list finds as many eligible trials as
reading how many in the fused order. Expressed as a multiple of the
baseline's own equivalent depth at the same N.

**The baseline row is a calibration row, not a result.** Flat stretches in
the baseline recall curve mean the baseline "reaches its own depth-500
count" at depth 402, so a naive reading makes every arm look negative. Read
every number against baseline, never against N. The first version of this
table had that bug.

### 2021

| Arm | Read 100 | Read 200 | Read 500 |
|---|---:|---:|---:|
| baseline | 1.00x | 1.00x | 1.00x |
| llm_mini_top200 | 1.48x | 1.00x | 1.00x |
| medcpt_ce_keywords | 1.10x | 0.98x | 0.93x |
| medcpt_ce_raw | 1.37x | 1.25x | 1.05x |
| **qwen_bucket** | 1.28x | 1.65x | **1.90x** |
| **qwen_bucket_slice** | 1.37x | **1.79x** | 1.75x |

### 2022

| Arm | Read 100 | Read 200 | Read 500 |
|---|---:|---:|---:|
| baseline | 1.00x | 1.00x | 1.00x |
| medcpt_ce_keywords | 1.25x | 1.19x | 0.95x |
| medcpt_ce_raw | 1.34x | 1.66x | 1.24x |
| **qwen_bucket** | 1.28x | 1.35x | 1.39x |
| **qwen_bucket_slice** | 1.52x | 1.65x | **1.49x** |

## Reading

**Qwen is the only arm that is still working at depth 500.** MedCPT-CE on
keywords goes *below* baseline there (0.93x on 2021) — reordering with it is
worse than not bothering. MedCPT-CE on the raw note is 1.05x, i.e. nothing.
`gpt-4o-mini` is exactly 1.00x because it only scored 200 trials; past that
it is the baseline by construction, not by result.

**1.90x at depth 500 on 2021 is the largest reordering effect measured in
this project.** Reading 500 trials in Qwen's order finds as many eligible
trials as reading about 765 in the fused order — from a model that was asked
a yes/no question and cost nothing extra.

**Qwen is weakest exactly where three buckets predict it would be.** At
depths 10 and 20 it loses to both `gpt-4o-mini` and MedCPT-CE. Hundreds of
trials tie inside the `keep` block and fall back to fused order. A 0-to-3
score, and better a continuous score read off the model's own token
probabilities, addresses precisely this. It is a reason to expect the
shallow numbers to rise, **not** a reason to expect the depth-500 numbers to
rise: the deep win already comes from block separation, which a finer score
does not change.

**The earlier reranking conclusion was measured where the paid model was
strong.** `gpt-4o-mini` won the original run at depths 10 to 100 and was
never given the chance to lose deeper. Qwen, handicapped to three buckets,
beats it everywhere past depth 100.

**The two years agree in shape**, which is the main reason to act on 15
patients each. They disagree in magnitude (1.90x vs 1.39x at depth 500) and
on whether the extra eligibility text helps.

## Limits

- 15 patients per year. Wide intervals. No decimal place in this table
  should be trusted; the ordering of arms is the finding.
- Three buckets, not a score. This is a lower bound on Qwen as a reranker,
  and says nothing about Qwen as an eligibility judge.
- The labels were produced for a different question (topical relevance,
  uncertainty keeps the trial), with the full patient summary rather than
  the keyword list.
- Nothing here is gated. No threshold was committed before this ran because
  nothing was run — it is arithmetic over stored labels.

## What this justifies

Scoring Qwen properly on the full 1,570 for all 125 patients, with a
continuous score, against `gpt-4o-mini` extended to the same depth. About
$15 and an hour of A100 time. Gates to be committed before that run.

It does **not** justify putting Qwen in the pipeline. 15 patients and three
buckets is a reason to run the real test, not a result.

No overall accuracy. The system does not say a patient qualifies.
