# Eligibility prompt v2 on the same 30 patients

Gates committed in `4424157` before any v2 score.
Same shortlist, same 30 patients (seed **20261001**). Prompt and
scoring both changed, so this is not a matched model comparison.
The question is whether true positives (human label 2) rose on the page.
The system does not say a patient qualifies.

GPU: NVIDIA H100 PCIe. Seconds: 25022.2. Scored: 47475.

**Decision:** do not replace v1 on this evidence

## 2021 (n=15)

| Arm | @10 | @20 | @50 | @100 | @200 | @500 | P@10 | P@20 | 10-in-20 |
|---|---|---|---|---|---|---|---|---|---|
| `baseline` | 8.5% | 13.8% | 25.3% | 36.0% | 53.3% | 76.7% | 30.0% | 28.3% | 2/15 |
| `v1_cont` | 14.2% | 22.7% | 36.1% | 51.9% | 68.7% | 85.4% | 55.3% | 48.7% | 7/15 |
| `v2_p_eligible` | 9.2% | 13.1% | 23.9% | 37.4% | 54.3% | 79.0% | 39.3% | 34.0% | 5/15 (Wilson 15–58%) |

| Arm | Read 20 | Read 200 | Read 500 |
|---|---:|---:|---:|
| `baseline` | 1.00x (17) | 1.00x (170) | 1.00x (402) |
| `v1_cont` | 2.73x (50) | 2.16x (389) | 1.64x (693) |
| `v2_p_eligible` | 1.40x (28) | 1.16x (202) | 1.13x (460) |

- Word mix: {'eligible': 812, 'ineligible': 18641, 'unsure': 4097}
- Word 'eligible' on label 2: 224/958 (macro TPR 24.9%)
- Word 'eligible' on label 1: 78/1282 (macro 4.2%)
- Unsure among judged 1+2: 35.2%
- P(eligible) AUROC label 1 vs 2: 0.607

## 2022 (n=15)

| Arm | @10 | @20 | @50 | @100 | @200 | @500 | P@10 | P@20 | 10-in-20 |
|---|---|---|---|---|---|---|---|---|---|
| `baseline` | 6.2% | 10.7% | 23.6% | 36.5% | 51.9% | 69.8% | 40.7% | 36.0% | 4/15 |
| `v1_cont` | 11.0% | 17.9% | 31.6% | 46.5% | 62.3% | 74.9% | 62.7% | 58.0% | 9/15 |
| `v2_p_eligible` | 7.7% | 12.1% | 20.4% | 36.7% | 53.9% | 72.0% | 46.7% | 38.3% | 5/15 |

| Arm | Read 20 | Read 200 | Read 500 |
|---|---:|---:|---:|
| `baseline` | 1.00x (16) | 1.00x (175) | 1.00x (438) |
| `v1_cont` | 3.01x (45) | 1.86x (324) | 1.40x (626) |
| `v2_p_eligible` | 2.30x (31) | 1.27x (216) | 1.15x (503) |

- Word mix: {'eligible': 518, 'ineligible': 19899, 'unsure': 3508}
- Word 'eligible' on label 2: 233/1085 (macro TPR 18.3%)
- Word 'eligible' on label 1: 34/725 (macro 3.9%)
- Unsure among judged 1+2: 38.8%
- P(eligible) AUROC label 1 vs 2: 0.590

The replace-gate is 2021 P@20 ≥ 50.7% with 2022 not more than 2 points worse than 58.0%.
Depth 200 is reported, not the replace-gate.

## What this means

The new prompt did not raise true positives. It made the first page
worse on both years, and it made 1-vs-2 separation worse (AUROC
**0.60** vs v1 **0.745**).

Across both years the word mix was **1,330 eligible / 38,540
ineligible / 7,605 unsure**. Among judged joinable pairs (label 2)
it said eligible **457**, ineligible **553**, unsure **1,033**. So
the commonest call on a trial humans marked joinable was “unsure,”
and it said no more often than yes.

That is why ranking died. The old “if unsure, pick 2” was a bad
*judgment* rule, but it kept maybes in the middle of the list,
where token probabilities could still order them. The new rule
forced a hard call. Unsure and ineligible both get a tiny
P(eligible), so joinable trials sank with the junk. Writing a
CHECK did not fix the thinking: some eligible verdicts still
argued for exclusion in the check text.

Do not replace v1. A later model test should not repeat 30 × 1,570
unjudged pairs. The question that is still open is whether a
stronger model can tell judged joinable (2) from judged
excluded-same-disease (1) when the fact is in the note. That only
needs the judged pairs.
