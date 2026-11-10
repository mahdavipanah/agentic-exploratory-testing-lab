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

Start with `python3 -I scripts/extract-findings.py results/<batch> > /tmp/sheet.csv`, which writes one row per finding or question. Columns: `run, section (finding|question), item, title, key_ids (;-separated), verdict, note`.

Record the matching in `scoring/map-<batch>.txt`, one line per row: `<run> <item> <key ids | - | FP> [| note]`. Write a note for every judgement call. `python3 -I scripts/apply-map.py /tmp/sheet.csv scoring/map-<batch>.txt > scoring/scores-<batch>.csv` fills the sheet. It computes TP and DUP in report order and refuses to run if any row is unmapped.

Then compute the table with `python3 -I scripts/score.py scoring/scores-<batch>.csv <ceiling> --schedule results/<batch>/schedule.txt` and write the batch's `summary.md`.

**Compound findings.** Agents often lump problems together, as in "Invalid dates are accepted and silently changed". Match on the title, not the body: a body may show more than the title claims. A title that names two problems ("negative price and checkout before checkin") claims both.

## Caveats to report with any result

- One app, one model, few runs: an illustration, not a study.
- Restful-booker is popular. The model may remember its bugs from training, so recall can be inflated. The docs given to agents are retitled "Booking API" to avoid naming it.
- The experimenter wrote arm B's charters (standing in for a human) and also judges the findings.

## Which runs count

Statistics rest on **isolated runs only**: `isolation=login`, `fresh` or `bare` in `meta.txt`. `extract-findings.py` skips everything else unless you pass `--all`. That excludes the pilot, which ran as agents isolated by instruction.

Check the memory audit before trusting a batch. `login_home_memory_changes` and `fresh_home_memory_files` should be 0 in every session's `meta.txt`, and `run-experiment.sh` prints a count. A login-mode session with changes may only mean you used Claude Code yourself during the batch. Look at its `login-home-memory-changes.txt`, and rerun it if in doubt.

## Statistics

- **Per arm:** mean, standard deviation and range of recall across runs.
- **Between arms:** a two-sided permutation test on the difference in mean findings recall. It is exact while every split of the pooled runs can be listed, and otherwise uses 20,000 random shuffles. With n runs per arm the smallest possible p is 2 / C(2n, n): 0.1 for 3 runs, 0.008 for 5. The output flags comparisons that can't reach 0.05.
- **Carry-over check** (needs `--schedule`): the Spearman correlation between the order sessions ran in and each session's recall minus its arm's mean, with a permutation p-value. A positive, significant correlation would mean later sessions did better, which is a sign of leakage between runs. Tested on made-up data: rho = +0.02 (p = 0.93) without leakage, and rho = +0.77 (p < 0.001) with leakage added.

## Arm M (memory check)

Arm M's findings are predictions, made without access to the API. Score each prediction like a finding: TP if it names a specific answer-key problem (the endpoint and the wrong behaviour), FP otherwise. Report recall only.

- **Hedged predictions.** A hedge counts if the title commits to the key's behaviour among a few named outcomes ("returns 500 or ignores the filter"). "Is not rejected", with no committed outcome, is FP.
- **Real but outside the key.** A prediction of real behaviour the key doesn't include (403 instead of 401) is FP here too, because M is scored for recall only.

- **What M's recall means:** how much of the answer key the model can name from memory and the docs alone. Compare it with the exploring arms' recall.
- **The "Why" field:** each prediction says whether it came from the docs or from prior knowledge. Predictions marked "prior knowledge" that name Restful-booker bugs are direct evidence of training-data recall.

## Blind scoring (batch-2 onwards)

For the held-out target, the experimenter never saw the answer key before the runs, and the scoring was done blind to the arm:

1. `scripts/blind-sheet.py results/<batch> <seed> <sheet.md> <codes.txt>` renames each run to a random code (R01, R02, ...) and keeps only its Findings and Questions. Charters, risks and coverage name the arm's instructions, so they are left out. The code table stays with the experimenter.
2. A scorer agent gets the sheet, the sealed key, these rules and the API docs, and nothing that names an arm. It writes one line per item (`R07 F3 T04 | note`). It confirms new problems on a fresh server and gives them ids from T16 upwards.
3. A second scorer agent independently scores a random sample of 100 items, for an agreement rate.
4. The experimenter translates codes to runs, writes `scoring/map-<batch>.txt` and applies it as usual. The scorers' raw files are kept beside it.

Claimdesk's ids use the letter T, so run `score.py` with `--prefix T`.