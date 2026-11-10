# Exploratory testing skill

An [Agent Skill](https://agentskills.io) that makes a coding agent explore software the way a good tester does: it learns the system, writes risk-based missions, follows them, and backs every claim with the request and the response that prove it. It works with Claude Code, Codex, Cursor, Gemini CLI and other agents that read `SKILL.md`.

Agents usually write the code and its tests from one picture of how a feature should work, so the tests mostly check that picture. Exploring the running software is how the agent questions it. The essay *Teaching Agents to Explore* (link coming soon) tells the story, and [`lab/`](lab/) holds the experiments behind it.

## Install

**Claude Code** (v2.1.275 or later), in a session:

```
/plugin install exploratory-testing --marketplace mahdavipanah/exploratory-testing-skill
```

Or from your shell:

```bash
claude plugin marketplace add mahdavipanah/exploratory-testing-skill
claude plugin install exploratory-testing@exploratory-testing-skill
```

**Any agent**, with the [skills CLI](https://skills.sh):

```bash
npx skills add mahdavipanah/exploratory-testing-skill
```

When it asks which agents to install for, pick yours. To use the skills CLI for Claude Code instead of the plugin, name it, or the skill may only land in `~/.agents/skills/`, which Claude Code doesn't read:

```bash
npx skills add mahdavipanah/exploratory-testing-skill -g -a claude-code
```

**By hand:** copy [`skills/exploratory-testing/`](skills/exploratory-testing/) into your agent's skills folder. For Claude Code that is `~/.claude/skills/`, or `.claude/skills/` in a project.

## Use it

Ask your agent to explore something that is running, ideally right after it built it:

> Explore the orders API you just built. It runs on localhost:3000 and the docs are in docs/api.md.

> Do an exploratory testing session on the signup flow at http://localhost:5173. Focus on what happens to existing accounts.

The skill also starts on words like "explore", "bug-hunt" or "sanity-check". In Claude Code you can call it directly with `/exploratory-testing:exploratory-testing` when it is installed as a plugin, or `/exploratory-testing` when you copied the folder.

The agent then:

1. Checks the environment first, with a probe that would fail if things weren't as they seem.
2. Models the system before listing risks: its entities, a table of its states and events, and everything it can vary.
3. Writes down the rules that must never break (money is never created or lost, one user never sees another's data), then ranks the risks.
4. Writes three to five charters, each with a tour and a budget, and uses the whole budget.
5. Follows the data after every change, tries every event in every state, repeats each probe on every path that does the same job, tests both sides of every boundary, and reads the whole response.
6. Backs every claim with the command and its output, and reports bugs, behaviour that needs a decision, and open questions separately, with what it saw working and what is still unknown.

The details are in [`SKILL.md`](skills/exploratory-testing/SKILL.md) and its [`references/`](skills/exploratory-testing/references/): heuristics, oracles, tours and the report template.

**Explore test environments with disposable data, never production with real credentials.** An exploring agent creates, changes and deletes data on purpose, and it reads whatever the system sends back, which could include instructions aimed at it.

## Does it work?

Claude Opus 5.5 explored two small APIs with five kinds of instructions, five isolated runs each. Restful-booker is a famous practice API. claimdesk is an API no model had seen, with 15 bugs planted by a separate agent and an answer key sealed until the scoring was done.

| Agent | Restful-booker: known problems found | claimdesk: planted bugs found | Wrong findings, both APIs |
| --- | --- | --- | --- |
| A, "Find bugs in this API." | 35% | 68% | 0 of 113 |
| B, charters written for it | 46% | 71% | 0 of 135 |
| C, its own charters | 39% | 63% | 0 of 105 |
| D, this skill | 48% | 72% | 1 of 133 |
| M, docs only, predicting | 50% | 71% | 219 of 380 |

- On Restful-booker, the skill and the human-written charters found clearly more than no mission (p = 0.016 and 0.008). On claimdesk, a small API whose docs state every rule, the exploring agents were level.
- The skill did best where bugs hide in state and in data you have to follow. A total that went stale in a list after an item was removed was found by 4 of 5 skill runs and 0 of 5 runs with no mission.
- Several bugs were found only by exploring: no prediction from memory or from the docs named them.

It is still young: two small APIs, one model. The full results, the harness and the answer keys are in [`lab/`](lab/), so you can rerun everything.

## Repository layout

```
skills/exploratory-testing/   the skill: SKILL.md and its references
.claude-plugin/               makes this repository a Claude Code plugin and marketplace
lab/                          the experiments: prompts, harness, targets, answer keys, results
CHANGELOG.md                  what changed in each version of the skill
```

## Credits and license

The method draws on Elisabeth Hendrickson's *Explore It!* (charters, models, heuristics), James Whittaker's *Exploratory Software Testing* (tours), Jonathan and James Bach's Session-Based Test Management, Maaret Pyhäjärvi's work on exploratory testing with AI, and Simon Willison's "agentic manual testing". The lab's first target is Mark Winteringham's [Restful-booker](https://github.com/mwinteringham/restful-booker). More in [`lab/README.md`](lab/README.md#credits-and-license).

MIT, see [`LICENSE`](LICENSE).
