# What a TREC note can support, and what that means for the reader

Written 4 October 2026, after re-reading the stored 2022 top-25
answers under the judges’ own combination rule. No new model
calls. No rented hardware. This note is for deciding what to do
next. The numbers live in `docs/trec_reader.md`. The lock is
`e8befec`. The live tracking run is
`reader_2022_top25_compatible`.

The system does not say a patient qualifies.

## Why this note exists

The rule-by-rule reader was scored, then scored again with a
fairer last step. The second pass changed the **words** on each
trial and did not change the **ranking** number. Talking that
through made a larger point: TREC never asked a computer to fill
in an eligibility form. Walking every requirement was the wrong
method for this test’s ranking job.

This file says that in one place, in plain language.

## The setup, once

**TREC** here means the 2022 Clinical Trials track: a search
contest. Each “patient” is a made-up hospital note, five to ten
sentences. Each “trial” is a public write-up from
ClinicalTrials.gov. Human judges marked trials as:

- **not relevant** — wrong disease or situation (their 0)
- **excluded** — right disease, but a written rule keeps the
  person out (their 1)
- **eligible** — their word for “this person could join”
  (their 2)

They used “eligible” on the score sheet. In the same overview
they say the note need only have **enough** to suggest the
person **may** be able to join, and must **not** show that they
are ruled out. Location and whether the trial was still
recruiting were ignored. That only makes sense if the thing
being scored is a first-page shortlist for a human, not a
decision that someone may enroll.

This project read the top 25 trials that search had already
surfaced for each of the 50 patients from 2022. That is 1,250
pairs. The model was Qwen2.5-7B-Instruct. Each trial’s
eligibility text was split into separate requirements (about 13
per trial, 16,516 in all). For each requirement the model could
say: the note shows this is true, the note shows this is false,
or the note does not say. If it claimed a sentence as evidence,
that sentence had to appear in the named source.

Those per-requirement answers are on disk and were not changed.

## Finding: a TREC note settles 7.6% of the written requirements

Of 16,516 requirements, the note had enough information to
answer **1,252**. That is **7.6%**. Averaged per trial the
share is **14.1%**, because some lists have more requirements
the note can speak to.

This is not “the model got 7.6% right.” It is “a short TREC
note can speak to about one requirement in thirteen.” The
other 92% are blanks. The notes are short **on purpose**. The
2022 overview says that was to keep the task as search, not as
supervised form-filling.

This project has not seen that fraction reported elsewhere. It
is a fact about the test, not about Qwen.

## Finding: the old last step was stricter than the judges

A **combination rule** is the recipe that turns ~13 small
answers into one verdict for the whole trial. Three recipes
were reported side by side. The first two were locked before
the GPU pass. The third was locked in `e8befec` **before** any
stored answer was re-read.

**Recipe 1 — prove every requirement.** Call the trial a yes
only if every requirement is settled and none keep the person
out. If any requirement is “the note does not say,” call the
whole trial **I don’t know**. Result: **1,138** I don’t know,
86 excluded, 26 yes. About **91%** I don’t know.

**Recipe 2 — similar, still will not say yes while anything is
open.** Result: 1,164 I don’t know, 60 excluded, 26 yes.

**Recipe 3 — compatible unless the note proves a problem.**
This is the judges’ rule. If the note shows a “must not” is
true, or shows a “must” is failed, the trial is **excluded**.
Otherwise it is **compatible**. “The note does not say” does
not vote. Silence cannot throw a trial out. Unsplit
requirements (the splitter could not tell inclusion from
exclusion) were treated as the first two recipes treat them:
a “false” is a contradiction, a “true” is a confirmation. Five
trials (0.4%) had exclusion language inside an unsplit block.
Noted, not repaired.

Result: **1,164 compatible, 86 excluded, 0 I don’t know.**

So the 91% figure was the old recipe. It should not stand as
the description of what the reader said. The labels **did**
become compatible. Compatible means only “nothing in this
short note rules the trial out.” It does not mean “this is a
good match,” and it does not mean the person qualifies.

Of those 1,164 compatible calls, 595 were the judges’ “could
join,” 176 were “right disease, a rule fails,” 262 were
irrelevant, 131 were never judged. Among pairs the judges had
already marked as could-join versus right-disease-but-out, the
compatible call is right **77.2%** of the time (595 / 771).
Guessing “compatible” every time on those same pairs is right
**75.7%** of the time (629 / 831). The flood of “compatible”
recovers the prior. When the reader said excluded (86 pairs),
the judges had still called 34 of those “could join.” A loud
no is often wrong. None of this is an overall accuracy number.

## Finding: the ranking number did not move

**AUROC** here means: take one trial the judges said this
person could join, and one they said they could not (same
disease, a rule fails). How often does the computer’s **number**
put the first trial above the second? 0.50 is a coin flip.
1.00 is never wrong.

| Recipe | AUROC | Patient interval |
|---|---:|---:|
| Prove every requirement | 0.595 | 0.551–0.635 |
| Similar, still needs a full yes | 0.584 | 0.537–0.630 |
| Compatible unless contradicted | 0.594 | 0.550–0.635 |
| Fine-tuned ranking model (mean of three repeats) | **0.779** | — |

The third recipe’s number was locked before looking: a proven
contradiction drops the trial near the bottom; among the rest,
a little credit for each requirement the note settles and
confirms; “the note does not say” adds nothing either way.

That sort is almost the same as recipe 1. Once contradictions
are at the bottom, “share confirmed” is just a rewrite of
“share settled.” Changing the **word** from “I don’t know” to
“compatible” does not change the **order**. The unfairness of
the old recipe was in the label, not in the sort.

**0.59 under the fair rule is the honest ranking answer.** It
does not beat 0.779. It was not expected to. A note that
speaks to 7.6% of the requirements does not give enough signal
to put a good trial above a bad one 78% of the time.

## What TREC was actually for

TREC is a search contest. Teams returned an ordered list of
trial IDs. The score that decided who won was: did the trials
humans marked “eligible” land near the top? Not: did the
computer prove the person could enroll?

The job the test rewards is:

1. Same disease / same situation.
2. Not obviously ruled out.
3. Enough overlap to be worth a human look.

The leftover work — the other twelve requirements, labs that
are not in the note, consent, site, whether the trial is open
— is a coordinator and later visits. You cannot have certainty
that a particular person is eligible from these notes. TREC
did not claim you could, even when it used the word
“eligible.”

## What that means for method

**Walking every requirement is the wrong tool for this test’s
ranking job.** It asks the model to fill in a form the note
cannot support. Combining the blanks cannot recover a ranking
signal that is not there.

It is still a fair **quote** job, when the note actually
speaks. Of 1,252 offered quotes, **3.75%** were paraphrased or
absent. That 3.75% is Qwen on TREC, offered quotes only. The
**5%** figure was a support-problem reference on an earlier
lung-cancer slice. The **1.3%** was GPT-5.4 on that same
slice. Different model, different corpus, different task. They
are not three points on one scale.

**A contradiction-only reader is not the same as the
fine-tuned model.** The idea would be: read the note, read the
trial as a whole, ask only whether anything **expressly**
rules the person out, and quote that sentence if so. That
matches the “do not exclude on silence” half of TREC. It would
look like recipe 3’s labels: almost everything survives. That
is a highlighter for a coordinator, not a way to order 25
trials. It has **not** been built.

The fine-tuned model already does the ranking job that fits
this test. It sees the **whole** eligibility block in one go.
It is asked whether the person **appears to meet** the stated
criteria (a 0–3 scale; if unsure, pick 2). Then it was
**trained** on the human TREC marks, so it copies what those
judges tended to do. The number is only for sorting. It does
not have to quote. It can use same-disease wording and
patterns from training. That is why it can reach 0.779 without
completing the form. The same 7-billion-parameter model, asked
a similar question **without** training, was much weaker
(about 0.65–0.72 on the same kind of comparison). There is
also a separate model whose only job is same disease.

| | Rule-by-rule reader | Contradiction-only (not built) | Fine-tuned Qwen |
|---|---|---|---|
| Reads | Each requirement | The trial as a whole | The trial as a whole |
| Must point to a sentence | Yes | Yes, if kept | No |
| Uses silence | Blank | Cannot exclude | Folded into “looks like a 2” and into training |
| Good for | Quotes, when the note speaks | Finding a smoking-gun exclusion | Putting trials in order on this test |
| Measured ranking | 0.59 | Not measured | 0.779 |

The split of labor that matches the test:

1. Search and the disease model: find trials about the same
   situation.
2. The fine-tuned model: among those, put the ones humans
   marked “could join” above the ones they marked “right
   disease, a rule fails.”
3. A human: the rest of the form.

A contradiction-only reader would sit next to (2) as evidence,
not as a replacement for (2).

## What not to do next without a new brief

- Do not start another GPU pass.
- Do not re-read any trial.
- Do not change the per-requirement prompt or loosen the
  “quote must exist in the source” check.
- Do not run 2021 or 2023.
- Do not invent an overall accuracy.
- Do not put 3.75%, 5%, and 1.3% on one scale.
- Do not treat “compatible” as “good match.”
- Do not treat 13 of 50 from the first probe as a score.

## Options if a next run is worth discussing

These are options, not a plan. None of them is started.

1. **Leave the reader where it is.** Ranking is the fine-tuned
   model. The reader’s delivered value is the quote check.
2. **Build a contradiction-only reader** (whole trial, one
   question, quote the ruling-out sentence). Measure it as
   evidence, not as a replacement for 0.779. Expect most
   trials to survive.
3. **Ask a larger paid model** whether it can settle more than
   7.6% of requirements. That is a spend. It tests the note,
   not a new combination rule.
4. **Stop spending on TREC form-filling** and write the
   finding: this benchmark rewards a shortlist, not certainty
   that someone qualifies.

The system does not say a patient qualifies.
