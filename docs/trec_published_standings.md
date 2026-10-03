# Where published TREC numbers actually sit

Reading only. No new scores. The ranker run is a separate brief.
This is the related-work note for anything we publish: what the
field's numbers mean, which ones can sit on the same axis, and
where we stand without pretending the axes match.

**NDCG@10** is a ranking score that cares about order in the
top ten and about how good each hit is. **P@10** is how much
of the top ten counts as a hit. **AUROC** is: pick one
positive example and one negative example, how often the
model scores the positive higher. 0.50 is a coin flip.

The system does not say a patient qualifies.

## 1. TrialGPT's exclusion AUROC — do not claim parity

TrialGPT reports **0.7979** AUROC for "excluding ineligible
clinical trials" with GPT-4 and feature combination, and
**0.7895** from its eligibility score alone. Our fine-tuned
adapter is **0.779 (0.770–0.793)** across three seeds, on
held-out 2022, joinable (label 2) versus explicitly excluded
(label 1).

If those measured the same thing, a self-hosted 7B model
would be at or near a GPT-4 pipeline on the hardest
judgement in the task. **They are not demonstrated to
measure the same thing. Do not make that comparison.**

### What the paper and code actually say

The main text: the excluding task "is modeled as a binary
classification task." It never names the two classes.

The supplement (28 pages) never names them either. It has
prompts, error types, and the aggregation template.

The public code (`github.com/ncbi-nlp/TrialGPT`) ranks
trials. `rank_results.py` never computes AUROC. There is
no evaluation script that shows `y_true`.

Methods, "Evaluation settings," is the closest statement.
They define a graded relevance score:

| Grade | TrialGPT's bin | What that is |
|---|---|---|
| 0 | irrelevant, or unlabelled | Wrong disease, or never judged |
| 1 | ineligible **or** potential | TREC "excluded" **and** SIGIR "would consider referring after more investigation" |
| 2 | eligible | Human said the patient can enroll |

They then say they report NDCG@10 and P@10 for ranking,
and AUROC for excluding, and that **unlabelled pairs are
dropped from the metrics**. They compute AUROC with
`sklearn`. That is all.

They also write TREC's middle label as
**"excluded/ineligible"** — right disease, a rule fails —
and they say ranking scores are meant to "exclude the ones
that are explicitly ineligible." The excluding score for
their dual-encoder baseline uses only exclusion-criteria
similarity, not the whole trial. Their combination score
for excluding goes up when inclusion criteria are unmet
or exclusion criteria are met. That is the language of
the middle class, not of "everything that is not eligible."

They evaluate ranking and excluding on the **top 500**
trials returned by their own retriever, then **average
across SIGIR 2016 (58 patients), TREC 2021 (75), and
TREC 2022 (50)**. They say so next to Table 2, and they
warn that the ranking numbers "are not directly comparable
to the results of TREC CT participating systems."

SIGIR has **no excluded label**. Its three labels are
irrelevant, potential, and eligible. Table 1 prints
"None" under excluded trials for SIGIR. Equation 27
puts SIGIR **potential** in the same grade-1 bin as TREC
**ineligible**. Those are different human judgements.
Potential is "maybe refer after more investigation."
Excluded is "right disease, a rule fails."

Figure 4's caption counts the top-500 pool across all
three cohorts: 60,240 unlabelled, 15,459 irrelevant,
6,981 excluded, 647 potential, 8,173 eligible. They keep
those groups separate in the figure. They still never
say which of them become the AUROC positive class.

### What we can and cannot say

**Cannot say.** Ours is eligible versus explicitly
excluded, irrelevant dropped, one held-out year. Theirs
is a three-cohort average that must accommodate SIGIR,
and they never write the binary mapping. Even the most
favourable reading (grade 1 versus grade 2, grade 0
dropped) folds SIGIR potential into the same positive
class as TREC excluded. That is not our task.

**Can say.** The paper treats TREC excluded as
"ineligible," treats excluding as hard (best non-LLM
baseline AUROC 0.6176, "only marginal improvement over
the random score baseline"), and builds a separate
excluding score around failed inclusion / met exclusion.
That is *about* the middle class. It is not a definition
of the AUROC.

A wrong parity claim here is worse than leaving the
number unused.

## 2. How official TREC metrics work

TREC 2021 and 2022 are the same task. Each **topic** is
a synthetic admission note. The collection is a
ClinicalTrials.gov snapshot. Assessors label pooled
retrieved trials:

- **2 / eligible** — the patient meets the stated rules
- **1 / excluded** — right disease, a rule fails
- **0 / not relevant** — not about this patient

Official metrics, from the 2022 overview (the 2021
overview is the same scheme):

| Metric | Labels | What a hit is |
|---|---|---|
| NDCG@10 | Graded: eligible=2, excluded=1, not relevant=0 | Order in the top ten, with excluded counting as a partial hit |
| P@10 | Binary | Eligible only. Excluded is merged with not relevant |
| RPrec | Binary | Same |
| MRR | Binary | Same |

Unjudged trials are treated as not relevant. A
submission is a ranked list of up to 1,000 trial IDs
per topic, from the full snapshot, scored by NIST
`trec_eval`.

That is the field's axis. Almost nobody who published
after the track stayed on it.

## 3. Comparison table

Numbers are copied from the papers, not remembered.
A blank cell means the paper does not report it.
**Not comparable** means the number exists but is not
on TREC's official axis.

| System | Cohorts and patients | Evaluation pool | Label handling | Metric definition | Mean or median | Model, hosted how | Cost or compute reported |
|---|---|---|---|---|---|---|---|
| **TD-MINER** (Zheng, TREC 2021 notebook) | TREC 2021, 75 topics | Official TREC run: up to 1,000 trials/topic from the 375k snapshot; NIST pooled judging | Official: NDCG graded 2/1/0; P@10 binary, excluded merged with not relevant | Official `trec_eval` NDCG@10, PREC@10, MRR | Mean. NDCG@10 **0.715**, P@10 **0.576**, MRR **0.834**. First on NDCG@10 and MRR among 101 automatic + 12 manual runs | Information extraction + manual concept ranking. **Manual run.** Not an LLM | No dollar cost. Author says most time went into the IE baseline |
| **IBM Research** (Biester et al., TREC 2021 notebook) | TREC 2021, 75 topics. Trained neural rerankers on SIGIR 2016 (60 patients, 3,870 pairs) and a 700k-pair MIMIC-derived set | Official TREC run. Lucene/BM25 and STS retrieve 1,000–2,000 from 375,580 trials | Official TREC labels at eval. SIGIR labels differ (they say so) | Official NDCG@10, PREC@10, reciprocal rank | Mean. Best run **IBMLucene**: NDCG@10 **0.3174**, P@10 **0.1973**, RR **0.3913**. Neural rerankers were worse | BM25 on Lucene beat BERT rerankers. IBM Watson ACD for query concepts. Self-hosted models + IBM service | No dollar cost. They blame the neural loss on weak training labels |
| **h2oloo** (`frocchio_monot5_e`) | TREC 2022, 50 topics | Official TREC run, pooled to depth 40 (35,394 judged pairs: 3,949 eligible, 3,047 excluded, 28,481 not relevant) | Official | Official | Mean. NDCG@10 **0.6125**, P@10 **0.5080**, RPrec 0.3297, MRR 0.7262. Best team on all four | monoT5 / T5 family, automatic run. From the overview table, not their notebook (we do not have that notebook in `docs/papers/`) | Not in the overview |
| **DoSSIER** (`DoSSIER_5`) | TREC 2022, 50 | Official | Official | Official | Mean. NDCG@10 **0.5565**, P@10 **0.4560** | Automatic. Second team | Not in the overview |
| **TrialGPT** (Jin et al., *Nat Commun* 2024) | SIGIR 2016 **58** (2 of 60 dropped), TREC 2021 **75**, TREC 2022 **50**. 183 patients. Eligible trials/patient: 7.3 / 74.3 / 78.8 | Judged pool as the collection: **3,621 / 26,149 / 26,581**. Retrieval then ranking on **top 500** per patient. Unlabelled pairs dropped from metrics | Graded 0/1/2 as in §1. Label 1 = TREC ineligible **or** SIGIR potential | **NDCG@10** graded. **P@10 = (sum of grades in top 10) / (max grade × 10)** — **not** TREC's binary P@10. **AUROC** for excluding: classes never stated | Mean, **averaged across three cohorts**. GPT-4 feature combination: NDCG@10 **0.7275**, P@10 **0.6688**, AUROC **0.7979**. No per-year table | GPT-4 and GPT-3.5 via Azure API. Zero-shot. Hybrid BM25+MedCPT retrieval | User study: 42.6% less screening time. No dollar cost. They note GPT-4 is closed |
| **TrialGPT 2.0** (Fang et al., arXiv 2609.01202; the multicenter paper) | Same three public cohorts for the ranking table (58+75+50), **plus** 288 real-note cases, 27 prospective tumor-board cases, 126 NIH-TrialBench vignettes | Public-benchmark ranking: judged pools, unlabelled dropped. Real-world: each site's own shortlist, often **<1,500** local trials, not the TREC pool | Public benchmarks: graded 0/1/2 used **directly** for P@10 and nDCG@10. MRR and MAP binarize at eligible=2 | Same **graded P@10** as TrialGPT 1.0 (their eq. 20). They say so | Mean, again averaged across SIGIR+2021+2022. They report **relative** lifts over 1.0: P@10 +4.5%, nDCG@10 +5.7%, MRR +9.8%, MAP +10.2%. Absolute three-cohort means are in Fig. 5d (figure, not a typed table) | GPT-4.1 API for the public-benchmark comparison. Deployed web tool | 3.20× faster than 1.0; 58% fewer input tokens, 73% fewer output tokens per pair. Real-world screening-time cut is claimed; no TREC dollar cost |
| **TrialMatchAI** (Abdallah et al., *Nat Commun* 2026) | TREC 2021 **75**, TREC 2022 **50**. Also 100 synthetic "ideal candidates," 52 real WIDE cancer patients | TREC: "over 26,000" judged trials per year. Hybrid retrieval to **~500** (they say 90% recall at **3%** of the collection). WIDE: 217 trials, not TREC | They name Irrelevant / Excluded / Eligible. They never say whether P@10 is TREC-binary or TrialGPT-graded. They compare their means to **both** official TREC P@10 and TrialGPT's graded P@10 | nDCG and P at 5/10/20. Formula for P@10 **not stated** | They lead with **medians**: nDCG@10 **0.75** both years; P@10 **0.77** (2021) and **0.72** (2022). Means: nDCG@10 **0.7232**, P@10 **0.6865**, averaged across the two TREC years only | Fine-tuned open models, self-hosted. Gemma-2-2B QLoRA rank 16 for rerank; Phi-4 QLoRA rank 32 for criterion reading. BGE-M3 embeddings | Designed for local/hospital deploy. No TREC dollar cost. QLoRA settings given |
| **Entity enrichment / TCRR** (Kusa et al., arXiv 2307.00381; later *J Biomed Inform*) | TREC 2021 **75** and 2022 **50**. Neural models train on one year, test on the other | First stage: BM25 over the TREC snapshot. Neural rerank of **top 50**. Unjudged treated as not relevant | They say they follow the TREC procedure. P@10 is treated as **eligible-only** ("only eligible trials are considered") | nDCG@5, nDCG@10, P@10, RR, "as reported by TREC" | Mean. Best 2022 (train 2021): TCRR-BioBERT nDCG@10 **0.604**, P@10 **0.482**, RR 0.672. They print TREC 2022 median nDCG@10 0.392, P@10 0.258. Lexical+enrichment 2021: nDCG@10 0.480 before neural rerank | BERT / BioBERT cross-encoder, self-hosted. One Quadro RTX 8000 | GPU named. No dollars |
| **Peikos et al. 2023** (from survey 2509.19327) | TREC 2021 and 2022 | Not fully specified in the survey row | Survey does not say | Survey reports official-looking names: nDCG@10, P@10, RPrec, MRR | 2021: nDCG@10 **0.512**, P@10 **0.323**. 2022: nDCG@10 **0.517**, P@10 **0.372**. GPT-3.5 Turbo | API | Not in the survey row |
| **Jullien et al. 2024** (arXiv 2409.18998; survey row) | TREC 2022, 50 | BM25 first stage, GPT-4 Turbo criterion reasoning | Survey does not say how label 1 is treated | Survey: NDCG@10, P@10, P@25, MRR | NDCG@10 **0.679**, P@10 **0.730**, P@25 0.630, MRR 0.860. **P@10 above official h2oloo 0.508 is a flag** unless they used graded P@10 or a different pool | GPT-4 Turbo API | Not in the survey row |
| **Rybinski et al. 2024** (*J Biomed Inform*) | TREC 2021, 2022, **and 2023**. Survey warns 2023 overlaps earlier years (leakage risk) | BM25 then LLM rerank | Survey does not say | nDCG@10, P@10, RR, also nDCG@1000 | Survey quotes one setting: BM25+TCRR+GPT-3.5 nDCG@10 **0.777**, P@10 **0.697**; BM25+CoT GPT-4o nDCG@10 **0.785**, P@10 **0.603**. **Which year, and whether 2023 is in the average, is not in the survey row** | Fine-tuned GPT-3.5; GPT-4o for one arm. API | ~$0.25 per 100 GPT-3.5 calls (per patient). GPT-4 latency 47.8s, ~15× a small model, for ~12% nDCG@10 |
| **Nievas / Trial-LLaMA 2024** (survey row) | SIGIR + TREC 2021 + TREC 2022 (same three as TrialGPT) | TrialGPT-style; they extend TrialGPT to open models | Survey reports AUROC alongside NDCG/P@10, so likely TrialGPT's excluding setup, classes still unstated | NDCG@10, P@10, AUROC, AUPRC | Trial-LLaMA 70B: NDCG@10 **0.6636**, P@10 **0.5886**, AUROC **0.6528**. Their GPT-4 re-run: 0.7728 / 0.7005 / 0.7390. Three-cohort, TrialGPT-shaped | Fine-tuned LLaMA 70B, self-hosted, plus GPT-4 comparison | Survey says fine-tuning cost was high; no figure in the row |
| **Panacea** (Lin et al. 2024; survey) | TREC 2021 and SIGIR 2016, plus their TrialAlign set | Survey: "yes; no metrics provided" for the TREC ranking column | — | F1 / precision / recall on their matching task | **No TREC NDCG or P@10 in the survey** | Fine-tuned Mistral-7B, self-hosted | — |
| **VERDICT** (Zhou et al., arXiv 2609.03366) | SIGIR-derived **552 pairs** (labels re-done by a GPT-5 panel, not official SIGIR); TREC 2021 **363 official-judgement pairs**, sampled | Pair classification, **not** a ranking over the collection | SIGIR labels replaced. TREC 2021 uses official eligibility judgements on the sampled pairs | Decision F1 / accuracy, policy consistency, counterfactual self-faithfulness. **No NDCG, no P@10** | TREC 2021 F1: 0.828 (GPT-5-mini), 0.800 (Claude Haiku 4.5), 0.738 (Qwen2.5-7B; 0.829 after distillation). Accuracies 0.838 / 0.815 / 0.697 | LLM formalizes; SMT solver decides. API and open backbones | Budget-limited backbone split across the two sets |
| **This project** (for the standings paragraph, not a published paper) | TREC 2021 **75**, TREC 2022 **50**. 2023 stopped | Judged pool **26,162 / 26,585**. Shortlist top **6%** (~1,570 / 1,595). Unjudged treated as not relevant for ranking tables we have computed | Official-style when we compute NDCG (graded) and P@10 eligible (binary). 1-vs-2 AUROC drops label 0 | See `trec_hybrid_retrieval.md`, `trec_rerank.md`, `trec_lora_elig.md`. **No NIST `trec_eval` submission** | Retrieval: eligible recall **91.6% / 91.4% at 6%**. Rerank 2021 best NDCG@10 **0.510**, P@10 eligible **0.384**; 2022 MedCPT-CE NDCG@10 **0.586**, P@10 eligible **0.508**. Adapter 1-vs-2 AUROC **0.779 (0.770–0.793)** | Keyword hybrid + Qwen2.5-7B LoRA, self-hosted. GPT used for the reader spike, not for TREC retrieval | LoRA ~$5/seed. Reader-spike citation audit on a lung-cancer slice: **1.2%** of GPT-5.4 quotes missing from the trial text |

Surveys used to find extra TREC 2021/2022 rows:
`2509.19327` (pipeline review) and `2506.15301` /
Ghosh 2025 (ACL). Datta et al. 2025 (P@10 0.7351,
NDCG@10 0.8109) and several TREC **2023** notebooks
are **2023** and out of scope. Gueguen 2025 uses
TrialGPT+Qwen2.5-7B on a molecular tumor board, not
TREC. PRISM, OncoLLM, RECTIFIER, and n2c2 2018 are
other tasks.

## 4. Does anyone report a like-for-like official TREC number?

**Official participants do.** TD-MINER, IBM, h2oloo,
DoSSIER, and the rest of the TREC notebooks are scored
by NIST on the same qrels, the same binary P@10, the
same graded NDCG@10. Those numbers can sit next to
each other.

**The LLM papers that came later, as a group, do not.**
Each one moves at least one of: the collection (judged
pool vs 375k snapshot), the depth (top 500 vs 1,000),
the cohorts (SIGIR mixed in), the average (three-dataset
mean, or median instead of mean), or the P@10 formula
(graded sum vs binary eligible). TrialGPT says this
out loud. TrialMatchAI compares its means to official
TREC *and* to TrialGPT's graded P@10 without stating
which P@10 it used. TrialGPT 2.0 writes the graded
P@10 formula down (eq. 20) and still averages SIGIR
in. Jullien's survey-row P@10 of 0.730 on 2022 is
higher than the official winner's 0.508; that is a
reason to distrust the comparison, not a reason to
say they beat TREC.

**Closest post-hoc paper to the official axis:** Kusa
et al. (entity enrichment / TCRR). They say they follow
TREC, treat unjudged as not relevant, treat P@10 as
eligible-only, train on one year and test on the other,
and land at 0.604 / 0.482 on 2022 — next to official
h2oloo 0.6125 / 0.5080. Still not a NIST submission
(they rerank BM25's top 50, not a 1,000-deep run from
the snapshot), but it is the one paper that is trying
to be on the same axis.

That gap is itself worth writing about. The field's
headline LLM numbers and TREC's official table are
not the same measurement.

## 5. The two originality claims

Both were written in `HANDOFF.md` before this pile
existed. Rechecked against the papers. **Both still
hold.** The file is updated with what was checked.

### Fabrication rate

Our sense: a quote attributed to the trial (or the
note) that is **not in that text**. We measured
**1.2%** of GPT-5.4's judged quotes missing from the
trial on the lung-cancer reader spike (54/4,516;
gate was 5%). Mini was 7.7%.

**TrialGPT's 87.3% is not that.** Three physicians
scored 1,015 patient–criterion pairs from 53 SIGIR
patients. They scored (1) whether the explanation was
correct / partly correct / incorrect as medical
reasoning, (2) whether the pointed-to sentence IDs
matched the physicians' sentence IDs (precision 90.1%,
recall 87.9%), and (3) whether the criterion-level
eligibility label matched consensus (accuracy 0.873).
"Faithful explanations" in that paper means "the
rationale and the sentence pointers look right to a
doctor." It is not a string check of a quoted span
against the source. Their error types are wrong
reasoning, missing medical knowledge, and fuzzy
label names. Invented quotes are not a reported rate.

**VERDICT is not that either.** VERDICT is about
rationales that are **unfaithful to the model's own
decision**: the write-up says one thing, the eligibility
bit says another, or flipping the "pivotal" conditions
does not flip the bit. They also ask for grounding
(a link `ℓ` back to source text) and for assumptions
to be named. They report decision F1, consistency, and
a counterfactual flip rate. They do not report "this
many quoted spans are absent from the trial." SIGIR
labels in VERDICT are not even the official ones
(they re-labelled 552 pairs with a GPT-5 panel).

TrialMatchAI's expert review (950 TREC criterion pairs;
88.8–97.4% by class) is again label accuracy plus a
required justification, not a missing-quote rate.

**Claim stands.** No paper in this pile reports a
fabrication rate in our sense. That is still the
clearest original measurement we have, and it has
only been run on the lung-cancer reader, not on TREC.

### Generalist versus specialist, by stage

Our finding: at **retrieval**, `text-embedding-3-small`
beat or matched MedCPT (91.8% vs 88.0% eligible
recall). At **reranking**, MedCPT-CE beat the
MS MARCO web-search cross-encoder by more than two
to one (8.2% vs 4.2% Recall@10 on 2021). Same corpus,
opposite outcome, because the stages ask different
questions.

Checked in this pile:

- TrialGPT: MedCPT beats BM25, hybrid wins. No
  general-purpose embedding vs medical embedding
  bakeoff, and no rerank-stage inversion.
- TrialMatchAI: BGE-M3 for both sides of hybrid
  search. No generalist-vs-specialist contrast.
- Kusa / entity enrichment: BioBERT vs ClinicalBERT
  vs bert-base as **rerankers**. Domain init helps
  at rerank; they do not run a generalist retriever
  against a specialist retriever on the same corpus.
- IBM 2021: BM25 beat their neural rerankers. Not
  this claim.
- Both surveys discuss embeddings and rerankers as
  pipeline stages. Neither states that a generalist
  wins retrieval and a specialist wins rerank on
  TREC 2021/2022.
- VERDICT and the multicenter paper are not about
  this.

**Claim stands.** Write it as an inversion across
stages on one corpus, with the two measurements
attached, not as "nobody uses both kinds of model."

## 6. Where we stand, in plain language

We have not put a NIST `trec_eval` number on the
board. Until we do, we should not say we beat or
lost to TD-MINER or h2oloo.

On **first-stage retrieval**, TrialMatchAI is
already ahead of us on the number the papers share:
**over 90% recall at 3% of the judged collection**,
against our **91.6% / 91.4% at 6%**. Same idea
(hybrid lexical + dense, then a shortlist), half
the reading list for the same recall. That result
is bettered. Say so. Their 3% is about 500 trials;
our 6% is about 1,570. We kept the longer list on
purpose so later stages could not discard an
eligible trial. That is a design choice, not a
better retriever.

On **first-page ranking**, the only numbers that
are truly like-for-like are the official TREC
means: 0.715 / 0.576 (TD-MINER, 2021) and
0.6125 / 0.5080 (h2oloo, 2022). Our stored
official-style figures — 0.510 / 0.384 (2021,
best rerank arm) and 0.586 / 0.508 (2022,
MedCPT-CE) — sit **below 2021's winner** and
**near 2022's winner on P@10**, on a shortlist
reorder rather than a 1,000-deep official run.
TrialGPT's 0.7275 / 0.6688 and TrialMatchAI's
median 0.75 / 0.72 look higher and are **not
on that axis** (three-cohort average, graded
P@10, or an unstated P@10). Kusa's 0.604 / 0.482
on 2022 is the fairest published post-hoc
neighbour; we have not yet published a number
that sits next to it on purpose.

On **label 1 versus label 2**, we have a
measurement the ranking papers mostly skip:
AUROC **0.779 (0.770–0.793)** for a 7B LoRA,
held-out 2022, human labels only. TrialGPT's
0.7979 is the number everyone will want to put
next to it. **Do not.** Section 1 is the whole
reason. What we can say is narrower and still
useful: a self-hosted 7B adapter separates
joinable from explicitly excluded on a held-out
year, and the published GPT-4 pipeline never
states that that is what its AUROC is.

On **explanations**, we are behind on TREC: we
have not run the per-criterion reader on TREC
at all. TrialGPT and TrialMatchAI have physician
scores on a thousand-ish criterion pairs.
VERDICT has a stricter test (does the rationale
match the decision) and still no missing-quote
rate. Our 1.2% fabrication figure is the thing
they do not report, and it is on a different
corpus.

On **cost and hosting**, the published LLM
systems that score well on their own axes are
mostly GPT-4-class APIs (TrialGPT, Jullien,
TrialGPT 2.0) or fine-tuned open models
(TrialMatchAI, Trial-LLaMA, our adapter).
TrialMatchAI is the paper that already argues
our side of that trade: open, local, LoRA rank
16. They also already beat our retrieval cut.

We are not the first hybrid retriever, not the
first LoRA, and not the first to say a 7B model
can do useful work here. We are, so far, the
ones who measured invented citations as a rate,
and who measured the generalist/specialist
inversion across two stages on the same TREC
corpus. Those survive this reading. The
exclusion-AUROC headline does not.

## 7. Measurements this reading suggests (not started)

1. **Official-style `trec_eval`** on 2021 and 2022
   for whatever ranker we ship — NDCG@10 graded,
   P@10 binary, unjudged = 0, one year at a time —
   so we can sit next to TD-MINER and h2oloo
   without a footnote. The live ranker brief is
   the place for that, not this one.
2. **Do not recompute TrialGPT's AUROC** unless
   they release the scored pairs and the `y_true`
   mapping. Re-inferring classes from Table 2
   would be the mistake section 1 exists to stop.
3. **Graded P@10 on our lists**, as a translation
   row only, if a reviewer insists on TrialGPT's
   axis. Label it as theirs, not as TREC.
4. **Fabrication rate on a TREC reader**, when
   that reader exists. The 1.2% figure is still
   a different corpus.
5. Leave 2023 alone.

## Sources opened

Local files in `docs/papers/`: TREC 2022 overview;
TD-MINER 2021; IBM 2021; TrialGPT 2024 + supplement;
TrialMatchAI 2026; Kusa 2307.00381; surveys
2509.19327 and 2506.15301 / Ghosh 2025; multicenter
2609.01202; VERDICT 2609.03366. TrialGPT GitHub
`README.md` and `trialgpt_ranking/rank_results.py`.
Our numbers from `trec_hybrid_retrieval.md`,
`trec_rerank.md`, `trec_lora_elig.md`, `STATUS.md`.

The system does not say a patient qualifies.
