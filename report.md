# What we did, and what we found

> **STATUS: HISTORICAL RECORD. Read `README.md` and `CONTEXT.md` first.**
>
> Every measurement below is accurate and still worth knowing. Two things have changed
> since it was written:
>
> 1. **This report's recommendation was rejected.** The closing sections, *"What this
>    means"* and *"Paths discussed after the result"*, argue for dropping search and
>    extracting each trial into a fixed set of columns. That was rejected because
>    columns only answer facts somebody chose in advance, and a schema tuned to lung
>    cancer would not transfer to another disease. `CONTEXT.md` Part 2 explains what
>    replaced it. **Do not act on the recommendations in those two sections.**
> 2. **This report optimised the wrong direction.** It tested single-fact questions
>    ("which trials refuse brain metastases") and tuned for precision — a tightened
>    phrase list, and restricting the search to the cannot-join section. The current
>    architecture joins many filters with *and*, which narrows multiplicatively, so
>    **precision per filter hardly matters and recall per filter is everything.** The
>    full-text recall numbers treated below as the weaker result (81.2% and 79.1%) are
>    the ones that matter now.
>
> What stands unchanged and is the reason this file is kept: meaning-based search cannot
> tell a refusal from a requirement, the measured mechanism for why, the cost of a
> frontier-model read, and the answer key itself.


28 September 2026. This is a record of the feasibility work on recruiting non-small cell lung cancer trials from ClinicalTrials.gov. It covers the download, the word-search measurements, the answer key, and the comparison of word search with meaning search. It also records the decisions that followed those numbers.

A clinical trial record says who may join the study. The part that matters here is free text called eligibility criteria. That text is usually split into a can-join list (inclusion criteria: the trial wants people who match these lines) and a cannot-join list (exclusion criteria: the trial refuses people who match these lines). The same medical fact can sit on either list, and the list changes the meaning. "Prior immunotherapy" on the can-join list means the trial wants people who already had it. On the cannot-join list, it means those people are refused.

The system must not say that a patient qualifies. No real patient records were used. The labels describe what the trial text says.

## The job this work was testing

ClinicalTrials.gov already lets you filter on structured fields: disease, recruiting status, age bounds, sex. The clinical rules that decide eligibility are not structured. They sit in one free-text field per trial.

The idea under test was a second step after that filter. Take the trials the structured filter returns, and search inside their eligibility text so that a question does not have to send every trial back to a large language model. A large language model is a paid text model. Here that model was GPT-5.4, from OpenAI. Reading all 1,308 trials once cost about $7. Doing that on every new question is what the search step was supposed to avoid.

Two facts were used as probes, not as the finished product:

- Prior immunotherapy: treatment the person has already received, or that is already underway, when they join. Checkpoint drugs and drugs aimed at PD-1, PD-L1, or CTLA-4 count. A laboratory result about PD-L1 on the tumor does not. A drug the study itself gives or forbids during the study does not.
- Brain metastases: cancer in the brain or central nervous system, including leptomeningeal disease (cancer in the membranes around the brain and spinal cord).

The question scored in the search test was: which trials refuse this fact?

## The trials

Downloaded 28 September 2026 from the public ClinicalTrials.gov API, version 2. No API key.

```
GET https://clinicaltrials.gov/api/v2/studies
    query.cond = non-small cell lung cancer
    filter.overallStatus = RECRUITING
```

The site reported 1,308 studies. All 1,308 were saved. Searching the abbreviation NSCLC instead of the full disease name returns a different set (about 1,377 recruiting). The full registry is on the order of 600,000 studies. About 124,000 mention cancer. This work did not search those larger sets.

Every saved trial had eligibility text. Across the 1,308:

- Total eligibility text: 4,684,121 characters
- Mean: 3,581 characters
- Longest: 20,203 characters

The can-join and cannot-join sections are not separate fields. A script splits them by looking for a heading.

- A heading on its own line, such as "Inclusion Criteria" or "Exclusion Criteria": 1,234 trials
- The same words somewhere in a line, used when the line-by-line heading was missing: 46 trials
- No heading found: 28 trials. For these, the cannot-join search has nothing to read. The full text is kept as the can-join side and the cannot-join side is empty.
- No trial had the cannot-join heading before the can-join heading.

Saved as `data/nsclc_recruiting.jsonl`. The API query is in `data/nsclc_recruiting_meta.json`.

## Word search, before any model

This reproduced the measurement that motivated the project. On an earlier unsaved slice of 300 trials, a word search for prior immunotherapy returned 142 trials, of which 49 had the phrase only on the cannot-join list. That is about 35%.

The same measurement on all 1,308 recruiting trials, with a tightened phrase list, landed in the same place.

Immunotherapy phrases, all required to match as written: immunotherapy, PD-1, PD-L1, checkpoint inhibitor, pembrolizumab, nivolumab, atezolizumab. "PD-1" required the hyphen. The letters ICI inside other words were not counted. Case-insensitive "ici" as letters anywhere hits 1,052 of 1,308 trials. ICI as its own word hits 50. The brand name Keytruda appears in zero eligibility texts. Durvalumab, which was not in the seven-phrase list, appears in 33.

Where the seven phrases sit:

| Where the phrase is | Trials |
|---|---:|
| Can-join list only | 230 |
| Cannot-join list only | 228 |
| Both lists | 207 |
| Phrase present, but no heading to split on | 17 |
| Nowhere | 626 |

Narrow precision treats a hit as right only when the phrase is on the cannot-join list and not also on the can-join list: 228 / 665 = 34.3%. The Wilson interval is 30.8% to 38.0%. A Wilson interval is a band around a percentage. On another similar set of trials, the percentage usually falls inside the band. This 34.3% matches the earlier 35% on the unsaved 300.

Wide precision treats any cannot-join mention as a hit, including trials that also mention the phrase on the can-join list: 435 / 665 = 65.4%.

A search that looks only at the cannot-join section returns those 435 trials. By construction, every one of them has the phrase on that section. 207 of the 435 also mention the phrase on the can-join list, so the section search does not mean the trial's rule is a simple refusal. 121 of the immunotherapy hits contain PD-1 or PD-L1 and none of the other history words. Those are often a lab marker, not a record of past treatment.

Brain phrases: "brain metast…", "brain mets", leptomeningeal, "CNS metast…", "central nervous system metast…", intracranial, carcinomatous meningitis. The exact phrase "brain mets" hit zero trials.

| Where the phrase is | Trials |
|---|---:|
| Can-join list only | 90 |
| Cannot-join list only | 413 |
| Both lists | 85 |
| Phrase present, but no heading | 10 |
| Nowhere | 710 |

Narrow precision: 413 / 588 = 70.2% (66.4% to 73.8%). Cannot-join search hits: 498.

This word search cannot read negation. A can-join line that says "No prior immunotherapy" is a refusal, and a cannot-join search misses it. NCT07103395 is one of those. The opposite error also happens: a cannot-join line that mentions immunotherapy can be a lab rule, a drug given during the study, or a requirement stated in a double negative.

The script is `scripts/keyword_section_check.py`. The counts are in `data/keyword_report.json`.

## The answer key

Word search cannot be scored for "does this trial refuse the fact?" until something else decides what the text means. That decision is the answer key. GPT-5.4 read each trial and assigned a class, with a verbatim quote. The classes are the same for every fact:

- required: the trial wants people who have it
- allowed: the trial accepts people who have it, does not demand it, and states no limit
- allowed with an exception: the trial accepts people who have it, and the passage states a limit
- barred: the trial refuses people who have it, and states no exception
- barred with an exception: the trial refuses people who have it, except in cases the passage states
- both classifications: one passage wants it and another refuses it, and they disagree about the same fact
- not mentioned
- unclear: the text mentions it but does not say whether people who have it are wanted or refused

Allowed-with-an-exception and barred-with-an-exception are chosen by the rule, not by the verb in the sentence. "Eligible if the brain metastases are stable" is acceptance with a limit. "Excluded unless the brain metastases are stable" is a refusal with a stated exception. Later counts of "trials that take stable brain metastases" have to include both.

The model was told not to decide whether any patient qualifies. A laboratory PD-1 or PD-L1 result is not treatment history. Treatment the protocol gives or forbids during the study is not prior immunotherapy.

### Pilots on 10 trials

The same 10 trials were labeled several times before the full run. They were chosen because the wording is checkable by hand: a plain refusal, a plain requirement, a refusal written on the can-join list ("No prior immunotherapy"), a PD-L1 lab score that only looks like a drug history, and brain-metastasis rules with an exception.

The trial ids: NCT05940532, NCT07154706, NCT06780085, NCT06983899, NCT04302025, NCT07103395, NCT06660407, NCT06363734, NCT05498428, NCT06424067.

GPT-5.4 mini is the smaller, cheaper model. Prices used for the estimates: mini $0.75 per million input tokens and $4.50 per million output tokens. GPT-5.4: $2.50 and $15. A token is a chunk of text the vendor bills, roughly three quarters of a word in ordinary English.

| Run | Model | Input tokens | Output tokens | Estimated cost | What it showed |
|---|---|---:|---:|---:|---|
| First mini | gpt-5.4-mini | 12,838 | 1,157 | $0.015 | Called a bone-metastasis list a brain rule. Called a drug forbidden during the study "prior immunotherapy." |
| Second mini | gpt-5.4-mini | 15,398 | 1,331 | $0.018 | Prompt patched with those 10 examples ("bone is not brain"). Rejected. A prompt fitted to 10 trials is not usable on 1,308. |
| Third mini | gpt-5.4-mini | 14,278 | 1,508 | $0.018 | Shared general prompt. Bone and concurrent-drug errors remained. "Allowed" was used when the same sentence stated a limit. |
| First GPT-5.4 | gpt-5.4 | 14,278 | 1,599 | $0.060 | Fixed the bone and concurrent-drug errors. Still called a limited permission "allowed." |
| Second GPT-5.4 | gpt-5.4 | 14,998 | 1,600 | $0.062 | Added allowed-with-an-exception. The limited immunotherapy permission was classified correctly. |

The shared prompt, not the patched one, is what labeled the full set. It lives in `scripts/mini_pilot.py`.

### Full labeling

GPT-5.4 labeled all 1,308 trials. The script is `scripts/label_corpus.py`. Six threads, with resume, so a stopped run can continue. 1,308 succeeded, 0 failed, about 8 minutes.

- Input tokens: 1,735,341
- Output tokens: 194,803
- Estimated cost: $7.26

Counts after four hand edits, described below. Immunotherapy was not edited.

Prior immunotherapy:

| Class | Trials |
|---|---:|
| not mentioned | 558 |
| barred | 259 |
| allowed with an exception | 179 |
| required | 168 |
| barred with an exception | 87 |
| allowed | 23 |
| both classifications | 22 |
| unclear | 12 |

Brain metastases:

| Class | Trials |
|---|---:|
| not mentioned | 589 |
| barred with an exception | 417 |
| barred | 124 |
| allowed with an exception | 111 |
| required | 47 |
| unclear | 7 |
| both classifications | 7 |
| allowed | 6 |

For the search test, a "real refusal" is barred or barred with an exception. That is 346 immunotherapy trials and 541 brain-metastasis trials. Trials labeled both-classifications or unclear were not counted as refusals. If a search returns them, they count as wrong returns.

### Quote check, and the four edits

Every quote was checked. The quote had to be an exact piece of the eligibility text, or the same text after removing backslashes and asterisks and collapsing whitespace. It also had to contain a word from that fact's list. A "not mentioned" label had to have an empty quote.

The check flagged 357 of 1,308 rows at first, and 353 after the edits below. Many flags are the checker being literal. Examples: the model quoted a real sentence that says ICPI, PD(L)-1, or durvalumab, and the word list did not include those spellings. Some quotes glue two real bullets. Some immunotherapy refusals are written as "no prior systemic therapy," which bars immunotherapy without using the word. Those labels were left as they were.

Four brain labels were changed by hand on 28 September 2026. The distant-spread bans were kept. A ban on distant spread does refuse brain metastases, because a brain metastasis is distant spread. About 35 trials of that kind stayed labeled barred.

- NCT05991193. Was a brain label copied from the trial title. The eligibility text is 463 characters and never mentions the brain. Exclusion text is "None." Changed to not mentioned, empty quote.
- NCT04852588. Oligometastatic disease with up to five metastases anywhere, plus a required brain MRI as a staging scan. The MRI is a test, not a rule that the person has brain metastases. Changed to not mentioned.
- NCT07401615. "No active distant metastasis or controlled distant metastasis" is spread to any organ, and this wording was the weak case rather than a clear ban. Changed to not mentioned.
- NCT06582940. Stays required. The quote was replaced with the exact substring "intracranial metastases during previous TKI therapy." The trial is for non-small cell lung cancer with brain metastasis.

Saved as `data/answer_key.jsonl`. The summary, including the four edited ids, is `data/answer_key_summary.json`.

## The search test

Three lookups, scored against the answer key, for both facts. Each meaning-search list was cut to the same length as the word search it is compared with, so a longer list cannot win recall just by returning more trials.

Precision is the share of returned trials that the answer key calls a real refusal. Recall is the share of real refusals the search found. The range after each percentage is a Wilson interval.

The word lists are the ones above. The meaning search does not use those lists. It embeds the question sentence. Embedding means turning a piece of text into a list of numbers. Closeness is a cosine: a score for whether two lists point the same way. 1 would mean the same direction. The model was OpenAI `text-embedding-3-small`, which can take a whole eligibility text in one piece. The longest text here is 20,203 characters, under that limit. Each of the 1,308 full texts was embedded, and so was each cannot-join section. The 28 empty cannot-join sections were not allowed to rank. Cost: 1,570,440 tokens, about $0.03.

Question sentences:

- "Trials that refuse patients who have already received immunotherapy, a checkpoint inhibitor, or a PD-1, PD-L1, or CTLA-4 drug."
- "Trials that refuse patients who have brain metastases or central nervous system metastases."

The full-text word-search counts are 682 and 598, a bit higher than the 665 and 588 above. The earlier counts left out the 17 and 10 trials that contain the phrase but have no heading. This test counts those as full-text hits. The cannot-join counts match: 435 and 498.

### Prior immunotherapy

346 trials should be returned.

| Lookup | Returned | Real refusals in that list | Precision | Recall |
|---|---:|---:|---|---|
| Word search, full text | 682 | 281 | 41.2% (37.6–44.9) | 81.2% (76.8–85.0) |
| Word search, cannot-join section | 435 | 222 | 51.0% (46.3–55.7) | 64.2% (59.0–69.0) |
| Meaning search, full text, closest 682 | 682 | 243 | 35.6% (32.1–39.3) | 70.2% (65.2–74.8) |
| Meaning search, cannot-join section, closest 435 | 435 | 177 | 40.7% (36.2–45.4) | 51.2% (45.9–56.4) |

### Brain metastases

541 trials should be returned.

| Lookup | Returned | Real refusals in that list | Precision | Recall |
|---|---:|---:|---|---|
| Word search, full text | 598 | 428 | 71.6% (67.8–75.0) | 79.1% (75.5–82.3) |
| Word search, cannot-join section | 498 | 415 | 83.3% (79.8–86.3) | 76.7% (73.0–80.1) |
| Meaning search, full text, closest 598 | 598 | 334 | 55.9% (51.8–59.8) | 61.7% (57.6–65.7) |
| Meaning search, cannot-join section, closest 498 | 498 | 310 | 62.2% (57.9–66.4) | 57.3% (53.1–61.4) |

Meaning search lost on both facts, on both the full text and the cannot-join section, on both precision and recall.

One OpenAI attempt was made before this, and it stopped immediately because the account had no credits. A small local model already on the computer (`all-MiniLM-L6-v2`) was run anyway. That run does not count. The model reads about 200 words at a time, it was not the model under test, and those scores were set aside. The table above is the `text-embedding-3-small` run after credits were added.

The script is `scripts/embed_and_search.py`. Vectors and the report: `data/embeddings_openai.npz`, `data/embeddings_openai_meta.json`, `data/search_test_report.json`.

## Why meaning search lost

The refuse question lands as close to trials that require the fact as to trials that refuse it. Often the requirement is closer. Every eligibility text scored in a narrow band, about 0.40 to 0.65. Inside the refusals, the spread from a low score to a high score is about 0.10. The gap between "requires it" and "refuses it" is about 0.01. The scatter inside one group is larger than the gap between the groups, so a ranking mixes them.

Prior immunotherapy, closeness of the full text to the refuse question:

| Answer-key class | Trials | Average closeness |
|---|---:|---:|
| required | 168 | 0.571 |
| allowed with an exception | 179 | 0.563 |
| barred | 259 | 0.559 |
| barred with an exception | 87 | 0.557 |
| not mentioned | 558 | 0.512 |

115 of the 168 requirement trials score above the typical refusal. The closest requirement, NCT05234307 at 0.65, says "Prior PD-1 and/or PD-L1 directed therapies are required." A real refusal, NCT05102110 at 0.40, says people are out if they have already received radiotherapy, chemotherapy, or immunotherapy. The question and the requirement share the drug names. "Refuse" versus "required" barely moves the score.

Of the 439 wrong trials in the immunotherapy full-text meaning-search list: 131 require prior immunotherapy, 145 accept it (132 of those with a stated limit), and 136 never mention it.

Brain metastases, closeness of the full text to the refuse question:

| Answer-key class | Trials | Average closeness |
|---|---:|---:|
| required | 47 | 0.579 |
| barred with an exception | 417 | 0.537 |
| allowed with an exception | 111 | 0.540 |
| barred | 124 | 0.529 |
| not mentioned | 589 | 0.502 |

41 of the 47 requirement trials score above the typical refusal. NCT06974370, at 0.65, says "at least 1 brain metastasis." Of the 264 wrong trials in the brain full-text list: 43 require brain metastases, 75 accept them, and 136 never mention them.

Trials that never mention the fact still enter the list. They sit only about 0.03 to 0.05 below a real refusal, and that gap is smaller than the scatter inside the refusal group.

Restricting meaning search to the cannot-join section does not fix it. On that section, immunotherapy refusals average about 0.58 and requirements average about 0.57. Brain-metastasis requirements still average higher than brain-metastasis refusals.

## What this means

> **SUPERSEDED — do not act on this section.** Its reasoning about
> meaning-based search and polarity still holds. Its conclusion that the reading step
> should replace search, and that a column table is the answer, was rejected. See
> `CONTEXT.md` Part 2, "Why the architecture changed after spike 1".

Meaning search finds trials that talk about the topic. It does not tell a refusal from a requirement. A database of those number lists cannot be the part that decides who is refused.

The cannot-join word search is the stronger shortlist of the methods tested. Its ceiling is visible in the table. It misses refusals that do not use the listed words, including "no prior systemic therapy" and "no distant spread," and it misses refusals written on the can-join list. It also returns trials that want the fact, trials that allow it with a limit, and lab-marker mentions. Those errors are a reading job. The model never recovers a trial the shortlist dropped.

GPT-5.4 can do that reading when it sees the text. The full read of 1,308 trials, for both facts, cost about $7 and produced an answer key that needed four hand edits on the brain fact. The government site has already cut the registry to these 1,308 trials. Meaning search is a way to avoid reading a pile that is too big to read. This pile is small enough that the read is the more accurate answer.

At the size of all cancer trials, about 124,000, a full read per question stops being cheap. The polarity problem remains at that size. Closeness search would still mix requirements and refusals.

## Paths discussed after the result

> **SUPERSEDED — do not act on this section.** Of the four paths listed here, the
> chosen direction is a changed version of the last one: pre-extracted columns are kept
> only as a cache for facts that recur, never as the schema the system depends on. The
> trained-embedding kill-test is not scheduled. `SPIKE_2_PLAN.md` is the current plan.

These were discussed. None of them has been run, except the measurements already in this report.

**Stop the meaning-search database.** This is the path the numbers support. The spike existed to find out whether closeness search could carry refusal versus requirement. It cannot, with the embedding model that was tested.

**Read all 1,308 with a cheaper model, such as Qwen on a rented GPU.** That can answer a question. It does not use a meaning-search database. On this computer, which has no NVIDIA GPU, a model that size would be slow. On a rented GPU it is a batch job that has to be shut off when it finishes. Restricting the model to the word-search hits is faster, and recall stays capped at 64% for immunotherapy and 77% for brain metastases.

**Train an embedding model to separate refusals from requirements.** Worth a short kill-test, not a build. Train on one fact only, using the quote or the sentences that contain the phrase, and then search the other fact. The result that would change the decision: on the fact the model was not trained on, requirements rank below refusals, and the search at least matches the cannot-join word search. The expected result is that held-out trials of the same fact look better, because the model memorized phrases such as "PD-1" and "brain metastasis," and the other fact does not improve. Same-fact improvement would not justify the database. There are 47 trials that require brain metastases, so that side of the test is small. The run belongs on one rented GPU, and the GPU should be shut off when the run ends.

**Turn each trial into columns once.** Run a reader once. Store, for each trial, the class for prior immunotherapy, the class for brain metastases, and the quote. Later questions filter that table. New trials get labeled once. This handles polarity, because the model makes that decision at labeling time. It only answers facts that have a column. A question about a mutation or a lab value that was never extracted has nothing to filter. The gold rows already in `data/answer_key.jsonl` are those two columns.

A DeBERTa classifier, which reads the words in order and outputs a class, fits the column path. It sees "no" and "required" while they are still in the sentence. That is a different tool from an embedding model.

## Money

Estimates from token counts and the published prices. They are not invoice totals.

| Step | Estimated cost |
|---|---:|
| Three mini pilots on 10 trials | $0.05 |
| Two GPT-5.4 pilots on 10 trials | $0.12 |
| GPT-5.4 labels for all 1,308 | $7.26 |
| text-embedding-3-small for the search test | $0.03 |
| **Sum** | **about $7.46** |

The discarded local embedding run cost nothing. No Lambda GPU has been started.

## What this work did not do

- No vector database, chatbot, or agent framework
- No read of the search shortlist by GPT-5.4, which would show how much a reader cleans up the word-search hits
- No coordinator-style question with several facts at once
- No search of the full registry or of all cancer trials
- No trained embedding model
- No column table beyond the two facts already in the answer key

## Files

| Path | What it is |
|---|---|
| `README.md` | Entry point: reading order, what is on disk, what is superseded. |
| `CONTEXT.md` | What the project is for, the domain, and the settled decisions. Current. |
| `SPIKE_2_PLAN.md` | The current plan. Written after this report. |
| `data/nsclc_recruiting.jsonl` | The 1,308 trials. |
| `data/keyword_report.json` | Word-search counts and section split. |
| `data/answer_key.jsonl` | GPT-5.4 labels, plus the four hand edits. |
| `data/answer_key_summary.json` | Label counts, cost, edited ids. |
| `data/embeddings_openai.npz` | Number lists from text-embedding-3-small. |
| `data/search_test_report.json` | Precision and recall for the four lookups. |
| `scripts/keyword_section_check.py` | Download and word search. |
| `scripts/mini_pilot.py` | The shared labeling prompt, and the 10-trial runner. |
| `scripts/label_corpus.py` | Full labeling run. |
| `scripts/embed_and_search.py` | Embedding and the search test. |

`data/` is gitignored. The briefs and `scripts/keyword_section_check.py` were in the first local commit. Later scripts and this report may be uncommitted. There is no remote repository.
