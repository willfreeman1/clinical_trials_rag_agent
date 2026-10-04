# How this system would stay current

This is a design document. Nothing in it is implemented
except the MLflow tracking setup described at the end.
No new scores, no GPU, no frontier labels.

It answers a question an employer will ask: once the
trials and the diseases move, how would you know the
system is still doing the job, and what would you retrain
on?

**A drift alarm is not a quality measurement.** The
signals below can fire when the world changed. They
cannot say the model got worse. Those are different
claims. Conflating them is the kind of thing a reviewer
catches.

The system does not say a patient qualifies.

## 1. Detecting change when there are no labels

In production there are no expert verdicts on each new
patient–trial pair. Quality cannot be measured directly.
What can be measured with no labels at all:

| Signal | What it is | Why it might move |
|---|---|---|
| Eligibility-score distribution | The mix of 0–3 scores, or of the continuous expected-digit, on incoming pairs | A shift toward 0 or toward 3 means the model is seeing a different mix, or answering differently |
| “Not enough information” rate | How often the model refuses a digit, dumps “not relevant,” or the quote-checker rejects the write-up | A climb is the model meeting notes or criteria it cannot ground |
| Unseen vocabulary | Drug names, interventions, and biomarkers that never appeared in training text | New products and new assays arrive every month |
| Disease mix | The categories of incoming patients against the spread of the 125 benchmark patients | A clinic that starts sending a disease the 125 never covered |
| Guardrail reject rate | How often the quote-verification check refuses a judgement because the cited sentence is not in the trial | The reader is inventing more, or the trial text shape changed |

Each of those is a **drift alarm**. It says “look.” It
does not say “the AUROC fell.” The AUROC, and every
other quality number in this repository, needs human
labels. Those labels do not exist on the live stream.

Do not put a pass/fail on an alarm and call it a
quality gate. The shipping gate is the frozen
benchmark, below.

## 2. 2023 is the worked example

This is not a hypothetical. The 2023 TREC year was new
territory, the project measured it, and the project
stopped.

2021 and 2022 topics are 5–10 sentence admission notes.
2023 topics are sparse questionnaire fields
(`definitive diagnosis: yes`, `visual acuity: 20/50`).
Mean eligible trials per 2023 topic: **315** (median
273). 2021 / 2022 means were about 74 / 79.

First-stage eligible recall at 6% of the judged
collection:

| Year | Recall at 6% | What the topics are |
|---|---:|---|
| 2021 | 91.6% | Admission notes |
| 2022 | 91.4% | Admission notes |
| 2023 | **65.4%** | Questionnaire fields |

The written gate was the worst year, and 70% was the
floor. 2023 is below it. Hybrid still beat both single
retrievers; keywords still beat the raw fields. The
architecture was not broken. The task changed.

That is the monitoring question arising and being
answered correctly: a measurable shift, no pretend that
the pipeline handled it, no 2023 ranking or reader
built on a 65% first stage. The same instinct applies
in production. An alarm that the notes look like 2023
is a reason to stop and measure, not a reason to keep
shipping 2021 numbers.

## 3. The frozen benchmark is the shipping gate

The 75 + 50 held-out patients, with their human
labels, become a permanent regression test.

Any candidate model — retrained, distilled, a new
prompt, a new cutoff — is scored on the **same
patients** with the **same measures**. It is rejected
if it does worse than the model currently in use, on
the measure that model was chosen for.

| What is being replaced | Gate, on the frozen patients |
|---|---|
| First-stage retriever | Eligible recall at 6% of the judged collection, 2021 and 2022. Floor is the current hybrid (91.6% / 91.4%). |
| Default ranker (topical slice) | Official-style P@10 and graded NDCG@10, both years, with patient-resampled intervals. |
| Eligibility adapter | Held-out 2022 1-versus-2 AUROC. Current mean **0.779 (0.770–0.793)** across three seeds. Quote the mean and the spread, not the best seed. |
| Cascade cutoff | Pre-registered paired P@10 against the topical slice, on a year that cutoff was not swept. |

This never requires trusting a frontier model as a gold
standard for the shipping decision. The gold standard
is the human labels already on disk.

A candidate can look better on a drift alarm and still
fail this gate. That is the point of keeping them
apart.

## 4. Where new labels come from

Stated in order of preference. Do not skip a higher
row because a lower one is cheaper.

1. **Human expert verdicts**, where they exist. TREC
   2021 and 2022 already gave 71,226 of these. They
   remain the training and test labels for anything
   that claims quality.
2. **Real feedback from coordinators actually using
   the system.** A coordinator who discards a
   suggested trial, or who opens one, is a weak label.
   It is still a human, on the live mix. None of that
   exists yet. The system is not deployed.
3. **Frontier-model labels**, only for territory
   neither of the above covers, **tagged as such in
   the training data** so every example remembers
   whether a human or a model wrote the label.

Establishing that a frontier model can stand in for
human assessors is a **research programme, not a
feature**. GPT-5.4 reached **0.83** AUROC on telling
joinable from excluded, on 411 judged pairs from the
30-patient sample. That is good. It is a different and
smaller sample than the 0.779 figure. It is not a gold
standard. The monitoring design does not rest on it.

## 5. Distillation — designed, not run

**Distillation** here means: train the 7B adapter on
labels written by a larger model, then test it on
human labels it has never seen.

The argument runs both ways. This project has not
tested it. `HANDOFF.md` §5.5 used to say distillation
is strictly worse than learning from the assessors.
That was reasoning, not a measurement. The file now
says so.

### For

GPT-5.4 (0.83, 411-pair sample) is better than the
fine-tuned 7B mean (0.779, all 50 of 2022). 82% of
each shortlist was never judged by experts, so
frontier labels could supply tens of thousands of
extra examples. Label noise is often tolerable when
it is random. GPT-5.4’s confidence values carry more
information than a bare yes/no: when it said
P(eligible) ≥ 0.75, the expert verdict was joinable
**85%** of the time (129 such calls).

### Against

The errors are systematic, not random. GPT-5.4 was
consistently stricter on specific patterns — a
“non-obstructing” stone against a trial that bars
“obstructive” disease; an organism not named as the
required family. Random noise averages out with more
data. Correlated noise gets learned. The plausible
failure is a model that faithfully reproduces the
teacher’s decision boundary, including its repeatable
disagreements with experts.

### The test the existing data already makes possible

Not run. Cost crosses the $25 ask-first line.

1. Label several thousand of the **never-judged 2021**
   pairs with GPT-5.4. Keep the confidence values, not
   just the verdict.
2. Fine-tune a LoRA on those labels, same setup as
   the human-label adapter (r=16, α=32, 1e-5, seed
   recorded).
3. Test against the **held-out 2022 expert verdicts**,
   joinable versus excluded.
4. Compare with **0.779 (0.770–0.793)** on the
   identical test.

Also specify the **hybrid** variant, which is the
actual production design: expert labels where they
exist, frontier labels for the 82% that were never
judged. That tests “what happens when expert labels
run out” inside data already in hand.

| Scale | Labelling | Fine-tune + score | Total |
|---|---:|---:|---:|
| 5,000 pairs | ~$22 (about $0.004 per pair, the observed GPT-5.4 rate) | ~$5 + ~$3 | **~$30** |
| 10,000 pairs | ~$44 | ~$8 | **~$50** |

Both cross $25. Do not start either from this
document.

### Three outcomes

| Result on held-out 2022 AUROC | What it would mean |
|---|---|
| Above 0.779, interval clear of the current mean | Distillation works. A documented project assumption was wrong. |
| About the same | Volume compensated for noise. Useful, not a win. |
| Below 0.779, interval clear the other way | The systematic bias transferred. Distillation is not free data. |

A result is only a result if the split, the pair IDs,
and the comparison are committed before the first
frontier label is written.

## 6. What this is not

- Not a decision that anyone qualifies.
- Not a licence to treat GPT-5.4 as the assessor.
- Not a 2023 ranking or reader.
- Not a reason to skip the frozen-benchmark gate
  because a drift alarm is quiet, or to ship because
  an alarm is loud.

## 7. Experiment tracking (set up, history backfilled)

**MLflow** is a self-hosted experiment tracker: each
run stores its settings, its metrics, and a pointer
at the files it produced. The **model registry** is
the shelf of trained adapters, with one marked as
the one in use.

It was added after the TREC scoring, not before.
The history in it was **retrofitted** from JSON
already on disk and from the tables in `docs/`. Live
use starts with the reader. An interviewer who asks
“did you use this from day one?” gets that answer.

The frozen-benchmark shipping gate will live on the
registry later: a candidate is registered, scored on
the same patients, and promoted or rejected in the
tool, not only in a markdown file.

```
pip install -r requirements.txt
set PYTHONIOENCODING=utf-8
python scripts/mlflow_backfill.py
python -m mlflow ui --backend-store-uri file:./mlruns --port 5000
```

The backfill is reproducible. `mlruns/` is not
committed; it is built from this repository plus
`data/trec/` when that folder is present.

The system does not say a patient qualifies.
