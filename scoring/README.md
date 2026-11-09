# Scoring

Restful-booker has no public answer key, so the key is built the way Maaret Pyhäjärvi built her "known ceiling": everything we can confirm, from every source.

## Building the answer key (after the runs, not before)

1. **Source review.** Read the server code and the docs; list every behaviour that contradicts the docs or that a reasonable client would call wrong. Tag these `source`.
2. **Run finds.** Add every confirmed finding from any run that is not already listed. Tag these `run`.
3. Each key item gets a one-line reproduction and a type:
   - `behaviour`: the API does something wrong (accepts invalid data, crashes, bypasses auth, loses data).
   - `contract`: behaviour and docs disagree, and either could be the one to fix (wrong status code, field missing from docs).

The **ceiling** is the number of key items. It grows as runs find new, confirmed problems.

## Scoring a run

Go through the run's report finding by finding and give each a verdict:

| Verdict | Meaning |
| --- | --- |
| TP | Matches a key item (first time in this report) |
| DUP | Matches a key item this report already claimed |
| FP | Not a bug: works as documented, a misread, or the agent's own mistake |

Per run, record:

- **Recall** = distinct key items found / ceiling
- **Precision** = TP / (TP + FP)
- **Requests used** and **minutes**, from the report and `meta.txt`

Write verdicts to `scores.csv` (one row per finding) and the per-run summary to `summary.md`.

## Caveats to report with any result

- One app, one model, few runs: an illustration, not a study.
- Restful-booker is popular. The model may remember its bugs from training, so recall can be inflated. The docs given to agents are retitled "Booking API" to avoid naming it.
- The experimenter wrote arm B's charters (standing in for a human) and also judges the findings.
