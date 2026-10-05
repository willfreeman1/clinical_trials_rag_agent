# Handoff — picking this project up in a cloud agent

Written 2026-10-01, at the end of a long conversation whose contents are not
all in the other files. The measured results live in `docs/`. **This file is
for the things that were argued out in chat and would otherwise be lost**:
why the architecture is shaped the way it is, which conclusions were wrong
and why, what is in flight, and how the person you are working for wants to
be worked with.

Read this, then `docs/STATUS.md`, then `CONTEXT.md`.

---

## 0. Read this first — the data is not in the repository

`data/` is in `.gitignore` and is **2.0 GB**, of which 1.7 GB is `data/trec/`.
The repository you have cloned is about 81 MB of code and documentation and
**contains none of the measurements, indexes, scores, snapshots or
judgements.**

Missing and needed to re-run anything:

| What | Size | Where it came from |
|---|---|---|
| `data/trec/docs_2021.jsonl` | 292 MB | The April 27 2021 ClinicalTrials.gov dump, parsed |
| `data/trec/rerank_pack.json`, `cheap_pass_pack.json` | ~295 MB | Packed patient/trial text for the rented GPU |
| `data/trec/index_2021/` | — | The search index |
| `data/trec/rerank_ce_scores.json`, `cheap_pass_gpu.json` | ~35 MB | Scores already paid for on rented hardware |
| `data/trec/qrels2021.txt`, `qrels2022.txt` | ~1.4 MB | **The human relevance judgements. Irreplaceable ground truth.** |
| `data/trec/rerank_shortlists.json` | 3.1 MB | The 1,570-trial shortlist per patient |

**You can do design, code, analysis of stored write-ups, and writing without
these. You cannot reproduce or extend a single measurement.** Before planning
any run, establish with Will how the data is reaching the cloud machine. The
small files (qrels, shortlists, scores, results JSON — a few tens of MB) are
worth getting first; they unlock all recomputation from stored outputs, which
is where several of this project's best findings came from. The 1.7 GB of
packed trial text is only needed to score new model/trial pairs.

The original snapshot is still downloadable from trec-cds.org
(`2021_data/ClinicalTrials.2021-04-27.part{1-5}.zip`, ~1.71 GB compressed)
if it has to be rebuilt. The qrels came from NIST; `docs/trec_retrievability.md`
has the provenance.

---

## 1. What this project is for

Will Freeman is a career-changing data scientist in Austin, about three years
in, with a marketing/growth-analytics and LLM-orchestration background.
**The obstacle in his job search is perceived machine-learning depth, not
domain knowledge.** This project exists to demonstrate that depth. It is a
portfolio project, not a product.

That shapes what counts as success. An honest negative result with a
pre-committed threshold is worth more here than a flattering number. He has
said he would rather kill a project than publish an inflated figure, and this
project has killed eight designs on measured evidence. **That record is the
deliverable**, as much as any working pipeline.

The project also exists to close specific gaps he found in about twenty job
descriptions: production vector databases, agent frameworks, explicit
function-calling, a named evaluation platform, structured output,
guardrails, and self-hosted inference. Most of those are still open. See
Part 0 of `CONTEXT.md`.

**Nothing here touches real patient data, ever.** Patient descriptions are
either invented or from the published benchmark. **The system never tells
anyone they qualify for anything** — it returns candidates plus the criterion
text a human must check. That line appears at the bottom of every write-up
in `docs/` and should keep appearing.

---

## 2. Where the work stands right now

### In flight

Commits `114cce7` and `b901e3d` committed gates and scripts for a three-run
GPU session that **had not been executed when this handoff was written.**
The gates are in the tail of `THRESHOLDS.md` and are binding — they were
committed before any score exists and must not be edited.

- **Run 1** — Qwen2.5-7B as a topical reranker, 0-to-3 score, all ~1,570
  shortlisted trials, all 125 patients, plus a continuous score read off the
  model's token probabilities. `gpt-4o-mini` extended to the same depth for a
  fair comparison. ~$16.
- **Run 2** — Qwen scoring **eligibility** directly against each trial's full
  criteria, one score per trial. ~$16.
- **Run 3** — separate go/no-go, needs Will's approval: Qwen vs a frontier
  model vs the human labels on a 30-patient sample. ~$14. Total crosses his
  $25 ask-first line, which is why it is split.

**Check whether these ran before planning anything.** If they have,
`docs/` should have the write-ups and `THRESHOLDS.md` the outcomes in
`DECISIONS.md`.

### The question those runs exist to answer

**Reordering the shortlist is not a feature. It is a cost workaround.** It is
in the design only because the eligibility judgement was assumed to need an
expensive model, so something cheap had to shrink 1,570 trials to the ~100 an
expensive reader could afford.

If a cheap model can judge eligibility on everything, the reordering stage
has no purpose — the eligibility score *is* the ranking. That is how TrialGPT
works; it has no separate reranker.

**Run 1 and Run 2 are deliberately in competition, and Run 2 is allowed to
delete Run 1.** The gates in `THRESHOLDS.md` are written so that a tie does
not default to keeping the stage. If you find yourself arguing for keeping
both, check that against the gate text rather than against intuition.

---

## 3. The architecture, in plain terms

**Stage 1 — search.** A model reads the patient's admission note and writes
10 to 30 search terms. **Each term runs as its own separate search**, two
ways (BM25 word matching and MedCPT vector similarity). The result lists are
merged by reciprocal rank fusion. Top 6% kept — about 1,570 trials.

This keeps **91.6%** of the patient's eligible trials (2021) and 91.4%
(2022), matching the published papers. **It works and is not under test.**

The single biggest win in the project is the keyword decomposition: using the
whole patient note as one query gets 58.1%; one query per term gets 91.6%.

**Stage 2 — whatever shrinks or sorts the 1,570.** This is the open question.
Of the 1,570, about 67 are eligible, 73 are right-disease-but-excluded, and
**91% is junk** — mostly trials never about this patient that matched a
generic term like "hypertension" or "nausea."

**Stage 3 — the per-criterion reader.** Measured on TREC 2022, top 25,
1,250 pairs. A TREC note settles **7.6%** of the written requirements
(about 13 per trial here, not the ~43 from the lung-cancer slice).
Walking every rule is the wrong ranking method for this test. The
fair last step calls most trials compatible; ranking stays 0.59
against the fine-tuned scorer’s 0.779. Quotes are usually real
(3.75% made up or paraphrased). Read `docs/trec_short_notes.md`
before proposing another reader.

---

## 4. What has been measured

Full detail in `docs/`. The short version, so you know what not to repeat:

| Finding | Where |
|---|---|
| GPT-5.4 0.821 vs trained 7B 0.779 on the same 6,249 2022 pairs; paired +0.038 | `trec_gpt_vs_adapter.md` |
| A TREC note settles 7.6% of requirements; rule-by-rule ranking 0.59; compatible-unless-contradicted changes labels not sort | `trec_short_notes.md`, `trec_reader.md` |
| Keyword-per-query hybrid search: 91.6% / 91.4% eligible recall at 6% | `trec_hybrid_retrieval.md` |
| 2023 is a different task (sparse questionnaire fields, ~315 eligible per topic); 65.4%. **Do not touch 2023** | same |
| Generic `text-embedding-3-small` **beat** medical MedCPT at retrieval (91.8% vs 88.0%) | same |
| Reranking: MedCPT cross-encoder fades past depth 100, **goes below baseline by 500**. General web-search reranker actively harmful | `trec_rerank.md` |
| Medical specialist **beat** the generalist at reranking — the opposite of retrieval | same |
| Shortlist composition: 4.3% eligible, 4.7% excluded, 91% junk | `trec_shortlist_diagnosis.md` |
| Weighted fusion, IDF weighting, section-aware ranking: all dead. First page unchanged | `trec_shortlist_fix.md` |
| Qwen as a cheap filter: keeps 96.6% of disease-relevant at 61.7% retention, essentially free | `trec_cheap_pass.md` |
| Qwen's three coarse labels, sorted into blocks, beat every reranker past depth 100 — **1.9× reading depth at 500** | `trec_qwen_preview.md` |
| Precision and ceilings for every arm | `trec_precision.md` |

Earlier spike work on a lung-cancer slice (closed-vocabulary matching,
containment hierarchy, the fabricated-quote audit) is in `docs/step*.md` and
`docs/STATUS.md`. **The fabricated-citation rate — 1.3% of stored quotes
absent from the source, traced to 212 specific wrong decisions — is the
clearest original contribution in the project.** A quote here means a span
the model attributed to the trial (or the note) that is not in that text.
Re-read 2026-10-03 against the pile in `docs/papers/` (TrialGPT, TrialMatchAI,
VERDICT, TrialGPT 2.0, both surveys, Kusa, the TREC notebooks). **The claim
still holds.** TrialGPT's 87.3% on 1,015 pairs is criterion-label accuracy
plus "does a doctor accept the rationale / sentence IDs," not a missing-quote
rate. VERDICT measures rationales that disagree with their own decision, not
invented spans. Details: `docs/trec_published_standings.md`. Do not lose
that thread; it should be measured again on whatever the final reader
turns out to be.

---

## 5. Things argued out in chat that are not in any other file

### 5.1 Four measurement errors, and the pattern behind them

This matters more than any single number, because the pattern will recur.

**Error 1 — reporting shallow recall as if it were a quality measure.**
"Recall at 10 is 9.0%" sounds like failure. A patient is eligible for ~74
trials and only 10 fit in a top-10 list, so there is a ceiling. Three gates
were set without working the ceiling out.

**Error 2 — computing the ceiling wrong while correcting error 1.** The
ceiling was first given as 10 ÷ 74 ≈ 13%, averaging the counts then dividing.
The right way is per patient, then average: **24.7%**. The eligible count per
patient runs from 6 to 203, and patients with few eligible trials have a
ceiling of 100%, which pulls the average up.

**Error 3 — multiplying a mean share by a mean count.** "9.0% recall at 10
means about 7 of the top 10 are eligible" is not valid arithmetic. The honest
figure was already on disk as precision@10: **2.9 of 10**, not 7.

**Error 4 — measuring arms at different depths and comparing them.**
`gpt-4o-mini` was scored only on the top 200 and won. Qwen, handicapped to
three buckets, beats it everywhere past 100. The original conclusion was an
artefact of the depth each arm was given.

**The pattern: being confident about how to measure something before working
the arithmetic.** When you set a gate, compute its ceiling first, and state
what the number would be under a perfect system. `DECISIONS.md` has the full
record under the 2026-10-01 entries.

### 5.2 The "10 eligible trials in a list of 20" bar is arbitrary

It was a number Will picked in conversation, not a requirement and not a
benchmark figure. **Neither published paper reports precision at 20**, so
there is nothing to compare it against. He has since said explicitly that it
is not a rule and that nobody knows a coordinator's real tolerance.

**The job is to give coordinators the best list, and to cut the cost of
producing it.** Do not treat 10-in-20 as a ship gate. The useful measure is
**equivalent depth** — reading N trials in this order finds as many eligible
trials as reading how many in the original order — because that converts
directly into the expensive reader's bill.

### 5.3 Equivalent depth has a trap in it

Flat stretches in the baseline recall curve mean the baseline reaches its own
depth-500 count at depth 402. Read equivalent depth against N and every arm
looks negative. **Always include the baseline's own equivalent depth as a
calibration row.** `docs/trec_qwen_preview.md` has the corrected form and
says where the bug was.

### 5.4 Ranking quality and decision accuracy are different properties

A model that is systematically too harsh about eligibility, but harsh in the
same direction every time, **ranks perfectly well** — you read further down
the list. A poor accuracy figure should not veto a good ranking figure. The
published work tends to conflate these. `THRESHOLDS.md` encodes the
separation for Run 3; keep it.

### 5.5 The human labels are free fine-tuning data

**TREC 2021 and 2022 come with 71,226 human relevance judgements.** If Qwen
is to be fine-tuned, prefer those. Distillation from a frontier model —
training the 7B adapter on GPT labels, then testing on humans — is
**untested in this project**. It is not known to be strictly worse. The
case for it is extra volume (82% of the shortlist was never judged) and
GPT-5.4's 0.83 on a 411-pair sample. The case against is that GPT-5.4's
errors are systematic, not random: it was consistently stricter than the
assessors on patterns such as "non-obstructing" versus "obstructive."
Random noise can wash out; correlated noise gets learned. The experiment
that would decide, its cost (~$30 for 5,000 pairs), and the three
outcomes are in `docs/trec_model_currency.md`. Do not run it from a
handoff. The frontier model being stricter than the assessors **is**
measured (`docs/trec_frontier_elig.md`). Whether that bias transfers
when you train on it is not.

Clean split: train on the 2021 patients (35,832 judgements), test on the
2022 patients (35,394). No patient appears in both.

Three caveats that must be stated if this is done:

- **The labels are per trial, not per criterion.** This trains a ranker, not
  an explainer. The criterion-by-criterion read is still needed for output.
- **Only judged pairs carry labels.** 82% of the shortlist was never judged.
  Training only on judged pairs trains on a different mix than deployment.
  Either sample unjudged trials as weak negatives and say so, or accept the
  limitation explicitly. Do not ignore it silently.
- **Label 1 versus label 2 is the hard distinction** — right disease, fails
  an exclusion. Retrieval is blind: excluded trials come back at 92.1%,
  eligible at 91.6%. A LoRA on the human labels reached mean AUROC
  **0.779 (0.770–0.793)** on held-out 2022. That is the headline; quote
  the mean and the spread, not the best seed.

### 5.6 The GPU work was slower than it needed to be

The reranking pass took 74 minutes and was called a failure against a
self-imposed 25-minute budget. Three avoidable causes:

- `scripts/lambda_rerank.py` **loads the model in 32-bit** and only does
  forward passes. Half precision is close to free speed — one line.
- It ran on an **A10**, roughly a third to a fifth of an A100.
- Batch size 64 at 512 tokens, conservative for a larger card.

Together, plausibly 10–20× available. The work that got dropped — cutting
each trial into overlapping windows so the model sees the whole criteria
section instead of the first 512 tokens — becomes affordable with those
fixes. **MedCPT has never read most trials' eligibility rules**, which is
the most likely reason it fades with depth. Qwen's 32k context does not have
this problem, which is a real architectural advantage.

### 5.7 Generalist versus specialist, by stage

At **retrieval**, the general-purpose OpenAI embedding beat the medical
specialist (91.8% vs 88.0%). At **reranking**, the medical specialist beat
the general-purpose web-search model by more than two to one (8.2% vs 4.2%).

Same corpus, opposite outcome, because the stages ask different questions —
coverage versus judgement on a specific pair. **Still unreported as an
inversion across stages on the same TREC corpus.** Re-read 2026-10-03
against TrialGPT, TrialMatchAI, Kusa, IBM, VERDICT, TrialGPT 2.0, and both
surveys. They compare retrievers, or they compare reranker inits, or they
pick one embedding and move on. None of them states that a general-purpose
model wins retrieval and a medical specialist wins rerank on this collection.
Details: `docs/trec_published_standings.md`. Worth writing up properly.

### 5.8 The recall figures are against the judged pool, not the full registry

Every number is measured against the **26,162 judged trials** for 2021, not
the **375,581** in the full snapshot. Both papers do the same and it is the
normal way to score this benchmark, but "91.6% of eligible trials survive
against 26,000 rivals" is a weaker claim than it looks, and performance
against 375,000 is unknown and would certainly be worse. **State this
whenever the 91.6% figure is used outside the repository**, including on a
resume.

---

## 6. Dead ends — do not re-run these

Each was measured with a pre-committed threshold. The negatives are part of
the project's value; re-running them wastes money and adds nothing.

1. **Similarity scoring on free text.** Three attempts: whole-document (58%),
   phrase-to-phrase (10%), normalised phrase (32%). A pair that should not
   match (brain vs bone spread) scored **higher** than true matches, so no
   cutoff exists.
2. **Off-the-shelf embeddings cannot represent "must have had" vs "must not
   have had."** 0.01 gap between groups against 0.10 spread within.
3. **A fixed set of columns does not cover the problem.** 5,578 distinct
   facts across 300 trials, 77% appearing once, 0 of 300 trials fully covered.
4. **UMLS cannot supply a general vocabulary.** 56.4% coverage, 66.2%
   precision, with polarity flips (`non-squamous NSCLC` resolving to squamous).
5. **Weighted fusion, IDF weighting, section-aware ranking.** All flat.
6. **MS MARCO MiniLM as a reranker.** Worse than doing nothing.
7. **MedCPT cross-encoder as a keep/drop filter.** Almost every pair scores
   far below the cut point; no threshold achieves both bars.
8. **Asking the patient clarifying questions to resolve conditional rules.**
   10.4% of trials wrongly discarded.

Also: **the six-name closed vocabulary does not transfer to TREC.** It was
built for a lung-cancer slice. Do not apply it here.

---

## 7. How Will wants to be worked with

These are not preferences; ignoring them has caused real friction.

**Plain words, every time, with no shorthand.** This includes shorthand
coined earlier in the same conversation. He context-switches between several
projects and comes back to this one cold. Never assume he has read a document
or remembers a term. Explain medical words and technical words on every use,
or use a plain substitute. He has had to say this three times and the third
time was not polite.

**Ask before spending money or starting long work**, even when a previous
message said "do it." He was once billed $6.72 for a run he had not
authorized and was angry about it. The standing line is **ask above about
$25 in one run.**

**Ask before creating files.** Propose, then write.

**Do not be over-deterministic in briefs for coding agents.** His words:
*"Let Grok think for itself... a lot of the failures where we had to go back
and re-word the plan was because you were being too deterministic."* State
what the decision hinges on and let the agent choose the method.

**Push back with evidence.** He wants disagreement when a plan is flawed, not
a list of options.

**No inflated numbers.** Compare against the strongest honest baseline, state
uncertainty, and say plainly when a result is weak.

---

## 8. Hard constraints

- `THRESHOLDS.md` is committed **before** each run and **never edited
  afterwards**. New reasoning goes in `DECISIONS.md`. The git history showing
  that ordering is part of what the project demonstrates.
- **Do not touch 2023.** Different task, 65.4% first stage.
- **Nothing in stage 2 discards trials** unless a gate explicitly authorises
  it. The shortlist stays 1,570 / 1,595.
- `PYTHONIOENCODING=utf-8`, and `encoding="utf-8"` on every file read and
  write. Trial text contains `≥`, `≤`, `×`, and a default Windows console
  crashes on them.
- **Terminate rented GPUs through the API, and copy scores off first.** A
  previous run hit an out-of-memory crash and the scores survived only
  because they had already been copied.
- The repository must not live in Google Drive — sync corrupts `.git`. It is
  at `C:\dev\clinical_trials_rag_agent` locally, now mirrored to a private
  GitHub repo.
- Commit small and often, with explanatory messages. There was a large pile
  of uncommitted work on 2026-10-01; do not repeat that.
- Priorities, in order: **honest results > a working end-to-end system >
  breadth of features.**

---

## 9. Open questions, in the order they matter

1. **Does a topical reordering stage earn its place at all, or does a cheap
   eligibility score replace it?** Runs 1 and 2. Gates already committed.
2. **How far is a 7B open model from a frontier model?** Measured on the
   same 6,249 2022 pairs as 0.779: GPT-5.4 AUROC **0.821** vs trained
   7B mean **0.779**, paired gap +0.038 (0.012–0.068).
   `docs/trec_gpt_vs_adapter.md`. Not a first-page score.
3. **Can anything separate label 1 from label 2** — right disease but
   excluded, versus eligible? Nothing has. This is the most valuable
   unanswered question in the project.
4. **Does the per-criterion reader work on TREC?** Measured. It produces
   usable quotes (3.75% fabrication on offered quotes) and does not
   rank (0.59). The open question is whether anything else is worth
   running — contradiction-only evidence, a larger model, or stop.
   `docs/trec_short_notes.md`.
5. **Would fine-tuning Qwen on the 71,226 human judgements beat the frontier
   model?** Decided by question 2.
6. **Does any of this survive against the full 375,581-trial registry rather
   than the 26,162 judged pool?** Unknown, and the honest caveat on every
   headline number.

Items from the original gap list that remain completely untouched: a
production vector database, an agent framework, a named evaluation platform,
structured output, guardrails, and a deployed service. There is still no API,
no container, and no user-facing anything. That is a deliberate consequence
of spending the effort on measurement, and it is the right trade for a
portfolio piece about depth — but it should be a conscious choice each time
it is renewed, not a drift.
