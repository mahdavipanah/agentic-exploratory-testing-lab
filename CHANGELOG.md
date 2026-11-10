# Changelog

Each version of the skill, and the experiment it came from. The reasoning behind every rule is in [`lab/skill-notes.md`](lab/skill-notes.md).

## 0.3 (10 Nov 2026)

Adds ideas from Elisabeth Hendrickson's *Explore It!*, in the skill's own words, and a new [`references/heuristics.md`](skills/exploratory-testing/references/heuristics.md).

- Model the system before listing risks: a short recon pass, then entities and relationships, a state table and the variables.
- Never and Always rules, as a source of risks and as an oracle.
- Follow the data, walk the state table, and act as every role that touches the same data.
- Vary inputs on purpose (zero, one, many; beginning, middle, end; other formats), not by habit.
- What to do when the exact answer can't be known, and when to stop.
- The report says what worked and what is still unknown.
- The report template's example no longer mirrors a known Restful-booker bug.

Tested in batch-2, on claimdesk, a target the skill had never seen.

## 0.2 (10 Nov 2026)

Lessons from batch-1.

- When to stop: use the whole budget, and switch tours when you run out of ideas.
- Nothing is correct after valid input alone: test the boundary value, both sides of it and an invalid value.
- Look at the whole response: status, headers and body.
- Memory guides, evidence decides: recognising a system helps you choose probes, but it is never evidence.

## 0.1 (9 Nov 2026)

The first version, written from the pilot's lessons (called v0 in the lab notes): check the environment first, list risks before endpoints, write charters with tours and budgets, repeat probes on every path, test both sides of a boundary, read back after every write, and report bugs, behaviour that needs a decision, and open questions separately.

Tested in batch-1, on Restful-booker.

## Releasing a new version

1. Change `metadata.version` in [`SKILL.md`](skills/exploratory-testing/SKILL.md) and `version` in [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json). Claude Code only offers an update when `version` changes.
2. Run `claude plugin validate --strict .` and, from `lab/`, `python3 -I scripts/validate-skill.py ../skills/exploratory-testing`.
3. Add an entry here.
