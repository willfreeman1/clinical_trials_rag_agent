# Eligibility prompt vs topical slice, and a first LoRA attempt

The headline from this session is not the adapter. **Asking Qwen
about eligibility, with no fine-tuning, separates joinable from
excluded trials better than the current topical ranker on a full
held-out year.** Combining the scores we already had bought
nothing. Changing the question bought about seven points.

Splits, pair IDs, the v1 prompt, and the first training settings
were committed in `2f04bfa` before any adapter. Train is the 60
patients from 2021 who are not in the 30-patient evaluation
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

## Headline: untrained eligibility vs everything we already had

A logistic regression on the stored topical, mini, MedCPT, and
retrieval-rank scores, fit on the 60 training patients, reached
**0.686** AUROC on the 50 2022 patients. The current default
ranker — Qwen topical slice — was **0.682**. Combining the old
signals did not beat the ranker we already have. Eligibility v1
could not be a feature in that control: those scores only existed
for the 30-patient sample.

Base Qwen with the v1 eligibility prompt was then scored on this
H100, on every judged 1 and 2 on the shortlist, **before any
adapter**, with the same scoring script later used for the
adapter and with the adapter switched off.

| | Patients | Excluded (1) | Joinable (2) | AUROC pooled | AUROC per-patient mean | Topical slice on the same pairs |
|---|---:|---:|---:|---:|---:|---:|
| Tuning set (2021 sample) | 15 | 1,282 | 958 | **0.755** | 0.749 | 0.687 |
| **Held-out 2022** | **50** | 2,635 | 3,614 | **0.749** | 0.722 | **0.682** |

The eligibility prompt already beats the current default by about
seven points on the full held-out year. The 0.759 seen earlier on
15 of these 2022 patients was not a fluke. The 0.72 on the
411-pair cap was a bit low for this prompt.

GPT-5.4’s 0.83 remains a different sample (411 capped pairs) and
is not recomputed here.

Word calls on the 50-patient test: 875 zeros, 25 ones, 4,384 twos,
965 threes. The model still piles on “2” (the old middle).

Whether this prompt should replace the topical slice as the
default ranker is a separate decision. It wins here on
joinable-versus-excluded, and it won on the first page in Run 2,
but it lost at depth 200 and it reads the full criteria, so it
costs more. That comparison is not made in this write-up.

## The first adapter is not a measurement of fine-tuning

Pairwise training: 4,782 within-patient comparisons from the 60
training patients (2,382 joinable-vs-excluded, 1,200
joinable-vs-not-relevant, 1,200 excluded-vs-not-relevant). v1
prompt, LoRA rank 16, one pass, learning rate 1e-4.

The adapter that was scored answered **1 on 6,248 of 6,249** 2022
pairs. Continuous scores sat around 0.99. Balanced accuracy was
0.500. That is a degenerate output, not a weak learner. A model
that had learned something small would still spread its answers.

On the 15 tuning patients, pooled AUROC was 0.704 (below the
base 0.755) while the per-patient mean was **0.773** (above the
base 0.749). Within a patient the ordering partly survived;
comparability across patients is what died. That pattern vanished
on 2022, so it is not a result. It is a hint that some signal
reached the model and was then drowned.

Those numbers are **not** a finding that “fine-tuning on the
human labels does not help.” They are a finding that this
adapter collapsed.

## Three checks on the collapse

**1. Prompt format, training vs scoring.** The system text is
the same 795 characters in the training script, the scoring
script, and `ELIG_SYSTEM_DIGIT`. The helpers that build the user
string match. Both sides wrap the same two roles in Qwen’s chat
template with `add_generation_prompt=True` and left-pad. This
was the main suspected setup bug. It is not the cause.

**2. The second run’s loss curve.** It is not on disk. Only the
first run’s log was copied off (`lora_train_log.json`, expected
digit, 2,079 seconds). The fallback run wrote
`lora_train_log_b.json` on the rented machine and that file was
not copied before terminate. We cannot tell from a log whether
that adapter trained. We can see its outputs, which collapsed.

The first run’s own curve is a warning on its own. Loss started
near 0.40, sat on **0.6931** (the pairwise loss when the two
trials get the same score: −log(1/2)) for 14 of 60 logged steps,
including the last four, and ended there. That is the collapse
happening during training, not only at eval.

**3. Scoring path without an adapter.** The 0.749 number was
produced by `lambda_qwen_lora_score.py` with `--adapter` empty —
the same script that later scored the adapter. Re-running that
on a GPU would cost money and would repeat a measurement already
in hand. The harness, with the adapter off, is what reported
0.749. The problem is not that the scoring script cannot
reproduce the base model.

So the remaining ordinary cause was a learning rate high enough
to push the adapter onto one answer. That is what the next run
tested.

## Second run: same setup, tenth the rate, raw 2-minus-1 score

Settings committed in `2f83393` before this adapter. Same
splits, same prompt, same comparison mix. Scalar is the raw
score for token **2** minus token **1**, before softmax.
Learning rate **1e-5**. The 15 tuning patients were scored at
the start, at 25%, and at 50%. The loss log was written as it
went and copied off the machine.

It did not collapse. Loss fell from about 1.14 to 0.22 and
never sat on 0.693. The typical win-minus-lose gap on the
tuning patients started at 2.27, was 1.20 at 25% (still more
than half the start), and 1.70 at 50%. Answers stayed spread
across 0 / 1 / 2. 2022 was scored once, at the end.

| | AUROC pooled | Per-patient mean |
|---|---:|---:|
| Untrained v1 (same 50 patients) | 0.749 | 0.722 |
| Tuning set at the start of this run | 0.756 | — |
| Tuning set at 25% | 0.780 | — |
| Tuning set at 50% | 0.778 | — |
| Tuning set after the full pass (labelled as such) | 0.834 | 0.837 |
| **Held-out 2022, 50 patients** | **0.793** | **0.798** |

On 2022 the words were 973 zeros, 4,074 ones, 1,202 twos. That
is a shift toward “excluded,” not a pin on a single token.
Continuous scores ran from 0.03 to 1.98.

The 0.834 on the 15 tuning patients is the set we watched
during training. It is not the headline. The headline for this
adapter is **0.793 on 2022**, which is above the untrained
0.749 on the same pairs.

GPT-5.4’s 0.83 is still a different sample (411 capped pairs).
This run does not recompute that.

## Cost

First session: H100 SXM5, **about $7**. Second session: H100
SXM5, 1.04 hours, **$4.48**. Both instances were terminated
through the API. The second loss log is on disk
(`data/trec/lora_train_log.json`).

No first-page rescore. No 2022-train / 2021-test swap.

## What is and is not decided

Decided: the untrained v1 eligibility score is **0.749** on all
50 2022 patients against **0.682** for the topical slice and
**0.686** for a logistic on the stored signals. Changing the
question bought seven points.

Decided: a LoRA on the human labels, at 1e-5 with the raw
2-minus-1 score, **does** move joinable-versus-excluded on the
held-out year, to **0.793**. The first adapter’s 0.700 was a
broken setup, not a measurement of fine-tuning.

Not decided: whether eligibility should replace the topical
slice as the default ranker (first page vs depth 200 vs cost).
Not decided: the other-way fold (train 2022, test 2021).

The system does not say a patient qualifies.
