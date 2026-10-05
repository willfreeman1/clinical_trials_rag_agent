# Laptop demo: seed data and a container

This is engineering, not a new measurement. The bar is: does it
build from a clean clone, does it run, is it tested, can someone
follow the README.

The system does not say a patient qualifies.

## What the seed covers

Three TREC 2022 patients (topics 1, 8, and 18) and **423**
trials from the 27 April 2021 ClinicalTrials.gov snapshot.

| Patient | Joinable | Excluded | Irrelevant in the seed |
|---|---:|---:|---:|
| 1 (young man, delayed puberty / low GnRH) | 76 | 117 | 48 |
| 8 (infant, Hirschsprung disease) | 14 | 26 | 57 |
| 18 (toddler, recurring rash) | 36 | 13 | 53 |

393 trials have a proper inclusion / exclusion heading. 21 have
no heading, so the splitter leaves them as one unsplit block.
One of those is NCT00001412, shipped on purpose so that
behaviour is visible.

75 stored reader replies (the 2022 top-25 reads for these three
patients). Expert marks for every seed pair we have a qrel for.
Embeddings: OpenAI `text-embedding-3-small`, 1,536 numbers per
trial, shipped in `demo/seed/embeddings.npz` so nobody needs an
embedding key.

Provenance and terms: `demo/seed/LICENSE.md`. Seed size on disk
is about **3 MB**.

## What replay mode does and does not execute

`MODEL_MODE=replay` is the default. Every `/health` and
`/v1/match` response names it.

**Runs for real:** turning the note into keyword queries (from
the stored list), word search, vector search over the shipped
embeddings, merging the lists, re-sorting by the stored disease
score, splitting eligibility text into rules, checking that a
quoted sentence is in the named source, combining the per-rule
verdicts.

**Does not run:** a live 7-billion-parameter model. The reader
calls a function that returns the stored raw reply for that
patient–trial pair. If there is no stored reply, that trial is
still ranked and the response says so.

This is not a trick. A demo that hid the mode would be the one
dishonest thing in the project.

`MODEL_MODE=live` plus `MODEL_URL` points that same function at
a real model server for anyone who has one.

## Clean-clone test

5 October 2026. Fresh folder, `docker compose build --no-cache`,
empty database volume. Docker Desktop had to be started first
on this machine.

**Did not work first time.** Three things:

1. The first image installed the whole measurement stack
   (MLflow, LangGraph) from the repo `requirements.txt`. That
   was unnecessary. The Dockerfile now installs only Flask,
   psycopg, and numpy. App image **246 MB**.
2. Host port 8000 was already taken by another local service.
   `curl` hit that process (`/health` returned a different
   project's champion checkpoint). Published port is now
   **8088**.
3. On Windows PowerShell, `curl` is not curl. The JSON body
   was eaten. Use `curl.exe` and a file: `--data-binary @req.json`.

After those fixes: `docker compose up --build` came up in about
**9 seconds** once images existed (first slim rebuild about
**25 seconds**; pulling `pgvector/pgvector:pg16` is **438 MB**).
Seed on disk **~3 MB**.

`GET /health` returned `model_mode: replay`, `n_patients: 3`,
`n_trials: 423`, database up.

`POST /v1/match` for patient 1, depth 5: 305 trials retrieved,
72 ms, mode named replay. First hit NCT01511588, expert mark
joinable, six rules, quote bucket `ok` (anosmia / low GnRH
from the note). Second hit expert-excluded. The existing 34
tests passed inside the container.

## Page

`GET /` serves one HTML page from the same container. It calls
`/v1/patients` and `/v1/match`. There is no separate frontend
build. Replay is named on the page. The three notes are the
only patients; there is no free-text box.

The looping GIF at the top of `README.md` is captured by
`scripts/capture_demo_gif.py` (Playwright plus Pillow) while the
demo is already running. It is not a screen recording.

The system does not say a patient qualifies.
