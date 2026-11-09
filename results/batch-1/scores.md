# batch-1 scores (generated)

Output of `python3 -I scripts/score.py scoring/scores-batch-1.csv 39 --schedule results/batch-1/schedule.txt`.

| Run | Findings | FP | Key items in findings | Recall (findings) | Key items noticed (findings + questions) | Recall (noticed) |
| --- | --- | --- | --- | --- | --- | --- |
| A-run1-claude | 14 | 0 | 15 | 38% | 19 | 49% |
| A-run2-claude | 11 | 0 | 14 | 36% | 17 | 44% |
| A-run3-claude | 12 | 0 | 14 | 36% | 17 | 44% |
| A-run4-claude | 12 | 0 | 13 | 33% | 17 | 44% |
| A-run5-claude | 13 | 0 | 13 | 33% | 19 | 49% |
| B-run1-claude | 17 | 0 | 18 | 46% | 21 | 54% |
| B-run2-claude | 16 | 0 | 19 | 49% | 24 | 62% |
| B-run3-claude | 16 | 0 | 18 | 46% | 25 | 64% |
| B-run4-claude | 17 | 0 | 17 | 44% | 24 | 62% |
| B-run5-claude | 16 | 0 | 17 | 44% | 26 | 67% |
| C-run1-claude | 6 | 0 | 7 | 18% | 11 | 28% |
| C-run2-claude | 14 | 0 | 17 | 44% | 20 | 51% |
| C-run3-claude | 13 | 0 | 19 | 49% | 23 | 59% |
| C-run4-claude | 14 | 0 | 19 | 49% | 24 | 62% |
| C-run5-claude | 11 | 0 | 14 | 36% | 19 | 49% |
| D-run1-claude | 17 | 0 | 20 | 51% | 22 | 56% |
| D-run2-claude | 17 | 0 | 23 | 59% | 24 | 62% |
| D-run3-claude | 16 | 0 | 20 | 51% | 24 | 62% |
| D-run4-claude | 14 | 0 | 16 | 41% | 18 | 46% |
| D-run5-claude | 14 | 0 | 15 | 38% | 20 | 51% |
| M-run1-claude | 34 | 11 | 19 | 49% | 19 | 49% |
| M-run2-claude | 34 | 11 | 20 | 51% | 20 | 51% |
| M-run3-claude | 30 | 7 | 22 | 56% | 22 | 56% |
| M-run4-claude | 31 | 9 | 20 | 51% | 20 | 51% |
| M-run5-claude | 32 | 13 | 19 | 49% | 19 | 49% |
| union of all runs | | | 34 | 87% | 35 | 90% |

## Per arm

| Arm | Runs | Mean recall (findings) | SD | Range | Mean recall (noticed) |
| --- | --- | --- | --- | --- | --- |
| A | 5 | 35% | 2% | 33% to 38% | 46% |
| B | 5 | 46% | 2% | 44% to 49% | 62% |
| C | 5 | 39% | 13% | 18% to 49% | 50% |
| D | 5 | 48% | 8% | 38% to 59% | 55% |
| M | 5 | 51% | 3% | 49% to 56% | 51% |

## Arm comparisons (findings recall, permutation test)

| Comparison | Mean difference | p | Method | Note |
| --- | --- | --- | --- | --- |
| B vs A | +10% | 0.008 | exact |  |
| C vs A | +4% | 0.643 | exact |  |
| D vs A | +13% | 0.016 | exact |  |
| M vs A | +16% | 0.008 | exact |  |
| C vs B | -7% | 0.405 | exact |  |
| D vs B | +3% | 0.627 | exact |  |
| M vs B | +6% | 0.024 | exact |  |
| D vs C | +9% | 0.254 | exact |  |
| M vs C | +12% | 0.048 | exact |  |
| M vs D | +3% | 0.556 | exact |  |

## Carry-over check

Each session's recall minus its arm's mean, against the order sessions ran in.

| Order | Run | Recall minus arm mean |
| --- | --- | --- |
| 1 | D-run4-claude | -7% |
| 2 | M-run4-claude | +0% |
| 3 | A-run2-claude | +1% |
| 4 | C-run2-claude | +5% |
| 5 | M-run2-claude | +0% |
| 6 | B-run5-claude | -2% |
| 7 | M-run5-claude | -3% |
| 8 | C-run5-claude | -3% |
| 9 | M-run1-claude | -3% |
| 10 | C-run3-claude | +10% |
| 11 | C-run4-claude | +10% |
| 12 | A-run5-claude | -2% |
| 13 | C-run1-claude | -21% |
| 14 | A-run1-claude | +3% |
| 15 | D-run3-claude | +3% |
| 16 | A-run4-claude | -2% |
| 17 | M-run3-claude | +5% |
| 18 | B-run1-claude | +1% |
| 19 | B-run4-claude | -2% |
| 20 | D-run2-claude | +11% |
| 21 | B-run3-claude | +1% |
| 22 | B-run2-claude | +3% |
| 23 | D-run1-claude | +3% |
| 24 | D-run5-claude | -10% |
| 25 | A-run3-claude | +1% |

Spearman rho = +0.22, permutation p = 0.285: no sign that later sessions did better.

Never noticed by any run: K27, K28, K36, K37
Only in questions, never in findings: K29

## Beyond memory (post hoc)

The 14 key items no arm-M run predicted. Output of `python3 -I scripts/score.py scoring/scores-batch-1.csv 39 --arms A,B,C,D --only K04,K20,K23,K27,K28,K29,K30,K31,K32,K33,K34,K36,K37,K39`, per-arm part.

### Per arm

| Arm | Runs | Mean recall (findings) | SD | Range | Mean recall (noticed) |
| --- | --- | --- | --- | --- | --- |
| A | 5 | 14% | 5% | 7% to 21% | 19% |
| B | 5 | 24% | 4% | 21% to 29% | 34% |
| C | 5 | 19% | 12% | 0% to 29% | 24% |
| D | 5 | 23% | 11% | 7% to 36% | 24% |

### Arm comparisons (findings recall, permutation test)

| Comparison | Mean difference | p | Method | Note |
| --- | --- | --- | --- | --- |
| B vs A | +10% | 0.032 | exact |  |
| C vs A | +4% | 0.635 | exact |  |
| D vs A | +9% | 0.222 | exact |  |
| C vs B | -6% | 0.548 | exact |  |
| D vs B | -1% | 1.000 | exact |  |
| D vs C | +4% | 0.698 | exact |  |

Never noticed by any run: K27, K28, K36, K37
Only in questions, never in findings: K29
