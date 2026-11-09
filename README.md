# Agentic Exploratory Testing Lab

Experiments behind the essay *Teaching Agents to Explore* (link coming soon), and the [exploratory-testing skill](skills/exploratory-testing/SKILL.md) for Claude and other coding agents that grows out of them.

**The question:** can a coding agent explore software well on its own if you give it a written mission, and can it write that mission itself?

> **Spoiler warning.** The target is [Restful-booker](https://github.com/mwinteringham/restful-booker), a practice API with deliberate bugs. If you want to hunt them yourself first, don't open `scoring/answer-key.md` or the reports in `results/`.

## The experiment

One target, four arms. The arms differ only in the mission the agent gets:

| Arm | Mission | Prompt |
| --- | --- | --- |
| A | None: "Find bugs in this API." | [`arms/A-baseline.md`](arms/A-baseline.md) |
| B | Four charters written by the experimenter from the docs, each with a tour | [`arms/B-human-charters.md`](arms/B-human-charters.md) |
| C | The agent lists risks, writes its own charters, then explores them | [`arms/C-agent-charters.md`](arms/C-agent-charters.md) |
| D | The [exploratory-testing skill](skills/exploratory-testing/) (v0), written from the pilot's lessons | [`arms/D-skill.md`](arms/D-skill.md) |
| M | Control, not an exploration: the docs only, no API access, "predict the bugs" | [`arms/M-memory.md`](arms/M-memory.md) |

The rest is the same in every arm ([`arms/shared-rules.md`](arms/shared-rules.md)):

- Black box: `curl` and the API docs only.
- A budget of 80 HTTP requests.
- An evidence rule: only report what you saw and reproduced.
- A fixed report format.
- A freshly restarted target.

Arm D was added after the pilot. Because the skill was written from the pilot's lessons on this same target, a good D score here shows the lessons were applied. It does not show the skill generalizes; that needs a target the skill has never seen (planned).

Charters use Elisabeth Hendrickson's template, *Explore (target) with (resources) to discover (information)*. Tours come from James Whittaker's *Exploratory Software Testing* ([`arms/tours.md`](arms/tours.md)).

## Results so far

**Pilot, 9 Nov 2026:** one run per arm, with Claude Opus 5.5. The answer key has 38 known problems. The pilot was exploratory: its sessions ran as agents inside a Claude session, isolated by instruction only. The statistics we report will come from the isolated batch: 5 runs per arm, each in its own isolated session.

| Arm | Known problems reported | Noticed, incl. "questions" | False positives | Requests |
| --- | --- | --- | --- | --- |
| A, no mission | 9 (24%) | 12 (32%) | 0 | 62 of 80 |
| B, experimenter's charters | 18 (47%) | 26 (68%) | 0 | 80 of 80 |
| C, agent's own charters | 20 (53%) | 27 (71%) | 0 | 80 of 80 |

- **A written mission roughly doubled the find rate,** and agent-written missions did as well as the experimenter's. With one run per arm, B and C are indistinguishable.
- **Exploration and source review found different bugs.** The runs found 4 bugs that reading the source missed. Reading the source found 8 that no run noticed, including the worst one.
- **What the agents got wrong points at what the skill must teach:** repeat each probe on every write path, test both sides of a boundary, and don't take the docs as the only oracle.

Full write-up: [`results/pilot-2026-11-09/summary.md`](results/pilot-2026-11-09/summary.md). Lessons for the skill: [`skill-notes.md`](skill-notes.md).

**Next:** the isolated batch: 5 runs each of arms A to D plus the memory check (arm M), in a shuffled order with a carry-over check.

## The skill

[`skills/exploratory-testing`](skills/exploratory-testing/) packages the method in the open [Agent Skills](https://agentskills.io) format, so any agent that reads `SKILL.md` can use it: Claude Code, Codex, Cursor, Gemini CLI and others. It covers:

- Checking the environment before exploring.
- Listing risks before endpoints.
- Charters with tours and budgets.
- Rules for the blind spots the pilot exposed.
- Evidence for every claim.
- A report that separates bugs, behaviour that needs a decision, and unconfirmed suspicions.

To install it with the [skills CLI](https://skills.sh):

```bash
npx skills add https://github.com/mahdavipanah/agentic-exploratory-testing-lab --skill exploratory-testing
```

Or copy `skills/exploratory-testing/` into your agent's skills folder: for Claude Code, `~/.claude/skills/` or a project's `.claude/skills/`. Then ask your agent to "explore" a feature, an API or an app you just built.

To check the skill against the spec: `python3 -I scripts/validate-skill.py skills/exploratory-testing`, or `skills-ref validate` from the [official reference library](https://github.com/agentskills/agentskills/tree/main/skills-ref).

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

This runs arms A to D in parallel, with a stand-in agent that sends one request. If it passes, ports, prompts and result folders all work.

### 3. Run the experiment

One command, using your normal Claude Code login. No token or API key is needed:

```bash
scripts/run-experiment.sh batch-1
```

It works through these steps:

1. Checks the prerequisites.
2. Sets up the target.
3. Verifies the answer key.
4. Runs one real test session, and stops if that session fails, writes no findings or touches memory files.
5. Runs the batch.
6. Prints a summary and the `git` command to share the results.

The batch is 5 runs of each exploring arm A to D, plus 5 of the memory check M: 25 sessions in a shuffled order, 4 at a time. A pilot session used about 100k to 120k tokens and 5 minutes, so expect around 2 million tokens and roughly 40 minutes. Subscription usage limits may slow it down. Don't use Claude Code yourself while it runs.

To add more runs to the same batch later:

```bash
AET_RUN_START=6 scripts/run-batch.sh batch-1 3 claude "A B C D M"
```

**Why 5 runs per arm:** with 3 runs each, even a perfect gap between two arms can't reach p < 0.05; the smallest possible p is 0.1. With 5 runs each, the floor is 0.008.

**What every session gets, in any mode:**

- A clean environment, with nothing inherited from a parent Claude Code session.
- Claude Code in `--safe-mode`, so none of your CLAUDE.md, skills, hooks, plugins or MCP servers apply.
- Settings read only from an empty folder.
- No saved session.
- A fresh target on its own port.
- A temporary directory holding only the prompt and `api.md`.
- Permission only to use `curl`, read `api.md`, and write `report.md`.

**How runs are kept apart.** That depends on how Claude Code logs in:

| Mode | Used when | What it adds |
| --- | --- | --- |
| `login` | Default without a token or key | Your normal login. Auto-memory switched off (`CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`), and your Claude Code home audited before and after every run: memory files that appear or change are counted in `meta.txt` (expected: 0). |
| `fresh` | Default when `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`) or `ANTHROPIC_API_KEY` is set | A brand-new, empty Claude Code home for every run, deleted afterwards, with auto-memory off. Nothing at all is shared between runs. |
| `bare` | `AET_ISOLATION=bare` plus `ANTHROPIC_API_KEY` | `claude --bare`: no CLAUDE.md, auto-memory, hooks, plugins or keychain. |

**Carry-over check.** Because the order is shuffled, `score.py` can test whether sessions that ran later did better than their arm's average. If runs leaked into each other, later ones would score higher. The schedule and its seed are in `results/<batch>/schedule.txt`.

Each session leaves its files in `results/<batch>/<arm>-run<n>-claude/`:

- `prompt.md`
- `transcript.jsonl`
- `report.md`
- `meta.txt`: versions, isolation mode, run order, exit status, memory audit, curl calls counted from the transcript, turns and cost.

**Arm M** gets the docs but no access to the API, and is asked to predict the bugs. If it predicts many of the 38, part of what the other arms "find" is the model remembering Restful-booker, not exploring it.

To run a single session: `scripts/run-arm.sh B 2 claude 3002 batch-1`. Adapters for `codex` and `gemini` exist but are untested.

### 4. Score it

```bash
python3 -I scripts/extract-findings.py results/batch-1 > scoring/scores-batch-1.csv   # isolated runs only
# fill in key_ids and verdict for each row (rules: scoring/README.md)
python3 -I scripts/score.py scoring/scores-batch-1.csv 38 --schedule results/batch-1/schedule.txt
```

Matching a finding to the answer key is a human judgment, on purpose: the filled-in CSV is the audit trail. A new, confirmed problem becomes a new K item in the answer key, and the ceiling grows.

`score.py` prints:

- Recall per run.
- Per-arm mean, standard deviation and range.
- Pairwise permutation tests between arms (exact for small samples, and they don't assume normal data).
- The carry-over check.

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
arms/            prompts: shared rules, the four arms, the tour menu
skills/          the exploratory-testing skill (Agent Skills format)
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
