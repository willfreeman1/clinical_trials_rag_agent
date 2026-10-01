# What is in the TREC shortlist (2021/2022 only)

Gates committed in `697d808` before any composition count.
2023 was not run. Same keyword-hybrid shortlist as the rerank run.
Nothing discarded. No reader. No trained ranker.

The 68/17/16 split is of **all judgments**, not of the shortlist.
The 144 / 91% figure is what you get if excluded trials are retrieved
at the same rate as eligible ones. That is the estimate under test.

## Composition of the shortlist (mean per patient)

| Year | Eligible (2) | Excluded (1) | Judged 0 | Unjudged | Disease-relevant (1+2) | Junk (0 + unjudged) |
|---|---:|---:|---:|---:|---:|---:|
| 2021 | 66.9 (4.3%) | 73.0 (4.7%) | 143.0 (9.1%) | 1287.1 (82.0%) | 139.9 (8.9%) | 1430.1 (91.1%) |
| 2022 | 72.3 (4.5%) | 52.7 (3.3%) | 261.2 (16.4%) | 1208.8 (75.8%) | 125.0 (7.8%) | 1470.0 (92.2%) |

## Retrieval rate at 6% of collection

| Year | Eligible recall | Excluded recall |
|---|---:|---:|
| 2021 | 91.6% | 92.1% |
| 2022 | 91.4% | 87.6% |

## Against the estimate

The estimate holds. Junk is the majority of the shortlist and disease-relevant volume is near 144. Retrieval is imprecise. Tasks 2 and 3 have a premise.

## Keywords that contribute the most junk in the shortlist

A trial can be hit by several keywords. These counts are BM25 top-1000
hits that also sit in the fused shortlist, summed over patients.

| Year | Keyword | Patients | Hits in shortlist | Junk share | Eligible | Excluded |
|---|---|---:|---:|---:|---:|---:|
| 2021 | abdominal pain | 8 | 3082 | 91.6% | 149 | 110 |
| 2021 | hypertension | 13 | 2502 | 94.4% | 86 | 53 |
| 2021 | vomiting | 8 | 2100 | 95.7% | 41 | 49 |
| 2021 | nausea | 7 | 1981 | 94.5% | 38 | 70 |
| 2021 | urinary urgency | 3 | 2153 | 83.9% | 221 | 125 |
| 2021 | fever | 7 | 1870 | 95.5% | 29 | 56 |
| 2021 | coronary artery disease | 5 | 2000 | 88.3% | 104 | 130 |
| 2021 | obesity | 8 | 1902 | 86.9% | 174 | 75 |
| 2021 | prostate health | 3 | 2081 | 78.8% | 323 | 119 |
| 2021 | urinary frequency | 3 | 1907 | 83.5% | 200 | 115 |
| 2021 | breast cancer | 2 | 1808 | 84.4% | 188 | 94 |
| 2021 | HER2-positive breast cancer | 2 | 1802 | 84.4% | 188 | 94 |
| 2021 | ER-negative breast cancer | 2 | 1765 | 84.1% | 188 | 93 |
| 2021 | PR-negative breast cancer | 2 | 1745 | 83.9% | 188 | 93 |
| 2021 | urinary retention | 3 | 1721 | 83.9% | 205 | 72 |
| 2022 | genetic disorder | 9 | 3412 | 94.8% | 95 | 82 |
| 2022 | genetic testing | 7 | 2773 | 95.4% | 57 | 71 |
| 2022 | muscle weakness | 4 | 2092 | 93.0% | 121 | 25 |
| 2022 | bleeding tendency | 3 | 2142 | 88.3% | 117 | 133 |
| 2022 | bleeding disorder | 3 | 2009 | 87.3% | 112 | 144 |
| 2022 | genetic counseling | 5 | 1802 | 96.0% | 26 | 46 |
| 2022 | muscle atrophy | 3 | 1621 | 93.0% | 94 | 19 |
| 2022 | eye examination | 2 | 1434 | 98.5% | 13 | 8 |
| 2022 | skin rash | 3 | 1441 | 97.2% | 23 | 18 |
| 2022 | bleeding diathesis | 2 | 1408 | 91.3% | 81 | 42 |
| 2022 | ocular examination | 2 | 1258 | 98.6% | 11 | 7 |
| 2022 | bleeding symptoms | 2 | 1309 | 91.4% | 74 | 39 |
| 2022 | hereditary bleeding disorder | 2 | 1247 | 91.7% | 67 | 36 |
| 2022 | joint pain | 3 | 1605 | 71.1% | 374 | 90 |
| 2022 | hypertension | 6 | 1176 | 95.3% | 35 | 20 |

## Decision

`run_2_and_3`

Tasks 2 and 3 were run under `c178dc4`. Best 2021 Recall@10 is
6.3%. Not a pipeline change. See `docs/trec_shortlist_fix.md`.

Per-patient JSON: `data/trec/trec_shortlist_diagnosis.json`.
No overall accuracy. The system does not say a patient qualifies.

