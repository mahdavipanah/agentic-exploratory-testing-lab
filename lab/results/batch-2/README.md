# batch-2: the held-out target

**What ran.** 25 sessions on 2026-11-10: arms A, B, C, D and M, five runs each, against [claimdesk](../../targets/claimdesk/).
- **Order:** seeded and shuffled, four sessions at a time (`schedule.txt`, seed 274144189).
- **Where and how:** on macOS with `AET_TARGET=claimdesk scripts/run-experiment.sh batch-2`, login isolation.
- **Agent:** Claude Code 2.1.322, model `claude-opus-5-5` (from each transcript), skill v0.3 for arm D.
- **Time:** 16:02–16:28 UTC.

**Checks.**
- All 25 sessions exited cleanly and saved their own report (`report_source=file`).
- None read local files through curl (`curl_file_urls=0`).
- All ran against the same committed target (`target_commit=071443c`).
- The answer key was sealed during the batch. Its SHA-256 had been committed beforehand in `targets/claimdesk/answer-key.sha256`.

**Memory audit.** Three sessions (B-run2, A-run4 and A-run1, orders 6–8) report `login_home_memory_changes=2`. All three ran together in wave 2, and each saw the same two files change.
- **Where the files were:** both were in another project's memory folder.
- **Who wrote them:** a Claude Code session working in an unrelated repository on the same machine at the same time.
- **Why it doesn't affect results:** the experiment's sessions run in temporary folders, with auto-memory off. The fourth session in that wave (M-run2) finished in 49 seconds, before the writes, and shows none. This is the home-wide audit noticing an outside write, not a leak between runs.
- **Redacted:** the file paths named a private project, so in these copies `login-home-memory-changes.txt` holds an explanation instead of the paths.

**Cost and effort per session (means).**

| Arm | Requests run (range) | Minutes | Cost |
| --- | --- | --- | --- |
| A | 77 (74–80) | 3.1 | $0.92 |
| B | 80 (79–80) | 3.7 | $1.09 |
| C | 77 (75–80) | 3.6 | $0.99 |
| D | 79 (77–81) | 4.2 | $1.23 |
| M | 0 | 1.0 | $0.27 |

Total: $22.48.
