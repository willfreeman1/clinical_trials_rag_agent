# Sparse-input asking — recover missing facts

Thresholds, seed **202609304**, and the 280 random subsets were committed
before any note was written. This page is the measurement.

The previous run measured **condition-resolution on complete notes**. The
prize was 5.8 points, and 41% of those conditions are about the trial's
own structure. That test had nothing missing to ask about.

This run measures **recovering the six facts when the note is incomplete**.
Age, sex, NSCLC, and clinic setting are always present. They are not one
of the six.

**79% is not a target.** It assumed every conditional discards. Many keep.
It is not reachable under any design. Do not quote it as a gap or a ceiling.

Sparsity is synthetic: complete descriptions with facts removed, not what
a coordinator would type. Real notes omit unpredictably, include irrelevant
detail, and phrase things in ways nobody anticipated. These numbers are an
**upper bound** on realistic input. This project has no real coordinator
notes. That is the honest next measurement, and it does not exist here.

## Gates

| Measure | Result | Gate |
|---|---|---|
| Level 0: 0.0% → 3 questions **45.0%** (half-gap 21.5%) | cleared | ≥ half the gap to 43.0% |
| Level 1: 11.8% → **47.6%** (half-gap 27.4%) | cleared | same |
| Level 2: 18.4% → **48.9%** (half-gap 30.7%) | cleared | same |
| Lower bound (quarter of the gap at 0–2) | not triggered | below a quarter → stop |
| Agent vs full 6-question checklist | **49.8% vs 50.2%** (−0.4pp), **2.96** questions | within 2pp and ≤3 questions |
| Stopping accuracy | 100% (280/280) | ≥70% within one of the right stop |
| Wrongly discarded | **11.4%** (916/8045; 66/581 unique pairs) | **BREACHED — overrides everything above** |

Asking recovers the facts. It does not ship. The 10% gate is unchanged.

## What asking recovers

Matching-gated narrowing against how many of the six facts were in the
note (`k`), then against how many questions were asked in checklist order.

| k | Start (parsed note) | After 3 questions |
|---|---:|---:|
| 0 | 0.0% | 45.0% |
| 1 | 11.8% | 47.6% |
| 2 | 18.4% | 48.9% |
| 3 | 28.1% | 49.9% |
| 4 | 34.9% | 50.1% |
| 5 | 41.3% | 50.2% |
| 6 | 47.4% | 50.2% |

| Questions asked | Mean matching-gated |
|---|---:|
| 0 | 26.0% |
| 1 | 39.5% |
| 2 | 45.8% |
| 3 | 48.9% |
| 4 | 49.9% |
| 5 | 50.2% |
| 6 | 50.2% |

With disease alone there is nothing to filter on (k=0 start is 0.0%).
Three checklist questions take that to 45.0% — past the 43.0% figure the
original notes reached, and most of the way to 50.2%, which is matching-
gated when all six facts are listed. Questions 4–6 add 1.4 points.
Almost all of the prize is in the first three facts, in discard-power
order: genetic marker, stage, immunotherapy.

The 50.2% landing point is the parse-perfect matching-gated number
already on file, not the 43.0% original-note figure. 43.0% was lower
because six of twenty original descriptions omitted the marker. These
stripped notes, once the missing facts are asked back, list the six
facts. That is why the checklist mean is 50.2%.

## Agent vs checklist

The baseline asks every missing fact, in discard-power order. The agent
uses the same order and stops after the first observed increment under
2 points.

| | Narrowing | Questions |
|---|---:|---:|
| Full checklist | 50.2% | all missing (up to 6) |
| Agent | 49.8% | **2.96** |

The agent lands within 0.4 points of asking everything, at three
questions. That is the edge the design asked for: **fewer questions for
the same narrowing**, and **knowing when to stop**. It is not a clever
order. A checklist of the three highest-value facts is already close to
optimal; stopping is what the agent adds.

Stopping accuracy is 100% within one question of the right stop. That
gate is weak by construction: the agent and the right stop walk the
same increment sequence, and "within one" absorbs the off-by-one of
including versus skipping the last small increment. It is not evidence
of a learned stopping policy. The real stopping result is the 2.96 vs
checklist comparison above.

79 questions the agent asked recovered a fact and changed narrowing by
zero. 203 on the full checklist walk. Those are facts whose gold value
does not discard any remaining trial (the patient's answer keeps them).

## First fact asked

The agent always asks the highest-power missing fact. Counts of the first
question, by k:

- k=0: marker 40 (always — nothing is listed)
- k=1: marker 31, stage 9
- k=2: marker 29, stage 10, immunotherapy 1
- k=3: marker 20, stage 12, immunotherapy 8
- k=4: stage 13, marker 13, immunotherapy 9, platinum 4, brain 1
- k=5: immunotherapy 11, stage 10, platinum 6, marker 5, brain 5, autoimmune 3
- k=6: brain 16, autoimmune 15, immunotherapy 9

At k=6 the note contains all six facts, so a first question means the
parser missed one. It missed something in all 40 of those notes. The
facts it missed were the lower-power ones more often than the marker.

## Parse quality at low completeness

The notes were parsed with the existing Step 4 parser, not a constructed
fact list. Precision is 100% at every k: the parser never invented an
excluded fact.

| k | Recall of intended facts | Notes that missed at least one |
|---|---:|---:|
| 0 | 100% | 0 / 40 |
| 1 | 97.5% | 1 / 40 |
| 2 | 90.0% | 8 / 40 |
| 3 | 85.0% | 17 / 40 |
| 4 | 79.4% | 22 / 40 |
| 5 | 78.0% | 30 / 40 |
| 6 | 71.2% | 40 / 40 |

A two-line note parses more reliably than a full one, not less. There is
nothing to miss. The original Step 4 problem — denser descriptions drop
the marker and other rows — reappears as soon as the note has several
facts. Asking then recovers the parse miss as well as the stripped fact.

## Leak check

280 notes, gpt-5.4, mechanical regex on every excluded fact (including
negation). Reject and regenerate, up to five tries.

**0 / 280 leaked on the first draft.** Final leak rate 0. Cost $0.26.
Under this check, the model followed include/exclude without leaking.
That is a small finding in its own right. It is not a claim about real
coordinator text.

## Wrongly discarded — measured fresh

Last time's 10.4% was condition-resolution. This is fact recovery.
The system already discards on facts at 5.6%. The question was whether
recovering a plain fact behaves better or worse. It is worse, overall.

| Slice | Rate |
|---|---|
| Agent discarded set, pooled across 280 configs | **11.4%** (916/8045) |
| Unique patient–trial pairs | 11.4% (66/581) |
| Trials that were already in the original discarded sample | **4.6%** (300/6561) |
| Originally-kept trials the agent now discards | **41.5%** (616/1484) |
| Same rate at every k | 11.4% at k=0 through k=6 |

The agent always asks until it is near 50% narrowing, so the discarded
set after asking is essentially the complete-six-facts discarded set,
regardless of how sparse the note started. That set is larger than the
original 43.0% discarded set. On the trials the original system already
threw away, the reader still agrees (4.6%, under 10%). The breach is
the extra discards: recovering omitted facts throws away trials the
original notes kept, and the expensive reader calls 41.5% of those a
candidate.

So the 10% gate which held at 43.0% (5.6%) fails at 50.2% (11.4%).
More complete fact lists discard more, and the additional discards are
the borderline ones. Asking is how a sparse note gets there. The gate
is not relaxed.

## Cost and rounds

| | |
|---|---:|
| Note generation | $0.26 |
| Step 4 parse | $1.30 |
| Scoring | no extra API |
| **Total this run** | **$1.56** |
| Mean questions per configuration | 2.96 |

280 configurations. 20 patients × k=0..6 × 2 random subsets. Seed
202609304. Random subsets, not a fixed ladder.

Will's check sheets were not regenerated. Conditional-rule asking was
not re-run. Steps 6 and 7 were not started.

## Decision

**Do not ship sparse-input asking.** Recovery works — three questions
from an empty note reach 45%, and the agent matches a six-question
checklist at three questions. Wrongly discarded is 11.4%, over 10%.
That overrides the recovery.

The last test and this one are different questions with the same
product conclusion. Condition-resolution had a 5.8-point prize and
failed safety. Fact recovery has a ~43-point prize, takes most of it
in three questions, and fails safety for a different reason: the
complete-fact discarded set includes joinable trials the original
43.0% system had kept.

The honest remaining measurement is real coordinator notes. This run
is an upper bound on that, and should not stand unqualified.
