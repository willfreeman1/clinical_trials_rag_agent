# Does UMLS cover this corpus's vocabulary?

Short Step 1 `concept` phrases, not eligibility sentences.
Gates committed in `107c1e2` before lookups. No download. No TREC.
Gene-symbol matching is not replaced.

Distinct phrases: **5578**. Occurrences: **13033**. Appear once: 4276 (76.7% of distinct).

## Gates

| Measure | Result | Gate |
|---|---|---|
| Coverage by occurrence | 56.4% | STOP below 60% |
| Coverage of distinct phrases | 30.5% | reported, no gate |
| Resolution precision (name agreement) | 66.2% (1125/1700) | BREACHED below 90% |

Excluding biomarker/mutation occurrences: 58.4%.

## By category (occurrence coverage is the one that matters)

| Category | Distinct | Distinct resolved | Occurrences | Occurrence coverage |
|---|---:|---:|---:|---:|
| comorbidity_or_history | 1770 | 41.5% | 3865 | 64.6% |
| organ_function_lab | 224 | 71.9% | 1246 | 81.6% |
| prior_systemic_therapy | 793 | 9.2% | 1041 | 15.2% |
| concurrent_medication | 474 | 33.3% | 766 | 47.4% |
| disease_or_stage | 364 | 39.3% | 735 | 57.6% |
| infection_status | 187 | 52.4% | 713 | 76.4% |
| biomarker_or_mutation | 284 | 15.1% | 687 | 20.1% |
| pregnancy_or_contraception | 100 | 46.0% | 668 | 81.7% |
| prior_local_therapy | 431 | 24.4% | 631 | 42.6% |
| consent_or_compliance | 307 | 12.4% | 588 | 34.0% |
| metastasis_site | 134 | 31.3% | 427 | 61.1% |
| histology_or_subtype | 241 | 46.1% | 413 | 53.5% |
| other | 284 | 19.4% | 402 | 32.1% |
| demographics | 31 | 51.6% | 273 | 92.7% |
| performance_status | 10 | 70.0% | 243 | 98.4% |
| measurable_disease | 55 | 21.8% | 194 | 43.8% |
| trial_participation | 112 | 1.8% | 138 | 3.6% |
| prior_supportive_care | 2 | 50.0% | 3 | 66.7% |

Biomarker/mutation is reported here and is **not** used to replace gene-symbol matching.

## What the misses look like

3,878 distinct phrases never resolved (5,682 occurrences). The common ones are
corpus-normal, not exotic compounds: `absolute neutrophil count` (71),
`egfr mutation` (66), `written informed consent` (65), `measurable lesion` (53),
`leptomeningeal disease` (31), `prior immunotherapy` (29), `sperm donation` (24),
`qtcf` (18), `hbv infection` / `hcv infection` (16 each), `stage iv nsclc` (10),
`platinum-based chemotherapy` (9). Investigational-drug phrases miss as expected.
So do many of the phrases the dictionary was supposed to own.

## Claude review of the 575 disagreements

Not a Will sheet. Full list: `docs/step13_umls_disagreements.md`.

The automatable check is conservative: many flagged rows are true synonyms
(`interstitial lung disease` → Lung Diseases, Interstitial; `nsclc` → Non-Small
Cell Lung Carcinoma; `stroke` → Cerebrovascular accident; `breastfeeding` →
Breast Feeding). Those should not count as precision failures.

The rest are not conservative. High-frequency wrongs, not edge cases:

| n | phrase | UMLS returned | Problem |
|---:|---|---|---|
| 68 | measurable disease | Measurement of Newcastle disease virus antibody | Unrelated virus assay |
| 56 | active infection | Post-Infectious Disorders | Wrong time: after, not active |
| 48 | organ function | Organ or tissue uptake | Imaging uptake, not labs |
| 29 | active autoimmune disease | AUTOIMMUNE DISEASE, MULTISYSTEM, INFANTILE-ONSET, 1 | One rare syndrome |
| 14 | allogeneic organ transplantation | Live donor allotransplant part organ pancreas | Pancreas only |
| 14 | compliance with study procedures | Pulmonary compliance study | Lung mechanics |
| 11 | non-squamous nsclc | Squamous non-small cell lung cancer | Polarity flip |
| 11 | other malignancy | Overlapping malignant neoplasm of brain and other parts of the CNS | One site |
| 10 | resectability | Transurethral Resection of Prostate | TURP |
| 7 | her2 mutation | Germline BRCA-mutated, HER2-negative metastatic breast cancer | Wrong gene and polarity |
| 5 | target lesion | Erythema Multiforme | Unrelated rash |
| 4 | ecog | Electrocorticogram | Homonym |
| 4 | histologic confirmation | Tuberculosis of lung, confirmed histologically | One disease |
| 3 | her2 amplification | Human epidermal growth factor 2 gene amplification not detected | Polarity flip |
| 3 | surgical sterilization | Vasectomy | Excludes tubal ligation |
| 2 | evaluable disease | Evaluation of risk factors for periodontal disease | Unrelated |
| 2 | interventional therapy | Crisis Intervention | Psychiatry |
| 2 | pulmonary impairment | CHOPS SYNDROME | One syndrome |
| 2 | stage iii | Stage level 3 | Not AJCC cancer stage |

A generous re-score that treats synonym and abbreviation rows as correct still
leaves the dangerous class well above 10% of resolved phrases. Matching on these
CUIs would join `non-squamous` to `squamous` and `her2 amplification` to
`amplification not detected`.

## Decision

**Stop.** Occurrence coverage 56.4% is below the 60% gate committed in `107c1e2`.
Excluding biomarker/mutation still 58.4%. Resolution precision 66.2% on the
automatable check is below 90%, and the eyeball of the disagreements does not
rescue it.

UMLS cannot supply the vocabulary for this corpus. The six-name approach stays.
Generalising needs a different answer. Gene-symbol matching is untouched. No
Metathesaurus download. No TREC assignment. Steps 6 and 7 not started.
