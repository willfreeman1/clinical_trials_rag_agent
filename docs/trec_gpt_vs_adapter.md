# GPT-5.4 vs the trained 7B, same 2022 pairs

Locked in `6f7bc99` before any new model call. Same 6,249
patient–trial pairs as the **0.779** figure: every trial on the
2022 shortlist that humans marked “could join” or “right
disease, a rule fails.” All 50 patients. Not 2021. Not 2023.

The question was the old eligibility question, the one that
asks whether the person appears to meet the stated criteria
and answers with 0, 1, 2, or 3. Not the wording that dumped
answers into “not relevant.” The ranking number is the
expected digit from the model’s token probabilities.

210 of the pairs already had that score from the earlier
411-pair run. Those were reused. The other 6,039 were new.
**$11.27.** No errors. Spend cap was $20.

This is not a first-page score. It does not say how many good
trials land in the top 10. It is not an overall accuracy. It
is not a decision that a person qualifies.

## What AUROC means here

Pick one trial humans said this person could join, and one
they said they could not (same kind of disease, a rule fails).
How often does the computer’s number put the first trial
above the second? 0.50 is a coin flip. 1.00 is never wrong.
Intervals redraw **patients**, not pairs.

## The numbers

| Model | AUROC | 95% patient interval |
|---|---:|---:|
| GPT-5.4 | **0.821** | 0.785–0.852 |
| Trained 7B, seed 20261003 | 0.793 | 0.748–0.835 |
| Trained 7B, seed 20261007 | 0.773 | 0.727–0.815 |
| Trained 7B, seed 20261006 | 0.770 | 0.723–0.815 |
| Trained 7B, mean of those three | **0.779** | — |
| Same 7B, no training | 0.749 | — |
| GPT-5.4 on the old 411-pair slice | 0.828 | — |

GPT’s point is **four points above 0.779** and in line with
the old 0.83. The 411-pair sample was not a fluke.

Each model’s own interval is wide, because 50 patients is 50
patients. GPT’s interval still includes 0.779. That is why
the fair test is a **paired** one: redraw the same patients
and subtract.

GPT minus the average of the three trained scores, same
patient draws: **+0.038** (0.012–0.068). Zero is outside.
Against the best of the three seeds: **+0.028** (0.003–0.054).
Zero is outside that too.

So: on these pairs, GPT-5.4 sorts the hard judgement more
cleanly than the trained 7B. The gap is real and modest. It
is not a different sport.

## What this does not say

- It does not replace the trained 7B as the default ranker.
  That decision also needs a first-page score (how many good
  trials in the top 10). That run is the other cheap option
  (~$3–10) and is not started.
- It does not say GPT is better at “same disease.” That was
  not asked.
- It does not say anyone qualifies.

Live tracking run `gpt54_vs_adapter_2022` (not retrofitted).

The system does not say a patient qualifies.
