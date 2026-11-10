# batch-1 summary

**What ran.** 25 sessions on 2026-11-09: arms A, B, C, D and M, five runs each.
- **Order:** seeded and shuffled, four sessions at a time. One session's server is never reused by another.
- **Isolation:** login, with auto-memory off. No memory file changed in any session.
- **Agent:** Claude Code 2.1.319, model `claude-opus-5-5`. Total cost $22.88.

**Answer key.** 39 items after this batch (one added: K39). Scores are against all 39.

**How the work was checked.**
- Finding-to-key matching: [`scoring/map-batch-1.txt`](../../scoring/map-batch-1.txt), with a note on every judgement call. It is applied by `scripts/apply-map.py` to give [`scoring/scores-batch-1.csv`](../../scoring/scores-batch-1.csv).
- Full statistics: [`scores.md`](scores.md).
- Eleven reports had to be rebuilt from the transcripts because of a harness bug. See [README.md](README.md); the rebuild was checked byte for byte on the 14 sessions that saved normally.

## Results

| Arm | What the agent got | Recall, findings (mean, range) | Recall, noticed | False positives | Requests | Minutes | Cost |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | "Find bugs in this API." | 35% (33–38%) | 46% | 0 of 62 | 66 | 3.0 | $0.91 |
| B | Four charters written for it | 46% (44–49%) | 62% | 0 of 82 | 80 | 4.1 | $1.18 |
| C | Write your own charters first | 39% (18–49%) | 50% | 0 of 58 | 65 | 3.5 | $0.99 |
| D | The exploratory-testing skill | 48% (38–59%) | 56% | 0 of 78 | 76 | 4.1 | $1.26 |
| M | Docs only, no API: predict the bugs | 50% (46–54%) | 50% | 56 of 161 don't match the key | 0 | 0.8 | $0.23 |

**Column definitions.**
- *Recall, findings:* distinct key items in the Findings section, out of 39.
- *Recall, noticed:* also counts items the agent raised under Questions.
- *Requests:* curl calls that ran, mean per session.
- *Minutes* and *Cost:* per session.

**Arm comparisons** (findings recall; exact permutation test, 5 vs 5, smallest possible p = 0.008):

| Comparison | Difference | p |
| --- | --- | --- |
| B vs A | +10 points | 0.008 |
| D vs A | +13 points | 0.016 |
| C vs A | +4 points | 0.64 |
| D vs B | +3 points | 0.63 |
| C vs B | −7 points | 0.41 |
| M vs A | +15 points | 0.008 |
| M vs B | +5 points | 0.056 |
| M vs C | +11 points | 0.063 |
| M vs D | +2 points | 0.71 |

**Carry-over check.** Spearman rho between the order sessions ran in and each session's recall minus its arm's mean: +0.11, p = 0.61. There is no sign that later sessions did better.

## What the numbers say

1. **A mission helps.** Both kinds of given mission beat no mission: human-style charters (B) and the skill (D), with p = 0.008 and 0.016. Five of five A runs landed between 33% and 38%. A also never reported `bookingid` re-keying (K24), PUT merging (K30) or PATCH skipping validation (K21) as findings.

2. **Writing its own charters helps less reliably.** Four of five C runs scored 36–49%, close to B. C-run1 wrote five sensible charters, used 37 of its 80 requests, declared the date filters correct after a shallow check, and stopped at 18%. With that run, C is not distinguishable from A. One run in five stopping early is the reliability problem a skill has to fix.

3. **The skill matches human charters on recall, and finds different things.** D and B are level (48% vs 46%, p = 0.63). D's distinct finds:
   - The `bookingid` re-keying problem (K24), in 4 of 5 runs. No other arm reported it.
   - A null `bookingdates` corrupting a booking (K23), once.
   - The new timezone-offset problem (K39), once.

   These trace to skill rules: "include fields the docs don't list, such as ids and other server-owned fields", "repeat each probe on every path", and the timezone item in the familiar-problems oracle. D also reported the 201 status codes as findings (3 of 5 runs). A–C left them under Questions because the docs show 201, and the skill says behaviour that matches wrong docs is still a finding. **But** those skill rules were written after the pilot, by someone who had seen this app's answer key. D is not a test of how the skill generalises. That needs a different target.

4. **On this app, memory alone scores as high as exploring.** Arm M never touched the API. All five M runs named Restful-Booker, and 84 of M's 94 matched predictions cite prior knowledge. Its recall (50%) is significantly higher than A's (p = 0.008), and level with B, C and D.

   Memory has two costs. 56 of 161 predictions (35%) don't match a key item. Some are real behaviours the key doesn't include (403 instead of 401). Others are wrong: for example, that XML input comes back with every value as a string.

   For about two-thirds of the key, recall here cannot tell exploring from remembering. The two exploring agents that mentioned Restful-Booker in their visible output (A-run3, D-run1) show recognition happens during exploring too. The agents' private reasoning is not in the transcripts.

5. **What only exploring found.** Ten key items appeared in exploring runs and in no M run:
   - the error text returned for the URL-encoded Accept (K31)
   - XML labelled as HTML (K32)
   - date rollover (K33)
   - non-string names crashing create (K04)
   - writes reporting failure but applying (K20)
   - null dates corrupting a booking (K23)
   - PUT merging (K30)
   - corrupt dates matching every filter (K34)
   - the timezone shift (K39)
   - ids parsed leniently, so `/booking/1abc` is booking 1 (K26)

   They depend on what the system actually returns, or on state built up across requests. You see them by running the system, not by reading about it.

   Restricted to the 15 items no M run predicted, recall was A 15%, B 23%, C 19%, D 21%. B vs A gives p = 0.03; the other differences are not significant. This restriction was chosen after seeing the data, so treat it as a lead, not a result.

6. **Exploring was precise.** None of the 280 findings from A–D was a false positive. Every one came with the command and the output (the evidence rule). Things the agents weren't sure about went under Questions.

7. **Never found in this batch:**
   - the case-sensitive Basic auth scheme (K27)
   - three documentation defects (K28, K36, K37). The pilot's C run raised K36 and K37 as questions.

   The PATCH examples using `curl -X PUT` (K29) appeared only as a question.

## Checking the scoring

A second scorer (a separate Claude agent) re-scored 101 rows blind: it had the answer key and the rules, but never saw this mapping.
- **The sample:** every row with a judgement-call note, plus 45 chosen at random.
- **Agreement:** 91 of 101 rows (90%). Eight of the ten disagreements were arm-M predictions; it read "the title must commit to an outcome" more strictly than I first had.
- **Adopted (7 rows):**
  - five M predictions changed to FP
  - two questions given key items I had missed: D-run4 Q1 (K29) and C-run1 Q1 (K07)
- **Kept (3 rows):**
  - two catch-all M hedges stay FP
  - M-run5 F5 stays K09, to match how the same title was scored in the other four M runs

The second scorer's answers are in [`scoring/blind-check-batch-1.txt`](../../scoring/blind-check-batch-1.txt), and the changed rows are marked "(blind check)" in the map. The numbers above are after the check; before it, M was 51%, and its leads over B and C were significant.

## Compared with the pilot

The pilot had one run per arm, with agents told (not forced) to ignore memory. It gave A 23%, B 46%, C 51% (rescored against 39 items), which suggested C ≥ B. With five isolated runs each, B is steady at 44–49%, while C ranges from 18% to 49%. The one-run pilot made C look better than it is, which is the reason for repeating runs.

## Lessons for the skill (to apply in v0.2)

- **Use the budget.** If the charters finish with budget left, add a charter for the area with the thinnest coverage, rather than stopping (C-run1).
- **A filter that "works for valid input" is not done.** Test the boundary value itself and the opposite direction before calling a filter correct (C-run1 missed K15 and K16).
- **Keep what worked** (the rules behind D's distinct finds): server-owned fields on every write path, read-back after every write, and wrong docs still count.

## Caveats

- One app, one model, five runs per arm.
- Restful-Booker is in the model's training data, and arm M shows the model can name half the key without running anything.
- The experimenter wrote arm B's charters and the skill, and also matched the findings to the key. Every match and judgement call is in `scoring/map-batch-1.txt` for review.
- Recall is against a known ceiling (every problem anyone confirmed), not against all the bugs in the app.
- **Leak found after the batch.** The skill's report template used an example title ("PATCH with one date wipes the other") that describes K22. Every arm found K22 in all 20 runs, so it doesn't change any comparison. It was removed in skill v0.3.

## Reproduce

```sh
scripts/run-experiment.sh batch-2 5 "A B C D M"          # on a machine with Claude Code logged in
python3 -I scripts/extract-findings.py results/batch-2 > /tmp/sheet.csv
# write scoring/map-batch-2.txt, then:
python3 -I scripts/apply-map.py /tmp/sheet.csv scoring/map-batch-2.txt > scoring/scores-batch-2.csv
python3 -I scripts/score.py scoring/scores-batch-2.csv 39 --schedule results/batch-2/schedule.txt
```
