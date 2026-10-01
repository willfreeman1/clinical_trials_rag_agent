# Clarifying-question agent

Thresholds were committed before the oracle draw and before assignment.
Old narrowing numbers stay on disk. This page is the new measurement.

The loop is a LangGraph StateGraph (rank → ask → fold, cap 3). If one round captures nearly everything, the framework is heavier than the problem.

| | Before | After 3 ranked questions | Gate |
|---|---:|---:|---|
| Perfect-finder ceiling | 51.9% | 56.0% | missed 65%; STOP (below a quarter of the gap) |
| Matching-gated | 43.0% | 48.0% | reported, no recovery gate |
| Wrongly discarded (lost-joinable) | 5.6% | 10.4% (63/605) | BREACHED — bad trade, overrides recovery |
| Ranked-3 vs random-3 unlocks | 148.2 vs 122.3 | ratio 1.2122 | missed 1.5× — drop ranking |

## Recovery curve (perfect finder)

| Questions | Narrowing |
|---|---:|
| 0 | 51.9% |
| 1 | 54.2% |
| 2 | 55.2% |
| 3 | 56.0% |
| 5 | 56.5% |
| Everything live | 57.7% |

Ranked-3 settles 65.4% of what asking every live question settles.

## Does round two earn itself?

Round 1 alone reaches 54.2%. Mean extra discards in round 2: 13.3.
**Round two adds a little, but the loop is not the product.** Round 1 already has almost all of the (small) gain. LangGraph is heavier than the problem.

Questions asked (count of patients): {'amenable_to_curative_therapy': 14, 'brain_symptoms': 10, 'brain_treatment': 9, 'systemic_washout_weeks': 9, 'leptomeningeal': 7, 'immuno_washout_weeks': 4, 'autoimmune_activity': 1, 'autoimmune_systemic_months': 1}

## Why 56% and not 65%

The 51.9→78.2 gap assumed that a settled conditional **discards**. For these 20
patients it often does not. Five of ten brain-mets patients are treated and
stable: asking the question keeps the trial, which is correct. Nineteen of
twenty have no autoimmune disease, so 376 autoimmune tags never go live.
789 of 1,918 assigned rules were `other` (cohort, trial histology, protocol
part) and cannot be asked of a coordinator. Asking every live question still
only reaches 57.7%. The 78.2% optimistic ceiling was not sitting in unasked
questions. It was sitting in exceptions the patients meet, and in conditions
that are not facts about the patient.

So the complexity is not earning itself. That is the stop the lower-bound
gate asked for. The 10% wrongly-discarded gate also failed (10.4%), which
would have vetoed the feature even if recovery had cleared 65%.

Ranking missed 1.5× (1.21×). Ranked-3 still settles 65% of asking-everything,
so coverage ranking is doing some work, but not enough to keep. A fixed order
would have been enough to test, and random was close.

Round 1 reaches 54.2%; rounds 2–3 add two more points. Half the patients
discard a few extra trials in round 2. That is not a loop. LangGraph was
heavier than the problem. Saying so is the point of having built it.

Assignment: 1,918 rules, $1.79, gpt-5.4. Scoring 1.508s, no extra API.

Will's check sheets were not regenerated. Steps 6 and 7 were not started.
