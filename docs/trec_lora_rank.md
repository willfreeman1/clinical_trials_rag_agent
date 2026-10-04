# Eligibility as a ranker: keep the topical slice

**Keep the topical slice as the default sort of the
shortlist.** The pre-specified cascade — re-sort the
top 100 of that list with the eligibility adapter —
is **+4.6 points of P@10** on 50 patients (0.616 vs
0.570). The paired patient-resampled interval is
**−0.4 to +9.6 points**. Zero sits inside it. Call
the cascade **promising, not better**.

The adapter alone is 0.550 against 0.570. That
interval is **−7.4 to +3.0 points**. Zero sits
inside that one too, and the ordering may not be
real. On the field’s graded metric the adapter
alone is worse: NDCG@10 **−0.069** (−0.125 to
−0.012), and zero is outside that interval.

That is a product choice, not a pass/fail gate.
Config and pair IDs were committed in `3b50e06`
before these scores. 2023 was not used. Nothing
was dropped from the shortlist. The 50 patients
are held-out 2022; they were not used to pick the
learning rate.

The system does not say a patient qualifies.

## How to read the numbers

**P@10** is how many of the first ten trials are
human-joinable (label 2), as a fraction. Excluded
(label 1: right disease, a rule fails) does not
count. That is TREC’s binary rule.

**NDCG@10** is TREC’s graded rule: eligible 2,
excluded 1, not relevant or unjudged 0. Order in
the top ten matters, and excluded is a partial
hit.

**Equivalent depth** is: reading N trials in this
order finds as many joinable trials as reading
how many in the fused search order. The multiple
is against the fused list’s *own* equivalent
depth at that N, so the fused row is always 1.0×.
That correction is from `docs/trec_qwen_preview.md`.
Do not read the raw depth against N; flat stretches
in the baseline curve made every arm look negative
in the first version of that table.

**10-in-20** is how many patients have at least
ten joinable trials in the first twenty. It is a
coarse count. It does not carry a claim by itself.

Intervals resample **patients**, not pairs, 5,000
draws, seed **20261009**. The earlier AUROC work
used the same idea (seed 20261004).

This is a reorder of the judged-pool shortlist,
not a NIST `trec_eval` run from the 375,000-trial
snapshot. See the pool caveat in
`docs/trec_published_standings.md`. Do not put
these P@10 or NDCG@10 numbers next to TD-MINER,
h2oloo, or Kusa as a win or a tie.

## 1. The cascade’s win has an interval

Same 50 patients, same 1,595-trial shortlist,
same human labels. Difference is cascade minus
topical slice, then patients are redrawn.

| Contrast | Point | Interval | Cascade / adapter higher | Topical higher | Tie |
|---|---:|---|---:|---:|---:|
| Cascade top-100 − topical, P@10 | +0.046 | −0.004 to +0.096 | 22 | 15 | 13 |
| Cascade top-100 − topical, NDCG@10 | +0.000 | −0.052 to +0.053 | 23 | 26 | 1 |
| Adapter-alone − topical, P@10 | −0.020 | −0.074 to +0.030 | 17 | 20 | 13 |
| Adapter-alone − topical, NDCG@10 | −0.069 | −0.125 to −0.012 | 18 | 31 | 1 |

Zero is inside the first three. The fourth
interval sits entirely below zero: replacing the
topical list with the adapter **hurts** graded
top-ten quality.

10-in-20 moves from 25/50 (topical) to 30/50
(cascade 100) and 33/50 (cascade 25). That is
suggestive and coarse. It is not the claim.

The earlier write-up treated 0.616 as a win and
said “layer, do not replace.” The point estimates
are the same. The interval was missing. With it,
layering at 100 is not a demonstrated win.

## 2. Equivalent depth — what each stage is for

Multiple of the fused list’s own equivalent
depth at the same N. Baseline row is calibration.

| Arm | P@10 | P@20 | 10-in-20 | Read 20 | Read 200 | Read 500 |
|---|---:|---:|---:|---:|---:|---:|
| Fused search order | 0.386 | 0.361 | 13 / 50 | 1.00× (17) | 1.00× (177) | 1.00× (409) |
| Topical slice, continuous | 0.570 | 0.530 | 25 / 50 | 3.42× (45) | 2.77× (430) | 1.95× (755) |
| Topical slice, typed digit | 0.514 | 0.499 | 27 / 50 | 2.89× (41) | 2.50× (384) | 1.76× (701) |
| Eligibility adapter, continuous | 0.550 | 0.520 | 28 / 50 | 4.03× (54) | **3.28× (508)** | **2.23× (837)** |
| Eligibility adapter, typed digit | 0.514 | 0.491 | 25 / 50 | 3.34× (43) | 2.88× (440) | 2.22× (836) |
| Cascade top 25 | 0.624 | 0.552 | 33 / 50 | 3.63× (50) | 2.77× (430) | 1.95× (755) |
| Cascade top 50 | 0.606 | 0.559 | 32 / 50 | 3.68× (53) | 2.77× (430) | 1.95× (755) |
| Cascade top 100 | 0.616 | 0.567 | 30 / 50 | 4.25× (57) | 2.77× (430) | 1.95× (755) |
| Cascade top 200 | 0.590 | 0.531 | 29 / 50 | 4.03× (54) | 2.77× (430) | 1.95× (755) |
| Cascade top 300 | 0.580 | 0.534 | 27 / 50 | 4.10× (54) | 2.88× (449) | 1.95× (755) |
| Cascade top 500 | 0.574 | 0.531 | 29 / 50 | 4.05× (54) | 3.03× (474) | 1.95× (755) |

Every arm keeps **91.4%** of the joinable trials
that were already in the shortlist. Reordering
cannot raise that.

**Fine-tuning fixed the depth-200 loss.
The cascade did not, and was not supposed to.**

Run 2, untrained eligibility on the 15-patient
2022 sample: 1.86× at 200 against the topical
slice’s 2.24× on those same 15. That comparison
recomputes exactly here. On those 15, the
fine-tuned adapter is **3.39×** at 200. On all
50 it is **3.28×** against topical **2.77×**.

Cascade windows of 25, 50, 100 and 200 have the
**same** equivalent depth at 200 as the topical
slice (2.77×). The tail of the list is still in
topical order, so a short head re-sort cannot
win a depth-200 reading budget. That is a real
finding about what each stage is for, not a
problem: the adapter earns the page only when
it is allowed to touch the head, and it earns
depth 200 only when it is allowed to sort the
whole list. Those are different jobs.

## 3. Cascade cutoff is a cost-quality curve

Top 100 was a guess. Sweep: 25, 50, 100, 200,
300, 500. Rate from this run: 79,750 scores,
3.71 hours, $6.65. Cost scales with pairs.

| Cutoff | P@10 | P@20 | Read 20 | Read 200 | Δ P@10 vs topical (interval) | GPU, 50 patients | Per patient |
|---|---:|---:|---:|---:|---|---:|---:|
| 25 | 0.624 | 0.552 | 3.63× | 2.77× | +0.054 (0.016 to 0.092) | $0.10 / 3.5 min | $0.002 |
| 50 | 0.606 | 0.559 | 3.68× | 2.77× | +0.036 (−0.010 to 0.082) | $0.21 / 7 min | $0.004 |
| 100 | 0.616 | 0.567 | 4.25× | 2.77× | +0.046 (−0.004 to 0.096) | $0.42 / 14 min | $0.008 |
| 200 | 0.590 | 0.531 | 4.03× | 2.77× | +0.020 (−0.036 to 0.074) | $0.83 / 28 min | $0.017 |
| 300 | 0.580 | 0.534 | 4.10× | 2.88× | +0.010 (−0.046 to 0.064) | $1.25 / 42 min | $0.025 |
| 500 | 0.574 | 0.531 | 4.05× | 3.03× | +0.004 (−0.050 to 0.058) | $2.08 / 70 min | $0.042 |
| Whole shortlist (adapter only) | 0.550 | 0.520 | 4.03× | 3.28× | −0.020 (−0.074 to 0.030) | $6.65 / 3.71 h | $0.133 |

The curve is **not flat between 50 and 300**.
It peaks in the 25–100 band (0.624 / 0.606 /
0.616) and then drops: 0.590 at 200, 0.580 at
300. 25–100 is a plateau. Past 100, extra
eligibility scores dilute the page back toward
the adapter-only number. The cutoff is not
delicate inside that first band, and it is not
free to wander up to 300.

Cutoff **25** is the only pre-computed window
whose P@10 interval excludes zero (+5.4 points,
0.016 to 0.092; 26 patients higher, 11 lower,
13 tie). It is also the cheapest. That window
was **not locked before the scores**. It is a
finding from the sweep, not a confirmed ship
rule. Its NDCG@10 interval still includes zero
(+0.027, −0.013 to +0.065).

If eligibility is scored for ranking at all,
**25 is the operating point**: about **$0.002
per patient**, fourteen seconds of A100-class
GPU at this rate, best first page in the sweep.
Do not spend $6.65 to sort the whole shortlist.
Do not treat 25 as settled without a locked
confirmation on another year.

## 4. TREC-official metrics

Definitions follow the TREC 2022 overview, not
our earlier conventions.

| Column | Rule |
|---|---|
| NDCG@10 | Graded. Eligible 2, excluded 1, not relevant / unjudged 0. Ideal DCG from all qrels for that topic. |
| P@10 | Binary. Eligible is relevant; excluded is merged with not relevant. |
| RPrec | Binary. Precision at R, R = number of eligible qrels for the topic. |
| MRR | Binary. 1 / rank of the first eligible trial; 0 if none. |

Means are the headline (TREC and TrialGPT).
Medians are a separate column (TrialMatchAI’s
headline). Intervals resample patients, 5,000
draws, seed 20261009. Both years where the arm
exists; 2022 only where it does not.

The three fine-tuned seeds cannot sit on this
axis. Seeds 20261003 and 20261006 were scored
only on judged 1-and-2 pairs (~125 per patient),
not the 1,595-trial shortlist. Burying the
unscored rows as zero would invent a ranking.
Their comparison stays the AUROC spread:
**0.793, 0.770, 0.773**. Mean **0.779**. The
ranking adapter is seed **20261007** (0.773),
the middle seed, closest to the mean. Do not
quote the best.

Untrained eligibility was scored on the
15-patient sample per year, not on all 75 / 50.
Those rows are marked.

### Headline arm, both years

One arm, both years: **topical slice,
continuous score**. It is the current default,
it exists on all 75 + 50 patients, and it is
not a different model per year. The old
standings row mixed 2021’s best rerank arm
(0.510 / 0.384) with 2022 MedCPT-CE (0.586 /
0.508). That is HANDOFF error 4.

| Year | n | NDCG@10 mean (interval) | NDCG@10 median | P@10 mean (interval) | P@10 median | RPrec mean | MRR mean |
|---|---:|---|---:|---|---:|---:|---:|
| 2021 | 75 | 0.657 (0.617–0.696) | 0.680 | 0.519 (0.468–0.567) | 0.500 | 0.415 | 0.700 |
| 2022 | 50 | 0.662 (0.585–0.734) | 0.696 | 0.570 (0.498–0.646) | 0.600 | 0.439 | 0.741 |

These are still judged-pool numbers. They are
not a NIST submission from the 375k snapshot.

### 2021, all 75 patients

NDCG@10 graded 2/1/0. P@10, RPrec, MRR binary
(eligible only).

| Arm | n | NDCG@10 mean (interval) | NDCG median | P@10 mean (interval) | P@10 median | RPrec mean (interval) | MRR mean (interval) |
|---|---:|---|---:|---|---:|---|---|
| Fused search order | 75 | 0.453 (0.409–0.497) | 0.460 | 0.285 (0.235–0.337) | 0.200 | 0.238 (0.205–0.272) | 0.484 (0.404–0.567) |
| gpt-4o-mini, full shortlist | 75 | 0.568 (0.522–0.612) | 0.582 | 0.384 (0.331–0.437) | 0.400 | 0.353 (0.311–0.393) | 0.609 (0.529–0.687) |
| Topical slice, digit | 75 | 0.597 (0.553–0.640) | 0.606 | 0.431 (0.377–0.484) | 0.400 | 0.396 (0.355–0.437) | 0.658 (0.578–0.740) |
| **Topical slice, continuous** | 75 | **0.657 (0.617–0.696)** | 0.680 | **0.519 (0.468–0.567)** | 0.500 | 0.415 (0.377–0.455) | 0.700 (0.623–0.777) |
| Title+conditions, digit | 75 | 0.578 (0.536–0.621) | 0.581 | 0.412 (0.359–0.465) | 0.400 | 0.366 (0.325–0.408) | 0.609 (0.529–0.689) |
| Title+conditions, continuous | 75 | 0.613 (0.576–0.651) | 0.625 | 0.451 (0.397–0.501) | 0.400 | 0.385 (0.346–0.426) | 0.676 (0.602–0.750) |
| MedCPT-CE, raw note | 75 | 0.538 (0.486–0.589) | 0.561 | 0.348 (0.292–0.407) | 0.300 | 0.289 (0.249–0.329) | 0.557 (0.470–0.644) |
| MedCPT-CE, keywords | 75 | 0.551 (0.497–0.605) | 0.542 | 0.369 (0.305–0.435) | 0.300 | 0.278 (0.236–0.320) | 0.545 (0.460–0.630) |
| Untrained eligibility, continuous | 15 | 0.610 (0.519–0.701) | 0.620 | 0.553 (0.460–0.647) | 0.500 | 0.398 (0.318–0.487) | 0.724 (0.571–0.869) |

### 2022, all 50 patients

Same rules as the 2021 table.

| Arm | n | NDCG@10 mean (interval) | NDCG median | P@10 mean (interval) | P@10 median | RPrec mean (interval) | MRR mean (interval) |
|---|---:|---|---:|---|---:|---|---|
| Fused search order | 50 | 0.506 (0.434–0.578) | 0.491 | 0.386 (0.318–0.458) | 0.300 | 0.296 (0.245–0.350) | 0.596 (0.502–0.687) |
| gpt-4o-mini, full shortlist | 50 | 0.627 (0.555–0.697) | 0.645 | 0.492 (0.416–0.568) | 0.500 | 0.415 (0.356–0.476) | 0.695 (0.602–0.786) |
| Topical slice, digit | 50 | 0.635 (0.566–0.703) | 0.682 | 0.514 (0.442–0.588) | 0.500 | 0.427 (0.365–0.488) | 0.720 (0.628–0.805) |
| **Topical slice, continuous** | 50 | **0.662 (0.585–0.734)** | 0.696 | **0.570 (0.498–0.646)** | 0.600 | 0.439 (0.377–0.502) | 0.741 (0.643–0.837) |
| Title+conditions, digit | 50 | 0.622 (0.552–0.691) | 0.671 | 0.490 (0.416–0.564) | 0.500 | 0.406 (0.345–0.466) | 0.710 (0.616–0.805) |
| Title+conditions, continuous | 50 | 0.618 (0.542–0.692) | 0.643 | 0.500 (0.426–0.576) | 0.500 | 0.411 (0.348–0.475) | 0.665 (0.561–0.765) |
| MedCPT-CE, raw note | 50 | 0.601 (0.523–0.677) | 0.680 | 0.482 (0.398–0.560) | 0.500 | 0.347 (0.289–0.407) | 0.744 (0.640–0.843) |
| MedCPT-CE, keywords | 50 | 0.620 (0.547–0.690) | 0.680 | 0.508 (0.432–0.582) | 0.500 | 0.372 (0.314–0.431) | 0.687 (0.588–0.786) |
| Eligibility adapter, continuous | 50 | 0.592 (0.528–0.655) | 0.569 | 0.550 (0.484–0.616) | 0.500 | 0.461 (0.406–0.516) | 0.737 (0.652–0.817) |
| Eligibility adapter, digit | 50 | 0.617 (0.557–0.676) | 0.615 | 0.514 (0.444–0.582) | 0.400 | 0.453 (0.399–0.507) | 0.693 (0.611–0.775) |
| Cascade top 25 | 50 | 0.688 (0.612–0.758) | 0.725 | 0.624 (0.546–0.702) | 0.700 | 0.446 (0.382–0.508) | 0.831 (0.749–0.907) |
| Cascade top 100 | 50 | 0.662 (0.595–0.725) | 0.661 | 0.616 (0.546–0.688) | 0.600 | 0.471 (0.412–0.531) | 0.782 (0.700–0.860) |
| Untrained eligibility, continuous | 15 | 0.685 (0.537–0.822) | 0.778 | 0.627 (0.480–0.773) | 0.600 | 0.440 (0.322–0.562) | 0.871 (0.713–1.000) |

On official NDCG@10 the topical slice and the
pre-specified cascade are the same mean (0.662).
Cascade 25 is higher on the point estimate
(0.688) and still overlaps topical on the
paired interval.

## What was scored

**Adapter:** seed **20261007**, the middle of
the three 1e-5 runs (0.793, 0.770, 0.773),
closest to the mean **0.779**. Not the 0.793
seed. Scoring all three adapters on the
shortlist would have tripled the GPU bill.

**Question:** the v1 eligibility prompt.
Continuous score is the expected digit from
the 0–3 token probabilities. The typed digit
is the backup arm and lost on the page.

**Cascade:** sort the shortlist by the topical
slice, then re-sort only the first N with the
adapter continuous score. The tail stays in
topical order.

79,750 pairs (50 × 1,595). An A100 SXM4,
**3.71 hours, $6.65**, then terminated through
the API. H100 was out of stock at launch.

## Why replace loses the page

The adapter is better at joinable versus
excluded (AUROC 0.773 on this seed). The first
page is still a fight with **junk**: trials
that matched a generic word and are not about
this patient. The topical slice is a “is this
even the right problem?” score on title,
conditions, and a short criteria slice. That
is the cheaper question, and it is the one
NDCG@10 still needs — excluded trials in the
top ten are a partial hit, and the adapter
pulls them up.

Once junk is mostly out of the way, the
eligibility score starts to pay at depth 200.
That is why adapter-only equivalent depth at
200 is the best of the whole-list sorts, and
why a short cascade can move P@10 without
moving depth 200.

## Recommendation

**Default ranking path**

1. Keep keyword-hybrid retrieval. Top 6% stays.
2. Sort that whole list with the topical slice,
   continuous score. That is the default.
   Incremental adapter cost: **$0 per patient**.
3. Do not ship adapter-only. It loses NDCG@10
   by enough that zero is outside the interval.
4. Do not ship the pre-specified top-100
   cascade as “better.” It is promising.

**If eligibility is scored for ranking anyway**

Use cutoff **25**, not 100: **$0.002 per
patient**, about 3.5 minutes of A100-class
GPU for all 50, best P@10 in the sweep, only
cutoff whose P@10 interval excludes zero.
Say it is a sweep finding. Do not treat it as
locked.

The adapter stays in the pipeline as a
1-versus-2 score (AUROC 0.779, 0.770–0.793)
and as the thing that wins equivalent depth
at 200 when it is allowed to sort the whole
list. Those jobs are real. They are not the
default first-page sort.

## What this is not

- Not a decision that anyone qualifies.
- Not official TREC against the 375k snapshot.
- Not 2021 adapter ranking, and not the
  other-way fold.
- Not GPT-5.4 on these 50 shortlists.
- Not a reason to discard anything from the
  1,595.
- Not a confirmed win for cascade 25. That
  cutoff was read off the same 50 patients.

## Measurements this suggests (not started)

1. **Lock cutoff 25 and confirm on 2021.**
   Needs a full 2021 adapter shortlist
   (~75 × 1,570 ≈ 118k pairs, about $10 and
   5.5 hours at this run’s rate). Do not
   start it from this brief.
2. **Full-shortlist scores for the other two
   seeds** if a ranking seed-spread is
   required. Two more 50-patient jobs,
   about $13. The AUROC spread already
   exists; do not invent official P@10 from
   the 1-and-2-only files.
3. Leave 2023, the reader, and a 375k
   official submission alone until someone
   asks.

The system does not say a patient qualifies.
