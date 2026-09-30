# Clinical-trial eligibility retrieval — start here

**Where the project is right now:** spike 1 is finished and reported. Spike 2 is
written and has not been started. Nothing has been built — no service, no vector
database, no agent framework, no container.

**Your task is `SPIKE_2_PLAN.md`.** Everything else on this page exists to tell you
what to read first and which parts of the older files are still true.

---

## Read these three files, in this order

| Order | File | Status | What it is |
|---|---|---|---|
| 0 | `docs/STATUS.md` | **CURRENT — read first** | Where the project stands, in plain language: every number measured so far, what is still broken, what has not been measured at all, and the decision to make. |
| 1 | `CONTEXT.md` | **CURRENT** | What the project is for, the medical words, who would use it, and every decision that has been argued and settled. Read all of it. |
| 2 | `SPIKE_2_PLAN.md` | **CURRENT — this is the work** | The seven steps to run, with thresholds. The thresholds are deliberately arbitrary placeholders; they get replaced before each step runs. |
| 3 | `report.md` | **HISTORICAL RECORD** | What spike 1 measured. The measurements are accurate and worth knowing. **Its two closing sections, "What this means" and "Paths discussed after the result", are superseded — do not follow their recommendations.** It carries a note saying so at the top. |

There is no other documentation. `SPIKE_PLAN.md`, the original spike brief, has been
**deleted** because its steps were executed and its architecture assumption turned out
to be wrong. Anything in it that is still true was moved into `CONTEXT.md` or
`SPIKE_2_PLAN.md`. If you find a reference to it anywhere, the reference is stale.

There is no full project brief, on purpose. The spikes decide whether writing one is
worth it.

---

## The current plan in one paragraph

A question like *"67-year-old, stage IIIB lung cancer, EGFR exon 20 insertion, ECOG 1,
prior carboplatin and pemetrexed, creatinine clearance 55, within 200 miles"* gets taken
apart into separate facts. Each fact becomes a **timid filter** that eliminates a trial
only when it is confident the trial cannot take this patient — a trial that never
mentions kidney function has no kidney rule, so silence is a pass. The filters run one
after another, most eliminative first, so each reads only what survived the last. A
frontier model then reads the few dozen trials left and decides properly. Because the
filters are joined by *and*, they narrow multiplicatively, which means **precision per
filter hardly matters and recall per filter is everything.** Spike 2 tests whether that
architecture holds up.

---

## What is already on disk

### Data — `data/` is gitignored, so it exists locally only

| File | What it is | Reuse? |
|---|---|---|
| `nsclc_recruiting.jsonl` | The 1,308 recruiting lung-cancer trials, downloaded 2026-09-28 | **Yes. Do not re-download.** |
| `nsclc_recruiting_meta.json` | The API query that produced them | Yes |
| `answer_key.jsonl` | A frontier model's label for each trial, for two facts (prior immunotherapy, brain metastases), plus a verbatim quote. Includes four hand edits. | **Yes — this is the development ground truth for spike 2** |
| `answer_key_summary.json` | Label counts, cost, the four edited trial ids | Yes |
| `keyword_report.json` | Word-search counts and the section split | Yes, as a reference |
| `search_test_report.json` | Precision and recall for the four spike-1 lookups | Historical |
| `embeddings_openai.npz`, `embeddings_openai_meta.json` | Whole-document and whole-section vectors from `text-embedding-3-small` | **Superseded.** Spike 2 needs per-bullet vectors, not whole-document ones. |
| `embeddings.npz`, `embeddings_meta.json` | A discarded run with a small local model | **Ignore.** Not the model under test; kept only for the record. |
| `mini_pilot*.json`, `gpt54_pilot*.json` | The five labelling pilot runs on 10 trials | Historical |

### Scripts — `scripts/`

| File | What it does | Reuse? |
|---|---|---|
| `keyword_section_check.py` | Downloads trials, splits inclusion from exclusion, runs word search | **Reuse the download and the section splitter.** The tightened phrase-list logic is superseded — spike 2 needs the broadest possible lists, not tightened ones. |
| `mini_pilot.py` | Holds the shared labelling prompt, and the 10-trial runner | **Reuse the prompt.** It is the standard the answer key was built to. |
| `label_corpus.py` | The full labelling run, six threads, resumable | **Reuse** when labelling more facts |
| `embed_and_search.py` | Whole-document embedding and the spike-1 search test | **Approach superseded.** Reuse only the embedding-cache plumbing. |

### Git

One commit so far (`Initial commit: spike brief and a repeatable registry word-search
check`). The later scripts and `report.md` are uncommitted. There is no remote
repository. `data/`, `.env` and `.specstory/` are gitignored.

---

## Things that are true and easy to get wrong

Five mistakes that would cost real time. All of them are explained in `CONTEXT.md`;
this is the short list.

1. **Set `PYTHONIOENCODING=utf-8` and pass `encoding="utf-8"` to every file read and
   write.** The trial text is full of `≥`, `≤` and `×`, which crash a default Windows
   console.
2. **Use word boundaries in every pattern, and check sampled hits.** Searching for the
   abbreviation `ICI` as a plain substring matches 242 of 300 trials; as
   `\bICIs?\b` it matches 10. The difference is *participants*, *toxicity*,
   *immunodeficiency*, *physician*.
3. **Never embed a whole patient question or a whole trial record.** Spike 1 measured
   why: every 3,581-character eligibility text landed within a narrow band of the
   question, and the gap between "requires it" and "refuses it" was about 0.01 while the
   scatter inside one group was about 0.10. Facts get embedded one at a time, against
   criteria bullets one at a time.
4. **A filter's ground truth is every trial with any rule about the fact**, not the
   trials that refuse it. In answer-key terms that is every label except
   `not mentioned` — 750 trials for immunotherapy, 719 for brain metastases. Measuring
   recall against the refusal set instead would test the wrong thing.
5. **A filter may only eliminate on confident evidence.** Silence is a pass. The whole
   argument that the filters narrow multiplicatively depends on this, and it is a
   non-negotiable in `SPIKE_2_PLAN.md`.

## Working practices

- **`THRESHOLDS.md`** — the real threshold for each step, committed **before** that
  step runs. The numbers in the plan are placeholders and are labelled as such.
- **`DECISIONS.md`** — a running log: date, decision, options considered, why, and what
  evidence would reverse it.
- **Track cost from the first API call.** Report spend at the checkpoint.
- **Ask Will** before spending over about $25 in one run, and before changing anything
  in the plan's Non-negotiables list.
- Commit small and often, with explanatory messages.
- You are expected to think, not just type. When the data contradicts an assumption in
  a plan, say so, propose a change, and log it. **Priorities, in order: honest results >
  a working end-to-end system > breadth of features.**
