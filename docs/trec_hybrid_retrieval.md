# TREC hybrid retrieval (stages 1–2 only)

Gates committed in `613635e` before keywords, encoding, or recall.
Judged pool is the collection. No trial text to an LLM. No reader, reranker, or ranking stage.
Six-name narrowing was not used.

2021 and 2022 use the **27 April 2021** ClinicalTrials.gov dump.
2023 uses the **8 May 2023** dump (confirmed on trec-cds.org; not the 2021 dump).

MedCPT was trained on PubMed search logs and is out of domain here. TrialGPT used it anyway.
Each trial is one `[title, body]` pair truncated to 512 tokens — the same as TrialGPT.
A typical trial is 3,581 characters, so the tail of eligibility is dropped.
Chunking (2.7 windows/trial) was started and abandoned on CPU (~5 hours per snapshot).
The cross-encoder was downloaded and not run.

## Collection

| Year | Snapshot | Topics | Judged trials (collection) | 6% depth |
|---|---|---:|---:|---:|
| 2021 | 2021-04-27 | 75 | 26162 | 1570 |
| 2022 | 2021-04-27 | 50 | 26585 | 1595 |
| 2023 | 2023-05-08 | 37 | 17105 | 1026 |

## Recall of eligible trials (label 2), keywords + hybrid

| Year | @10 | @20 | @50 | @100 | @200 | @500 | @6% |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2021 | 5.7% | 10.7% | 22.4% | 36.5% | 53.0% | 76.4% | 91.6% |
| 2022 | 7.4% | 13.3% | 27.2% | 40.4% | 58.3% | 79.5% | 91.4% |
| 2023 | 1.0% | 2.0% | 4.9% | 9.7% | 17.7% | 39.6% | 65.4% |

## Reproduction checks and gate

| Check | Result |
|---|---|
| Hybrid beats BM25 and MedCPT | True |
| Keywords beat raw note | True |
| Eligible recall @ 6% of collection | 2021 **91.6%**; 2022 **91.4%**; 2023 **65.4%** |

The gate is the worst year. 2023 is below 70%, so **stop**. 2021 and 2022 are in the published league. The implementation checks passed on every year (hybrid beat both singles; keywords beat the raw note).

## Diagnosis of 2023

Not a broken fusion. The two years the papers used clear 91%. 2023 is a different task.

- 2021/2022 topics are 5–10 sentence admission notes. 2023 topics are sparse questionnaire fields (`definitive diagnosis: yes`, `visual acuity: 20/50`).
- Mean eligible trials per 2023 topic: **315** (median 273, max 799). Mean relevant (labels 1+2): **604**. 6% of that collection is 1,026 rows, so the budget can hold every eligible trial. 65% is a ranking miss, not a short list.
- Keywords still beat the raw fields (65.4% vs 62.8%), but only just. BM25 (64.7%) almost is the whole hybrid. MedCPT (59.4%) and `text-embedding-3-small` (59.7%) both lose to words.
- TrialMatchAI already noted 2023 recall@1000 sits near 0.64 for the same reason: a large relevant set.

Do not start the reader or a reranker on the back of a 65% 2023 first stage. If this architecture is used, it is on the 2021/2022 note-shaped task, where it matches the papers.

## The earlier embedding result

On 2021/2022, keyword queries + `text-embedding-3-small` reach 91.8% / 90.3% at 6%, level with MedCPT. The old negative was a whole patient note against a whole trial document. That is the raw-note row here (58% / 57%). The failure was the query shape, not "embeddings as a class."

## Ablations (eligible recall @ 6%)

| Year | Raw hybrid | KW BM25 | KW MedCPT | KW OpenAI 3-small | KW hybrid | KW hybrid+OpenAI |
|---|---:|---:|---:|---:|---:|---:|
| 2021 | 58.1% | 87.8% | 88.0% | 91.8% | 91.6% | 93.2% |
| 2022 | 56.8% | 88.5% | 89.2% | 90.3% | 91.4% | 92.2% |
| 2023 | 62.8% | 64.7% | 59.4% | 59.7% | 65.4% | 65.0% |

Relevant (labels 1+2) at the same depths is in `data/trec/trec_hybrid_results.json`.
No six-name vocabulary. Steps 6 and 7 not started.
