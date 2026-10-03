# Fine-tuning Qwen on the human TREC labels

Splits, pair IDs, the v1 prompt, and the training settings were
committed in `2f04bfa` before any adapter was trained. Train is
the 60 patients from 2021 who are not in the 30-patient evaluation
sample. The 15 held-out 2021 patients are the tuning set. Test is
all 50 patients from 2022. 2023 was not touched.

This is not a first-page ranking. **Precision at 20 was not
computed** and should not be compared to the earlier tables.

**AUROC** here means: if you pick one human-joinable trial (label
2) and one human-excluded trial (label 1: right disease, a rule
fails), how often does the model give the joinable one the higher
“looks eligible” score? 0.50 is a coin flip. 1.00 is a perfect
sort.

The system does not say a patient qualifies.

## What was already on disk, before any GPU

A logistic regression on the stored topical, mini, MedCPT, and
retrieval-rank scores, fit on the 60 training patients, reached
**0.686** AUROC on the 50 2022 patients. The current default
ranker — Qwen topical slice, no eligibility question — was
**0.682**. Combining the old signals did not beat the ranker we
already have. Eligibility v1 could not be a feature in that
control: those scores only existed for the 30-patient sample.

## Base Qwen, v1 eligibility prompt, no adapter

Scored on this H100 session, on every judged 1 and 2 on the
shortlist, before any training.

| | Patients | Excluded (1) | Joinable (2) | AUROC pooled | AUROC per-patient mean | Topical slice on the same pairs |
|---|---:|---:|---:|---:|---:|---:|
| Tuning set (2021 sample) | 15 | 1,282 | 958 | **0.755** | 0.749 | 0.687 |
| **Held-out 2022** | **50** | 2,635 | 3,614 | **0.749** | 0.722 | **0.682** |

The eligibility prompt already beats the current default, by about
seven points on the full held-out year. The 0.759 seen earlier on
15 of these 2022 patients was not a fluke. The 0.72 on the 411-pair
cap was a bit low for this prompt; on every judged 1 and 2 it is
about **0.75**.

GPT-5.4’s 0.83 remains a different sample (411 capped pairs) and
is not recomputed here.

Word calls on the 50-patient test: 875 zeros, 25 ones, 4,384 twos,
965 threes. The model still piles on “2” (the old middle), same
shape as before.

## The adapter

Pairwise training: 4,782 within-patient comparisons from the 60
training patients (2,382 joinable-vs-excluded, 1,200
joinable-vs-not-relevant, 1,200 excluded-vs-not-relevant). v1
prompt, LoRA rank 16, one pass, loss on the usual 0–3 expected
digit.

That first run’s loss went the wrong way (early steps about 0.51,
late steps about 0.63). The fallback scalar — raw score for token
“2” minus token “1” — was trained next. That adapter was the one
scored on the tuning set and, once, on 2022.

| | AUROC pooled | Per-patient mean | Balanced accuracy |
|---|---:|---:|---:|
| Adapter on the 15 tuning patients | 0.704 | 0.773 | 0.500 |
| **Adapter on 50 2022 patients** | **0.700** | 0.711 | 0.500 |

On 2022 the adapter answered **1 on 6,248 of 6,249 pairs** and 2
on one pair. The continuous scores sat in a tight band around
0.99. That is a collapse, not a ranker. Balanced accuracy 0.50 is
the coin-flip you get when every trial is called “excluded.”

The 60 training patients were not rescored. A model that says
“1” on both held-out sets is not a memorization-of-2021 story
worth another GPU pass.

Label-0 trials were not scored with the adapter. With every
disease-relevant trial already pinned to 1, junk sorting is not
something this adapter can be trusted to keep.

Spot checks of “wrong no” on joinable trials are not informative
here: the adapter said no to almost every pair, including ones
the base model and the humans called joinable. That is not the
old “stricter than the assessor, fact on the page” pattern. It
is a broken output.

## Cost actually spent

H100 SXM5, us-south-2, 1.63 hours, **about $7**. Scores and the
fallback adapter were copied off. The instance was terminated
through the API. The local launcher then failed on a leftover
`touch` (the path was eaten by the SSH quoting). That did not
lose the files.

No first-page rescore. No 2022-train / 2021-test swap.

## Did fine-tuning move the gap?

**No. Do not keep the adapter.**

On the 50 held-out 2022 patients:

- Current default (topical slice): **0.682**
- Logistic on stored scores: **0.686**
- Base Qwen, v1 eligibility, no adapter: **0.749**
- This LoRA: **0.700**, and it collapsed to a single word
- GPT-5.4 on the older 411-pair sample: **0.83**

The useful finding from the GPU session is the base number, not
the adapter. Asking Qwen about eligibility, without fine-tuning,
already beats the topical ranker on joinable vs excluded. Fine-tuning
on the human labels, with this setup, made that worse.

The 0.11 gap to GPT-5.4 is still there. This run did not close it.

The system does not say a patient qualifies.
