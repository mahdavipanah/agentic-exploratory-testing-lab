# batch-2 summary: the held-out target

**What ran.** 25 sessions on 2026-11-10 against [claimdesk](../../targets/claimdesk/), a team expense-claims API with 15 planted problems (13 behaviour, 2 docs defects).
- **Arms:** A, B, C, D (skill v0.3) and M, five runs each, in a shuffled order.
- **Isolation:** login isolation. No memory leaked between runs; see [README.md](README.md).
- **Agent:** `claude-opus-5-5`. Total cost $22.48.

**How it was scored.**
- **Sealed key.** The answer key was sealed until after scoring. Its SHA-256 was committed at 15:58 UTC, four minutes before the first session. The published key, [`scoring/claimdesk/answer-key.md`](../../scoring/claimdesk/answer-key.md), matches that hash, and its verifier still reproduces all 15 items.
- **Blind to the arm.** A scorer agent matched every finding and question against the key without knowing which arm wrote it. A second scorer independently re-scored 100 random items and agreed on 96. No new problems were confirmed beyond the 15.
- **Records:** the mapping is [`scoring/map-batch-2.txt`](../../scoring/map-batch-2.txt); the full statistics are in [`scores.md`](scores.md).

## Results

| Arm | What the agent got | Recall, findings (mean, range) | Findings per run | Precision |
| --- | --- | --- | --- | --- |
| A | "Find bugs in this API." | 68% (53–80%) | 10.2 | 51 of 51 |
| B | Four charters written from the docs | 71% (60–80%) | 10.6 | 53 of 53 |
| C | Write your own charters first | 63% (53–73%) | 9.4 | 47 of 47 |
| D | The exploratory-testing skill, v0.3 | 72% (67–87%) | 11.0 | 54 of 55 |
| M | Docs only, no API: predict the bugs | 71% (67–73%) | 43.8 | 56 of 219 |

*Recall:* distinct planted problems in the findings, out of 15. *Precision:* findings that match a planted problem. Questions added almost nothing here: "noticed" recall is within 2 points of findings recall for every arm.

**No difference between arms is significant** (exact permutation tests, 5 vs 5; the smallest p is 0.135, for M vs C). There's also no carry-over between sessions: Spearman rho = +0.03, p = 0.89.

## By problem

Runs, out of 5, whose findings include each planted problem:

| Item | Problem | Difficulty | Hidden behind state | A | B | C | D | M |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T01 | Amount 0 accepted | easy | | 3 | 5 | 1 | 2 | 5 |
| T02 | `next_page` past the end when the last page is full | easy | | 2 | 2 | 1 | 3 | 4 |
| T04 | `owner` filter lists claims you can't see | easy | | 2 | 1 | 2 | 1 | 5 |
| T12 | Unknown `sort` value gives 500 | easy | | 1 | 0 | 2 | 0 | 0 |
| T14 | Default `per_page` 10, docs say 20 | easy | | 5 | 5 | 5 | 5 | 0 |
| T03 | A rejected claim can't be resubmitted | medium | yes | 3 | 5 | 2 | 3 | 0 |
| T08 | Day 90 refused, docs say it's allowed | medium | | 5 | 5 | 5 | 5 | 5 |
| T09 | PATCH writes `status` and review fields | medium | | 4 | 4 | 4 | 5 | 5 |
| T11 | Paying twice pays twice | medium | yes | 5 | 5 | 5 | 5 | 5 |
| T15 | `q` doesn't search item descriptions | medium | | 5 | 4 | 4 | 4 | 5 |
| T05 | Any manager can review another team's claim | hard | yes | 5 | 5 | 5 | 5 | 5 |
| T06 | Amounts truncated to the cent below (19.99 → 19.98) | hard | | 1 | 1 | 1 | 2 | 0 |
| T07 | Meals limit checked per item, not per day | hard | yes | 5 | 5 | 5 | 5 | 5 |
| T10 | Removing an item: list total and payment keep the old sum | hard | yes | 0 | 5 | 2 | 4 | 4 |
| T13 | Deleting an item from someone else's claim | hard | yes | 5 | 1 | 3 | 5 | 5 |

## What the numbers say

1. **On this target, the mission made no measurable difference to overall recall.** All four exploring arms found about two-thirds of the planted problems, with about 10 findings each, and almost all were real: one false positive among 206 findings. With 15 items and 5 runs per arm, one item is worth 6.7 points, so differences under about 15 points can't be detected. A small, well-documented API with 12 endpoints and an 80-request budget let even "Find bugs in this API" cover most of the surface. This is unlike Restful-booker, where B and D clearly beat A.

2. **The docs pointed at the bugs, so prediction did well on recall.** The agent that built claimdesk planted almost every bug exactly where the docs make a precise promise: paying twice is safe, `owner` narrows among the claims you can see, `next_page` is null on the last page, day 90 is the earliest accepted date. Reading the docs and predicting "this promise is broken" found 71%. None of the five M runs recognised the app; their "prior knowledge" was general bug patterns.

   But M spread 44 guesses per run to get there: **only 56 of its 219 predictions were right (26%)**. To know which ones hold, someone has to test them, and that is exploring. Prediction is a good way to generate charters, but it can't be the report.

3. **What prediction missed:**
   - a rule that is too strict rather than too lenient (T03)
   - money that loses a cent on ordinary values (T06)
   - a 500 on an unknown parameter (T12)
   - a default that differs from the docs (T14), which every exploring run reported and no prediction did

   These show up only in what the system actually returns. Recall restricted to these four items is level across the exploring arms (50–55%).

4. **Where the mission did show:** on specific bugs that need following data across views. These per-item comparisons are post hoc, with many comparisons, so treat them as leads.
   - **T10** (the list and the payment keep a total the detail no longer shows) was found by B in 5 of 5 runs, by D in 4 of 5, and by A in 0 of 5 (Fisher exact p = 0.008 for A vs B, 0.048 for A vs D). B's FedEx charter ("one claim's data across every view") and the skill's "follow the data" rule both send the agent to compare views. A never did.
   - **T03** (resubmitting a rejected claim) was found in all 5 B runs. B's lifecycle charter lists "reject, resubmit", taken straight from the docs.
   - **Against that, T13** (deleting another user's item through your own claim's path) was found by B in only 1 of 5 runs, against 5 of 5 for A and D. Each charter steers attention somewhere and away from somewhere else.

5. **The skill was the most consistent on the hardest problems.** On the five hard items, D averaged 84% against 64–68% for A to C. On the six problems hidden behind state, D averaged 90%. It had the highest minimum of any exploring arm (67%) and the top run (87%). None of this is significant overall.

## Compared with batch-1

| | Restful-booker (batch-1) | claimdesk (batch-2) |
| --- | --- | --- |
| Known to the model | Yes: M named it in every run | No |
| Mission vs none (B, D vs A) | +10 and +13 points, significant | +3 and +4 points, not significant |
| Docs-only prediction (M) | 50%, mostly from memory | 71%, from the docs' promises |
| Prediction precision (M) | 65% | 26% |
| Exploring precision | 280 of 280 | 205 of 206 |

**What holds across both:**
- Exploring agents report almost nothing false.
- Prediction alone gets a fair share of recall, at the price of many wrong claims.
- Some bugs only exist in what the system actually returns.
- Charters and the skill help most on bugs that need following data or state across requests.

**What doesn't hold:** a simple claim that "a mission makes agents find more bugs". It depends on the target. On a sprawling, oddly-behaved API it helped a lot; on a small API whose docs state every rule, the default agent already covers the surface.

## Caveats

- **The model built the target.** The agent that built claimdesk is the same model family as the agents exploring it, and it placed bugs where a model expects them. A target with bugs planted by people, or real bugs from a project's history, would test exploring harder.
- **One person wrote both sides.** The experimenter wrote the target's spec (the bug classes) and skill v0.3 on the same day, and also wrote arm B's charters from the docs. Arm B's charters name "reject, resubmit" and "every view", which are the routes to T03 and T10. The experimenter never saw the key or the source before scoring.
- **15 items, 5 runs per arm.** The test can only detect large differences.
- **Not comparable across batches.** Skill versions differ (v0.1 in batch-1, v0.3 here), and the targets differ. Compare arms only within a batch.
