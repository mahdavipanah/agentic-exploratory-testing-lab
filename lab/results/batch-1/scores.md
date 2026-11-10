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
| C-run1-claude | 6 | 0 | 7 | 18% | 12 | 31% |
| C-run2-claude | 14 | 0 | 17 | 44% | 20 | 51% |
| C-run3-claude | 13 | 0 | 19 | 49% | 23 | 59% |
| C-run4-claude | 14 | 0 | 19 | 49% | 24 | 62% |
| C-run5-claude | 11 | 0 | 14 | 36% | 19 | 49% |
| D-run1-claude | 17 | 0 | 20 | 51% | 22 | 56% |
| D-run2-claude | 17 | 0 | 23 | 59% | 24 | 62% |
| D-run3-claude | 16 | 0 | 20 | 51% | 24 | 62% |
| D-run4-claude | 14 | 0 | 16 | 41% | 19 | 49% |
| D-run5-claude | 14 | 0 | 15 | 38% | 20 | 51% |
| M-run1-claude | 34 | 13 | 18 | 46% | 18 | 46% |
| M-run2-claude | 34 | 11 | 20 | 51% | 20 | 51% |
| M-run3-claude | 30 | 9 | 21 | 54% | 21 | 54% |
| M-run4-claude | 31 | 10 | 20 | 51% | 20 | 51% |
| M-run5-claude | 32 | 13 | 19 | 49% | 19 | 49% |
| union of all runs | | | 34 | 87% | 35 | 90% |

## Per arm

| Arm | Runs | Mean recall (findings) | SD | Range | Mean recall (noticed) |
| --- | --- | --- | --- | --- | --- |
| A | 5 | 35% | 2% | 33% to 38% | 46% |
| B | 5 | 46% | 2% | 44% to 49% | 62% |
| C | 5 | 39% | 13% | 18% to 49% | 50% |
| D | 5 | 48% | 8% | 38% to 59% | 56% |
| M | 5 | 50% | 3% | 46% to 54% | 50% |

## Arm comparisons (findings recall, permutation test)

| Comparison | Mean difference | p | Method | Note |
| --- | --- | --- | --- | --- |
| B vs A | +10% | 0.008 | exact |  |
| C vs A | +4% | 0.643 | exact |  |
| D vs A | +13% | 0.016 | exact |  |
| M vs A | +15% | 0.008 | exact |  |
| C vs B | -7% | 0.405 | exact |  |
| D vs B | +3% | 0.627 | exact |  |
| M vs B | +5% | 0.056 | exact |  |
| D vs C | +9% | 0.254 | exact |  |
| M vs C | +11% | 0.063 | exact |  |
| M vs D | +2% | 0.714 | exact |  |

## Carry-over check

Each session's recall minus its arm's mean, against the order sessions ran in.

| Order | Run | Recall minus arm mean |
| --- | --- | --- |
| 1 | D-run4-claude | -7% |
| 2 | M-run4-claude | +1% |
| 3 | A-run2-claude | +1% |
| 4 | C-run2-claude | +5% |
| 5 | M-run2-claude | +1% |
| 6 | B-run5-claude | -2% |
| 7 | M-run5-claude | -2% |
| 8 | C-run5-claude | -3% |
| 9 | M-run1-claude | -4% |
| 10 | C-run3-claude | +10% |
| 11 | C-run4-claude | +10% |
| 12 | A-run5-claude | -2% |
| 13 | C-run1-claude | -21% |
| 14 | A-run1-claude | +3% |
| 15 | D-run3-claude | +3% |
| 16 | A-run4-claude | -2% |
| 17 | M-run3-claude | +4% |
| 18 | B-run1-claude | +1% |
| 19 | B-run4-claude | -2% |
| 20 | D-run2-claude | +11% |
| 21 | B-run3-claude | +1% |
| 22 | B-run2-claude | +3% |
| 23 | D-run1-claude | +3% |
| 24 | D-run5-claude | -10% |
| 25 | A-run3-claude | +1% |

Spearman rho = +0.11, permutation p = 0.606: no sign that later sessions did better.

Never noticed by any run: K27, K28, K36, K37
Only in questions, never in findings: K29

## Beyond memory (post hoc)

The 15 key items no arm-M run predicted. Output of `python3 -I scripts/score.py scoring/scores-batch-1.csv 39 --arms A,B,C,D --only K04,K20,K23,K26,K27,K28,K29,K30,K31,K32,K33,K34,K36,K37,K39`, per-arm part.

### Per arm

| Arm | Runs | Mean recall (findings) | SD | Range | Mean recall (noticed) |
| --- | --- | --- | --- | --- | --- |
| A | 5 | 15% | 3% | 13% to 20% | 19% |
| B | 5 | 23% | 4% | 20% to 27% | 32% |
| C | 5 | 19% | 13% | 0% to 33% | 24% |
| D | 5 | 21% | 10% | 7% to 33% | 24% |

### Arm comparisons (findings recall, permutation test)

| Comparison | Mean difference | p | Method | Note |
| --- | --- | --- | --- | --- |
| B vs A | +8% | 0.032 | exact |  |
| C vs A | +4% | 0.683 | exact |  |
| D vs A | +7% | 0.302 | exact |  |
| C vs B | -4% | 0.706 | exact |  |
| D vs B | -1% | 1.000 | exact |  |
| D vs C | +3% | 0.849 | exact |  |

Never noticed by any run: K27, K28, K36, K37
Only in questions, never in findings: K29
