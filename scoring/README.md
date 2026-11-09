# Scoring

Restful-booker has no public answer key, so the key is built the way Maaret Pyhäjärvi built her "known ceiling": everything we can confirm, from every source.

## Building the answer key (after the runs, not before)

1. **Source review.** Read the server code and the docs; list every behaviour that contradicts the docs or that a reasonable client would call wrong. Tag these `source`.
2. **Run finds.** Add every confirmed finding from any run that is not already listed. Tag these `run`.
3. Each key item gets a one-line reproduction and a type:
   - `behaviour`: the API does something wrong (accepts invalid data, crashes, bypasses auth, loses data).
   - `contract`: behaviour and docs disagree, and either could be the one to fix (wrong status code, field missing from docs).

The **ceiling** is the number of key items. It grows as runs find new, confirmed problems. `scripts/verify-answer-key.py` replays every item against a fresh target, so the key can be checked at any time.

## Scoring a run

Go through the run's report finding by finding and give each a verdict:

| Verdict | Meaning |
| --- | --- |
| TP | Matches a key item (first time in this report) |
| DUP | Matches a key item this report already claimed |
| FP | Not a bug: works as documented, a misread, or the agent's own mistake |

Findings marked `Kind: needs a decision` (arm D's report format) are scored like any other finding. Because that format moves confirmed-but-unsure items out of Questions, compare arms on "noticed" recall as well.

A finding claims one key item: the one its title describes. It claims a second only if its title names that problem too.

Per run, record:

- **Recall (findings)** = distinct key items claimed in Findings / ceiling
- **Recall (noticed)** = the same, also counting confirmed behaviours the agent put under Questions
- **Precision** = TP / (TP + FP)
- **Requests used** and **minutes**, from the report and `meta.txt`

Start the sheet with `python3 -I scripts/extract-findings.py results/<batch> > scoring/scores-<batch>.csv`, which writes one row per finding or question. Columns: `run, section (finding|question), item, title, key_ids (;-separated), verdict, note`. Then compute the table with `python3 -I scripts/score.py scoring/scores-<batch>.csv <ceiling>` and write the batch's `summary.md`.

## Caveats to report with any result

- One app, one model, few runs: an illustration, not a study.
- Restful-booker is popular. The model may remember its bugs from training, so recall can be inflated. The docs given to agents are retitled "Booking API" to avoid naming it.
- The experimenter wrote arm B's charters (standing in for a human) and also judges the findings.

## Which runs count

Statistics rest on **isolated runs only**: `isolation=fresh` (the default) or `isolation=bare` in `meta.txt`. `extract-findings.py` skips everything else unless you pass `--all`. That excludes the pilot, which ran as agents isolated by instruction, and safe-mode runs, which used your normal Claude Code home.

## Statistics

- **Per arm:** mean, standard deviation and range of recall across runs.
- **Between arms:** a two-sided permutation test on the difference in mean findings recall. It is exact while every split of the pooled runs can be listed, and otherwise uses 20,000 random shuffles. With n runs per arm the smallest possible p is 2 / C(2n, n): 0.1 for 3 runs, 0.008 for 5. The output flags comparisons that can't reach 0.05.
- **Carry-over check** (needs `--schedule`): the Spearman correlation between the order sessions ran in and each session's recall minus its arm's mean, with a permutation p-value. A positive, significant correlation would mean later sessions did better, which is a sign of leakage between runs. Tested on made-up data: rho = +0.02 (p = 0.93) without leakage, and rho = +0.77 (p < 0.001) with leakage added.

## Arm M (memory check)

Arm M's findings are predictions, made without access to the API. Score each prediction like a finding: TP if it names a specific answer-key problem (the endpoint and the wrong behaviour), FP otherwise. Report recall only.

- **What M's recall means:** how much of the answer key the model can name from memory and the docs alone. Compare it with the exploring arms' recall.
- **The "Why" field:** each prediction says whether it came from the docs or from prior knowledge. Predictions marked "prior knowledge" that name Restful-booker bugs are direct evidence of training-data recall.

