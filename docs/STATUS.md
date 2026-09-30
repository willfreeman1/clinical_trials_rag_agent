# Where this project stands

**As of 29 September 2026.** This is a status document, not the final write-up. Two steps of
the plan have not been run, and one of them is the one that measures whether the answers are
actually any good.

Plain language throughout. Everything is explained where it first appears.

---

## The question

A person screening one patient against open clinical trials. Each trial publishes a long list
of rules about who may join — about 43 rules per trial on average. Today a human does this by
hand and it takes 30 to 90 minutes per patient.

Sending every trial's rules to a large, capable language model works, and costs about **$9 per
patient** across the 1,307 lung-cancer trials on disk. Against 30 to 90 minutes of a
coordinator's time, that is already cheap enough to be a product.

The problem is scale. Across all cancer trials — roughly 124,000 — reading everything is
impossible. So the question the project has been testing is:

> **Can something cheap throw most trials away first, so the expensive model only reads a few?**

---

## The headline numbers

| | Share of trials thrown out |
|---|---:|
| What the system actually achieves now | **40.6%** |
| What it would achieve if the patient descriptions were parsed perfectly | 48.6% |
| The ceiling, if rules were always found perfectly | 54.2% |
| The ceiling, if we could also settle conditional rules | 79.0% |
| The target that originally justified building this | 70% |

Two things to take from that table.

**The 40.6% is real and hard-won.** A week ago the same measurement said 23.2%, and before the
fix described below it looked like the approach had failed.

**But even the 54.2% ceiling misses the 70% target.** That target was never reachable with these
six facts, regardless of how good the matching got. The reason is explained under "the ceiling"
below, and it has nothing to do with any model.

### What it means in money

At the full cancer set, after the free structured filter leaves roughly 1,500 trials, at the
measured cost of $0.0068 per trial read:

| | Trials left to read | Cost per patient |
|---|---:|---:|
| No cheap filter at all | 1,500 | **$10.13** |
| **Current system, 40.6%** | 891 | **$6.06** |
| With parsing fixed, 48.6% | 771 | $5.24 |
| With perfect rule-finding, 54.2% | 687 | $4.64 |
| The original 70% target | 450 | $3.04 |

**So the cheap step as built removes about 40% of the cost.** Whether that justifies the
machinery is the decision to make.

---

## The five things that have been measured

Each with its deciding number written down and committed to version control *before* the run
that produced it.

### 1. Meaning-similarity search cannot tell "must have had this" from "must not have had this"

The first attempt turned text into numbers so that similar meanings get similar numbers, then
ranked trials by closeness to a question. Every trial scored in a narrow band. The gap between
trials that *require* a treatment and trials that *refuse* it was about **one hundredth**,
against a spread of about a tenth inside a single group. When the variation within one group is
ten times the distance between two groups, ranking mixes them.

Dead end, and measured properly.

### 2. You cannot pre-fill a fixed set of columns

If the rules only depended on a manageable list of facts, you could read every trial once, fill
in a spreadsheet, and answer patients by filtering it.

They don't. Trials depend on **5,578 differently-worded facts**, 77% of which appear exactly
once, and the 40 commonest cover only **24%** of all rules. Not one trial out of 300 sampled had
all its facts inside those 40.

### 3. The ceiling is about half, and that is a property of the text

A cheap filter may only throw a trial away when it is *certain*. Many rules are written
conditionally — *"excluded unless it was treated and has been stable for four weeks"* — and a
conditional rule can never be settled from a patient description alone, because the description
usually doesn't contain the extra detail. So those rules always keep the trial.

How many rules are like that, out of 1,307 trials:

| Fact | Rules that can never be acted on |
|---|---:|
| Disease stage | **744** |
| Cancer spread to the brain | **416** |
| Autoimmune disease | 316 |
| Tumour genetic marker | 206 |
| Previous immunotherapy | 87 |
| Previous platinum chemotherapy | 15 |

More than half of all stage rules and nearly a third of brain rules are unreachable **no matter
how good any model is.** That is what caps the ceiling at 54.2%, and it is the single most
important finding in the project.

### 4. Free-text matching loses half the ceiling; matching by a fixed vocabulary does not

This was the interesting engineering result, and it came in two parts.

**The failure.** Every early attempt matched **free text against free text** — the patient's
wording against the trial's wording — hoping they would look similar. It didn't work. On tidied
wording, "previous immunotherapy" against "immunotherapy" scored 0.73 and "tumour genetic
marker" against "EGFR mutation" scored 0.52, where those need to be high. And a pair that should
*not* match — cancer spread to the brain versus spread to the bone — scored 0.86. **The pairs we
wanted matched scored lower than the pair we wanted kept apart**, so no cutoff could separate
them. Realistic elimination came out at **23.2%.**

**The fix.** Stop comparing free text. Have the large model assign **both sides to the same
short, fixed list of six names.** The patient's marker becomes `tumour genetic marker`. The
trial's rule becomes `tumour genetic marker`. Then matching is exact string equality — no
similarity scores, no cutoffs, nothing to tune. The hard translation happens once on each side,
by a model that can do it, and the matching becomes trivial by construction.

Result: realistic elimination went from **23.2% to 40.6%**, and the rules are now found
reliably:

| Fact | Share of its rules found | Wrongly picked up |
|---|---:|---:|
| Tumour genetic marker | **99.9%** | 0.2% |
| Autoimmune disease | 99.4% | 0.0% |
| Cancer spread to the brain | 93.9% | 0.0% |
| Disease stage | 93.3% | 0.0% |
| Previous immunotherapy | 81.4% | 0.0% |
| Previous platinum chemotherapy | **37.2%** | 0.0% |
| **Mean** | **84.2%** | **0.03%** |

Two bugs were also fixed in the same round. Patients with no genetic marker previously retrieved
no marker rules at all, because "none" doesn't resemble a gene name — and those were exactly the
patients the ceiling throws out most. That is now handled as a rule rather than a search: if the
patient has no marker, every trial demanding one is out. And brain matching previously picked up
45.5% of trials wrongly because the phrase "cancer spread to the brain" shares the word "cancer"
with almost every stage rule. Removing the shared word index took that to 0.0%.

### 5. The one positive finding worth reporting on its own

Conditional rules can't be settled from a patient description — but most of them turn on one or
two specific details, like whether brain lesions were treated and have stayed stable.

If those details were available, elimination would rise from 54.2% to **79.0%**.

**So asking the coordinator one or two follow-up questions is worth more than adding several
more facts.** That is a design conclusion with a number behind it, and it holds regardless of
what happens to the rest of the project.

---

## What is still broken

Neither of these is a matching problem.

**Previous platinum chemotherapy finds only 37% of its rules — and it is a definitional
disagreement, not a failure.** Most of those rules never mention platinum. They say "no prior
systemic treatment" or "any previous chemotherapy." The answer key counts those as platinum
rules, because a blanket ban on previous treatment does bar platinum. The name-assigner, which
sees only the sentence and not the question, files them as `other`. Both readings are defensible
and the disagreement needs settling before the number means anything. Five of the six facts
clear 81%.

**Six of twenty patient descriptions omitted the genetic-marker row entirely.** If every
description had listed every always-relevant fact, elimination would be 48.6% rather than 40.6%.
So roughly eight percentage points are being lost to the description-parsing step, not to
matching. The parsing instructions have already been revised once, which is all the plan
permits, so this needs a decision rather than another silent retry.

---

## What has NOT been measured — read this before quoting any number above

**Nobody has checked whether the system's answers are correct.** Every figure in this document
is about *how many trials get thrown away* and *whether rules get found*. None of them says
anything about whether the final answer given to a coordinator is right. That measurement is
Step 8 of the plan and it has not been run.

**The answer key has never been checked by a human.** Every number here is measured against one
model's reading of 1,307 trials, corrected by hand in four places. Checking it is Step 9 and it
has not been run. On the six-fact labelling run, an automated quote check flagged **52% of rows**
— mostly stage quotes stitched together from separate sentences — and that flag was noted rather
than resolved.

**The test set is 20 invented patients, balanced by design rather than realistic.** Half carry
brain metastases where a real clinic would see nearer a third. So no average across these
patients estimates what a real clinic would experience. And because several facts are yes-or-no,
the 20 patients produce only a handful of distinct outcomes.

**One trial of 1,308 failed to label** and was dropped, leaving 1,307.

---

## Spend to date

| | |
|---|---:|
| First spike — data collection, answer key, the failed similarity search | $7.46 |
| Could a fixed set of columns work | $6.72 |
| The ceiling measurement | $0 |
| Free-text matching tests | ~$1.10 |
| Parsing patient descriptions, twice | $0.30 |
| Labelling six facts across all trials | $15.62 |
| Closed-name matching | $2.36 |
| **Total** | **~$33.6** |

No graphics-card time has been rented. Nothing has been trained.

---

## The decision to make

The cheap filter works. It removes about 40% of the reading cost, and with two known fixes it
would remove closer to 49%. That is real but it is not the tenfold reduction that would make the
full cancer registry trivially cheap, and the ceiling of 54% means no amount of further work on
matching gets there either.

**Three options.**

**A. Stop here and write it up.** The project has produced four measured negative results, one
useful positive one, a working costed baseline, and a clean engineering finding about why
free-text matching fails and fixed vocabularies don't. Everything was measured against
thresholds committed in advance. This is a legitimate outcome and it is what two previous
projects did.

**B. Finish the measurement first, then write it up.** Run Step 8 — how accurate is the whole
thing, and how accurate is reading everything — and Step 9, the human check on the answer key.
Roughly $19 and two days. This is the difference between "we measured how much gets thrown away"
and "we measured whether the thing works," and right now only the first is true.

**C. Keep building** — settle the platinum definition, fix the parsing gap, then train a small
model to judge rules. Steps 6 and 7, about $15, currently on hold.

**Recommendation: B, then decide between A and C.**

Option C is the weakest of the three right now, because training a model to judge rules more
cheaply is an optimisation of a system whose accuracy nobody has measured. And option A is
premature for the same reason — a write-up that reports elimination rates without a single
accuracy number invites the obvious question and has no answer.

Step 8 is the missing leg. It is two days and $19, and it turns a collection of measurements
into a result.
