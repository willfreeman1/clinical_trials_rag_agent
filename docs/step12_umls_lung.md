# UMLS lung-slice gate (REST API)

Gene-symbol matching for tumour genetic marker was not replaced.
scispaCy unused (no concept is-a). No Metathesaurus download.
Thresholds: `a2dfda5`, before any REST call.

**This is not a UMLS success.** Searching full eligibility sentences
against the API resolved **13 of 3,390** unique quotes (miss rate
**99.62%**). Almost every trial–fact pair fell back to the existing
closed-name matcher. Mean recall 94.4% and mean false pickup 3.7%
are the six-name system with a 13-quote overlay, not a general
vocabulary.

Do not proceed to TREC assignment. Do not download RxNorm or MeSH
on the strength of these gates.

## What the gates would have said, if taken at face value

| Measure | Result | Gate |
|---|---|---|
| Mean recall | 94.4% (six-name 93.9%) | ≥84% — number cleared, test did not |
| Mean false pickup | 3.7% | ≤5% — number cleared, test did not |

## Per fact

Marker row is the existing matcher, as committed.

| Fact | Recall | False pickup | Path |
|---|---:|---:|---|
| Tumour genetic marker | 99.9% | 0.3% | **unchanged** gene-symbol / closed name |
| Cancer spread to the brain | 98.5% | 0.0% | mostly fallback |
| Autoimmune disease | 98.5% | 0.0% | mostly fallback |
| Disease stage | 93.2% | **11.4%** | overlay hurt; six-name was 0.0% |
| Previous platinum | 88.8% | 6.4% | same as six-name |
| Previous immunotherapy | 87.6% | 4.1% | same as six-name |

The only material UMLS effect in this run is stage false pickup:
13 extra trials, 11.4% vs 0.0% on the hand-written names. When the
API did resolve a long quote, it was the wrong concept often enough
to pick up trials that have no stage rule.

## Lookups

| | |
|---|---:|
| Unique quotes searched | 3,390 |
| Quotes that got a CUI | 13 |
| Unique CUIs in the whole run | 15 |
| Patient phrases (5 facts) | 7 (5 resolved) |
| Pairs decided by UMLS is-a | 160 |
| Pairs that fell back to closed names | 130,540 |

Hierarchy was barely exercised. Containment cannot be judged from
15 concepts.

Cause: the lookup string was the **whole eligibility sentence**
(median 169 characters, some over 2,000). UMLS search is built for
a short subject — "carboplatin", "brain metastases" — not a
bullet of inclusion text. That is the same reason Will is rewriting
the extraction prompt: the model must emit a phrase, and the API
resolves the phrase. This run skipped that step and proved why it
cannot be skipped.

## What happens next (not started)

1. Extract **one subject phrase per rule** (Will's prompt). Then
   look that phrase up. Until miss rate is low, the 84% / 5% gates
   are not measuring UMLS.
2. Only then: standalone RxNorm + MeSH, SQLite on the internal
   drive. External disk for raw files only.
3. TREC assignment remains a self-hosted GPU batch after that
   gate is honestly cleared. Not $5,100 of gpt-5.4.

Steps 6 and 7 not started. No Metathesaurus. Marker matching
untouched.
