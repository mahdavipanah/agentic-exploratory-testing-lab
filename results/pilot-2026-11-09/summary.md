# Pilot, 9 Nov 2026: one run per arm

**Result:** with a written mission, the explorer found about twice as many known problems as the baseline: 9 for A, 18 for B and 20 for C, out of a 38-item ceiling. The agent-written missions (C) did at least as well as the experimenter-written ones (B). With one run per arm, B and C can't be told apart.

## Setup

- Target: Restful-booker at `619d031`, restarted fresh for each run (ports 3001 to 3003).
- Explorers: Claude Opus 5.5 subagents (general-purpose), run in parallel. Each got exactly the prompt in its `prompt.md`. They could not write files, so each returned its report as text, saved verbatim as `report.md`.
- Isolation was by instruction ("black box, read only api.md"), not enforced as it is in `run-arm.sh` with the `claude` CLI.
- Scoring: `scoring/answer-key.md` (38 items) and `scoring/scores-pilot-2026-11-09.csv`, computed with `scripts/score.py`.

## Scores

| Run | Findings | False positives | Key items in findings | Recall (findings) | Key items noticed (findings + questions) | Recall (noticed) | Requests | Minutes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A, no mission | 9 | 0 | 9 | 24% | 12 | 32% | 62 of 80 | 5.1 |
| B, experimenter's charters | 15 | 0 | 18 | 47% | 26 | 68% | 80 of 80 | 5.7 |
| C, agent's own charters | 18 | 0 | 20 | 53% | 27 | 71% | 80 of 80 | 4.9 |
| All three combined | | | 22 | 58% | 30 | 79% | | |

## What stood out

1. **A mission roughly doubled what was found.** A wrote itself a coverage plan ("exercise every documented endpoint") and stopped at 62 requests once it had covered everything. B and C had risk-oriented missions and spent the whole budget digging.
2. **The agent wrote good missions.** C ranked risks from the docs, put auth bypass first, and wrote five charters with budgets. Auth held up (no bypass), and its other charters found 20 key items. That fits Hamid's hypothesis, but one run proves nothing.
3. **Zero false positives in any arm.** The evidence rule (only report what you saw and reproduced) kept every finding real. It had a cost: B and C pushed 7 to 8 *confirmed* behaviours into "Questions" because they weren't sure they were bugs. Counted as noticed, recall rises to about 70%.
4. **Exploration found what source review missed.** Four behaviour bugs (K31 to K34) came only from runs. K31 is a broken documented response format, on a line the source review had read.
5. **Source review found what exploration missed.** Eight items no run noticed at all, including the two most damaging:
   - **K24:** a `bookingid` in a PATCH or PUT body re-keys a booking, so ids get duplicated and lost. B and C both sent `bookingid` in a *POST* body, saw it ignored, and called extra fields harmless. Neither repeated the probe on PATCH or PUT.
   - **K23:** `bookingdates: null` permanently breaks a booking.
6. **Docs worked as an oracle, and that fooled the agents.** Where behaviour matched the docs (POST returns 200 rather than 201, K02; DELETE returns 201), the agents accepted it, or flagged it only as a question. A even reasoned its way out of reporting DELETE's 201.
7. **One-sided boundary checks mislead.** A probed the checkout filter at one boundary, saw it "include" that date, and concluded the filter was correct. The filter is actually inverted.

## Caveats

- One run per arm and one model. The A-to-B/C gap is large; the B-to-C gap is noise.
- Restful-booker is well known, so the model may remember some of its bugs. The docs were retitled "Booking API" and nothing in the prompts names it.
- The experimenter (Claude) wrote B's charters, built the answer key and judged the findings. B's charters are in git before the source was read; Hamid should review the verdicts in the CSV.
- The shared rules already carry a lot of method (evidence, report format, budget). So arm A is "no mission", not "no guidance", and isn't comparable to Pyhäjärvi's unguided prompt.
