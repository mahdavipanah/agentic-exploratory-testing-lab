# claimdesk: the held-out target

A small team-expense-claims API (Node 18+, no dependencies, in-memory, seeded on every start) with planted bugs.

**How it was built.** A separate agent session built it on 10 Nov 2026 from a written spec. It never saw the skill, the arm prompts or any results. The experimenter has not read `server.js`, `seed.js` or the answer key.
- **The spec:** a realistic domain with roles, a state machine, money and dates; 12–15 realistic bugs across common classes (validation, boundaries, state machine, authorization, arithmetic, dates, partial update, consistency between views, idempotency, error handling); two docs defects; at least four bugs that only show after several requests.
- **The result:** 15 planted items, including the 2 docs defects. A sealed verifier reproduced all 15 on a fresh start, and 91 happy-path checks passed.

**The answer key was sealed until scoring.** Its SHA-256 is in [`answer-key.sha256`](answer-key.sha256), committed before batch-2 ran. Since scoring finished, the key is published at [`scoring/claimdesk/answer-key.md`](../../scoring/claimdesk/answer-key.md). Check it against the commitment with `shasum -a 256 scoring/claimdesk/answer-key.md`, and replay it with `scoring/claimdesk/verify-key.py <port>` on a fresh server.

**Spoilers:** `server.js` contains the bugs. If you want to explore claimdesk yourself, read only `api.md` and run the server with `start.sh <port>`.

| File | What it is |
| --- | --- |
| `api.md` | The documentation the agents get |
| `start.sh <port>` | Runs the server in the foreground with `TZ=UTC` |
| `server.js`, `seed.js` | The implementation and seed data (spoilers) |
| `B-charters.md` | Arm B's charters, written by the experimenter from `api.md` only |
| `target.conf` | Settings for the harness |
| `answer-key.sha256` | Commitment to the sealed answer key |
