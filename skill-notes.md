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
