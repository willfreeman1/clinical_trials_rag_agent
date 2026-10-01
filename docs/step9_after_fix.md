# Step 9 — numbers after the remaining-list fixes

Previous reports stay on disk. This page is the side-by-side after
the bounded remaining list: 12 stage labels, 70 crossings, the
qualifier convention, the free scope count, then one re-score.

A smaller headline that discards fewer joinable trials is the better
system, not a regression.

| | Before | After | Change | Why |
|---|---:|---:|---:|---|
| Ceiling (perfect finder) | 54.2% | 51.9% | −2.4 pp | Twelve title-inferred stage requirements no longer discard anyone. 147 qualified bars (`active`, `uncontrolled`, `untreated`, `symptomatic`, `within N months`) became `barred_with_exception` and keep the trial. 70 mixed-polarity / heuristic-disagree slots were re-labelled. |
| Matching-gated narrowing | 44.7% | 43.0% | −1.7 pp | Same key changes, still gated on matching. Matching itself was not re-run. |
| Lost-joinable (gpt-5.4) | 6.3% (38/600) | 5.6% (32/569) | −0.7 pp | Existing reads, scored against the corrected matching-gated discarded set. 32 sampled discards are no longer discards; 1 sampled keep became a discard (600 − 32 + 1 = 569). |
| Ceiling if conditionals could be settled | 79.0% | 78.2% | −0.8 pp | Qualifier pass moves rows into this bucket; they already were not discarding under the realistic rule. |
| Matching-gated if every fact were queried | 51.9% | 50.2% | −1.7 pp | Same key, complete-parse arm. |

**10% lost-joinable gate: cleared.** 5.6% is under 10%. The 43.0% narrowing figure is **not withdrawn**.

Old files (unchanged): `data/step2_ceiling.json`, `data/step3d_match_report.json`, `data/step8_report.json`.

New files: `data/step2_ceiling_after_fix.json`, `data/step3d_match_report_after_fix.json`, `data/step8_report_after_fix.json`.

The Will extra-exclusion sheet was not regenerated.

## What was applied, in order

1. **Twelve stage labels cleared.** Eligibility stated no stage rule; the stored `required` came from the title. 212 wrong discards among the 20 patients. Mechanical. Snapshot `data/answer_key_step5b_pre_remaining.jsonl`.
2. **Seventy crossing slots re-labelled.** 50 mixed polarity, 20 where the polarity check disagreed. gpt-5.4, ~$0.97, verbatim eligibility substring required. 24 first-pass quotes were stitches or truncations; a one-contiguous-passage retry verified all 70. Other facts on those trials were left alone.
3. **Qualifier convention.** A word that narrows a bar makes it conditional. 147 `barred` quotes became `barred_with_exception`: immunotherapy 12, brain 34, platinum 9, autoimmune 92. That keeps the trial. It is why the headline fell, and that is correct.
4. **Scope count (free).** See `docs/step9_scope_count.md`. 281 of 1,307 trials (21.5%) list a named cancer other than lung on ClinicalTrials.gov `conditions`. 308 quotes across 231 trials name another cancer. The 34 missing-quote labels were not a basket problem (12 title-inferred stage, 0 basket-scoping). The corpus-level basket problem is larger than that slice. Wholesale scoping re-label is still held; this count is what would justify it.

Steps 6 and 7 were not started.
