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
