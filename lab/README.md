# The lab

The experiments behind the [exploratory-testing skill](../skills/exploratory-testing/SKILL.md) and the essay *Teaching Agents to Explore* (link coming soon). Run every command below from this `lab/` folder.

Until 10 Nov 2026 the lab was the whole repository, named `agentic-exploratory-testing-lab`, so commits and tags from before then (such as `batch-1`) have these folders at the repository root.

**The question:** can a coding agent explore software well on its own if you give it a written mission, and can it write that mission itself?

> **Spoiler warning.** The targets are [Restful-booker](https://github.com/mwinteringham/restful-booker), a practice API with deliberate bugs, and [claimdesk](targets/claimdesk/), written for this lab with 15 planted bugs. If you want to hunt them yourself first, don't open `scoring/` or the reports in `results/`.

## The experiment

Two targets, four exploring arms and one control. The arms differ only in the mission the agent gets:

| Arm | Mission | Prompt |
| --- | --- | --- |
| A | None: "Find bugs in this API." | [`arms/A-baseline.md`](arms/A-baseline.md) |
| B | Four charters written by the experimenter from the docs, each with a tour | [`arms/B-human-charters.md`](arms/B-human-charters.md) |
| C | The agent lists risks, writes its own charters, then explores them | [`arms/C-agent-charters.md`](arms/C-agent-charters.md) |
| D | The [exploratory-testing skill](../skills/exploratory-testing/), written from the pilot's lessons (batch-1 ran v0.1, batch-2 ran v0.3) | [`arms/D-skill.md`](arms/D-skill.md) |
| M | Control, not an exploration: the docs only, no API access, "predict the bugs" | [`arms/M-memory.md`](arms/M-memory.md) |

The rest is the same in every arm ([`arms/shared-rules.md`](arms/shared-rules.md)):

- Black box: `curl` and the API docs only.
- A budget of 80 HTTP requests.
- An evidence rule: only report what you saw and reproduced.
- A fixed report format.
- A freshly restarted target.

Arm D was added after the pilot. Because the skill was written from the pilot's lessons on Restful-booker, a good D score there shows the lessons were applied, not that the skill generalizes. Batch-2 tests that on claimdesk, a target the skill had never seen.

Charters use Elisabeth Hendrickson's template, *Explore (target) with (resources) to discover (information)*. Tours come from James Whittaker's *Exploratory Software Testing* ([`arms/tours.md`](arms/tours.md)).

## Results so far

**batch-1, 9 Nov 2026:** 5 isolated runs of each arm, 25 sessions in a shuffled order, Claude Opus 5.5 (`claude-opus-5-5`). Scored against the 39 known problems in the answer key.

| Arm | Recall, findings (mean, range) | Noticed, incl. questions | False positives | Requests |
| --- | --- | --- | --- | --- |
| A, no mission | 35% (33–38%) | 46% | 0 of 62 | 66 |
| B, experimenter's charters | 46% (44–49%) | 62% | 0 of 82 | 80 |
| C, agent's own charters | 39% (18–49%) | 50% | 0 of 58 | 65 |
| D, the skill | 48% (38–59%) | 56% | 0 of 78 | 76 |
| M, docs only, no API | 50% (46–54%) | 50% | 56 of 161 predictions don't match | 0 |

- **A mission helps.** B and D beat A: p = 0.008 and 0.016 (exact permutation test). C is not distinguishable from A: four C runs scored 36–49%, but one stopped at 37 of 80 requests and scored 18%.
- **The skill matches human charters, and finds different bugs.** One of them, re-keying a booking through `bookingid`, appeared in 4 of 5 D runs and nowhere else. The skill was written after the pilot on this same app, so this is not a test of how it generalizes.
- **Memory alone scores as high as exploring.** Arm M, docs only, recognized Restful-booker in all five runs. For much of the key, recall here can't separate exploring from remembering. Ten items were found only by exploring; they show up only when you run the system and watch its responses and state.
- **No sign of carry-over** between sessions: Spearman rho = +0.11, p = 0.61.
- **The scoring was checked:** a second scorer re-scored 101 rows blind and agreed on 91. The disagreements are settled in the summary.

Full write-up: [`results/batch-1/summary.md`](results/batch-1/summary.md). One harness bug affected this batch and was repaired from the transcripts; see [`results/batch-1/README.md`](results/batch-1/README.md).

**batch-2, 10 Nov 2026: the held-out target.** [claimdesk](targets/claimdesk/) is an API the model has never seen, with 15 bugs planted by a separate agent session. Its answer key was sealed (hash committed before the runs) and the scoring was done blind to the arm, with 96 of 100 items confirmed by a second scorer. 5 runs per arm, skill v0.3.

| Arm | Recall (mean, range) | Precision |
| --- | --- | --- |
| A, no mission | 68% (53–80%) | 51 of 51 |
| B, experimenter's charters | 71% (60–80%) | 53 of 53 |
| C, agent's own charters | 63% (53–73%) | 47 of 47 |
| D, the skill | 72% (67–87%) | 54 of 55 |
| M, docs only, no API | 71% (67–73%) | 56 of 219 |

- **No arm difference is significant here.** On a small API whose docs state every rule, the default agent already covers most of the surface.
- **Prediction gets recall by guessing a lot.** The bugs sit where the docs make promises, so predicting from the docs found as many, but 3 in 4 predictions were wrong.
- **Missions show on specific bugs.** One example: a total that goes stale in the list after an item is removed was found by 5 of 5 B runs and 4 of 5 D runs, against 0 of 5 for A.

Full write-up: [`results/batch-2/summary.md`](results/batch-2/summary.md).

**Pilot (earlier the same day):** one run per arm, isolated by instruction only. Rescored against 39 items: A 23%, B 46%, C 51%. With one run, C looked at least as good as B. Five runs show C is the least reliable. See [`results/pilot-2026-11-09/summary.md`](results/pilot-2026-11-09/summary.md). Lessons for the skill: [`skill-notes.md`](skill-notes.md).

Batch-1 used skill v0.1 (commit [`c0795db`](https://github.com/mahdavipanah/exploratory-testing-skill/tree/c0795db)); batch-2 used v0.3 (batch-1's lessons plus Elisabeth Hendrickson's *Explore It!*; see [`skill-notes.md`](skill-notes.md)). Each run's `prompt.md` holds the exact skill text it got.

## The skill

The skill lives in [`../skills/exploratory-testing`](../skills/exploratory-testing/), and the [main README](../README.md) says how to install and use it. Arm D inlines that folder into its prompt (`scripts/compose-prompt.sh`; set `AET_SKILL_DIR` to test another version). To check the skill against the spec: `python3 -I scripts/validate-skill.py ../skills/exploratory-testing`, or `skills-ref validate` from the [official reference library](https://github.com/agentskills/agentskills/tree/main/skills-ref).

## Reproduce it

Tested on Linux with Node 22, Python 3.13 and Claude Code 2.1.319. The scripts need only bash, curl, git, lsof and the Python standard library, so macOS works too. The target always runs with `TZ=UTC`; see the answer key for why.

### 1. Set up and see the bugs (no AI needed, about a minute)

```bash
git clone https://github.com/mahdavipanah/exploratory-testing-skill
cd exploratory-testing-skill/lab
scripts/setup-target.sh                   # Restful-booker at the pinned commit, plus target/api.md
python3 -I scripts/verify-answer-key.py   # replays all 39 known problems on a fresh server (spoilers)
```

The last line should read `39 of 39 items reproduced.` The output from our machine is in [`scoring/answer-key-verification.md`](scoring/answer-key-verification.md).

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

**Another target.** `AET_TARGET` picks one from [`targets/`](targets/); Restful-booker is the default. For example, for the held-out target [claimdesk](targets/claimdesk/), whose answer key stays sealed until scoring:

```bash
AET_TARGET=claimdesk scripts/run-experiment.sh batch-2
```

A target is a folder `targets/<name>/` containing:
- `start.sh <port>`, which runs the server in the foreground
- `api.md`, the docs the agents get
- `B-charters.md`, arm B's charters
- optionally `target.conf`, which can set `RECORDS` (what the data is called in the prompts)

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
- `meta.txt`: versions, model, isolation mode, run order, exit status, memory audit, curl calls from the transcript, turns, cost, and `report_source` (`file`, or `transcript` if the report had to be rebuilt).

**Arm M** gets the docs but no access to the API, and is asked to predict the bugs. If it predicts many of the 39, part of what the other arms "find" is the model remembering Restful-booker, not exploring it.

To run a single session: `scripts/run-arm.sh B 2 claude 3002 batch-1`. Adapters for `codex` and `gemini` exist but are untested.

### 4. Score it

```bash
python3 -I scripts/extract-findings.py results/batch-2 > /tmp/sheet.csv   # isolated runs only
# write scoring/map-batch-2.txt: one line per finding or question (rules: scoring/README.md)
python3 -I scripts/apply-map.py /tmp/sheet.csv scoring/map-batch-2.txt > scoring/scores-batch-2.csv
python3 -I scripts/score.py scoring/scores-batch-2.csv 39 --schedule results/batch-2/schedule.txt
```

Matching a finding to the answer key is a human judgment, on purpose. The map file is the audit trail: it says which key items each finding claims, with a note on every judgement call. `apply-map.py` computes the TP and DUP verdicts from it and fails if any finding is left unmapped. A new, confirmed problem becomes a new K item in the answer key, and the ceiling grows.

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

Inside `lab/`:

```
arms/            prompts: shared rules, the arms, the tour menu
scripts/         setup, start/stop target, verify the answer key, run a session or a batch, extract and score findings
scoring/         scoring rules, answer key and its verification, per-finding verdicts
results/         one folder per batch of runs
skill-notes.md   what each experiment teaches for the skill
target/          Restful-booker is cloned here and api.md generated by setup (not committed)
targets/         other targets, one folder each; claimdesk is the held-out target (answer key sealed)
```

## Credits and license

- **Target:** [Restful-booker](https://github.com/mwinteringham/restful-booker) by Mark Winteringham (GPL-3.0). It is cloned at setup and not redistributed here.
- **Held-out target:** claimdesk was written for this lab by a separate agent session, and is MIT-licensed with the rest of the repo.
- **Method:** charters from Elisabeth Hendrickson's *Explore It!* (2013); tours from James Whittaker's *Exploratory Software Testing* (2009); session structure from Jonathan and James Bach's Session-Based Test Management; scoring against a known ceiling after Maaret Pyhäjärvi; "agentic manual testing" after Simon Willison.
- **This repo:** MIT, see [`LICENSE`](../LICENSE).
