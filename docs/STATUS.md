# Where this project stands

**As of 30 September 2026.** This is a status document, not the final write-up. Step 8
(the reader) has now been run. Step 9 — a human check of the answer key — has not.
Steps 6 and 7 stay on hold. The platinum hole is closed. **44.7% is not withdrawn:**
on discarded trials, gpt-5.4 called the patient a candidate 6.3% of the time, under
the 10% unsafe gate. There is still no overall accuracy figure. Acceptances cannot be
verified with a six-fact key, and that number was not attempted.


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
| What the system actually achieves now | **44.7%** |
| What it would achieve if the patient descriptions were parsed perfectly | 51.9% |
| The ceiling, if rules were always found perfectly | 54.2% |
| The ceiling, if we could also settle conditional rules | 79.0% |
| The target that originally justified building this | 70% |

Two things to take from that table.

**The 44.7% is real and hard-won.** Closed names got this from 23.2% to 40.6%. A three-level
prior-therapy hierarchy, consulted only at comparison time, got the rest. Platinum recall went
from 37.2% to 88.8%. The 70% elimination target is still out of reach: the ceiling with these
six facts is 54.2%, and that is a property of the trial text, not of matching.

**But even the 54.2% ceiling misses the 70% target.** That target was never reachable with these
six facts, regardless of how good the matching got. The reason is explained under "the ceiling"
below, and it has nothing to do with any model.

### What it means in money

At the full cancer set, after the free structured filter leaves roughly 1,500 trials, at the
measured cost of $0.0068 per trial read:

| | Trials left to read | Cost per patient |
|---|---:|---:|
| No cheap filter at all | 1,500 | **$10.13** |
| **Current system, 44.7%** | 829 | **$5.64** |
| With parsing fixed, 51.9% | 721 | $4.90 |
| With perfect rule-finding, 54.2% | 687 | $4.64 |
| The original 70% target | 450 | $3.04 |

**So the cheap step as built removes about 45% of the cost.** Whether that justifies the
machinery is the decision to make.

---

## The six things that have been measured

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

Result: realistic elimination went from **23.2% to 40.6%**. Five of six facts cleared 81%.
Platinum was 37.2%, because 284 of its rules said "no prior chemotherapy" or "no prior
systemic treatment" and never named platinum — the list had nowhere to file them.

**Then containment.** Two broader names were added, and a three-level hierarchy
(`therapy_hierarchy.json`) is consulted only when comparing. A patient who had platinum sits
inside a ban on any chemotherapy. A patient whose note only says "chemotherapy" is *not*
thrown out of a trial that bars platinum specifically. Immunotherapy sits under systemic
treatment, not under chemotherapy. Realistic elimination is now **44.7%**. Platinum recall
is **88.8%**.

| Fact | Share of its rules found | Wrongly picked up |
|---|---:|---:|
| Tumour genetic marker | **99.9%** | 0.3% |
| Autoimmune disease | 99.6% | 0.0% |
| Cancer spread to the brain | 94.2% | 0.0% |
| Disease stage | 93.4% | 0.0% |
| Previous platinum chemotherapy | **88.8%** | 6.4% |
| Previous immunotherapy | 87.7% | 4.1% |
| **Mean** | **93.9%** | **1.8%** |

Wrongly-picked-up on platinum and immunotherapy rose because they share a parent. A method
that matched nothing would score 0% there; do not read those two columns alone. On five
invented patients with deliberately vague treatment history, wrongly applying a
platinum-specific rule was **0%**.

Two earlier bugs stay closed. Patients with no genetic marker retrieve marker rules by the
name `tumour genetic marker`, not the value `none`. Brain matching no longer shares a word
index with stage, so the 45.5% false pickup is still 0.0%.

### 5. The one positive finding worth reporting on its own

Conditional rules can't be settled from a patient description — but most of them turn on one or
two specific details, like whether brain lesions were treated and have stayed stable.

If those details were available, elimination would rise from 54.2% to **79.0%**.

**So asking the coordinator one or two follow-up questions is worth more than adding several
more facts.** That is a design conclusion with a number behind it, and it holds regardless of
what happens to the rest of the project.

### 6. The reader, measured without pretending acceptances are knowable

gpt-5.4 read 250 trials per patient × 6 patients, discarded and kept stratified, plus 20 pairs
twice. Mini did the same sample.

On trials the cheap filter had thrown away, gpt-5.4 still called the patient a candidate
**6.3%** of the time (38 of 600). The gate to withdraw 44.7% was 10%. It holds. Mini was
**10.8%** — the wrong side of that line, and that comparison had no gate.

1.2% of gpt-5.4's judged quotes were missing from the trial text (gate 5%). Mini: 7.7%.
Where the six-fact key definitely excludes the patient, gpt-5.4 also excluded 87.0% of the
time (gate 85%). Mini: 81.6%. Published doctor–doctor agreement on this task is 64–70%;
do not read the 80s as failure. Mini still fails the gates written for a production reader.

The reader also excluded 352 kept trials the six facts do not exclude. Twenty of those are in
`docs/step8_will_check.md` for Will — does the quote say what is claimed, not a medical call.

There is **no overall accuracy figure**. The key cannot confirm an acceptance.

---

## What is still broken

**Six of twenty patient descriptions omitted the genetic-marker row entirely.** If every
description had listed every always-relevant fact, elimination would be 51.9% rather than 44.7%.
So roughly seven percentage points are being lost to the description-parsing step, not to
matching. The parsing instructions have already been revised once, which is all the plan
permits, so this needs a decision rather than another silent retry.

The platinum hole is closed. The 284 generic "no prior chemotherapy / no prior systemic
treatment" sentences now have a place to go. Immunotherapy sits under systemic treatment and
not under chemotherapy; that distinction was tested and held. A patient whose note only says
"chemotherapy," with no drug named, is not thrown out of a trial that bars platinum
specifically. None of the original 20 was that case — they all name a drug — so five extra
patients were written to test it. UMLS was not used and is not needed for this hole.

---

## What has NOT been measured — read this before quoting any number above

**There is still no overall accuracy figure.** Step 8 measured four verifiable things
(lost joinables, fabricated quotes, agreement on key exclusions, extra catches). It did
not, and cannot, score acceptances. Do not quote 6.3% or 87% as "the system is 87%
accurate."

**The answer key has never been checked by a human.** Every number here is measured against one
model's reading of 1,307 trials, corrected by hand in four places. Checking it is Step 9 and it
has not been run. On the six-fact labelling run, an automated quote check flagged **52% of rows**
— mostly stage quotes stitched together from separate sentences — and that flag was noted rather
than resolved. Will's 20-row sheet from Step 8 is a quote-vs-claim check, not a key audit.

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
| Prior-therapy hierarchy (re-assignment + five extra patients) | $0.79 |
| The reader, two models, 3,040 reads | ~$18 |
| **Total** | **~$52** |

No graphics-card time has been rented. Nothing has been trained.

---

## The decision to make

The cheap filter works, and the full read of what it throws away does not find a pile of
joinable trials (6.3%, under 10%). Mini is not a drop-in for that read. The ceiling of 54%
still means matching work cannot reach the original 70% target.

**Three options.**

**A. Stop here and write it up.** Narrowing, matching, and the reader are now all measured.
The honest hole left is that acceptances were never scored, because they cannot be with this
key.

**B. Check the answer key (Step 9), then write it up.** Free, 90 minutes of reading.
The 20 extra-exclusion rows from Step 8 are done (20/20 agree).

**C. Keep building** — fix take-apart, or try Qwen3 on Lambda as the cheap reader. Steps 6
and 7 stay on hold: mini is not close enough that a trained judge is the next cost win, and
the expensive reader is already the one you would ship.

**Recommendation: Step 9, then write it up.** Option C waits on Qwen or on a real-notes sample that looks
like V01, where lost-joinable was 13%.
