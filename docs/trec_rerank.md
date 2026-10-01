# TREC reranking the shortlist (2021/2022 only)

Gates committed in `44878a7` before any rerank score.
2023 was not run. Reranking reorders; it discards nothing.
Shortlist is keyword hybrid (BM25 + MedCPT, RRF), top 6% of the judged pool.
Document text starts as the same 512-token `[title, body]` truncation as retrieval.
MedCPT-CE judges whether a PubMed article answers a search query, not eligibility.
MS MARCO MiniLM is web search. The cheap model scores topical relevance.
Polarity and conditional rules stay the reader's job. The system does not say a patient qualifies.
The 0.81 NDCG figure in the literature is on 2023 and is not a comparison here.

## Eligible recall

| Year | Arm | @10 | @20 | @50 | @100 | @200 | Full shortlist |
|---|---|---:|---:|---:|---:|---:|---:|
| 2021 | baseline | 5.7% | 10.7% | 22.4% | 36.5% | 53.0% | 91.6% |
| 2021 | medcpt_ce_keywords | 8.2% | 14.1% | 25.9% | 38.1% | 51.7% | 91.6% |
| 2021 | medcpt_ce_raw | 8.1% | 13.6% | 27.0% | 39.2% | 52.3% | 91.6% |
| 2021 | msmarco_ce_keywords | 4.2% | 7.1% | 14.8% | 24.1% | 36.0% | 91.6% |
| 2021 | msmarco_ce_raw | 3.0% | 5.4% | 10.6% | 17.4% | 27.8% | 91.6% |
| 2021 | llm_raw_top200 | 9.0% | 16.7% | 31.7% | 44.4% | 53.0% | 91.6% |
| 2022 | baseline | 7.4% | 13.3% | 27.2% | 40.4% | 58.3% | 91.4% |
| 2022 | medcpt_ce_keywords | 11.5% | 18.6% | 32.7% | 46.3% | 60.2% | 91.4% |
| 2022 | medcpt_ce_raw | 10.4% | 16.3% | 30.2% | 43.2% | 56.6% | 91.4% |
| 2022 | msmarco_ce_keywords | 5.1% | 8.7% | 17.0% | 27.1% | 38.9% | 91.4% |
| 2022 | msmarco_ce_raw | 2.8% | 4.7% | 8.1% | 13.8% | 22.4% | 91.4% |

## NDCG@10 and precision@10

| Year | Arm | NDCG@10 | P@10 eligible | P@10 relevant |
|---|---|---:|---:|---:|
| 2021 | baseline | 39.9% | 28.5% | 59.7% |
| 2021 | medcpt_ce_keywords | 49.3% | 36.9% | 71.1% |
| 2021 | medcpt_ce_raw | 47.8% | 34.8% | 69.9% |
| 2021 | msmarco_ce_keywords | 29.7% | 22.8% | 41.2% |
| 2021 | msmarco_ce_raw | 25.5% | 18.9% | 35.6% |
| 2021 | llm_raw_top200 | 51.0% | 38.4% | 72.7% |
| 2022 | baseline | 46.9% | 38.6% | 59.2% |
| 2022 | medcpt_ce_keywords | 58.6% | 50.8% | 71.2% |
| 2022 | medcpt_ce_raw | 57.0% | 48.2% | 67.4% |
| 2022 | msmarco_ce_keywords | 33.2% | 26.4% | 38.8% |
| 2022 | msmarco_ce_raw | 17.2% | 13.6% | 25.6% |

## Gates

| Check | Result |
|---|---|
| Best 2021 Recall@10 | 9.0% (`gpt-4o-mini` on the raw note, top 200) |
| Triple bar (above 17%) | missed |
| Double bar (11.4%) | missed |
| Full-shortlist recall unchanged | True — 91.6% / 91.4% on every cross-encoder arm |
| Gate | **below_doubling_stop** |

**STOP. Reranking is not earning itself.** The best 2021 Recall@10 is 9.0%, up from 5.7%. That is a small move, not a double, and not a triple. A coordinator reading ten still sees almost nothing.

## Which arm wins

No gate. On 2021 Recall@10 the cheap model wins (9.0%), then MedCPT-CE on keywords (8.2%) and on the raw note (8.1%). MS MARCO MiniLM **hurts** the list (4.2% / 3.0%).

The medical specialist beat the generic reranker. That is the opposite of retrieval, where `text-embedding-3-small` matched or beat MedCPT. Worth stating: the generic win does not repeat at rerank.

The raw-note question is closed for these cross-encoders. Keywords and the full note are the same on MedCPT (8.2% vs 8.1%). The note is worse on MiniLM. Dilution was a first-stage vector problem. Reading both texts together did not make the full note the better query.

At the matched depth of 200, MedCPT-CE does not beat the unre-ranked hybrid (51.7% vs 53.0% in 2021). The cheap model equals baseline at 200 because it only reorders those 200 rows.

NDCG@10 and P@10 moved more than eligible recall@10 (NDCG 39.9% → 51.0% on the cheap model; P@10 eligible 28.5% → 38.4%). Those score how high *relevant* items sit, including label 1. They are not the gate. The 0.81 figure in the literature is 2023 and is not a comparison.

2022, no language-model arm: MedCPT-CE on keywords is best at 11.5% from 7.4%. Still below that year's double (14.8%).

## Honest limitation, as written before the scores

MedCPT-CE was trained to judge whether a PubMed article answers a search query. MiniLM is web search. The cheap model was told to score topical relevance and not eligibility. The lift we got is topical. Polarity and conditional rules were never this model's job, and the top 10 did not fill with eligible trials.

## What was skipped

Chunk-and-take-max was not run. The truncated MedCPT pass alone took 74 minutes on an A10; the written budget for starting chunking was 25 minutes. Trials still average 3,581 characters against a 512-token window. That remains a limitation, not an excuse: the gate failed by a wide margin on the same truncation retrieval used.

GPU: A10, scores copied off, instance terminated via the API. Language-model arm: $0.75.

Per-arm JSON is in `data/trec/trec_rerank_results.json`.
No overall accuracy. The system does not say a patient qualifies.

