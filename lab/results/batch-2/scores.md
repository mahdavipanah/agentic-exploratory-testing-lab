# batch-2 scores (generated)

Output of `python3 -I scripts/score.py scoring/scores-batch-2.csv 15 --prefix T --schedule results/batch-2/schedule.txt`.

| Run | Findings | FP | Key items in findings | Recall (findings) | Key items noticed (findings + questions) | Recall (noticed) |
| --- | --- | --- | --- | --- | --- | --- |
| A-run1-claude | 8 | 0 | 8 | 53% | 8 | 53% |
| A-run2-claude | 10 | 0 | 10 | 67% | 10 | 67% |
| A-run3-claude | 12 | 0 | 12 | 80% | 12 | 80% |
| A-run4-claude | 10 | 0 | 10 | 67% | 10 | 67% |
| A-run5-claude | 11 | 0 | 11 | 73% | 11 | 73% |
| B-run1-claude | 12 | 0 | 12 | 80% | 12 | 80% |
| B-run2-claude | 11 | 0 | 11 | 73% | 11 | 73% |
| B-run3-claude | 9 | 0 | 9 | 60% | 9 | 60% |
| B-run4-claude | 10 | 0 | 10 | 67% | 10 | 67% |
| B-run5-claude | 11 | 0 | 11 | 73% | 11 | 73% |
| C-run1-claude | 8 | 0 | 8 | 53% | 9 | 60% |
| C-run2-claude | 9 | 0 | 9 | 60% | 9 | 60% |
| C-run3-claude | 10 | 0 | 10 | 67% | 10 | 67% |
| C-run4-claude | 9 | 0 | 9 | 60% | 10 | 67% |
| C-run5-claude | 11 | 0 | 11 | 73% | 11 | 73% |
| D-run1-claude | 11 | 0 | 11 | 73% | 11 | 73% |
| D-run2-claude | 10 | 0 | 10 | 67% | 11 | 73% |
| D-run3-claude | 11 | 1 | 10 | 67% | 10 | 67% |
| D-run4-claude | 10 | 0 | 10 | 67% | 10 | 67% |
| D-run5-claude | 13 | 0 | 13 | 87% | 13 | 87% |
| M-run1-claude | 39 | 28 | 10 | 67% | 10 | 67% |
| M-run2-claude | 40 | 30 | 10 | 67% | 10 | 67% |
| M-run3-claude | 50 | 38 | 11 | 73% | 11 | 73% |
| M-run4-claude | 46 | 34 | 11 | 73% | 11 | 73% |
| M-run5-claude | 44 | 33 | 11 | 73% | 11 | 73% |
| union of all runs | | | 15 | 100% | 15 | 100% |

## Per arm

| Arm | Runs | Mean recall (findings) | SD | Range | Mean recall (noticed) |
| --- | --- | --- | --- | --- | --- |
| A | 5 | 68% | 10% | 53% to 80% | 68% |
| B | 5 | 71% | 8% | 60% to 80% | 71% |
| C | 5 | 63% | 8% | 53% to 73% | 65% |
| D | 5 | 72% | 9% | 67% to 87% | 73% |
| M | 5 | 71% | 4% | 67% to 73% | 71% |

## Arm comparisons (findings recall, permutation test)

| Comparison | Mean difference | p | Method | Note |
| --- | --- | --- | --- | --- |
| B vs A | +3% | 0.810 | exact |  |
| C vs A | -5% | 0.484 | exact |  |
| D vs A | +4% | 0.683 | exact |  |
| M vs A | +3% | 0.802 | exact |  |
| C vs B | -8% | 0.222 | exact |  |
| D vs B | +1% | 1.000 | exact |  |
| M vs B | +0% | 1.000 | exact |  |
| D vs C | +9% | 0.175 | exact |  |
| M vs C | +8% | 0.135 | exact |  |
| M vs D | -1% | 1.000 | exact |  |

## Carry-over check

Each session's recall minus its arm's mean, against the order sessions ran in.

| Order | Run | Recall minus arm mean |
| --- | --- | --- |
| 1 | C-run1-claude | -9% |
| 2 | B-run3-claude | -11% |
| 3 | A-run3-claude | +12% |
| 4 | A-run5-claude | +5% |
| 5 | M-run2-claude | -4% |
| 6 | B-run2-claude | +3% |
| 7 | A-run4-claude | -1% |
| 8 | A-run1-claude | -15% |
| 9 | B-run1-claude | +9% |
| 10 | M-run4-claude | +3% |
| 11 | D-run1-claude | +1% |
| 12 | D-run3-claude | -5% |
| 13 | C-run2-claude | -3% |
| 14 | D-run5-claude | +15% |
| 15 | C-run4-claude | -3% |
| 16 | M-run3-claude | +3% |
| 17 | C-run5-claude | +11% |
| 18 | B-run5-claude | +3% |
| 19 | D-run4-claude | -5% |
| 20 | C-run3-claude | +4% |
| 21 | D-run2-claude | -5% |
| 22 | A-run2-claude | -1% |
| 23 | B-run4-claude | -4% |
| 24 | M-run5-claude | +3% |
| 25 | M-run1-claude | -4% |

Spearman rho = +0.03, permutation p = 0.889: no sign that later sessions did better.

Never noticed by any run: none
Only in questions, never in findings: none
