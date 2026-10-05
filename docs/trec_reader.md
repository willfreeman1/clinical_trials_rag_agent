# Rule-by-rule reader on the 2022 top 25

What those numbers mean for method, and what to discuss next:
`docs/trec_short_notes.md`.

The reader is a program that splits one trial's eligibility text into
rules, asks a self-hosted 7-billion-parameter model
(Qwen2.5-7B-Instruct) to judge each rule against one patient note,
and checks that any quoted sentence actually appears in the named
source. It never says the patient qualifies.

**The headline.** On all 50 patients from 2022, reading the top 25
trials the default ranker had already surfaced (1,250 pairs), a
TREC patient note settles **7.6%** of a trial's eligibility
rules. That is a fact about the notes, not about the model: they
are 5 to 10 sentences on purpose. Under the combination rule the
assessors used — compatible unless a quote contradicts — the
reader calls **1,164** of 1,250 trials compatible and **86**
excluded. It still does **not** sort expert-joinable trials from
expert-excluded ones. The fine-tuned scorer's mean 1-versus-2
AUROC is **0.779**. The reader's is **0.59** under all three
combination rules (0.55–0.64). A coin flip is 0.50.

When the model *does* offer a quote, the quote is usually real:
**3.75%** of offered quotes were paraphrased or absent (D+E). That
is a different measurement from the **5%** support-problem
reference on an earlier lung-cancer slice, and from the **1.3%**
GPT-5.4 audit on that same slice. The three numbers are not
points on one scale.

There is no overall accuracy number here. Under the first two
combination rules most calls are "uncertain," and that third
label is not a wrong 1 or 2. Under the third rule most calls are
"compatible," which means only that nothing in the note rules
the trial out. Do not average either into a percentage.

13 of 50 from the first probe is **not** accuracy. That was a
schema-conformance rate while an output contract was rejecting
empty quotes. It was never scored against expert verdicts.

The system does not say a patient qualifies.

## What was asked

Locked in `f852d6c` before any score, then amended in `621e898` and
`89a2bf4` after the first probe broke. 2022 only. Not 2021 (60 of
those patients trained the adapter). Not 2023. No frontier model.
No pass/fail threshold.

Three ways to turn per-rule verdicts into one trial-level call.
The first two were locked before the GPU pass. The third was
locked in `e8befec` before any stored verdict was re-read. No
new model calls.

- **any_hard_fail** — one failed inclusion, or one firing
  exclusion, and the trial is excluded. Joinable only if every
  inclusion is met, no exclusion fires, and nothing is unsettled.
- **net_balance** — a firing exclusion still excludes. Otherwise
  the share of settled inclusions that were met is the score.
- **compatible_unless_contradicted** — the TREC 2022 assessors'
  rule. Excluded if an exclusion fires or an inclusion is
  positively failed. Otherwise compatible. Unsettled rules get
  no vote. Silence never excludes.

Unsplit rules: `not_met` is a contradiction, `met` is a
confirmation, the same as the first two rules. Five trials
(0.4%) had exclusion language inside an unsplit block, where
that polarity can invert. Noted, not repaired.

The first two rules demand proof. The judges asked for
compatibility. The 0.59 that used only the first two was an
unfair reading of what the reader can do as a label, and it
should not stand uncorrected. The ranking number was already
using the settled-rule share, so it does not move.

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

| Trial-level call | any_hard_fail | net_balance | compatible-unless-contradicted |
|---|---:|---:|---:|
| Uncertain | 1,138 | 1,164 | 0 |
| Excluded | 86 | 60 | 86 |
| Joinable / compatible | 26 | 26 | 1,164 |

About **91%** of trials stay unsettled under the first two
rules. That is not the model failing. Three things produce it
together: the prompt was told to answer "not enough information"
when the note is silent, a deliberate choice with a cost; TREC
notes are 5 to 10 sentences by design, so most of a 13-rule
list has nothing to quote; and those two rules refuse to call
a trial joinable while any rule is still open. The judges did
not require that.

Under the assessors' rule the same 1,138 "uncertain" trials
become **compatible**. Compatible means "nothing in this note
rules the trial out." That is a weaker claim than "this is a
good match."

When the first two rules called **joinable** (26 pairs):
experts had said joinable on 17, excluded on 2, irrelevant on 4,
unjudged on 3. When any_hard_fail or the third rule called
**excluded** (86 pairs): experts had said joinable on 34,
excluded on 26, irrelevant on 18, unjudged on 8. A loud “no”
often lands on a trial humans still called joinable.

Of the 1,164 **compatible** calls, 595 were expert-joinable
(label 2), 176 expert-excluded (label 1), 262 irrelevant
(label 0), 131 unjudged. Precision of compatible for label 2
among the 1-versus-2 pairs it called: **77.2%** (595 / 771).
The base rate of label 2 among 1-versus-2 in this slice is
**75.7%** (629 / 831). Calling almost everything compatible
recovers the prior. Precision of excluded for label 1 among
1-versus-2: **43.3%** (26 / 60; Wilson 0.32–0.56). Do not read
either figure as overall accuracy.

| 1-versus-2 AUROC | Pooled | 95% patient interval |
|---|---:|---:|
| any_hard_fail | 0.595 | 0.551–0.635 |
| net_balance | 0.584 | 0.537–0.630 |
| compatible_unless_contradicted | 0.594 | 0.550–0.635 |
| Fine-tuned eligibility scorer (mean of three seeds) | **0.779** | — |

The third rule's ranking score penalises each contradiction
into a band at most 0.05, then ranks the rest by how many
rules the note confirms (0.50 to 1.00). Silence is zero either
way. Those weights were committed in `e8befec` before this
table. The AUROC is the same as any_hard_fail because, once
contradictions are sent to the bottom, "share confirmed" is a
monotone rewrite of "share settled." The unfairness of the old
rule was in the **label**, not in the **sort**.

Neither interval includes 0.779. The reader does not beat the
purpose-built scorer, and it was not expected to. **0.59 under
the fair rule is the honest ranking answer.** The reader's
value is evidence on an already-ranked shortlist, not ranking.

One of the 50 patients had no label-1 or label-2 trial in this
top 25, so the AUROC uses 49 patients (38 had both a 2 and a 1).

## How much of a trial a TREC note can settle

16,516 rules across 1,250 pairs. The note settles **1,252** of
them — **7.6%** of eligibility criteria, **14.1%** if you
average the per-trial share (some lists have more rules the
note can speak to). That is why a ranking score built on
confirmations still has thin signal, and why 91% of trials
looked uncertain under the old rule. This project has not seen
that fraction reported elsewhere. It is a limit of the benchmark.

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
interval.

That 3.75% is Qwen2.5-7B-Instruct on TREC 2022, offered quotes
only, buckets D (paraphrase) and E (absent). The **5%** figure
was a support-problem reference on an earlier lung-cancer
slice. The **1.3%** was GPT-5.4 on that same slice, a different
model, a different corpus, and a different quote-audit task.
They answer different questions. They are not three readings
of one rate.

A 80-row sheet for a hand check is in
`docs/trec_reader_will_check.md`. Reading only: does the quoted
sentence plainly support the one-sentence explanation? Not a
medical judgment.

## Does it work?

**As a citation check, partly.** When the model claims a span, the
span is usually on the page.

**As a stand-in for the 0.779 eligibility scorer, no.** Even
under the assessors' own combination rule it will not tell
joinable from excluded on this shortlist (AUROC 0.59, same as
before). A TREC note settles 7.6% of the rules. That is not
enough ranking signal. The fine-tuned scorer was built for
exactly this comparison.

**As a label that matches how the judges defined eligible,
partly.** Compatible-unless-contradicted stops treating silence
as a failed proof. Most trials come back compatible because
that is what the definition says to do. Precision of that call
is the prior. The value that already delivered is the quote
check: 3.75% fabrication on 1,252 offered quotes.

That is a measured finding, not a pass/fail. The locked
question was how it does. This is how it does.

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

Live MLflow runs `reader_2022_top25` (the GPU pass) and
`reader_2022_top25_compatible` (this re-read; threshold
`e8befec`; not retrofitted). The same numbers are in
`docs/trec_mlflow_runs.csv`.

The system does not say a patient qualifies.
