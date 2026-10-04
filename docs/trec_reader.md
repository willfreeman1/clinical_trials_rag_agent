# Rule-by-rule reader: first probe, diagnosis, re-probe

The reader is a program that splits one trial's eligibility text into
rules, asks a model to judge each rule against one patient note, and
checks that any quoted sentence actually appears in the named source.
It never says the patient qualifies.

This note is the **rate-and-schema probe** on 2022 patients 1 and 2
(50 trials, the top 25 of the topical slice for each). It is not the
1,250-pair measurement against expert verdicts. Do not quote anything
here as reader accuracy.

The design was locked in `f852d6c` before any score. The first probe
broke. The diagnosis and the amendment were committed in `621e898`
and `89a2bf4` before the re-probe. The quote-exists-in-source check
was not loosened.

The system does not say a patient qualifies.

## What 13 of 50 is not

The first probe produced valid JSON for **13 of 50** trials. The other
37 used all three retries and were discarded. **That is a
schema-conformance rate, not agreement with TREC labels.** The first
run was not scored against expert verdicts. Nobody should quote 13 of
50 as model performance.

The guardrail that rejected those 37 did its job. A layer that
refuses three-quarters of its inputs under a real fault is evidence
the design is sound, not that it is broken.

## The first probe was not a token-limit failure

The working hypothesis was that `MAX_NEW = 2048` (the cap on new
tokens the model is allowed to write) was cutting the JSON off on
long trials. The stored raw replies say otherwise.

- No failure sat at or near 2,048 output tokens. The longest failure
  was 1,390 tokens.
- Failures were not concentrated in high-rule-count trials. A
  45-rule trial passed. A 2-rule trial failed.

Of the 37 last replies:

| Last-reply error | Trials |
|---|---:|
| Empty quote on `met` or `not_met` | 27 |
| Empty `quote_source` | 5 |
| Broken JSON | 4 |
| Invented `rule_id` | 1 |

Among empty-quote rows in the replies that still parsed: **145
`not_met`**, **16 `met`**. The model was treating a silent note as
`not_met` and sending no span.

All 37 used three greedy retries. The retry pasted the previous
JSON, so the same empty quotes came back. That is why the first
projection was **$33.73** for 1,250 pairs: every failure burned four
generations.

## Two rules that are not the same

Two requirements lived in the same validator and were easy to
conflate.

1. **Quote guardrail (never loosen).** If a quote is offered, it must
   exist in the named source. That is what measures fabrication.
   `reader/verify_quote.py` is unchanged.
2. **Output contract (this was wrong).** Requiring every `met` and
   `not_met` to carry a quote is unsatisfiable for absence
   judgements. A silent note has no span to cite.

The second rule contradicted a principle this project already
locked in `CONTEXT.md`: a filter may only eliminate on confident
evidence; silence is a pass. `not_met` means the note positively
fails the rule, and that always has a quote. A rule the note is
silent about is `not_enough_information`.

The output contract required evidence for every negative judgement,
but judgements grounded in absence have no span to cite, so the
contract was unsatisfiable for a whole class of cases. The prompt
change is consistency with that settled rule, not a workaround.

If the model still returns `met` or `not_met` with no quote, that
row is converted to `not_enough_information`, flagged
`coerced_to_nei`, and counted. That case is not retried. One
targeted repair remains, only for broken JSON or a leftover schema
error, and it names only the failed rule IDs. It does not paste the
previous reply.

No rule-batching (that was the truncation design). No
grammar-constrained decoding (the worker is `transformers.generate`,
not vLLM). `MAX_NEW` stays 2,048.

## Re-probe, same 50 trials

Same patients, same trials, same model (Qwen2.5-7B-Instruct), A100
SXM4. Reads copied off. Instance terminated through the API.

| | First probe | Re-probe |
|---|---:|---:|
| Valid JSON | 13 / 50 | **50 / 50** |
| Generations | 167 (3.3 per trial) | **55 (1.1 per trial)** |
| Hours / cost | 0.75 h / $1.35 | **0.26 h / $0.46** |
| Projected 1,250 | 18.8 h / $33.73 | **6.4 h / $11.50** |

Five of the 50 used the one leftover repair. Seventeen rules on
eight trials were coerced to `not_enough_information`. That count
is a model-behaviour metric, not a hidden failure.

This is still not accuracy against TREC. Two patients cannot answer
the locked question.

## What the 50 reads look like, without scoring them

600 rules. **554** were `not_enough_information` with an empty
quote. That empty quote is bucket **E** by construction (absent
from the source) and is not fabrication: the verdict says the note
does not settle it.

The 46 rules that offered a quote (35 `met`, 11 `not_met`):

| Quote check | n |
|---|---:|
| `ok` (span in the named source) | 36 |
| `B` (same span after punctuation) | 7 |
| `E` (offered, but not in the source) | 3 |
| `D` (paraphrase) | 0 |

Honest fabrication on offered quotes is **D + E: 3 / 46**. That is
too small a sample to compare to the 5% reference or the earlier
1.3% measurement. The 1,250 is the place for that comparison.

Under both locked aggregations the 50 trial-level calls are mostly
**uncertain** (40 `any_hard_fail`, 42 `net_balance`). That is what
silence-is-pass does when most rules are `not_enough_information`:
the trial stays unsettled rather than being called joinable. Do
not read that as a TREC score.

## Cost and what happens next

Reader GPU spend on these probes is about **$1.81** of scoring
($1.35 + $0.46), plus a few dollars of failed boots while the
launcher and the empty-quote contract were being fixed. The
re-probe projection sits inside the original $7–$15 sketch without
cutting patients or trials.

The 1,250-pair pass is running under that projection. Agreement
with expert verdicts, joinable-versus-excluded AUROC on the same
1-versus-2 basis as 0.779, and the fabrication rate on offered
quotes will be written when those reads are copied off.

The system does not say a patient qualifies.
