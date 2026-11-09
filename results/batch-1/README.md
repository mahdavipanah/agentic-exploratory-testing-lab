# batch-1

25 sessions: arms A, B, C, D and M, five runs each, in a seeded shuffled order (`schedule.txt`, seed 2608332159), four at a time.
Run on macOS with `scripts/run-experiment.sh`, login isolation, Claude Code 2.1.319, model `claude-opus-5-5` (from each transcript's init event), 2026-11-09 15:44–16:13 UTC.

Every session exited cleanly, and no memory file in the Claude Code home changed during any of them (`login_home_memory_changes=0` in every `meta.txt`).

## Incident: 11 reports were rebuilt from transcripts

**What happened.** The prompt told the agent to write its report to `/var/folders/.../T//aet-run-XXXXXX/report.md`. On macOS, `/var` is a symlink to `/private/var`. Claude Code resolves its working directory to the `/private/var` path and checks the `Write(./report.md)` rule against that path. A write to the `/var` spelling therefore matched no rule and was denied.

The pilot ran on Linux, where `/tmp` is not a symlink, so this never showed up there. The smoke test passed only because that agent happened to retry with the resolved path.

**What the agents did.**
- 14 sessions checked the folder, retried with the `/private/var` path and saved their report.
- 11 sessions stopped and replied that the report was ready but could not be saved. The B charters ask for unusual payloads, and their payload-file writes were refused too, so B lost four of five reports this way. The 11 are A-run5, B-run1, B-run2, B-run4, B-run5, D-run3 and all five M runs.

Every one of the 11 reached the end of its session.
- In nine, the denied `Write` to `report.md` was the agent's last action.
- In B-run1 and B-run5, the agent then listed the run folder with `ls` and stopped there, without writing again.

**What we did.**
- `scripts/recover-report.py` rebuilds `report.md` by replaying the agent's own `Write` and `Edit` calls to that file, in order, from `transcript.jsonl`. Nothing is added or edited by hand.
- To test the method, we replayed the 14 sessions that did save: in all 14 the replay matches the saved file exactly (`recover-report.py --check`).
- Each `meta.txt` now ends with `report_source=file` or `report_source=transcript`, plus `report_write_calls` and `report_write_denied`.

Dropping the 11 sessions instead would have biased the comparison: the failure depended on the arm (4 of 5 B runs, but only 1 of 5 A runs). So the recovered reports are scored like the others.

**Fix for later batches.**
- `run-arm.sh` resolves the run folder with `pwd -P`, so the prompt names the same path the permission rule checks.
- It rebuilds the report automatically if the write is still refused.
- `run-experiment.sh`'s smoke test now fails unless the agent saved `report.md` itself.

## Other measurement notes

- **Request counts.** `curl_invocations_counted` (the original field) counts every curl the agent asked for, including commands the permission system refused. `curl_invocations_executed` (added afterwards from the same transcripts) leaves those out. By executed count, every session stayed within about one request of the 80 budget. Both count a shell loop as one request.
- **Refused commands.** Only `curl` was allowed in Bash, so commands that combined curl with `echo`, variable assignments or heredocs were refused (`refused_tool_calls`). Agents rewrote them as plain curl calls. This cost the B arm the most, for the same reason as above.
- **Added fields.** The lines after `subtype=` in each `meta.txt` (`model_used`, `curl_invocations_executed`, `refused_tool_calls`, `report_*`) were added after the batch, by running the current `transcript_stats.py` and `recover-report.py` on the unchanged transcripts.
