# Clinical-trial eligibility retrieval

**Finding the clinical trials a patient might be able to join — and showing a
human the exact rules they need to check.**

Clinical trials fail more often from not finding enough patients than from
anything that happens in the lab. The people who match patients to trials —
research coordinators — face a registry of more than 375,000 studies, each with
dozens of eligibility rules written in dense medical prose. Reading them is the
bottleneck.

This project builds and measures a system that narrows that search and shows its
working. **It never tells anyone they qualify.** It returns a ranked shortlist
plus the specific criterion text a person must verify, with the sentence the
system relied on quoted underneath.

![A patient description, ranked trials with expert verdicts, and one quoted eligibility rule](docs/images/demo.gif)

*The demo runs on a laptop in one command. Search and ranking execute live; the
`replay` badge means the rule-reading replies are stored rather than a live
model call, and the page says so.*

---

## What this is, and what it is not

It is a **portfolio project built to demonstrate machine-learning depth.** It is
not a product, and nobody is going to deploy it.

That shapes what counts as success here. **An honest negative result with a
threshold written down in advance is treated as more valuable than a flattering
number.** The project has killed more than eight designs on measured evidence,
retracted two of its own headline figures when they failed re-examination, and
documented every one. That record is the deliverable as much as any working
code.

No real patient data is involved anywhere. The patient descriptions are either
invented or taken from a published research benchmark.

---

## The five findings worth knowing

**1. How you ask the search engine matters more than which search engine you
use.** Feeding the whole patient description in as one query finds 58% of the
trials a patient is eligible for. Having a model break that description into 10
to 30 separate search terms, running each as its own query, and merging the
results finds **91.6%** — while reading only 6% of the collection. Same data,
same models, a third more eligible trials.

**2. A small model you run yourself, fine-tuned for about $5, gets most of the
way to a frontier model.** On the hardest judgement in the task — telling "this
patient could join" from "right disease, but a rule disqualifies them" — the
scores run: 0.682 for the pipeline's default, 0.749 for simply asking a better
question, **0.779** after fine-tuning a 7-billion-parameter open model on the
benchmark's expert verdicts, and 0.821 for GPT-5.4. Fine-tuning closed roughly
40% of the gap for the price of a sandwich, on hardware that never sends patient
data anywhere.

**3. The system was measured for making things up.** When it quotes a sentence
as its evidence, how often does that sentence not actually exist in the source?
**3.75%** across 1,252 quotes. A naive check flagged 52% as suspect, and almost
all of that was benign — quotes stitched from two real passages, or the checker's
own word list missing a match. Separating real fabrication from checker noise is
the work. **No published system in this area reports a figure like this.**

**4. A patient admission note can only settle 7.6% of a trial's written rules.**
Trial criteria ask about lab values, prior treatments, exact dates. A five-to-ten
sentence admission note contains almost none of it. That single number explains
why an entire category of approach — walking every rule and tallying the answers
— cannot rank trials on this benchmark, and it is a measurement about the
benchmark rather than about any model.

**5. Which model wins depends on which stage you ask about.** A general-purpose
embedding model beat a medical specialist at finding candidate trials (91.8%
against 88.0%). At re-ranking those candidates, the medical specialist beat a
general-purpose model by more than two to one. Same corpus, opposite result,
because the two stages ask different questions.

---

## What this demonstrates

| | Where to see it |
|---|---|
| **Information retrieval** — hybrid keyword and vector search, reciprocal rank fusion, recall measured against expert verdicts | `docs/trec_hybrid_retrieval.md` |
| **Fine-tuning open models** — LoRA adapters, a collapsed first attempt diagnosed and fixed, three random seeds reported with their spread | `docs/trec_lora_elig.md` |
| **Evaluation design** — confidence intervals by resampling patients rather than pairs, thresholds committed to version control before each run, a pre-registered replication on held-out data | `THRESHOLDS.md`, `docs/trec_lora_rank.md` |
| **Structured output and guardrails** — schema validation with retries, and a check that every quoted span actually exists in the source | `reader/`, `docs/trec_reader.md` |
| **Experiment tracking and model registry** — MLflow, with the shipping candidate marked and the governing threshold commit on every run | `docs/trec_mlflow_runs.csv` |
| **Shipping** — containerised service, HTTP API, seed data so a clean clone runs with no GPU and no API key, tests | `docker-compose.yml`, `service/` |
| **Reading the literature critically** — a comparison against published systems that documents why most of the comparisons are invalid rather than quietly making them | `docs/trec_published_standings.md` |

**The thing I would most want read** is `HANDOFF.md`, which records four
measurement errors the project made and corrected, and the designs it killed.
Most portfolio projects show only what worked.

---

## Try it (no GPU, no API key, one command)

```bash
git clone https://github.com/willfreeman1/clinical_trials_rag_agent.git
cd clinical_trials_rag_agent
docker compose up --build
```

Wait for the logs to say the app is ready, then open
**http://127.0.0.1:8088** and pick one of the three published patient
descriptions.

Search, fusion, ranking, rule splitting, quote checking and verdict combination
all run for real. The rule-reading replies for the three seed patients are
stored and replayed rather than calling a model, so no graphics card is needed —
and every response states which mode it is in.

The seed is three patients from the 2022 benchmark and 423 trials, about 3 MB,
with embeddings precomputed. Licensing is in `demo/seed/LICENSE.md`; exactly
what replay does and does not execute is in `docs/trec_demo.md`.

<details>
<summary>API and tests</summary>

```bash
curl http://127.0.0.1:8088/health
curl -s http://127.0.0.1:8088/v1/match -H "Content-Type: application/json" -d "{\"patient_id\":\"1\"}"
```

On Windows PowerShell use `curl.exe` and put the JSON in a file
(`--data-binary @req.json`) — the `curl` alias eats the quotes.

```bash
docker compose --profile test run --rm test
```

A live model server is optional (`MODEL_MODE=live` and `MODEL_URL`). The demo
does not need it.

</details>

---

## The measurements in full

All figures come from the TREC Clinical Trials benchmark — 75 patients from 2021
and 50 from 2022. Medical experts judged each patient–trial pair **joinable**,
**excluded** (right disease, but a rule disqualifies the patient), or
**irrelevant**.

### Finding the right trials

| | Result |
|---|---|
| Eligible trials kept, searching 6% of the collection | **91.6%** (2021), **91.4%** (2022) |
| Same search using the whole patient note as one query | 58.1% |

A model reads the patient note and writes 10 to 30 search terms. **Each term
runs as its own separate search** — word matching and vector similarity — and
the result lists are merged.

### Ordering the results

The default is a self-hosted Qwen2.5-7B model scoring each trial for disease
relevance.

| | Graded NDCG@10 | Precision@10 |
|---|---|---|
| 2021, 75 patients | 0.657 (0.617–0.696) | 0.519 (0.468–0.567) |
| 2022, 50 patients | 0.662 (0.585–0.734) | 0.570 (0.498–0.646) |
| `gpt-4o-mini`, 2021, same shortlist | 0.568 (0.522–0.612) | 0.384 (0.331–0.437) |

Ranges are 95% intervals from resampling patients — not pairs, since pairs from
one patient are not independent. Precision@10 is the share of the first ten
trials an expert called joinable. Graded NDCG@10 is the benchmark's own measure,
which gives full credit for a joinable trial and **half credit for an excluded
one**.

The self-hosted model beats the paid commercial one here, with non-overlapping
intervals.

### Telling "joinable" from "right disease, but excluded"

The hardest judgement in the task. The measure is AUROC: given one joinable
trial and one excluded trial, how often does the score rank the joinable one
higher? A coin flip is 0.50.

| Approach | AUROC |
|---|---|
| Disease-relevance score (the default ranker) | 0.682 |
| Logistic regression combining every signal already on disk | 0.686 |
| Asking the model about eligibility instead, untrained | 0.749 |
| **Fine-tuned on the benchmark's expert verdicts** | **0.779** (three seeds: 0.793, 0.770, 0.773) |
| GPT-5.4, same 6,249 pairs | **0.821** (0.785–0.852); +0.038 against the trained 7B on the same patients |

The logistic-regression row is the control that makes the rest meaningful:
combining every signal already available bought almost nothing, so the gains came
from changing the question and from training, not from better bookkeeping.

Fine-tuning cost about $5 of rented GPU time per run. It used a LoRA adapter — a
small file of extra numbers trained on top of a frozen base model — learning from
comparisons **within a single patient**, so the patient's note carries no
information about which of two trials should rank higher and the model has to
read the trial.

Changing the question was worth about seven points; fine-tuning added about three
more. The cheap insight beat the expensive machinery by more than two to one.

### Reading the rules one by one, and fabricated citations

A later pass asked the same 7B model to judge each eligibility rule on the 2022
top 25 (1,250 trials, about 13 rules each) and quote the sentence it used. The
design was locked before any score existed; an initial 50-trial probe broke on an
unsatisfiable output contract and is not an accuracy figure.

**A TREC note settles 7.6% of a trial's rules.** Under the assessors' own
combination rule the reader calls most trials compatible — meaning "nothing in
the note rules this out," not "this is a good match." It does **not** sort
joinable from excluded (AUROC **0.59**, interval 0.55–0.64, under all three
combination rules) the way the fine-tuned scorer does at 0.779.

When it does offer a quote, **3.75%** of those quotes were paraphrased or absent
from the source. The earlier lung-cancer work measured 1.2% for its reader and
1.3% across 4,384 stored quote slots — a different model on a different corpus,
so not a like-for-like comparison. The whole reader pass cost $7.70. Details in
`docs/trec_reader.md` and `docs/trec_short_notes.md`.

---

## Honest caveats

Read these before quoting any number above.

1. **The collection is the judged pool, not the full registry.** Every figure is
   measured against the 26,162 (2021) / 26,585 (2022) trials that experts judged
   — not the 375,581 in the full snapshot. Official benchmark submissions searched
   all 375,581. **That makes this an easier task, in this project's favour, and it
   means no comparison with official benchmark runs is valid.**
2. **No official submission was ever made.** Nothing here was scored by the
   benchmark organisers.
3. **No published system shares this evaluation setup.** Different papers use
   different collections, different treatments of the "excluded" verdict, and at
   least three incompatible definitions of "precision at 10".
   `docs/trec_published_standings.md` documents this rather than papering over it.
4. **The 2023 benchmark year is a different task** and was deliberately left
   alone. Its criteria are sparse questionnaire fields rather than prose, and
   first-stage recall falls to 65.4%.
5. **The two-stage sort is an option, not the default.** Re-sorting the top 25
   with the eligibility model adds about five points of precision for roughly
   two-tenths of a cent per patient. It replicated on a pre-registered test, but
   60 of those 75 patients were in the model's training data, so the conservative
   figure is the one from unseen patients.

---

## How it works

**Stage 1 — search.** A model turns the patient note into 10 to 30 search terms.
Each runs as its own query, two ways: BM25 word matching and vector similarity.
The lists are merged by reciprocal rank fusion and the top 6% kept, about 1,570
trials. This stage works and is not under test.

**Stage 2 — ordering those 1,570.** Of them, roughly 4% are joinable, 5% are
right-disease-but-excluded, and **91% is junk** that matched a generic term like
"hypertension". A self-hosted Qwen2.5-7B model scores each trial for disease
relevance. A fine-tuned variant can optionally re-sort the top 25.

**Stage 3 — reading the rules.** The model reads each eligibility rule, judges
it, and quotes the sentence it relied on. Because a note settles only 7.6% of
rules, this produces evidence for a human rather than a better ranking.

---

## Experiment tracking

A local MLflow store holds the fourteen TREC runs that produced reported results
— not every experiment the project ran — with settings, metrics and intervals,
the write-up, and the threshold commit that governed each run. The three
fine-tuned adapters are on the registry; seed 20261007 is marked as the one in
use. The store itself is not in version control; the same numbers are in
`docs/trec_mlflow_runs.csv`, one row per run-and-metric.

**The history was backfilled from stored results rather than captured live.**
Live tracking starts with the reader.

![Five MLflow experiments and their run counts](docs/images/mlflow_experiments.png)

![Fine-tuning run: learning rate, seed, AUROC with interval, threshold commit](docs/images/mlflow_run_adapter.png)

![Model registry: three adapters, AUROC, in_use alias on seed 20261007](docs/images/mlflow_registry.png)

---

## What is not built

- A hosted production database, or a pipeline that keeps ClinicalTrials.gov current
- A public URL. The container, the API and the page run on a laptop
- The model choosing among named tools, with a measured choice accuracy
- A prompt-injection test set
- Langfuse. MLflow is the evaluation registry
- vLLM in the demo container. The 7B was measured on rented GPUs; the laptop demo replays stored replies

LangGraph was used for a clarifying-question loop, measured, and not kept in the
product path. The reader's output schema and quote check are in the demo.

---

## Where to read what

| File | What it is |
|---|---|
| `HANDOFF.md` | Why the architecture is shaped this way, four measurement errors and their corrections, dead ends not worth re-running |
| `docs/trec_published_standings.md` | How these numbers relate to published work, and why most comparisons are invalid |
| `docs/trec_hybrid_retrieval.md` | The search stage and the keyword-decomposition result |
| `docs/trec_lora_rank.md` | Benchmark-standard measures for every approach tried, both years |
| `docs/trec_lora_elig.md` | The fine-tuning work, including a collapsed first attempt and its diagnosis |
| `docs/trec_gpt_vs_adapter.md` | GPT-5.4 against the trained 7B on the same 6,249 pairs: 0.821 against 0.779 |
| `docs/trec_frontier_elig.md` | GPT-5.4 as a measured baseline |
| `docs/trec_reader.md` | Rule-by-rule reader: 7.6% of rules settled, AUROC 0.59, fabrication 3.75% |
| `docs/trec_short_notes.md` | What a short patient note can support, and why walking every rule is the wrong ranking method |
| `docs/trec_model_currency.md` | How the system would stay current; distillation designed but not run |
| `docs/trec_demo.md` | Seed data, replay mode, and the clean-clone container test |
| `docs/trec_mlflow_runs.csv` | The fourteen reported runs, one row per run-and-metric, with intervals |
| `docs/trec_shortlist_diagnosis.md`, `docs/trec_shortlist_fix.md` | What the shortlist contains, and three approaches that did not help |
| `THRESHOLDS.md` | Each run's deciding numbers, committed **before** that run |
| `DECISIONS.md` | Every decision, its options, and what evidence would reverse it |
| `CONTEXT.md` | Project purpose, medical vocabulary, settled arguments |
| `docs/papers/` | Local copies of the papers this work is measured against |

Earlier work on a lung-cancer slice — closed-vocabulary matching, the containment
hierarchy, the original fabricated-quote audit — is in `docs/step*.md` and
`report.md`. `docs/STATUS.md` and `SPIKE_2_PLAN.md` describe that earlier phase
and are partly superseded.

---

## Reproducing the measurements

**The demo runs from a clone. The measurements do not.** `data/` is excluded from
version control and runs to about 2 GB, of which 1.7 GB is the trial corpus. The
repository holds code and write-ups, not the indexes, scores or expert verdicts.

The 2021 snapshot is downloadable from trec-cds.org
(`2021_data/ClinicalTrials.2021-04-27.part{1-5}.zip`). The expert verdicts came
from NIST; `docs/trec_retrievability.md` records the provenance.

Set `PYTHONIOENCODING=utf-8` and pass `encoding="utf-8"` to every file read and
write. The trial text contains `≥`, `≤` and `×`, which crash a default Windows
console.

---

## Working practices

- Each run's deciding numbers go into `THRESHOLDS.md` **before** that run and are
  never edited afterwards. The git history showing that order is part of what the
  project demonstrates.
- Every reported figure carries an interval, and fine-tuned results report several
  random seeds with their spread rather than the best one.
- Results are retracted when they fail re-examination. The fine-tuning headline
  moved from 0.793 to 0.779 when two more seeds came in, and a claimed parity with
  a frontier model was withdrawn once the comparison turned out to be measuring
  something else.
- Priorities, in order: **honest results > a working end-to-end system > breadth
  of features.**

**The system does not say a patient qualifies.**
