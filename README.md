# Agentic Exploratory Testing Lab

Experiments for the essay *Teaching Agents to Explore* and for an exploratory-testing skill for Claude and other coding agents.

**The question:** can a coding agent explore software well on its own if you give it a written mission, and can it write that mission itself?

## The experiment

One target, three arms. Each arm differs only in the mission it gives the agent:

| Arm | Mission | File |
| --- | --- | --- |
| A | None: "Find bugs in this API." | `arms/A-baseline.md` |
| B | Four charters written by a human from the docs, each with a tour | `arms/B-human-charters.md` |
| C | The agent lists risks and writes its own charters, then explores them | `arms/C-agent-charters.md` |

These stay the same in every arm (`arms/shared-rules.md`): black box (curl and the API docs only), a budget of 80 HTTP requests, the evidence rule (only report what you saw and reproduced), the report format, and a freshly restarted target.

**Target:** [Restful-booker](https://github.com/mwinteringham/restful-booker), a deliberately buggy practice API by Mark Winteringham, pinned to commit `619d031`. It has no public answer key, so we build one (see `scoring/README.md`).

## Run it

Requires Node 20+, Python 3 and an agent CLI (`claude` is the tested one).

```bash
scripts/setup-target.sh                 # clone the target at the pinned commit, build target/api.md
scripts/run-arm.sh A 1                  # arm A, run 1, with claude, on port 3001
scripts/run-arm.sh B 1 claude 3002      # parallel runs need different ports
scripts/run-arm.sh C 1 claude 3003
```

Each run writes `results/<label>/<arm>-run<n>-<agent>/` with the exact prompt, the transcript, the report and timing. The agent runs in a temporary directory holding only the prompt and a copy of the docs; for `claude`, tools are limited to `curl`, reading `api.md` and writing `report.md`.

`codex` and `gemini` adapters exist in `run-arm.sh` but are untested.

## Layout

```
arms/        prompts: shared rules, the three arms, the tour menu
target/      api.md (the only doc agents see); the target is cloned here by setup
scripts/     setup, start/stop target, compose prompt, run one arm
scoring/     how runs are scored; answer key and scores once a batch is done
results/     one folder per batch of runs
skill-notes.md   what each experiment teaches for the skill
```

## Status

- Harness: done.
- **Pilot, 9 Nov 2026** (one run per arm, Claude Opus 5.5 subagents): out of a 38-item ceiling, A found 9, B 18 and C 20, with zero false positives. See [`results/pilot-2026-11-09/summary.md`](results/pilot-2026-11-09/summary.md).
- Full batch (three runs per arm, `claude` CLI with enforced tool limits): not yet run.

Score a batch: `python3 -I scripts/score.py scoring/scores-<batch>.csv 38`
