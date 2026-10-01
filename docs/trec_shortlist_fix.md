# Weighted fusion and section ranking (2021/2022 only)

Gates committed in `c178dc4` before any new ranking score.
Official arms reorder the existing shortlist. Nothing discarded.
Unweighted RRF is the published TrialGPT fusion. IDF weights are a departure.
Section split reuses `split_sections`. Exclusion-only is down-ranked, never dropped.
2023 was not run. No reader. No trained ranker.

## Eligible recall

| Year | Arm | @10 | @20 | @50 | @100 | @200 | Full shortlist |
|---|---|---:|---:|---:|---:|---:|---:|
| 2021 | baseline | 5.7% | 10.7% | 22.4% | 36.5% | 53.0% | 91.6% |
| 2021 | idf_rrf | 5.6% | 10.5% | 22.4% | 36.6% | 51.8% | 91.6% |
| 2021 | bm25_sum | 6.3% | 10.8% | 21.8% | 34.2% | 50.1% | 91.6% |
| 2021 | section_mult | 6.2% | 11.4% | 23.3% | 37.0% | 53.4% | 91.6% |
| 2021 | section_tie | 5.7% | 10.7% | 22.4% | 36.5% | 53.0% | 91.6% |
| 2021 | idf_section | 6.3% | 11.3% | 23.6% | 36.9% | 51.5% | 91.6% |
| 2021 | probe_idf_full | 5.6% | 10.5% | 22.4% | 36.6% | 51.8% | 89.8% |
| 2022 | baseline | 7.4% | 13.3% | 27.2% | 40.4% | 58.3% | 91.4% |
| 2022 | idf_rrf | 8.3% | 13.5% | 27.2% | 41.4% | 58.4% | 91.4% |
| 2022 | bm25_sum | 7.0% | 12.6% | 24.4% | 37.5% | 53.5% | 91.4% |
| 2022 | section_mult | 7.7% | 13.7% | 27.1% | 41.1% | 58.3% | 91.4% |
| 2022 | section_tie | 7.4% | 13.3% | 27.2% | 40.4% | 58.3% | 91.4% |
| 2022 | idf_section | 8.6% | 13.3% | 27.6% | 41.4% | 58.3% | 91.4% |
| 2022 | probe_idf_full | 8.3% | 13.5% | 27.2% | 41.4% | 58.4% | 90.1% |

## Gates

| Check | Result |
|---|---|
| Best official 2021 Recall@10 | 6.3% (idf_section) |
| Full-shortlist recall unchanged | True |
| Probe R@6% vs 91.6%/91.4% | 2021 89.8% / 2022 90.1% |
| Gate | not_a_pipeline_change |

Best official 2021 Recall@10 is 6.3% (`idf_section`). Beats 5.7% but under
+3 points (8.7%). Do not replace unweighted RRF.

## Reading

The 91% junk is real, and it is not cheaply ranked away.

**Task 2.** Rarest-token IDF on RRF does nothing on 2021 (5.6% vs 5.7%).
Summing BM25 scores instead of ranks is 6.3%. Generic keywords do dump
junk (`hypertension`, `nausea`, `abdominal pain`), but those same lists
also carry eligible trials. Down-weighting them does not separate the
two. Unweighted RRF is still the published TrialGPT fusion; IDF is not
an improvement on it.

**Task 3.** Down-ranking exclusion-only keyword hits is 6.2%. The junk
is not "right disease, cannot-join list." It is mostly trials never
judged for this patient. They can mention a generic term in the
can-join list. The section split is not the cheap signal.

**Probe.** Full-collection IDF-RRF **drops** eligible recall at 6%
(91.6% → 89.8%, 91.4% → 90.1%). Rejected. Freezing the set was not
hiding a better first stage.

A coordinator reading ten still sees almost nothing. The next thing
that could move the top of the list is reading, not another fusion
trick. That is the reader, which this run did not start.

JSON: `data/trec/trec_shortlist_fix.json`. No overall accuracy.
The system does not say a patient qualifies.

