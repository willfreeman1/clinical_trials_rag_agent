# Frontier-model baseline on eligibility judging

Pair list and prompts were committed in `99f795c` before any new
score. Same 30 patients (seed **20261001**). Up to 7 joinable and 7
excluded trials per patient (pair seed **20261002**). **411 pairs**
that humans already labelled: 201 **excluded** (right disease, a
rule fails) and 210 **eligible** (joinable). 2023 was not touched.

This is not a first-page ranking. **Precision at 20 cannot be
computed** here and should not be compared to the earlier P@20
tables.

**AUROC** here means: if you pick one human-joinable trial and one
human-excluded trial, how often does the model give the joinable
one the higher “looks eligible” score? 0.50 is a coin flip. 1.00
is a perfect sort.

**Balanced accuracy** is the average of “got excluded right” and
“got joinable right,” so the 201/210 split does not tilt it. For
the TREC-label prompt, a lot of answers were **0 (not relevant)**.
Those are *not* counted in balanced accuracy, which only looks at
answers that were 1 or 2. The 0s are reported separately.

The system does not say a patient qualifies.

## Cost actually spent

- GPT-5.4: **$1.75** (636,914 input tokens, 10,680 output). Token
  probabilities were available on the v1 digit.
- Qwen TREC prompt: A10, 0.18 hours, about **$0.23**. Scoring time
  374 seconds after setup. 411 scores copied off; instance
  terminated through the API.
- Qwen v1: reused the stored scores. **$0**.
- **Total about $2.**

## 2 × 2

| | v1 prompt (0–3; if unsure, choose 2) | New TREC-label prompt (0 / 1 / 2 + P(eligible)) |
|---|---|---|
| **GPT-5.4** | AUROC **0.828**. Balanced accuracy 78.3%. Called excluded on 61/210 joinable. Called eligible on 29/201 excluded. Never said 0. | AUROC **0.829**. Balanced accuracy 77.8% *among the 1/2 answers*. Called excluded on 23/210 joinable. Called eligible on 25/201 excluded. Said **not relevant on 173/411** (116 excluded + 57 joinable). |
| **Qwen2.5-7B** | AUROC **0.722**. Balanced accuracy 60.4%. Called excluded on 15/210 joinable. Called eligible on **145/201** excluded (the old middle pile). | AUROC **0.647**. Balanced accuracy 59.2% among 1/2 answers. Called excluded on 38/209 joinable. Called eligible on 41/199 excluded. Said not relevant on **192/408**. Three pairs did not parse. |

GPT’s two prompts sort 1 vs 2 about the same (0.83). The new
prompt does not help Qwen; it makes Qwen worse, same pattern as
eligibility prompt v2.

## Does the confidence number mean anything?

On the TREC prompt, **yes, at the high end, for GPT.** When
GPT-5.4 said P(eligible) ≥ 0.75, the human label was joinable
**85%** of the time (129 such calls). When it said ≤ 0.25, the
human label was excluded **69%** of the time (253 calls). So a
loud “yes” is fairly trustworthy; a loud “no” is weaker, partly
because many “nos” are really “not relevant / I am not sure.”

On v1, both models pile high scores: GPT marked 353/411 pairs as
high, and only 58% of those were joinable. That number is not a
useful yes.

## Spot checks of wrong “no” on joinable trials

These are pairs humans marked eligible (2) and the model marked
excluded (1). The excluding fact was in the note.

- **NCT00554996** (2021 patient 13). The trial bars “obstructive
  urolithiasis.” The note says a **non-obstructing** stone in the
  left ureter. GPT-5.4 (both prompts) and Qwen’s TREC run all
  said excluded. A picky reading of “obstructive” vs
  “non-obstructing” can explain the no. The humans still called
  it joinable.
- **NCT01138566** (same patient). The trial wants a
  community-onset UTI caused by Enterobacteriaceae and bars
  complete obstruction. The note has recurrent UTIs, a
  suprapubic catheter, and a non-obstructing stone. GPT said
  excluded with P(eligible) 0.05. The organism is not clearly
  named as Enterobacteriaceae in the opening of the note. This
  one may be missing a required fact, or the humans treated the
  history of UTIs as enough.

Same shape as before: some “wrong nos” are the model being
stricter than the assessor, with the fact on the page.

## Is there enough of a gap to try a fine-tune?

**Yes, as a model-size gap. No, as a prompt-gap.**

GPT-5.4’s AUROC is **0.83** on both prompts. Qwen’s best cell is
the old v1 score at **0.72**. That is about **0.11** — not a coin
flip, and not a tie. A stronger model sees 1 vs 2 more cleanly
than the 7B model does.

The new TREC wording did not close that gap. Both models used
“not relevant” as a dump (173 and 192 times) on pairs humans had
already called 1 or 2. Do not build on that prompt.

If a fine-tune is tried later, train on the **human TREC labels**,
not on GPT-5.4’s answers. This run is a measured baseline only.
The system does not say a patient qualifies.
