# Rule-by-rule reader on the 2022 top 25

The reader is a program that splits one trial's eligibility text into
rules, asks a self-hosted 7-billion-parameter model
(Qwen2.5-7B-Instruct) to judge each rule against one patient note,
and checks that any quoted sentence actually appears in the named
source. It never says the patient qualifies.

**The headline.** On all 50 patients from 2022, reading the top 25
trials the default ranker had already surfaced (1,250 pairs), the
reader almost always says **not enough information**. It does
**not** sort expert-joinable trials from expert-excluded ones the
way the fine-tuned eligibility scorer does. That scorer's mean
1-versus-2 AUROC is **0.779**. The reader's is **0.59**
(0.55–0.64). A coin flip is 0.50.

When the model *does* offer a quote, the quote is usually real:
**3.75%** of offered quotes were paraphrased or absent (D+E). The
locked reference treated above **5%** as a support problem and
earlier work measured **1.3%**. This sits between those two. It is
not a new gate.

There is no overall accuracy number here. Most calls are
"uncertain," and that third label is not a wrong 1 or 2. Do not
average it into a percentage.

13 of 50 from the first probe is **not** accuracy. That was a
schema-conformance rate while an output contract was rejecting
empty quotes. It was never scored against expert verdicts.

The system does not say a patient qualifies.

## What was asked

Locked in `f852d6c` before any score, then amended in `621e898` and
`89a2bf4` after the first probe broke. 2022 only. Not 2021 (60 of
those patients trained the adapter). Not 2023. No frontier model.
No pass/fail threshold.

Two ways to turn per-rule verdicts into one trial-level call:

- **any_hard_fail** — one failed inclusion, or one firing
  exclusion, and the trial is excluded. Joinable only if every
  inclusion is met, no exclusion fires, and nothing is unsettled.
- **net_balance** — a firing exclusion still excludes. Otherwise
  the share of settled inclusions that were met is the score.

If those two disagree on the headline, that is the finding. They
do not. Both say: mostly uncertain, and a weak sort of 1 vs 2.

**AUROC** here means: pick one trial experts called joinable
(label 2) and one they called excluded — right disease, a rule
fails (label 1). How often does the reader give the joinable one
the higher “looks joinable” score? Intervals resample **patients**,
not pairs.

## The 1,250-pair result

A100 SXM4. Reads copied off. Instance terminated through the API.
**4.3 hours, $7.70.** Valid JSON on **1,240 / 1,250** (99.2%).
**1.1** model calls per trial. **1,009** rules were converted from
an empty-quote `met`/`not_met` to `not_enough_information` and
counted. That conversion is a model-behaviour metric, not a hidden
failure.

Of 1,250 pairs, experts had called **629** joinable, **202**
excluded, **280** irrelevant (label 0), and **139** unjudged.

| Trial-level call | any_hard_fail | net_balance |
|---|---:|---:|
| Uncertain | 1,138 | 1,164 |
| Excluded | 86 | 60 |
| Joinable | 26 | 26 |

About **91%** of trials stay unsettled. That is what
silence-is-a-pass does when most rules come back
`not_enough_information`: the trial is not called joinable.

When the reader did call **joinable** (26 pairs, both rules):
experts had said joinable on 17, excluded on 2, irrelevant on 4,
unjudged on 3. When it called **excluded** under any_hard_fail
(86 pairs): experts had said joinable on 34, excluded on 26,
irrelevant on 18, unjudged on 8. A loud “no” often lands on a
trial humans still called joinable. A loud “yes” is rare.

| 1-versus-2 AUROC | Pooled | 95% patient interval |
|---|---:|---:|
| any_hard_fail | 0.595 | 0.551–0.635 |
| net_balance | 0.584 | 0.537–0.630 |
| Fine-tuned eligibility scorer (mean of three seeds) | **0.779** | — |

Neither interval includes 0.779. Neither includes 0.50, but both
are close to a coin flip. The two aggregations agree: this reader
is not the 1-versus-2 instrument.

One of the 50 patients had no label-1 or label-2 trial in this
top 25, so the AUROC uses 49 patients (38 had both a 2 and a 1).

## Quotes

16,516 rules. Most are `not_enough_information` with an empty
quote. That empty quote is bucket E by construction and is **not**
fabrication: the verdict already says the note does not settle it.

**1,252** rules offered a quote (`met` or `not_met`):

| Bucket | n | What it is |
|---|---:|---|
| ok | 1,115 | Span in the named source |
| B | 54 | Same span after punctuation |
| A | 24 | Stitched from two real spans |
| C | 12 | In the trial text, but not about this rule |
| D | 11 | Paraphrase |
| E | 36 | Offered, but not in the source |

Raw flag rate (anything other than ok): **10.9%**. Honest
fabrication (D+E): **47 / 1,252 = 3.75%**. n ≥ 200, so no Wilson
interval. Under the 5% reference; above the earlier 1.3%.

A 80-row sheet for a hand check is in
`docs/trec_reader_will_check.md`. Reading only: does the quoted
sentence plainly support the one-sentence explanation? Not a
medical judgment.

## Does it work?

**As a citation check, partly.** When the model claims a span, the
span is usually on the page.

**As a stand-in for the 0.779 eligibility scorer, no.** It will
not tell joinable from excluded on this shortlist. Silence-is-pass
is the same principle the project already locked; applied
rule-by-rule on TREC notes it leaves almost every trial unsettled.

That is a measured finding, not a pass/fail. The locked question
was how it does. This is how it does.

## First probe, and why 13 of 50 is not a score

The first 50-trial probe (patients 1 and 2) produced valid JSON
for 13 of 50. The other 37 used all three retries and were
discarded. **That is a schema-conformance rate.** It was not
scored against TREC labels. Do not quote it as model performance.

The layer that rejected those 37 did its job. A check that
refuses three-quarters of its inputs under a real fault is
evidence the design is sound, not that it is broken.

The working hypothesis was that a 2,048-token output cap was
cutting the JSON off on long trials. The stored replies say
otherwise. No failure sat at or near 2,048 tokens. The longest
failure was 1,390. A 45-rule trial passed; a 2-rule trial failed.

Of the 37 last replies: 27 empty quotes on `met`/`not_met`, 5
empty quote sources, 4 broken JSON, 1 invented rule ID. Among
empty-quote rows that still parsed: **145 `not_met`**, **16
`met`**. Three greedy retries pasted the previous JSON, so the
same empty quotes came back. That is why the first projection was
$33.73: every failure burned four generations.

## Two rules that are not the same

1. **Quote guardrail (never loosened).** If a quote is offered, it
   must exist in the named source. That is what measures
   fabrication.
2. **Output contract (this was wrong).** Requiring every `met` and
   `not_met` to carry a quote is unsatisfiable for absence
   judgements. A silent note has no span to cite.

The second rule contradicted a principle already locked in
`CONTEXT.md`: a filter may only eliminate on confident evidence;
silence is a pass. `not_met` means the note positively fails the
rule, and that always has a quote. A silent note is
`not_enough_information`.

The output contract required evidence for every negative
judgement, but judgements grounded in absence have no span to
cite, so the contract was unsatisfiable for a whole class of
cases. The prompt change is consistency with that settled rule,
not a workaround.

If the model still returns `met` or `not_met` with no quote, that
row is converted to `not_enough_information`, flagged, and
counted. That case is not retried. One targeted repair remains,
only for broken JSON or a leftover schema error, and it names
only the failed rule IDs.

The splitter’s 4% no-header trials and five mixed-polarity trials
(0.4%) were noted before scores and left as-is.

## Re-probe, then the full pass

Same 50 trials as the broken probe, after the amendment:

| | First probe | Re-probe | Full 1,250 |
|---|---:|---:|---:|
| Valid JSON | 13 / 50 | 50 / 50 | 1,240 / 1,250 |
| Generations per trial | 3.3 | 1.1 | 1.1 |
| Hours / cost | 0.75 h / $1.35 | 0.26 h / $0.46 | **4.3 h / $7.70** |

The re-probe projected $11.50. The full pass came in under that,
inside the original $7–$15 sketch, without cutting patients or
trials.

Live MLflow run `reader_2022_top25` (not retrofitted). The same
numbers are in `docs/trec_mlflow_runs.csv`.

The system does not say a patient qualifies.
