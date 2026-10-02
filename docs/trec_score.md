# Does a reordering stage earn its place? (2021/2022 only)

Gates committed in `114cce7` before any 0–3 score.
2023 was not touched. The shortlist was not cut. Nothing discarded.
Equivalent depth is a multiple of the **baseline's own equivalent depth**
at the same N. The baseline row is calibration, not a result.
A continuous score is judged at depths 10 and 20. It does not get
credit for a depth-200 or depth-500 win.

Qwen GPU: NVIDIA A100-SXM4-40GB. Elapsed 21389.0s. Mini: $8.996.

Notes: elig_full cut to sample: elapsed 15171s projected 37929s rate 26.04/s

## Run 1 — all 125 patients (topical scoring)

Eligibility is not in these tables. That arm was cut to a sample.

### 2021 (n=75)

#### Eligible recall (label 2)

| Arm | @10 | @20 | @50 | @100 | @200 | @500 | P@10 | P@20 | 10-in-20 |
|---|---|---|---|---|---|---|---|---|---|
| `baseline` | 5.7% | 10.7% | 22.4% | 36.5% | 53.0% | 76.4% | 28.5% | 26.0% | 9/75 |
| `mini_full` | 9.0% | 17.1% | 32.5% | 47.5% | 65.6% | 85.5% | 38.4% | 38.0% | 23/75 |
| `qwen_topical_title_cond_digit` | 9.3% | 17.5% | 33.8% | 52.1% | 70.9% | 87.1% | 41.2% | 39.5% | 22/75 |
| `qwen_topical_title_cond_cont` | 10.4% | 19.0% | 35.1% | 52.4% | 71.3% | 87.8% | 45.1% | 43.1% | 24/75 |
| `qwen_topical_slice_digit` | 10.0% | 18.8% | 36.9% | 54.8% | 73.2% | 87.3% | 43.1% | 42.5% | 27/75 |
| `qwen_topical_slice_cont` | 12.1% | 20.3% | 38.1% | 55.8% | 74.2% | 88.1% | 51.9% | 47.9% | 37/75 |
| `medcpt_ce_raw` | 8.1% | 13.6% | 27.0% | 39.2% | 52.3% | 70.1% | 34.8% | 32.8% | 18/75 |
| `medcpt_ce_keywords` | 8.2% | 14.1% | 25.9% | 38.1% | 51.7% | 70.2% | 36.9% | 33.5% | 20/75 |

#### Equivalent depth (multiple of baseline's own)

| Arm | Read 20 | Read 200 | Read 500 |
|---|---:|---:|---:|
| `baseline` | 1.00x (16) | 1.00x (180) | 1.00x (432) |
| `mini_full` | 2.47x (37) | 2.01x (356) | 1.77x (757) |
| `qwen_topical_title_cond_digit` | 2.71x (42) | 2.36x (418) | 1.90x (823) |
| `qwen_topical_title_cond_cont` | 3.15x (48) | 2.39x (425) | 1.97x (857) |
| `qwen_topical_slice_digit` | 3.10x (47) | 2.58x (459) | 1.89x (816) |
| `qwen_topical_slice_cont` | 3.48x (54) | 2.73x (487) | 1.98x (861) |
| `medcpt_ce_raw` | 1.97x (30) | 1.33x (234) | 0.92x (400) |
| `medcpt_ce_keywords` | 2.09x (29) | 1.30x (223) | 0.98x (411) |

Full-shortlist eligible recall (must stay 91.6%): 91.6%.

### 2022 (n=50)

#### Eligible recall (label 2)

| Arm | @10 | @20 | @50 | @100 | @200 | @500 | P@10 | P@20 | 10-in-20 |
|---|---|---|---|---|---|---|---|---|---|
| `baseline` | 7.4% | 13.3% | 27.2% | 40.4% | 58.3% | 79.5% | 38.6% | 36.1% | 13/50 |
| `mini_full` | 11.0% | 18.9% | 36.3% | 53.1% | 68.2% | 84.6% | 49.2% | 46.0% | 23/50 |
| `qwen_topical_title_cond_digit` | 10.4% | 18.2% | 36.6% | 52.5% | 70.3% | 85.1% | 49.0% | 45.5% | 24/50 |
| `qwen_topical_title_cond_cont` | 11.0% | 19.2% | 36.5% | 53.0% | 70.1% | 85.4% | 50.0% | 47.3% | 20/50 |
| `qwen_topical_slice_digit` | 11.0% | 20.7% | 40.1% | 55.2% | 71.9% | 85.3% | 51.4% | 49.9% | 27/50 |
| `qwen_topical_slice_cont` | 12.2% | 22.4% | 39.9% | 56.4% | 73.1% | 86.2% | 57.0% | 53.0% | 25/50 |
| `medcpt_ce_raw` | 10.4% | 16.3% | 30.2% | 43.2% | 56.6% | 73.2% | 48.2% | 40.2% | 18/50 |
| `medcpt_ce_keywords` | 11.5% | 18.6% | 32.7% | 46.3% | 60.2% | 74.2% | 50.8% | 45.8% | 24/50 |

#### Equivalent depth (multiple of baseline's own)

| Arm | Read 20 | Read 200 | Read 500 |
|---|---:|---:|---:|
| `baseline` | 1.00x (17) | 1.00x (177) | 1.00x (409) |
| `mini_full` | 2.13x (30) | 2.41x (363) | 1.62x (648) |
| `qwen_topical_title_cond_digit` | 2.15x (30) | 2.42x (378) | 1.77x (699) |
| `qwen_topical_title_cond_cont` | 2.41x (34) | 2.32x (359) | 1.92x (732) |
| `qwen_topical_slice_digit` | 2.89x (41) | 2.50x (384) | 1.76x (701) |
| `qwen_topical_slice_cont` | 3.42x (45) | 2.77x (430) | 1.95x (755) |
| `medcpt_ce_raw` | 1.95x (27) | 1.31x (216) | 1.10x (429) |
| `medcpt_ce_keywords` | 2.43x (33) | 1.45x (232) | 1.11x (421) |

Full-shortlist eligible recall (must stay 91.4%): 91.4%.

## Run 2 vs Run 1 — matched 30-patient sample

Same seed **20261001** as the cheap-pass sample. 15 patients per year.
This is the only fair Run 1 vs Run 2 comparison.

### 2021 (n=15)

#### Eligible recall (label 2)

| Arm | @10 | @20 | @50 | @100 | @200 | @500 | P@10 | P@20 | 10-in-20 |
|---|---|---|---|---|---|---|---|---|---|
| `baseline` | 8.5% | 13.8% | 25.3% | 36.0% | 53.3% | 76.7% | 30.0% | 28.3% | 2/15 |
| `mini_full` | 11.2% | 20.5% | 34.0% | 44.8% | 60.6% | 84.9% | 40.0% | 38.7% | 5/15 |
| `qwen_topical_title_cond_digit` | 11.3% | 21.3% | 34.7% | 49.0% | 66.0% | 87.2% | 42.0% | 38.0% | 4/15 |
| `qwen_topical_title_cond_cont` | 12.1% | 22.7% | 34.3% | 50.0% | 69.2% | 87.6% | 45.3% | 42.3% | 4/15 |
| `qwen_topical_slice_digit` | 11.3% | 21.6% | 37.1% | 50.8% | 71.5% | 86.9% | 42.7% | 40.7% | 5/15 |
| `qwen_topical_slice_cont` | 13.5% | 22.5% | 36.1% | 51.9% | 71.3% | 87.8% | 48.7% | 44.3% | 7/15 |
| `qwen_elig_full_digit` | 12.4% | 19.0% | 33.1% | 47.4% | 64.5% | 84.8% | 45.3% | 40.7% | 4/15 |
| `qwen_elig_full_cont` | 14.2% | 22.7% | 36.1% | 51.9% | 68.7% | 85.4% | 55.3% | 48.7% | 7/15 |
| `medcpt_ce_raw` | 11.4% | 18.3% | 29.2% | 39.5% | 52.6% | 73.7% | 37.3% | 34.7% | 4/15 |
| `medcpt_ce_keywords` | 11.1% | 18.2% | 25.9% | 33.9% | 46.6% | 69.2% | 36.7% | 33.7% | 3/15 |

#### Equivalent depth (multiple of baseline's own)

| Arm | Read 20 | Read 200 | Read 500 |
|---|---:|---:|---:|
| `baseline` | 1.00x (17) | 1.00x (170) | 1.00x (402) |
| `mini_full` | 1.62x (27) | 1.91x (344) | 1.70x (704) |
| `qwen_topical_title_cond_digit` | 1.48x (31) | 2.02x (360) | 1.85x (778) |
| `qwen_topical_title_cond_cont` | 1.93x (38) | 2.10x (376) | 1.89x (795) |
| `qwen_topical_slice_digit` | 1.68x (34) | 2.41x (432) | 1.77x (746) |
| `qwen_topical_slice_cont` | 2.11x (41) | 2.35x (421) | 1.90x (801) |
| `qwen_elig_full_digit` | 1.80x (36) | 1.78x (312) | 1.53x (640) |
| `qwen_elig_full_cont` | 2.73x (50) | 2.16x (389) | 1.64x (693) |
| `medcpt_ce_raw` | 1.41x (28) | 1.22x (213) | 1.05x (423) |
| `medcpt_ce_keywords` | 1.37x (23) | 0.98x (167) | 0.92x (375) |

Full-shortlist eligible recall (must stay 91.6%): 91.5%.

### 2022 (n=15)

#### Eligible recall (label 2)

| Arm | @10 | @20 | @50 | @100 | @200 | @500 | P@10 | P@20 | 10-in-20 |
|---|---|---|---|---|---|---|---|---|---|
| `baseline` | 6.2% | 10.7% | 23.6% | 36.5% | 51.9% | 69.8% | 40.7% | 36.0% | 4/15 |
| `mini_full` | 10.5% | 16.3% | 30.3% | 43.8% | 59.5% | 73.7% | 50.7% | 45.3% | 6/15 |
| `qwen_topical_title_cond_digit` | 7.8% | 14.5% | 28.1% | 44.0% | 59.1% | 74.3% | 48.7% | 46.0% | 7/15 |
| `qwen_topical_title_cond_cont` | 9.0% | 14.5% | 27.9% | 43.5% | 60.1% | 73.9% | 53.3% | 49.3% | 6/15 |
| `qwen_topical_slice_digit` | 9.9% | 15.5% | 32.3% | 47.4% | 62.8% | 75.2% | 58.0% | 52.0% | 7/15 |
| `qwen_topical_slice_cont` | 10.0% | 15.8% | 30.5% | 48.2% | 64.4% | 76.3% | 58.7% | 53.3% | 6/15 |
| `qwen_elig_full_digit` | 9.8% | 16.0% | 30.3% | 44.9% | 59.1% | 75.6% | 58.7% | 52.0% | 7/15 |
| `qwen_elig_full_cont` | 11.0% | 17.9% | 31.6% | 46.5% | 62.3% | 74.9% | 62.7% | 58.0% | 9/15 |
| `medcpt_ce_raw` | 9.0% | 15.8% | 28.5% | 41.4% | 56.7% | 70.4% | 46.7% | 42.3% | 6/15 |
| `medcpt_ce_keywords` | 9.2% | 14.6% | 27.9% | 40.5% | 51.3% | 65.6% | 49.3% | 44.0% | 7/15 |

#### Equivalent depth (multiple of baseline's own)

| Arm | Read 20 | Read 200 | Read 500 |
|---|---:|---:|---:|
| `baseline` | 1.00x (16) | 1.00x (175) | 1.00x (438) |
| `mini_full` | 2.18x (28) | 1.87x (324) | 1.41x (626) |
| `qwen_topical_title_cond_digit` | 1.90x (27) | 1.76x (315) | 1.49x (662) |
| `qwen_topical_title_cond_cont` | 1.88x (30) | 1.77x (313) | 1.56x (684) |
| `qwen_topical_slice_digit` | 2.58x (37) | 2.13x (377) | 1.67x (731) |
| `qwen_topical_slice_cont` | 2.49x (35) | 2.24x (384) | 1.74x (762) |
| `qwen_elig_full_digit` | 2.25x (37) | 1.44x (256) | 1.50x (663) |
| `qwen_elig_full_cont` | 3.01x (45) | 1.86x (324) | 1.40x (626) |
| `medcpt_ce_raw` | 2.43x (29) | 1.76x (290) | 1.24x (541) |
| `medcpt_ce_keywords` | 2.20x (29) | 1.22x (209) | 0.94x (416) |

Full-shortlist eligible recall (must stay 91.4%): 84.0%.

## Verdict against `114cce7`

**Run 1 earns a topical-reordering slot.** Best arm is
`qwen_topical_slice_cont`: equivalent depth at 200 is **2.73×**
on 2021 and **2.77×** on 2022. Both clear 1.20× / 1.10×. The
15-patient preview did not overstate the direction.

**Continuous wins the shallow bet.** On the winning document
(slice), P@20 is +5.4 points on 2021 (42.5% → 47.9%) and +3.1
on 2022 (49.9% → 53.0%). Credit stops there. Depth 200/500 is
almost the same for digit and continuous, as predicted.

**Mini does not keep the stage.** At matched full depth, mini
is 2.01× at 200 on 2021 against Qwen's 2.73× (ratio 0.74, well
under 0.90). Extending mini past 200 did help versus baseline
(2.01×, not the 1.00× cap of the top-200 stitch). Qwen is still
better, and free.

**Run 2 does not delete Run 1. Split.** On the matched
30-patient sample, best eligibility (`elig_full_cont`) is
**2.16×** at 200 on 2021 against topical slice **2.41×**, and
**1.86×** against **2.24×** on 2022. That is not ≤ 1.05×
baseline — a single score *can* rank — but it loses the reader
budget. It wins the page: P@20 48.7% vs 44.3% on 2021 (+4.4)
and 58.0% vs 53.3% on 2022 (+4.7). Different jobs. Do not
delete. Run 2 had more text and still lost at 200, so this is
not "more text won."

The product bar is still a fail: **37/75** is a lift from 9/75
and 22/75, not a pass (74 possible).

Run 3 was not started.

## Cost

- Qwen seconds: {"topical_title_cond": 6253.0, "topical_title_cond_slice": 8917.1, "elig_full": 6216.6}
- Mini: $8.996 in 5085.3s

The system does not say a patient qualifies.
