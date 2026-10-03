# Where this project stands

**As of 2 October 2026.** This is a status document, not the final write-up. Step 8
(the reader) has now been run. Step 9's remaining list is done: 12 stage labels,
70 crossings, the qualifier convention, a free basket count, then one re-score.
Steps 6 and 7 stay on hold. There is still no overall accuracy figure. Acceptances
cannot be verified with a six-fact key, and that number was not attempted.

**Quote 43.0% as the current matching-gated figure**, next to 44.7% before the
key corrections. On discarded trials, gpt-5.4 called the patient a candidate
**5.6%** of the time (32/569), under the 10% unsafe gate. The narrowing figure
is not withdrawn. Old JSON reports stay on disk; the side-by-side is
`docs/step9_after_fix.md`. A smaller number that discards fewer joinable
trials is the better system, not a regression.

Two asking tests are measured, and neither ships. Condition-resolution on
complete notes took the ceiling from 51.9% to 56.0% and wrongly-discarded to
10.4%. Sparse-input fact recovery takes an empty note from 0% to 45% with
three questions, and matches a six-question checklist at 2.96 questions —
then wrongly-discarded is **11.4%**. Details: `docs/step10_questions.md` and
`docs/step11_sparse.md`. **Do not quote 79% / 78.2% as a target or a
ceiling.** Those figures assumed every conditional discards. Many keep. They
are not reachable under any design.

TREC hybrid retrieval (stages 1–2) is measured. Judged pool as the
collection. **Eligible recall at 6% of collection: 91.6% (2021), 91.4%
(2022), 65.4% (2023).** The written gate is the worst year; 2023 is
below 70%, so stop. Hybrid beat both singles; keywords beat the raw
note. 2021/2022 are admission notes and match the papers. 2023 is
questionnaire fields and does not. Keyword + `text-embedding-3-small`
matches MedCPT on 2021/2022; the old whole-note embedding miss was
the query shape. The reranker on that shortlist was then
measured and did not earn itself. Details:
`docs/trec_hybrid_retrieval.md` and `docs/trec_rerank.md`.

The free ClinicalTrials.gov `conditions` field does **not** already
do that first stage. 2021/2022 only. Loose match on the first
keyword keeps a mean 994 / 581 trials (3.8% / 2.2% of the pool)
and recalls **62.3% / 49.2%** of eligible trials. Keyword hybrid
at the same per-patient depth is 73.3% / 62.2% — **11 and 13
points** better. The field is almost never empty. The misses are
second problems in the same note, synonyms with no shared token,
and parent/sibling headings. Filter-then-hybrid is capped at the
filter's recall (62% / 49%) and loses to hybrid at 6% of the
pool. Details: `docs/trec_condition_baseline.md`.

Reranking that hybrid shortlist was stopped on a **17% recall@10
gate that was the wrong target**, not an impossible one (real 2021
recall@10 ceiling is 24.7%, not 13%). On the product bar — ≥10
eligible in the top 20, 75 patients, possible for 74 — hybrid is
**9/75** and the old mini-top-200 rerank is **22/75**. Qwen2.5-7B
as a 0–3 topical scorer, continuous, title+conditions+800-char
slice, on the full shortlist, is **37/75**. P@20 is 47.9% (9.6
eligible in 20). Equivalent depth at 200 is **2.73×** baseline
on 2021 and **2.77×** on 2022, so topical reordering earns a
slot. A single cheap eligibility score on the full criteria
(30-patient sample) can rank (2.16× at 200) but does **not**
beat topical at the reader budget; it does win P@20. Do not
delete the topical stage. Mini at full depth ($9) loses to
free Qwen. MedCPT-CE still fades past 100. Product bar still
fails. Run 3 not started. Details: `docs/trec_score.md`.
Original 9.0% / 17% figures stay in `THRESHOLDS.md` as committed.

A rewritten eligibility prompt (written CHECK, then
eligible / ineligible / unsure; rank by P(eligible)) was run
on the **same 30 patients**. Gates in `4424157` before any v2
score. True positives on the page went **down**, not up: 2021
P@20 **34.0%** vs v1 **48.7%**, 10-in-20 **5/15** vs **7/15**;
2022 P@20 **38.3%** vs **58.0%**. The word "eligible" caught
only about a fifth of judged joinable trials. Unsure was 35–39%
of judged 1+2, not a dump. 1-vs-2 AUROC **0.60** (v1 was 0.745).
Do not replace v1. The commonest call on a judged joinable
trial was “unsure”; it said no more often than yes. Details:
`docs/trec_elig_v2.md`. A frontier-model check, if it runs,
should use judged 1-vs-2 pairs, not another 30 × 1,570
shortlist. That check is now done: GPT-5.4 AUROC **0.83** vs
Qwen v1 **0.72** on 411 judged pairs. The TREC-worded prompt
did not help; both models dumped “not relevant.” Details:
`docs/trec_frontier_elig.md`.

The finding from that GPU session is the **untrained** v1
eligibility score: **0.749** on all 50 2022 patients against
**0.682** for the topical slice and **0.686** for a logistic
on the stored signals. Changing the question bought seven
points; combining old scores bought nothing. A first LoRA at
1e-4 collapsed; that was a setup failure, not a measurement.
A second run at **1e-5** on the raw 2-minus-1 score, same
splits, did not collapse. Three seeds of that setup on
held-out 2022: **0.793, 0.770, 0.773**. Mean **0.779
(0.770–0.793)**. Quote the mean and the spread, not the
best run. Patient-resampled interval on the first seed
was 0.748–0.834; 0.749 sits just inside it. Junk-sort on
the same judged-0 pool as the 0.85 figure did **not**
degrade (adapter 2-vs-0 **0.921** vs slice 0.888). Extra
seeds: H100 SXM5, **$8.20**, terminated. The fine-tuning
question is closed. Details: `docs/trec_lora_elig.md`.
No first-page rescore. Run 3 not started.

The 1,570 is **91% junk**. Mean 2021 shortlist: 67 eligible,
73 excluded, 143 judged-not-relevant, **1,287 unjudged** for
that patient. Disease-relevant (1+2) is 140, next to the
guessed 144. Excluded trials are retrieved at 92.1%, same as
eligible 91.6%. The leftover is not "right disease, failed a
criterion." Cheap IDF fusion and exclusion-section down-rank
move Recall@10 from 5.7% to **6.3%**. Do not replace
unweighted RRF. Details: `docs/trec_shortlist_diagnosis.md`
and `docs/trec_shortlist_fix.md`. Do not start a reader from
this.

A cheap topical pass on that shortlist does **not** earn a
pipeline slot. 30 patients, 2021/2022 only, gates committed
before any score. Question: could this trial conceivably be
about this patient's problem? Unsure keeps. Qwen2.5-7B
recalls 96.6% of disease-relevant trials and keeps 61.7% of
the list. Mini is 88.7% / 50.7% (slice: 86.0% / 41.7%).
MedCPT-CE at logit > 0 keeps almost nothing. Lexical first
keyword is 63.5% / 20%. **No arm hits ≥90% recall and ≤50%
retention.** Full scale was not run. The 1,570 stays. Details:
`docs/trec_cheap_pass.md`.

UMLS cannot supply this corpus's vocabulary (56.4% of phrase
occurrences). The six-name approach stays for that hole. Gene-symbol
matching is untouched. Details: `docs/step13_umls_coverage.md`.


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

| | Before remaining-list fixes | After (current) |
|---|---:|---:|
| What the system actually achieves | 44.7% | **43.0%** |
| If the patient descriptions were parsed perfectly | 51.9% | 50.2% |
| Ceiling, if rules were always found perfectly | 54.2% | 51.9% |
| The target that originally justified building this | 70% | 70% |

The old 79.0% / 78.2% "optimistic" row is retired. It treated every
conditional as a discard. Many resolve in the patient's favour and keep the
trial. It is not a ceiling and not a prize. Leaving it in the table is what
invited the condition-resolution test.

Two things to take from that table.

**The 43.0% is the current system.** Closed names got this from 23.2% to 40.6%. A three-level
prior-therapy hierarchy, consulted only at comparison time, got the rest, to 44.7%. The
remaining-list key fixes then brought it to 43.0%, because twelve false stage requirements
and 147 qualified bars were discarding trials they should keep. Platinum recall went
from 37.2% to 88.8%. The 70% elimination target is still out of reach: the ceiling with these
six facts is 51.9%, and that is a property of the trial text, not of matching.

**But even the 51.9% ceiling misses the 70% target.** That target was never reachable with these
six facts, regardless of how good the matching got. The reason is explained under "the ceiling"
below, and it has nothing to do with any model.

### What it means in money

At the full cancer set, after the free structured filter leaves roughly 1,500 trials, at the
measured cost of $0.0068 per trial read:

| | Trials left to read | Cost per patient |
|---|---:|---:|
| No cheap filter at all | 1,500 | **$10.13** |
| **Current system, 43.0%** (was 44.7%) | 855 | **$5.81** |
| With parsing fixed, 50.2% (was 51.9%) | 747 | $5.08 |
| With perfect rule-finding, 51.9% (was 54.2%) | 722 | $4.91 |
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
how good any model is.** That is what caps the ceiling at 51.9% (was 54.2%), and it is the single most
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
treatment, not under chemotherapy. Realistic elimination became **44.7%**, then **43.0%**
after the remaining-list key fixes. Platinum recall is **88.8%**.

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

### 5. Asking was measured twice. Neither version ships.

Conditional rules can't be settled from a patient description. Treating every
conditional as a discard produced a 78.2% figure (was 79.0%). **That figure is
retired.** Many conditionals resolve in the patient's favour and keep the
trial. 41% of assigned conditions were about the trial's own structure. The
number is not reachable under any design.

Two tests, both with gates committed first:

**Condition-resolution on complete notes** (`docs/step10_questions.md`). The
descriptions already had every one of the six facts. The only remaining job
was settling conditionals. Prize: 5.8 points. Result: 51.9% → 56.0% ceiling,
wrongly discarded 10.4%. Asking every live question still only reaches 57.7%.

**Fact recovery on sparse notes** (`docs/step11_sparse.md`). 280 random
subsets, seed 202609304. Prize: 0% with none of the six facts, up to 43.0%
with all six (50.2% if listed perfectly). Result: three questions from an
empty note reach 45.0%. The agent matches a six-question checklist at 2.96
questions (49.8% vs 50.2%). Wrongly discarded **11.4%**, over 10%. The extra
discards are trials the original 43.0% system had kept; the reader calls
41.5% of those a candidate.

Recovery of missing facts works. Safety does not hold once the discarded set
is the complete-six-facts set. Do not ship asking. Do not quote 79%.

### 6. The reader, measured without pretending acceptances are knowable

gpt-5.4 read 250 trials per patient × 6 patients, discarded and kept stratified, plus 20 pairs
twice. Mini did the same sample.

On trials the cheap filter had thrown away, gpt-5.4 still called the patient a candidate
**6.3%** of the time (38 of 600). After the remaining-list key fixes, the same reads against
the corrected discarded set are **5.6%** (32/569). The gate to withdraw narrowing was 10%.
It holds. Mini was **10.8%** on the original sample — the wrong side of that line, and that
comparison had no gate.

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
description had listed every always-relevant fact, elimination would be 50.2% rather than 43.0%
(was 51.9% rather than 44.7%). So roughly seven percentage points are being lost to the
description-parsing step, not to matching. The parsing instructions have already been revised
once, which is all the plan permits, so this needs a decision rather than another silent retry.

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
not, and cannot, score acceptances. Do not quote 5.6% or 87% as "the system is 87%
accurate."

**The answer key has never been checked by a human on the labels that discard trials.**
Step 9's 30-row sheet was judged by a language model, not by Will; that is a
second-model agreement check (DECISIONS.md), not a human audit. 4 of 29
checkable rows disagreed (13.8%), above 10%. The 52% quote-flag recategorisation
still holds as a citation audit: D+E 1.3%, D+E+C3 now 3.9% after adding a
treatment-naive parent. **441 discards on missing quotes are not 441 wrong
labels.** Triage of the 34 labels: 22 supported (wrong citation only, including
NCT06868485), **12 unsupported** stage-required labels inferred from the title —
212 patient–trial pairs, named in `docs/step9_triage.md`. 282 crossings: 50 have
mixed polarity; the rest are redundant or padding. Scoping re-label is held.

**The test set is 20 invented patients, balanced by design rather than realistic.** Half carry
brain metastases where a real clinic would see nearer a third. So no average across these
patients estimates what a real clinic would experience. And because several facts are yes-or-no,
the 20 patients produce only a handful of distinct outcomes.

**Sparse-input asking used stripped complete descriptions, not real coordinator notes.**
The 45% recovery is an upper bound. This project has no real notes.

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
| Remaining-list re-label (70 crossings) | ~$0.97 |
| Clarifying-question assignment | $1.79 |
| Sparse-note generation and parse (280 configs) | $1.56 |
| **Total** | **~$57** |

No graphics-card time has been rented. Nothing has been trained.

---

## The decision to make

The cheap filter works, and the full read of what it throws away does not find a pile of
joinable trials (5.6% after the key fixes, under 10%). Mini is not a drop-in for that read.
The ceiling of 52% still means matching work cannot reach the original 70% target.

**Three options.**

**A. Stop here and write it up.** Narrowing, matching, the reader, and the remaining-list
key fixes are now all measured. The honest hole left is that acceptances were never scored,
because they cannot be with this key. The corpus-level basket problem (281 of 1,307 trials
list another cancer) is sized and still unfixed.

**B. Re-label the basket/other-cancer quotes, then write it up.** 231 trials have a quote
that names a cancer other than lung. That is the remaining known key risk.

**C. Keep building** — fix take-apart, or try Qwen3 on Lambda as the cheap reader. Steps 6
and 7 stay on hold: mini is not close enough that a trained judge is the next cost win, and
the expensive reader is already the one you would ship.

**Recommendation: write it up.** Both asking tests are measured and neither
ships. UMLS does not cover this corpus (56.4% of phrase occurrences; stop
below 60%). The remaining named residual is the basket/other-cancer quotes
(281 of 1,307 trials). Steps 6 and 7 stay on hold. Real coordinator notes
do not exist for this project; the sparse run is an upper bound on that.
