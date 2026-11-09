# Agentic Exploratory Testing Lab

Experiments behind the essay *Teaching Agents to Explore* (link coming soon) and the exploratory-testing skill for Claude and other coding agents that grows out of it.

**The question:** can a coding agent explore software well on its own if you give it a written mission, and can it write that mission itself?

> **Spoiler warning.** The target is [Restful-booker](https://github.com/mwinteringham/restful-booker), a practice API with deliberate bugs. If you want to hunt them yourself first, don't open `scoring/answer-key.md` or the reports in `results/`.

## The experiment

One target, three arms. The arms differ only in the mission the agent gets:

| Arm | Mission | Prompt |
| --- | --- | --- |
| A | None: "Find bugs in this API." | [`arms/A-baseline.md`](arms/A-baseline.md) |
| B | Four charters written by the experimenter from the docs, each with a tour | [`arms/B-human-charters.md`](arms/B-human-charters.md) |
| C | The agent lists risks, writes its own charters, then explores them | [`arms/C-agent-charters.md`](arms/C-agent-charters.md) |

The rest is the same in every arm ([`arms/shared-rules.md`](arms/shared-rules.md)):

- Black box: `curl` and the API docs only.
- A budget of 80 HTTP requests.
- An evidence rule: only report what you saw and reproduced.
- A fixed report format.
- A freshly restarted target.

Charters use Elisabeth Hendrickson's template, *Explore (target) with (resources) to discover (information)*. Tours come from James Whittaker's *Exploratory Software Testing* ([`arms/tours.md`](arms/tours.md)).

## Results so far

**Pilot, 9 Nov 2026:** one run per arm, with Claude Opus 5.5. The answer key has 38 known problems.

| Arm | Known problems reported | Noticed, incl. "questions" | False positives | Requests |
| --- | --- | --- | --- | --- |
| A, no mission | 9 (24%) | 12 (32%) | 0 | 62 of 80 |
| B, experimenter's charters | 18 (47%) | 26 (68%) | 0 | 80 of 80 |
| C, agent's own charters | 20 (53%) | 27 (71%) | 0 | 80 of 80 |

- **A written mission roughly doubled the find rate,** and agent-written missions did as well as the experimenter's. With one run per arm, B and C are indistinguishable.
- **Exploration and source review found different bugs.** The runs found 4 bugs that reading the source missed. Reading the source found 8 that no run noticed, including the worst one.
- **What the agents got wrong points at what the skill must teach:** repeat each probe on every write path, test both sides of a boundary, and don't take the docs as the only oracle.

Full write-up: [`results/pilot-2026-11-09/summary.md`](results/pilot-2026-11-09/summary.md). Lessons for the skill: [`skill-notes.md`](skill-notes.md).

**Next:** three runs per arm with the `claude` CLI, where tool limits are enforced rather than requested.

## Reproduce it

Tested on Linux with Node 22, Python 3.13 and Claude Code 2.1.319. The scripts need only bash, curl, git, lsof and the Python standard library, so macOS works too. The target always runs with `TZ=UTC`; see the answer key for why.

### 1. Set up and see the bugs (no AI needed, about a minute)

```bash
git clone https://github.com/mahdavipanah/agentic-exploratory-testing-lab
cd agentic-exploratory-testing-lab
scripts/setup-target.sh                   # Restful-booker at the pinned commit, plus target/api.md
python3 -I scripts/verify-answer-key.py   # replays all 38 known problems on a fresh server (spoilers)
```

The last line should read `38 of 38 items reproduced.` The output from our machine is in [`scoring/answer-key-verification.md`](scoring/answer-key-verification.md).

### 2. Check the pipeline without an LLM

```bash
scripts/run-batch.sh smoke 1 dry && rm -rf results/smoke
```

This runs arms A, B and C in parallel, with a stand-in agent that sends one request. If it passes, ports, prompts and result folders all work.

### 3. Run a batch

```bash
AET_MODEL=claude-opus-5-5 scripts/run-batch.sh batch-1 3    # 3 runs per arm with the claude CLI
```

Every session runs the same way:

- A fresh target on its own port.
- A temporary directory holding only the prompt and `api.md`.
- Claude Code in `--safe-mode`, so none of your CLAUDE.md, skills, hooks or MCP servers apply.
- Only three uses are permitted: `curl`, reading `api.md`, and writing `report.md`.

Each session leaves four files behind:

- `prompt.md`
- `transcript.jsonl`
- `report.md`
- `meta.txt`: versions, exit status, curl calls counted from the transcript, turns and cost.

A pilot session used about 100k to 120k tokens and 5 minutes.

To run a single session: `scripts/run-arm.sh B 2 claude 3002 batch-1`. Adapters for `codex` and `gemini` exist but are untested.

### 4. Score it

```bash
python3 -I scripts/extract-findings.py results/batch-1 > scoring/scores-batch-1.csv
# fill in key_ids and verdict for each row (rules: scoring/README.md)
python3 -I scripts/score.py scoring/scores-batch-1.csv 38
```

Matching a finding to the answer key is a human judgment, on purpose: the filled-in CSV is the audit trail. A new, confirmed problem becomes a new K item in the answer key, and the ceiling grows.

### How the pilot differs

The pilot ran its three sessions as Claude Opus 5.5 subagents inside a Claude session, not through `run-arm.sh`. The prompts were the same, but isolation was by instruction only, and the reports came back as text. Batches run with `run-batch.sh` are the repeatable version.

## How the answer key was built

Restful-booker has no public answer key, so we built one in the spirit of Maaret Pyhäjärvi's "known ceiling": every problem we could confirm, from any source.

1. Arm B's charters were committed before anyone read the target's source (see the git history).
2. Source review found 30 problems, each reproduced on a fresh server.
3. Confirmed findings from the runs added 8 more.

The key, the rules and every verdict are in [`scoring/`](scoring/).

## Layout

```
arms/            prompts: shared rules, the three arms, the tour menu
scripts/         setup, start/stop target, verify the answer key, run a session or a batch, extract and score findings
scoring/         scoring rules, answer key and its verification, per-finding verdicts
results/         one folder per batch of runs
skill-notes.md   what each experiment teaches for the skill
target/          the target is cloned here and api.md generated by setup (not committed)
```

## Credits and license

- **Target:** [Restful-booker](https://github.com/mwinteringham/restful-booker) by Mark Winteringham (GPL-3.0). It is cloned at setup and not redistributed here.
- **Method:** charters from Elisabeth Hendrickson's *Explore It!* (2013); tours from James Whittaker's *Exploratory Software Testing* (2009); session structure from Jonathan and James Bach's Session-Based Test Management; scoring against a known ceiling after Maaret Pyhäjärvi; "agentic manual testing" after Simon Willison.
- **This repo:** MIT, see [`LICENSE`](LICENSE).
