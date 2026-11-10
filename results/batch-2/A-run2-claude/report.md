# Exploration report

## Charters
none

Tokens below: ALICE=f900627f…, BOB=94c77287…, CAROL=7cf6e61b…, FRANK=9a9f3128…, DAVE=1e310c47… (from `POST /auth/login`). Base URL: http://localhost:3002. "Today" during the run: 2026-11-10 (UTC).

## Findings

### F1: PATCH lets the owner set `status` directly (self-approve, then get paid)
- Severity: high
- Request: `curl -s -X PATCH http://localhost:3002/claims/13 -H 'Content-Type: application/json' -H "Authorization: Bearer $ALICE" -d '{"status":"approved","owner":"bob","total":1,"title":"  Renamed  ","purpose":""}'`
- Expected: Docs say that only `title`, `purpose` and `currency` can be changed with PATCH: "any other field in the body, such as `status`, `owner` or `total`, is ignored". The status should stay `draft`.
- Actual: 200, `"status":"approved"` (`owner` and `total` were ignored; `reviewed_by` is null). Finance then paid it: `POST /claims/13/pay` as DAVE returned 200 `"status":"paid","amount_paid":80`. So an employee can skip manager review and get paid.
- Reproduced: 2 (claim 13, and `PATCH /claims/12 {"status":"approved"}` → 200 `"status":"approved"`)

### F2: A manager can review claims from another team
- Severity: high
- Request: `curl -s -X POST http://localhost:3002/claims/3/review -H 'Content-Type: application/json' -H "Authorization: Bearer $FRANK" -d '{"decision":"approve"}'`
- Expected: "Only a manager of the claim owner's team can review it". Frank (mobile) cannot see bob's claim 3 (platform). `GET /claims/3` as FRANK returns 404, so the review should return 404 too.
- Actual: 200, `"status":"approved","reviewed_by":"frank"`.
- Reproduced: 2 (frank → claim 3 of platform; carol → claim 6 of mobile, 200 `"reviewed_by":"carol"`)

### F3: Paying an already-paid claim records a second payment
- Severity: high
- Request: `curl -s -X POST http://localhost:3002/claims/1/pay -H 'Content-Type: application/json' -H "Authorization: Bearer $DAVE" -d '{"reference":"REF-2"}'` (sent after a first successful pay with `REF-1`)
- Expected: "If the claim is already `paid`, the call is safe to repeat: it returns `200` with the claim and changes nothing."
- Actual: 200 with `"amount_paid":502.8` (total is 251.4, so it was paid twice), and `payment_reference` changed to `"REF-2"`. `paid_at` and `updated_at` were also updated.
- Reproduced: 2 (claim 1: 251.4 → 502.8; claim 3: 204.8 → 409.6, reference R3a → R3b)

### F4: You can delete an item through a different claim's URL, even if that claim is approved
- Severity: high
- Request: `curl -s -i -X DELETE http://localhost:3002/claims/13/items/23 -H "Authorization: Bearer $ALICE"` (item 23 belongs to claim 12)
- Expected: "The item must belong to the claim in the path", so the response should be 404.
- Actual: 204, and item 23 is gone from claim 12 (total 80 → 40). Claim 12's `updated_at` did not change. Second case: `DELETE /claims/11/items/24` (claim 11 is a draft) removed item 24 from claim 12 while claim 12 was `approved`. Claim 12 then showed `"status":"approved","items":[],"total":0`. This gets around the draft/rejected-only rule.
- Reproduced: 2

### F5: A rejected claim cannot be submitted again
- Severity: high
- Request: `curl -s -X POST http://localhost:3002/claims/9/submit -H "Authorization: Bearer $ALICE"` (claim 9 had just been rejected by carol with a comment)
- Expected: Submit is allowed "from `draft` and from `rejected`" (lifecycle diagram: rejected ──submit──▶ submitted).
- Actual: 409 `{"error":"invalid_state","message":"claim is rejected; only draft claims can be submitted"}`
- Reproduced: 2 (seed claim 5 as BOB; claim 9 as ALICE after rejection and after adding an item)

### F6: The meals limit of 60.00 per day is checked per item, not as a daily total
- Severity: medium
- Request: `curl -s -X POST http://localhost:3002/claims/13/items -H 'Content-Type: application/json' -H "Authorization: Bearer $ALICE" -d '{"date":"2026-11-07","category":"meals","description":"Dinner","amount":40}'` (the claim already had a 40.00 meals item on 2026-11-07)
- Expected: "the `meals` items that share a date may add up to at most 60.00. An item that would take that day over 60.00 is rejected with `400`."
- Actual: 201, so the day adds up to 80.00. On claim 11, meals for 2026-11-10 reached 65.01 (30 + 30 + 0.01 + 5), all 201. `POST /claims` with two 40.00 meals on the same day also returned 201 (claim 12). A single 61.00 meals item is rejected correctly.
- Reproduced: 3 (two times via POST /claims/{id}/items, once via POST /claims)

### F7: Item date exactly 90 days ago (2026-08-12) is rejected
- Severity: low
- Request: `curl -s -X POST http://localhost:3002/claims/11/items -H 'Content-Type: application/json' -H "Authorization: Bearer $ALICE" -d '{"date":"2026-08-12","category":"travel","description":"T","amount":5}'`
- Expected: Docs: "If today is 2026-11-10, the earliest accepted date is 2026-08-12".
- Actual: 400 `{"error":"validation_failed","message":"date must not be more than 90 days in the past","field":"date"}`
- Reproduced: 2 (also inside `POST /claims`, `field: items[1].date`)

### F8: Text search `q` does not search item descriptions
- Severity: medium
- Request: `curl -s "http://localhost:3002/claims?q=hotel" -H "Authorization: Bearer $DAVE"`
- Expected: "A claim matches if its title or any of its item descriptions contains the text." Claims 1 and 6 have items "Hotel, 1 night".
- Actual: 200 `{"data":[],"meta":{...,"total_count":0}}`. `q=TAXI` returned only claim 9 (match on title). Claim 3, which has the item "Taxi to client office", was missing.
- Reproduced: 2

### F9: Default `per_page` is 10 instead of 20
- Severity: low
- Request: `curl -s "http://localhost:3002/claims?status=paid" -H "Authorization: Bearer $DAVE"`
- Expected: "`per_page` … Default 20."
- Actual: 200, `"meta":{"page":1,"per_page":10,...}`
- Reproduced: 4 (`?q=TAXI`, `?q=hotel`, `?status=paid`, `/claims/` as FRANK)

### F10: `meta.next_page` is not null on the last page
- Severity: medium
- Request: `curl -s "http://localhost:3002/claims?per_page=5&page=2" -H "Authorization: Bearer $DAVE"`
- Expected: With `total_count` 10 and `per_page` 5, page 2 is the last page, so `next_page` should be `null` ("or `null` on the last page").
- Actual: 200, `"meta":{"page":2,"per_page":5,"total_count":10,"next_page":3}`
- Reproduced: 2 (also `per_page=2&page=5&sort=total` → `next_page: 6` with total_count 10)

## Questions
- After F4, claim 12's `updated_at` stayed the same even though its item was removed. This is probably part of the same bug, so it is not listed separately.
- After the self-approval in F1, the claim has `reviewed_by: null` and `submitted_at: null`, but finance can still pay it. It is unclear whether `pay` should check anything beyond `status`.
- I could not test the length limits (title over 120 characters, comment over 500, reference over 64) because building long strings in my shell was blocked.
- `PUT /claims/9` gives `Allow: GET, PATCH, DELETE`, which looks correct.

## Coverage
Tested: login for all 6 users; visibility of drafts and other teams' claims (GET); review permissions (cross-team, owner, finance, reject without comment, wrong state); pay (finance only, wrong state, repeat pay); item rules (date boundaries, future date, invalid calendar date, 2-decimal amounts, string amount, max 10000, meals limit) in both POST /claims and POST /claims/{id}/items; deleting an item through another claim's URL; PATCH (ignored fields, status, null title, lower-case currency, manager editing); delete of a non-draft claim; submitting an empty claim and resubmitting a rejected claim; list filters (status, q), sort=total, pagination meta, trailing slash, zero-padded id, 405, invalid JSON / non-object body, lower-case `bearer`.
Not covered: length limits (title, purpose, comment, reference, description), 1 MB body limit, `owner` filter, `sort=-total` / `created_at` tie-break ordering, `per_page` / `page` validation (0, 51, non-numeric), invalid `status`/`sort` values, deleting a draft and checking its items are gone, 401 cases.
Requests used: 74 of 80.
