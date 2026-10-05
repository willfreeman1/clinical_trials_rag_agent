# Provenance and licensing of the demo seed

This folder is a small slice used so the container can run from a
clean clone. It is not the full TREC collection.

## Clinical trial records

The trial titles, condition lists, summaries, and eligibility text
come from the **27 April 2021 ClinicalTrials.gov snapshot** that
the TREC Clinical Trials track used as its document collection
(posted on [trec-cds.org](https://www.trec-cds.org/2022.html)).
ClinicalTrials.gov is a US National Library of Medicine public
registry. The records are posted for public use. This seed keeps
only a few hundred of those records, enough to exercise search
and ranking.

Recruitment status, phase, and site are columns in the database
because a later update pipeline would need them. They are empty
in this seed: the local parse of the 2021 dump did not store
those fields, and the benchmark ignored them on purpose.

## Patient notes and expert marks

The three patient notes are TREC 2022 topics 1, 8, and 18, from
`topics2022.xml` as published on trec-cds.org. The joinable /
excluded / irrelevant marks are the corresponding lines from the
public 2022 qrels released after the track.

The generic [TREC Individual User Agreement](https://duc.nist.gov/forms/ind_appl_trec.html)
is written for older newspaper collections (Financial Times, Los
Angeles Times, and others named as copyright holders). It forbids
redistributing those collections except as small excerpts. Those
copyright holders do not own ClinicalTrials.gov records, and they
do not own these synthetic case notes.

The Clinical Trials track posted the topics and the qrels on
public pages without that newspaper click-wrap. This repository
ships a **three-topic excerpt** for a non-commercial research
demonstration. Anyone who wants the full topic set or the full
qrels should take them from NIST / trec-cds.org and follow
whatever terms NIST publishes at the time.

If NIST later says these notes or marks must not sit in a git
repository, delete this folder and replace it with a download
script. The trial records can stay.

## Embeddings and stored model replies

The vectors were computed here with OpenAI `text-embedding-3-small`
from the trial and keyword text already in this seed. They are a
derived file so the demo does not need an embedding key.

The stored reader replies are the raw JSON the project’s 7B model
already produced for these pairs. They are not new model calls.

## What this is not

This is not a statement that anyone qualifies for a trial. The
notes are invented cases from a research track. They are not real
patients.
