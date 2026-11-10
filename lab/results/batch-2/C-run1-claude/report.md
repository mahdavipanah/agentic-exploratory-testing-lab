# Exploration report

## Charters

Risks (most harmful to a client first):
- R1 Visibility/authorization leaks: managers seeing other teams or drafts, employees seeing/changing others' claims, self-approval, wrong 403 vs 404.
- R2 Money/lifecycle: double payment, amount_paid != total, illegal transitions, edits after submit changing a paid/approved total.
- R3 Item validation: date window boundaries (90 days, future), amount decimals/limits, meals daily 60.00 limit (incl. float sums), string amounts, atomic POST /claims with items.
- R4 Listing: total_count/next_page wrong, sort/tie order, filters leaking hidden claims, invalid params not rejected.
- R5 Request plumbing: malformed JSON, non-object bodies, ids like 007/0, trailing slash, 405 + Allow.

Charters (budget 80 requests; ~6 reserved for logins):
1. Explore claim visibility and permissions with all six seed users (Saboteur tour) to discover authorization leaks or wrong 403/404 codes. Budget 20.
2. Explore the claim lifecycle and payment with create/submit/review/pay sequences repeated and reordered (Obsessive-compulsive tour) to discover illegal transitions or double payments / wrong totals. Budget 18.
3. Explore item validation with boundary and malformed values (Antisocial tour) to discover accepted invalid expenses or rejected valid ones. Budget 18.
4. Explore GET /claims filters, sorting and pagination with the seed data (Guidebook tour) to discover wrong counts, ordering or leaks. Budget 12.
5. Explore request plumbing (bad JSON, odd ids, methods, trailing slash) (Back alley tour) to discover crashes or undocumented responses. Budget 6.

Actual spend: C1 24 (incl. 6 logins), C2 14, C3 19, C4 8, C5 5 (+4 lifecycle checks at the end) = 80. No new charters were added; the PATCH mass-assignment issue was found inside C2.

Tokens used below: ALICE=2b57e867…, BOB=f6bd0260…, CAROL=cdccc9f5…, FRANK=4a98d365…, DAVE=5fcc7bf3… (from POST /auth/login, full values in the commands).

## Findings

### F1: A manager can approve/reject claims from another team (that they cannot even see)
- Severity: high
- Request: `curl -s -X POST http://localhost:3001/claims/3/review -H 'Authorization: Bearer 4a98d365f4279b0a35f5b5eca2ce7f466b6f18169e3ef7ad' -H 'Content-Type: application/json' -d '{"decision":"approve"}'` (frank, mobile manager; claim 3 belongs to bob, platform)
- Expected: 404 not_found. Docs: "A claim you are not allowed to see behaves as if it did not exist: every endpoint returns 404"; only "a manager of the owner's team" may review. Frank's `GET /claims/9` correctly returns 404.
- Actual: 200, `"status":"approved","reviewed_by":"frank"`.
- Reproduced: 2 times (claim 3 approved; claim 9 of alice rejected by frank with `{"decision":"reject","comment":"cross-team test"}` → 200, `"status":"rejected","reviewed_by":"frank"`).

### F2: PATCH accepts `status`, letting an owner approve their own claim, which finance then pays
- Severity: high
- Request: `curl -s -X PATCH http://localhost:3001/claims/5 -H 'Authorization: Bearer f6bd0260d8f26882a0ab3513714f6e9c5c4bf30305985cf6' -H 'Content-Type: application/json' -d '{"status":"approved"}'` (bob, his rejected claim 5)
- Expected: `status` is ignored ("any other field in the body, such as `status`, `owner` or `total`, is ignored"); status stays `rejected`.
- Actual: 200, `"status":"approved"`. `POST /claims/5/pay` as dave then returned 200 `"status":"paid","amount_paid":58`. (`owner` and `total` are correctly ignored: PATCH /claims/4 `{"owner":"bob","total":1}` left owner alice, total 249.)
- Reproduced: 2 times (claim 9 by alice with `{"title":"  Taxi edited  ","status":"approved",...}` → 200 `"status":"approved"`; claim 5 by bob).

### F3: Paying an already paid claim pays again (amount_paid doubles) and overwrites reference/paid_at
- Severity: high
- Request: `curl -s -X POST http://localhost:3001/claims/8/pay -H 'Authorization: Bearer 5fcc7bf332358f8f71686a235a0e8adac4731d328bb3bbe2'` sent twice
- Expected: second call returns 200 and "changes nothing" / "records nothing new"; amount_paid equals total.
- Actual: 200 both times; claim 8 (total 85): amount_paid 85 then 170, paid_at changed. Claim 1 (total 251.4): first pay with reference REF-A → amount_paid 251.4; second with REF-B → amount_paid 502.8, payment_reference "REF-B", new paid_at/updated_at. Seed claim 10 (already paid, total 299) → amount_paid 598.
- Reproduced: 3 times (claims 1, 8, 10).

### F4: `owner` filter on GET /claims returns claims the caller may not see, including drafts
- Severity: high
- Request: `curl -s 'http://localhost:3001/claims?owner=bob' -H 'Authorization: Bearer 2b57e867a29bb50eec6b53aa5b3b24b1784ee3cdedf343a3'` (alice, employee)
- Expected: empty list; `owner` "narrows the list ... among the claims you can see", and employees see only their own claims.
- Actual: 200, bob's claims 3, 8, 5 with titles, totals, statuses; total_count 3.
- Reproduced: 3 times (alice→owner=bob; erin→owner=alice returned all 4 of alice's claims incl. draft 4; carol (platform manager)→owner=erin returned erin's claims incl. draft 7).

### F5: Meals daily limit of 60.00 is only checked per item, not per day
- Severity: medium
- Request: `curl -s -X POST http://localhost:3001/claims -H 'Authorization: Bearer f6bd0260d8f26882a0ab3513714f6e9c5c4bf30305985cf6' -H 'Content-Type: application/json' -d '{"title":"Meals test","currency":"EUR","items":[{"date":"2026-11-09","category":"meals","description":"Lunch","amount":50},{"date":"2026-11-09","category":"meals","description":"Dinner","amount":20}]}'`
- Expected: 400 — "meals items that share a date may add up to at most 60.00".
- Actual: 201, claim 11 with total 70. A single 61.00 meals item is correctly rejected ("meals are limited to 60.00 per day").
- Reproduced: 3 times (claim 11 via POST /claims; claim 4 via POST /items 50 + 20 on 2026-11-09; claim 4 30.1 + 29.9 + 0.01 on 2026-11-10 all 201).

### F6: `q` search ignores item descriptions
- Severity: medium
- Request: `curl -s 'http://localhost:3001/claims?q=flight' -H 'Authorization: Bearer 5fcc7bf332358f8f71686a235a0e8adac4731d328bb3bbe2'`
- Expected: claim 3 (item "Flight Hamburg to Munich"); docs: "A claim matches if its title or any of its item descriptions contains the text."
- Actual: 200, `"data":[]`, total_count 0.
- Reproduced: 3 times (q=flight; q=Taxi%20to%20Hamburg as alice → empty though claim 9 item is "Taxi to Hamburg airport"; q=LUNCH returned only claim 5 by title, not claim 3 with item "Lunch").

### F7: The documented earliest item date (today − 90 days) is rejected
- Severity: low
- Request: `curl -s -X POST http://localhost:3001/claims/4/items -H 'Authorization: Bearer 2b57e867a29bb50eec6b53aa5b3b24b1784ee3cdedf343a3' -H 'Content-Type: application/json' -d '{"date":"2026-08-12","category":"other","description":"earliest","amount":1}'`
- Expected: 201; docs: "If today is 2026-11-10, the earliest accepted date is 2026-08-12" (today is 2026-11-10).
- Actual: 400 `"date must not be more than 90 days in the past"`. 2026-08-13 is accepted (201) — off by one.
- Reproduced: 2 times.

### F8: Default `per_page` is 10, not 20
- Severity: low
- Request: `curl -s 'http://localhost:3001/claims' -H 'Authorization: Bearer 5fcc7bf332358f8f71686a235a0e8adac4731d328bb3bbe2'`
- Expected: `meta.per_page` 20 ("Default 20").
- Actual: 200, `"meta":{"page":1,"per_page":10,...}`.
- Reproduced: 6+ times (every list request without per_page).

## Questions
- Resubmitting a rejected claim seems to be refused: bob's claim 11 (submitted, then rejected by carol) → `POST /claims/11/submit` gave 409 "claim is rejected; only draft claims can be submitted". Docs allow submit from `rejected`. Seen once only (out of budget to repeat); the same "only draft claims can be submitted" wording appeared for other states, which supports it.
- I could not confirm that default per_page 10 actually truncates results (no user sees more than 10 claims); only meta was checked.
- Unchecked: whether trimming of `description`/`title` counts characters correctly at 200/120, purpose 500 limit, `reference` > 64, 1 MB body limit, PATCH currency change with items.

## Coverage
- Explored: visibility of all list/detail endpoints for all six roles; review/patch/delete/create permission checks; auth (missing, unknown, lowercase scheme); pay/repay/pay-wrong-state; submit/delete in wrong states; PATCH ignored fields; item date/amount/description/category validation and meals limit; atomic POST /claims with invalid item (correct, `items[1].date`); list sort, paging, next_page, invalid status/page/per_page, search; invalid JSON, array body, id `007`, trailing slash, 405 with Allow header (all correct).
- Not explored: DELETE item endpoints, PATCH currency, length limits, 413, approve with comment, updated_at semantics in detail, sort ties.
- Requests used: 80 of 80.
