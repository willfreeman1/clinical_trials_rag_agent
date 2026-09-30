# Step 9 Task 1 — mechanical quote-flag recategorisation

No human. No API. Thresholds committed before this ran.

Checked quote-slots (six facts, labels that need a quote): **4384**.
Originally flagged by the stored checker: **1353**.

## Buckets among originally flagged slots

| Bucket | n | share of flagged |
|---|---:|---:|
| A — Stitched | 619 | 45.8% |
| B — Whitespace / punctuation | 3 | 0.2% |
| C — Word-list miss | 675 | 49.9% |
| D — Paraphrased | 13 | 1.0% |
| E — Absent | 43 | 3.2% |
| ok — Would now pass (stored flag was stale) | 0 | 0.0% |

**D + E = 57 of 4,384 slots (1.3%).** Gate: above 5% is a support problem.
Cleared. Step 8 reader's missing-quote rate was 1.2% — the same neighbourhood.

Most of the old 52% trial-level flag was **C** (word-list) and **A** (stitched
stage quotes). 334 of the C flags are platinum quotes that say chemotherapy or
systemic treatment without naming platinum. That is a real passage, not a
spelling variant. The platinum word list is not widened to "chemotherapy";
that would hide the hierarchy hole Step 3d already measured.

Residual flag rate once A, B, and C are handled: **1.3%**.

## By fact

| Fact | slots | orig. flagged | D+E |
|---|---:|---:|---:|
| autoimmune_disease | 465 | 26 | 2 |
| brain_metastases | 719 | 91 | 2 |
| disease_stage | 1206 | 425 | 37 |
| driver_mutation | 698 | 150 | 9 |
| prior_immunotherapy | 750 | 285 | 3 |
| prior_platinum_chemo | 546 | 376 | 4 |
