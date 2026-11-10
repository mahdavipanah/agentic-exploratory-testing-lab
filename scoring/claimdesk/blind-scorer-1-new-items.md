# New items for batch blind-2 (scorer: map-blind-1.txt)

## New items (T16+)

None. Every confirmed defect claimed in this batch matches one of T01–T15. Nothing new reached the key's standard (contradicts the docs, or a reasonable client would call it wrong, and not just a symptom of an existing item).

## Candidates rejected

Each was checked against a fresh server (ports 3201–3203, stopped afterwards) or against the docs, key and seed data.

- **Description of 199 characters rejected as "over 200 characters"** (R03 F8; R03 Q5 follows up). Does not reproduce, so it's scored `FP`. On a fresh server, `curl -s -o /dev/null -w '%{http_code}' -X POST $B/claims/4/items -H "Authorization: Bearer $TA" -H 'Content-Type: application/json' -d '{"date":"<today-5>","category":"other","description":"<199 x d>","amount":1}'` gave 199 → `201`, 200 → `201`, 201 → `400 "description must be at most 200 characters"`. The agent's string was probably longer than it thought.
- **Victim claim's `updated_at` doesn't change after a cross-claim item delete; the path claim's `updated_at` changes instead** (R05 Q1, R09 Q1, R12 Q2, R15 Q2, R16 Q2, R17 Q1, R18 Q1, R19 Q1, R20 Q2, R21 Q2; also R23 F1 body). This is real but only a symptom of T13: the delete shouldn't happen at all. Fresh server: `DELETE /claims/4/items/7` as alice → `204`. Claim 3 then had items `[5, 6]` and total 185.9, with `updated_at` still `2026-10-22T07:50:00.000Z`. Claim 4's `updated_at` moved to now. Scored `-`.
- **Item id 17 "skipped" (seed ends at 16, first new item is 18)** (R03 Q3, R21 Q5; R11 Q4 similar). This is a misread. The seed has 17 items (claim 10's ticket is item 17), and the first new item on a fresh server got id 18. Scored `-`.
- **Docs give port 3001 but the API ran on 3002** (R21 Q1). This is run setup, not a defect: the docs say "see your run instructions for the actual port". Scored `-`.
- **A claim with total 0 can be submitted** (R03 Q1, R22 Q4). This follows from T01 (amount 0 accepted); the docs only require at least one item. It's a design question. Scored `-`.
- **A claim set to `paid` through PATCH has `paid_at`/`amount_paid` null and shows as paid to finance** (R01 Q1, R10 Q2, R18 Q2, R20 Q4). This is a consequence of T09 and scored as T09 (DUP in each run), not a new item.
- **`amount_paid` ≠ `total` on claim 9 after double pay plus cross-claim deletes** (R19 Q2). This comes from T11 and T13 combined, not from T10's stale-total payment. Scored T11;T13.
- **Reviewing with a blank comment returns 409 instead of 400** (R15 Q3, R16 Q4). The claims were no longer `submitted`. State check before body validation is known quirk Q19. Scored `-`.
- **Prediction-only claims outside the key** (R06, R07, R13, R14, R24): float-sum totals, valid two-decimal amounts rejected, timezone date shifts, impossible dates, non-atomic create, lax id parsing, missing 405/Allow, body-parsing 500s, lowercase bearer, non-updated `updated_at`, sort tie order, invalid sort/status silently ignored, and so on. None of these behaviours occurs in the server, and arm M scores anything outside the key as `FP` in any case.
