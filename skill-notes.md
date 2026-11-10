# Notes for the exploratory-testing skill

Everything we learn from the experiment that should end up in the skill. Each note says where it came from.

## Design decisions so far

- **Black box first.** The explorer gets the running system and its docs, nothing else. Source access is a separate, later experiment (arm D).
- **Charter template.** Hendrickson's *Explore (target) with (resources) to discover (information)*. Same template for human-written (B) and agent-written (C) missions, so only the author changes.
- **Tours as a menu.** Six Whittaker tours, one line each (`arms/tours.md`). Both B and C get the same menu.
- **Evidence rule.** No finding without a real response seen and reproduced; suspicions go under Questions. Kept the same in every arm so it doesn't explain differences between arms.
- **Budget in requests, not minutes.** 80 HTTP requests per session. Requests are what an agent can count.
- **Restart the target before every session.** Earlier sessions' data would otherwise leak into later ones.

## Lessons from building the harness

- **A check can pass for the wrong reason.** The first `start-target.sh` "restarted" the server and then pinged it. The ping passed, but the old server answered: the new one had failed to bind the port, and old data leaked into the next session. Only a stateful probe caught it: create a booking, restart, and check that the new id is the seed's next id again. Skill rule: **before exploring, verify the environment is in the state you think, with a probe whose answer would differ if it weren't.**
- **The environment is part of the test.** The target formats dates in the server's local time. In New York every date comes back a day early; in UTC the bug is invisible. Skill rule: **record the environment (timezone, versions, config) with every session, and when a result looks environment-shaped, vary the environment.**
- **Docs are an oracle and a target.** The published docs contradict themselves (a "Success 200" table above a `201 Created` example; PATCH examples that use PUT). The skill should treat doc-vs-behaviour gaps as findings to report, and say which side looks wrong.

## Lessons from runs

From the pilot (`results/pilot-2026-11-09/summary.md`):

1. **Plan around risks, not coverage.** The no-mission agent wrote a coverage plan and stopped when the list was done (62 of 80 requests, 9 key items). Risk-based charters kept the agents digging (18 to 20). The skill should start with "list the risks", never "list the endpoints".
2. **The agent can write the charters.** Agent-written charters did as well as the experimenter's. The skill can let the agent draft charters, and the human edit them.
3. **Repeat each probe on every write path.** Extra fields were "ignored" on POST, so two agents called them harmless, and both missed that PATCH and PUT accept a `bookingid` that re-keys the record. Rule: a probe that passes on one endpoint proves nothing about the others.
4. **Check both sides of a boundary.** One probe at one edge made a filter look correct when it was inverted.
5. **Use more than one oracle.** The docs are one; HTTP conventions (201 means created, 4xx for client errors), consistency between endpoints, and what a client would expect are others. Behaviour that matches wrong docs is still a finding.
6. **Report "confirmed, needs a decision" as findings, not questions.** The evidence rule gave zero false positives, but agents parked confirmed behaviours under Questions when unsure whether they were bugs. The skill should have three buckets: bugs, confirmed behaviour that needs a human decision, and unconfirmed suspicions.
7. **After a destructive input, read the record back.** The worst missed bug (`bookingdates: null` breaks the booking for good) only shows on a later GET. Every write probe should be followed by a read.

## Skill v0 (9 Nov 2026)

The lessons above are now [`skills/exploratory-testing`](skills/exploratory-testing/), in the open Agent Skills format, and run as arm D.

- **Where each lesson went:** the environment check is under "Before you start". Risks before endpoints, charters and budgets are workflow steps 2 and 3. Repeating probes on every path, both sides of a boundary, reading back after a write and several oracles are the rules in step 4. The three report buckets are step 6.
- **Kept generic on purpose.** The oracle and tour examples were rewritten so they don't mirror Restful-booker's bugs. The first draft quoted several (`false` stored as true, a price losing its cents) and would have leaked the answer key into arm D.
- **Known bias:** the rules themselves come from this target's misses, so arm D on Restful-booker measures whether the lessons were applied, not generalization. Next: a held-out target the skill has never seen, such as a small API with bugs planted by someone else.
- **Report format:** findings carry `Kind: bug | needs a decision`, and Questions holds only unconfirmed suspicions. Expect D's recall from findings to rise for that reason alone; compare arms on "noticed" recall too.


## Lessons from batch-1 (9 Nov 2026)

From `results/batch-1/summary.md` (5 isolated runs per arm):

1. **Use the whole budget.** One self-chartered run (C-run1) wrote five good charters, used 37 of 80 requests and stopped at 18% recall. The other four C runs scored 36–49%. Rule for v0.2: when the charters finish with budget left, add a charter for the area with the thinnest coverage, rather than stopping.
2. **"Works for valid input" is not done.** C-run1 called the date filters correct after one valid query each, and missed both filter bugs. The boundary rule needs to be stronger: test the boundary value itself and the opposite direction before calling anything correct.
3. **The rules that only D followed found what only D found.**
   - "Include server-owned fields such as ids, on every write path" found `bookingid` re-keying in 4 of 5 D runs, and in no other arm.
   - "Behaviour that matches wrong docs is still a finding" moved the 201 status codes from Questions into Findings.
   - The timezone item in the familiar-problems oracle found a new key item (K39).

   Keep all three.
4. **Memory is a weak oracle; evidence is the strong one.** With docs and no API, the model named Restful-booker in every run and predicted half the key. But 35% of its predictions matched nothing in the key, and some were plainly wrong. The exploring arms had 0 false positives in 280 findings, because every finding needed a command and its output. Rule to keep: if you recognise the system, use that to choose what to probe, never as evidence.
5. **What only exploring finds is what the skill is for.** These come from watching responses and state, not from reading:
   - an error message returned with 200
   - XML labelled as HTML
   - dates that roll over
   - records broken by an earlier write
   - a timezone shift

   The skill should push agents toward reading back every write in every representation, and inspecting headers as well as bodies.

## Lessons from building the harness (batch-1)

- **A check that passed by luck, again.** The smoke test passed because its agent happened to retry a refused write with a different spelling of the same path. In the batch, 11 of 25 agents didn't retry. The fixed smoke test checks the outcome that matters: the agent saved the report itself.
- **Same thing, two names.** On macOS, `/var/...` and `/private/var/...` are the same folder, but the permission check sees only one of them. For an explorer: when something is refused or missing, check whether you used the name the system resolves to, not just a name that points there.

## Skill v0.2 (10 Nov 2026)

Batch-1's lessons, added to `SKILL.md`. Examples are kept generic, so nothing mirrors Restful-booker's answer key.

- **"When to stop"**, a new subsection. Use the budget: if charters finish early, add one for the least certain risk or the thinnest area. Stop only when the budget is spent or every top risk has an evidenced answer. Running out of ideas means switching tours, not stopping. (From C-run1.)
- **"Nothing is correct after valid input alone"** replaces the boundary bullet. Test the boundary value itself, both sides of it, the opposite direction and an invalid value before calling anything correct. (From C-run1's filters.)
- **"Look at the whole response"**, a new bullet: status, headers and body. (Several of the bugs only exploring found were an error text with 200 and a mislabelled format.)
- **Memory guides, evidence decides**, added to the Evidence section: if you recognise the system, use that to choose probes, never as evidence. (From arm M: 35% of its predictions matched nothing.)
- **Your own mistakes** now name typos, stale tokens and different spellings of the same path. (From the harness's `/var` vs `/private/var` bug.)

Unchanged: the rules behind D's distinct finds (server-owned fields on every write path, read-back, wrong docs still count).

## Skill v0.3 (10 Nov 2026): from *Explore It!*

Elisabeth Hendrickson's *Explore It!* (2013) has a full chapter for each of several things v0.2 only hinted at. v0.3 adds them, in its own words. A new [`references/heuristics.md`](skills/exploratory-testing/references/heuristics.md) holds the details.

- **Model before risks.** A short recon pass (about a tenth of the budget), then three models: entities and relationships, a state table (states × events), and variables. From her chapters on recon sessions, entities, states and variables.
- **Never and Always rules** as a source of risks and an oracle: what must hold whatever anyone does. Plus the "worst headline" exercise for finding them (her Nightmare Headline Game).
- **Follow the data**, **walk the state table** (the cells the docs don't cover are where surprises live), and act as every role that touches the same data.
- **Vary on purpose, not by habit:** zero/one/many, some/none/all, beginning/middle/end, Goldilocks, other formats, plus nouns-and-verbs pairing and personas to break routine. Agents have strong habits, the same "John Doe" data and the same create-read-update-delete order every time, so this matters more for them than for people.
- **Ask the deeper question:** not "did it succeed?" but "can I use what it produced?"
- **When the exact answer is unknowable:** invert it, check a range or property, push inputs to extremes. Added to `oracles.md`.
- **Stopping and reporting:** stop when you're no longer learning, or more probing wouldn't change the report. Out of budget means saying what remains unknown. Report what you saw working, and give facts, not verdicts.
- **If you wrote the code:** watch the server's logs while you explore ("testability is visibility and control").

**A leak, found and fixed.** The report template's example title in v0 to v0.2 ("PATCH with one date wipes the other") was Restful-booker's K22. It reached arm D in batch-1. It made no difference to the comparison, because every arm found K22 in all 20 runs, A included. v0.3 uses an example from an unrelated domain.

**Known bias for batch-2.** The experimenter wrote both the held-out target's specification and v0.3, on the same day. The spec asks for common bug classes: state machine, authorization, arithmetic, dates, partial update, consistency, idempotency, error handling. The skill's heuristics are generic and come from a 2013 book, but they cover those same classes. The experimenter has not seen the planted bugs or the target's source.

## Lessons from batch-2 (10 Nov 2026): the held-out target

From `results/batch-2/summary.md`. claimdesk has 15 planted bugs; all arms scored 63–72%, with no significant difference.

1. **The skill's edge is on bugs that need following data or state, not on overall recall.** D averaged 84% on the five hard items and 90% on the six hidden behind state, against 64–68% and 73–87% for the other exploring arms. The clearest single case: the list and payment kept a stale total after an item was removed. D found it in 4 of 5 runs and B in 5 of 5 (its charter said "every view"); A found it in 0 of 5. "Follow the data" earns its place.
2. **Predicting from the docs is a charter generator, not a report.** Docs-only prediction (M) matched the exploring arms on recall, but 3 in 4 of its 44 guesses per run were wrong. A skill step that lists the docs' promises and predicts how each could break would be a cheap way to aim charters. Every prediction still needs a probe before it is reported.
3. **Prediction misses what only the system shows.** Every exploring run, and no prediction, reported a default that differs from the docs. Prediction also missed a rule that is too strict rather than too lenient, cents lost on ordinary amounts, and a 500 for an unknown parameter. The skill should keep pushing agents to compare actual responses, defaults included, against the docs. It should also test that allowed things are allowed, not only that forbidden things are refused.
4. **Each charter hides something.** B's charters made it find some bugs every time and another (deleting another user's item through your own claim's path) only once in 5, where A and D found it every time. A skill that lets the agent choose charters from risks may cover more than any fixed set.
