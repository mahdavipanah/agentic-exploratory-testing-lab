# Notes for the exploratory-testing skill

Everything we learn from the experiment that should end up in the skill. Each note says where it came from.

## Design decisions so far

- **Black box first.** The explorer gets the running system and its docs, nothing else. Source access is a separate, later experiment (arm D).
- **Charter template.** Hendrickson's *Explore (target) with (resources) to discover (information)*. Same template for human-written (B) and agent-written (C) missions, so only the author changes.
- **Tours as a menu.** Six Whittaker tours, one line each (`arms/tours.md`). Both B and C get the same menu.
- **Evidence rule.** No finding without a real response seen and reproduced; suspicions go under Questions. Kept the same in every arm so it doesn't explain differences between arms.
- **Budget in requests, not minutes.** 80 HTTP requests per session. Requests are what an agent can count.
- **Restart the target before every session.** Earlier sessions' data would otherwise leak into later ones.

## Lessons from runs

(filled in after each batch of runs)
