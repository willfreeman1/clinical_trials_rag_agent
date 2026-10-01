# Cheap topical pass on the shortlist (2021/2022 only)

Gates committed in `b3431c6` before any keep/drop score.
30-patient sample, seed **20261001** (15 from 2021, 15 from 2022).
2023 was not run. This is not the reader. Full criteria was not the
default document text.

Question: **could this trial conceivably be about this patient's
problem?** Uncertainty keeps the trial.

**No candidate cleared both bars. Full scale was not run.** The
1,570-trial shortlist is unchanged. Nothing else in the pipeline
discards trials.

## Gates

- Disease-relevant recall (TREC labels 1+2 on the existing shortlist)
  **≥90%** to ship; below **80%** the candidate is rejected.
- Retention **≤50%** of the 1,570 / 1,595.
- Winner: among those that clear both, lowest retention, then lowest
  cost. If none clear both, do not run full scale.

Why these numbers: losing 10% of disease-relevant trials here leaves
end-to-end eligible recall 91.6% × 90% ≈ 82%. That is the most this
pass may eat of the retrieval win. Keeping more than half the
shortlist still leaves about $5.50 of reading and does not earn a
pipeline slot.

Wilson 95% intervals on n=30. No overall accuracy. The system does
not say a patient qualifies.

## Sample result

Micro = all disease-relevant shortlist trials in the 30 patients
pooled. Eligible column is label 2 only.

| Candidate | Doc text | Disease-relevant recall | Eligible recall | Retention | Gate |
|---|---|---:|---:|---:|---|
| Lexical, first keyword | title+conditions | 63.5% | 71.1% | 20.0% | reject recall |
| MedCPT-CE, logit > 0 | title+conditions | 7.2% | 8.3% | 0.9% | reject recall |
| MedCPT-CE, logit > 0 | +800 chars eligibility | 13.0% | 13.2% | 1.7% | reject recall |
| MedCPT-CE, logit > 0 | 512-token title+body | 9.7% | 9.4% | 1.4% | reject recall |
| Qwen2.5-7B | title+conditions | **96.6%** | 97.5% | 61.7% | fail retention |
| Qwen2.5-7B | +800 chars eligibility | **92.6%** | 96.4% | 51.5% | fail retention |
| gpt-4o-mini | title+conditions | 88.7% | 93.5% | 50.7% | mixed recall |
| gpt-4o-mini | +800 chars eligibility | 86.0% | 93.2% | **41.7%** | mixed recall |

Patients with ≥90% disease-relevant recall (n=30, Wilson 95%):

| Candidate | Doc | k/30 | Wilson |
|---|---|---:|---|
| Qwen2.5-7B | title+conditions | 27 | 74–97% |
| Qwen2.5-7B | +slice | 22 | 56–86% |
| gpt-4o-mini | title+conditions | 17 | 39–73% |
| gpt-4o-mini | +slice | 13 | 27–61% |
| Lexical | title+conditions | 10 | 19–51% |
| MedCPT-CE (any) | — | 0 | 0–11% |

## Cost and wall-clock

| Arm | What was billed | Per patient on this sample |
|---|---|---|
| Lexical | nothing | 0.2s, $0 |
| MedCPT-CE | A10 scoring, ~16 min of forwards | ~5–18s depending on doc text |
| Qwen2.5-7B | A100 SXM 40GB, ~46 min instance at $1.99/hr ≈ **$1.53**. Scoring 15 min then 26 min | ~30s / ~52s |
| gpt-4o-mini | **$2.61** for 30 patients × two doc variants ($0.087 / patient for both) | ~1–2 min wall with 8 concurrent workers |

The A10 that first tried Qwen was stopped after an OOM; CE scores
were copied off first. Hosted mini one-timeout restart; completed
from the saved file.

## What extra context buys

Title+conditions is enough to see the trade. Adding the opening 800
characters of eligibility:

- Qwen: recall 96.6% → 92.6%, retention 61.7% → 51.5% (still over 50%).
- Mini: recall 88.7% → 86.0%, retention 50.7% → 41.7% (now under 50%, still under 90% recall).

The slice helps the model drop junk. It also drops some
disease-relevant trials. Full criteria was not run. The 512-token
body truncation did not rescue MedCPT-CE.

The conditions field alone was previously 62% eligible recall as a
retriever. As a **filter on the hybrid shortlist**, first-keyword
loose match keeps 20% and recalls 63.5% of disease-relevant rows —
same hole (synonyms, parent conditions, second problems), now on a
set that already mixed in generic-keyword junk.

## MedCPT-CE: committed point and sweep

Keep-if-logit-**> 0** was committed before seeing scores. Almost
every pair scores far below zero (title+conditions: median −11.6,
0.9% of pairs > 0). That operating point is not a topical filter
here.

A sweep is not the gate. No threshold hits both bars. Closest on
title+conditions: logit > −12 is 89.5% recall and 56.7% retention.
At 50% retention (around −11.5) recall is 85%. Extra eligibility
text shifts scores more negative and does not open a joint window.

Rerank failure does not explain this. Ordering by eligibility and
separating other-disease junk are different jobs; on this job the
110M encoder still has no usable keep/drop cut.

## Qwen and mini: unsure is the pile

Committed rule: KEEP / DROP / UNSURE, and unsure keeps.

| Model | Doc | keep | unsure | drop |
|---|---|---:|---:|---:|
| Qwen2.5-7B | title+conditions | 13,066 | 16,222 | 18,187 |
| Qwen2.5-7B | +slice | 11,153 | 13,314 | 23,008 |
| gpt-4o-mini | title+conditions | 15,120 | 8,947 | 23,408 |
| gpt-4o-mini | +slice | 14,229 | 5,585 | 27,661 |

Qwen's unsure mass is why 97% recall still keeps 62% of the list.
Mini is less unsure and closer to the box, but 88.7% is the mixed
band, not ship.

A **probe** (not the gate): count only KEEP, treat unsure as drop.

| Probe | Recall | Retention |
|---|---:|---:|
| Qwen, title+conditions, KEEP only | 85.2% | 27.5% |
| Qwen, +slice, KEEP only | 82.5% | 23.5% |
| Mini, title+conditions, KEEP only | 84.0% | 31.8% |
| Mini, +slice, KEEP only | 79.3% | 30.0% |

Retention clears. Recall does not. The two bars do not have a joint
operating point on this sample for these models, with or without the
unsure-keeps rule.

Mini's reader failure (10.8% wrongly discarded) was not used as a
reason to skip this arm. It was run. It is the closest, and it still
misses 90% recall.

## Is the question mis-posed?

No. Qwen can keep 97% of the disease-relevant shortlist from title
and conditions, using the patient summary rather than the generic
keyword list. The models are answering the easy question. The
committed pair of bars — lose at most 10% of those trials, and cut
the list in half — is what they cannot satisfy together. Tightening
the question would be a different pass and would need its own gates.

End-to-end eligible recall if one of these shipped anyway (retrieval
91.6%/91.4% times this pass's eligible recall, 2021 / 2022):

- Qwen title+conditions: about 91% / 86%
- Mini title+conditions: about 88% / 81%

Those are not a ship. They show the recall is there if retention were
the only bar.

## Decision

Do not put a cheap topical pass in the pipeline. Do not run full
scale. Do not start the per-criterion reader from this. The shortlist
stays 1,570 / 1,595.

Per-patient JSON: `data/trec/cheap_pass_results.json`.
No overall accuracy. The system does not say a patient qualifies.
