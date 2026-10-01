# TREC Clinical Trials — is the scoreboard usable?

Gates: `THRESHOLDS.md`, commit **03d95b5**, before the live-API probe
and before this count. Snapshot checked first.

**Yes. An archived snapshot exists and still downloads.** The live
registry is not the corpus. Do not revert to the lung slice.

The 70% per-level live-API gate applies only if that dump is gone. It
is not gone.

## 1. Patients and judgments

Relevance: **0** not relevant, **1** excluded (meets inclusion, fails
an exclusion), **2** eligible. Official NIST labels.

| | 2021 | 2022 | Combined |
|---|---:|---:|---:|
| Patient descriptions (topics) | 75 | 50 | 125 |
| Judgments | 35,832 | 35,394 | 71,226 |
| Unique NCT IDs | 26,162 | 26,585 | **48,714** |

| Relevance | 2021 judgments | 2022 judgments |
|---|---:|---:|
| 0 not relevant | 24,243 (67.7%) | 28,419 (80.3%) |
| 1 excluded | 6,019 (16.8%) | 3,036 (8.6%) |
| 2 eligible | 5,570 (15.5%) | 3,939 (11.1%) |

Unique NCT IDs are lower than judgment counts because the same trial
is judged for more than one patient. 4,033 trials appear in both years.

Topics: [topics2021.xml](https://www.trec-cds.org/topics2021.xml),
[topics2022.xml](https://www.trec-cds.org/topics2022.xml).
Qrels: NIST `qrels2021.txt` / `qrels2022.txt`. NIST's TLS certificate
was expired on this machine; the files were fetched earlier via the
browser tool and counted locally. Topic XML came from trec-cds.org.

## 2. Snapshot — this is the corpus

Both years use **one** collection: an **April 27, 2021** dump of
ClinicalTrials.gov, **375,581** records (ir_datasets: 375,580 docs).

Still up at [trec-cds.org/2021.html](https://www.trec-cds.org/2021.html),
path `2021_data/ClinicalTrials.2021-04-27.part{1–5}.zip`. HEAD of all
five parts returned **200**, application/zip, ~1.71 GB compressed:

| Part | Bytes |
|---|---:|
| 1 | 382,792,518 |
| 2 | 378,478,271 |
| 3 | 375,998,752 |
| 4 | 360,825,058 |
| 5 | 296,625,845 |

Also indexed as ir_datasets `clinicaltrials/2021` (same dump), with
qrels as `clinicaltrials/2021/trec-ct-2021` and `…/trec-ct-2022`.

**Use this dump, not the live API, as the trial text.** Eligibility
wording on ClinicalTrials.gov has moved on. The judgments are about
the 2021 text.

The five zips have not been downloaded onto this machine yet. They
do not need to be until we actually read trial XML. Existence is
enough for Task A.

## 3. Live API (does not decide usability)

450 unique judged NCT IDs, seed **202609305**, 150 per relevance
level, ClinicalTrials.gov API v2 `filter.ids`.

| Level | Sampled | Still resolve | Rate |
|---|---:|---:|---:|
| 0 not relevant | 150 | 150 | 100% |
| 1 excluded | 150 | 150 | 100% |
| 2 eligible | 150 | 150 | 100% |
| Overall | 450 | 450 | 100% |

No skew in this sample: eligible IDs are not missing while irrelevant
ones remain. "Resolves" means the NCT ID still has a registry page.
Completed and withdrawn trials still resolve. The hole that would
kill the benchmark is **removed records** and **changed eligibility
text**. The snapshot sidesteps both.

## 4. Gate

| Condition | Result |
|---|---|
| Archived snapshot downloadable | **Yes** |
| Live-API 70% per level | Does not apply (snapshot exists). Sample was 100% at every level anyway |

TREC is usable as the scoreboard. The lung slice stays as the
diagnostic bench. Do not start TREC-scale concept assignment.

## Cost — bring to Will; do not start

Judged pool: **48,714** unique trials. At ~43 rules each: **2.09 million**
rules.

Rough gpt-5.4 phrase-extraction ($2.50 / $15.00 per million tokens,
~500 in / 80 out per rule): **about $5,100** for the judged pool
only.

The full 375k snapshot at the same rate is on the order of **$40,000**.
Do not do that.

Options, not started:

1. A cheap model for assignment (likely an order of magnitude less).
2. Extract patient phrases first (125 notes — dollars), then assign
   only trial rules that could match those concepts — still needs a
   trial-side pass unless retrieval happens first.
3. Assign only the judged pool, on the snapshot text, after Task D
   clears on the lung slice.

Do not start any of these until the number is agreed.

## What was not done

- UMLS not installed. Need the Metathesaurus files from Will (see
  chat). API not used for bulk.
- No concept assignment.
- No TREC retrieval run.
- Steps 6 and 7 not started.
- Lung slice not discarded.
- Direction rule not touched.
