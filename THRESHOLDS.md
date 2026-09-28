# Thresholds

Committed **before** the run they apply to. Git history is the evidence they were not
moved afterward. If one turns out badly chosen, it gets logged in `DECISIONS.md` and
said plainly in the memo — it does not get edited here after results exist.

---

## Spike 2, Step 1 — concept concentration in the corpus

**Committed 2026-09-28, before any extraction run.** Set by Claude with reasoning
below, not picked arbitrarily. Will may override; an override gets a `DECISIONS.md`
entry.

### What is being measured

How many distinct clinical facts do these trials actually gate on, and how concentrated
is that distribution? This decides whether a fixed set of pre-extracted columns could
cover what real questions ask about (an extraction project, which overlaps the NHTSA
classification work already in the portfolio) or whether the long tail forces filters
built at query time (a retrieval project, which is what the gap table wants).

Measured from the corpus rather than from a question set, because **a fact no trial
gates on cannot eliminate any trial** — if a patient mentions something no trial has a
rule about, every trial passes that filter trivially. So the vocabulary that matters is
defined by the trials, not by the questions. TREC topics are not used here: they span
all diseases, so their fact diversity would mostly reflect disease diversity, and
against a lung-cancer corpus that would produce a misleadingly long tail in the
direction that flatters the project.

### Sample

300 trials drawn from the 1,308 in `data/nsclc_recruiting.jsonl`, random seed
**20260928**. The drawn id list is committed to `data/step1_sample_ids.json` so the run
is reproducible.

### Granularity rules — fixed before the run, because the answer depends on them

The measurement is meaningless without these, and they are the easiest thing to get
wrong.

**Level 1, coarse category.** A closed list of 17. The model must choose from it and may
not invent a category. Concentration at this level is bounded by construction, so the
reportable thing is how the mass distributes, not whether 40 categories suffice.

`disease_or_stage`, `histology_or_subtype`, `biomarker_or_mutation`,
`prior_systemic_therapy`, `prior_local_therapy`, `performance_status`,
`organ_function_lab`, `comorbidity_or_history`, `metastasis_site`, `infection_status`,
`pregnancy_or_contraception`, `concurrent_medication`, `trial_participation`,
`consent_or_compliance`, `demographics`, `measurable_disease`, `other`.

**Level 2, fine concept.** Open vocabulary, but strictly formatted: a short lowercase
noun phrase naming the specific clinical thing being gated on.

- **Name the thing, not the threshold.** "creatinine clearance ≥60" → `creatinine
  clearance`.
- **Name the thing, not the direction.** "No prior immunotherapy" → `prior
  immunotherapy`. This is deliberate and aligns the measurement with the architecture:
  a filter searches for the *topic*, and polarity is resolved later by the model that
  reads the survivors.
- No numbers, no units, no negation words, singular where natural.

**Normalisation after extraction.** The same concept will come back spelled several
ways. Report the concentration curve three ways so the sensitivity is visible: raw
strings; lowercased and punctuation-stripped exact merge; and an embedding-based merge
of near-duplicates at cosine 0.85 and again at 0.90. State in the memo which curve the
decision was read from.

### Thresholds

Read from the **fine-concept** curve, on the exact-merge normalisation, using the share
of all gating criteria covered by the 40 most common concepts.

| Result | Decision |
|---|---|
| Top 40 concepts cover **≥90%** of gating criteria | **Extraction project.** Columns cover nearly everything a question would raise. Retrieval is marginal, the project overlaps NHTSA, and it should stop and be reconsidered. |
| Top 40 cover **70–90%** | **Continue, case is mixed.** The memo must say so plainly rather than claiming retrieval is necessary. |
| Top 40 cover **<70%** | **Retrieval project.** The tail is real, query-time filters are needed, and the gap table's vector database has a defensible justification. |

**Reasoning for 90 and 70, rather than picking round numbers.** A question raises about
six facts, and it is most likely to raise the facts trials most commonly gate on, so
frequency-weighted coverage of the top concepts is a fair proxy for "would columns have
answered this question." At 90% coverage, a six-fact question has a good chance of
being fully covered by columns and the fallback path is rarely exercised, which makes
the retrieval machinery decorative. Below 70%, roughly one fact in three needs
query-time handling, so almost every question exercises the fallback and it is
load-bearing.

**Second reported number, no threshold attached:** the share of trials whose entire
gating set falls inside the top 40 concepts. That is the "a pure column system could
handle this trial" rate. Reported for interpretation, not used as a gate, because it
answers a per-trial question while the decision is per-question.

### Known limits of this measurement, recorded before seeing results

- One model does the extraction. No second-model agreement check and no human check.
  Acceptable because a concentration curve is robust to small per-item error, but it
  means the curve is an estimate, not ground truth.
- 300 of 1,308 trials, so tail concepts appearing once or twice corpus-wide are
  under-sampled. That biases the measured tail **shorter** than reality, which means it
  biases toward the extraction conclusion — the conservative direction for this
  project, which is the right way round.
- Lung cancer only. Concentration in another disease area is unmeasured.
