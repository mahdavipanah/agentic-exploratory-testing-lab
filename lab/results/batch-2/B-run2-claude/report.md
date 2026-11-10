# Exploration report

## Charters
1. Explore the claim lifecycle (create, add and remove items, edit, submit, reject, resubmit, approve, pay, then read again) with the seed users of each role to discover whether every step does what the docs say and returns the documented status code. Tour: Guidebook.
2. Explore one claim's data across every view (detail, list summaries, search, status and owner filters, sorting, pagination, and each role's view of it) with a single distinctive claim to discover data that changes, disappears or disagrees between views. Tour: FedEx.
3. Explore creating claims and adding items with bad and boundary data (missing, extra, null and wrong-type fields; amounts at 0, 0.01, 10000.00 and with three decimals; dates at the 90-day limit, in the future and impossible; the meals limit; very long and non-ASCII text) to discover what the API wrongly accepts and what it rejects badly. Tour: Antisocial.
4. Explore authorization and the claim rules with each role acting on other users' and other teams' claims, missing and wrong tokens, unknown ids, and actions from statuses the docs don't allow to discover who can see and change what, and whether the documented rules hold. Tours: Saboteur and Back alley.

Tokens used below: `$ALICE`, `$BOB`, `$CAROL`, `$FRANK`, `$DAVE` are tokens from `POST /auth/login` for the seed users. `B=http://localhost:3002`. "Today" was 2026-11-10.

## Findings

### F1: PATCH /claims/{id} accepts `status`, so an owner can mark their own claim approved or paid
- Severity: high
- Request: `curl -s -X PATCH "$B/claims/12" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"status":"approved","owner":"bob"}'`
- Expected: The docs say "any other field in the body, such as `status`, `owner` or `total`, is ignored". Status should stay `draft`.
- Actual: `200` with `"status":"approved"` (`owner` was ignored and stayed `alice`). Nobody reviewed it: `reviewed_by` and `submitted_at` are null. Finance could then pay it: `POST /claims/12/pay` as dave returned `200` with `"status":"paid","amount_paid":5`. Earlier, `PATCH /claims/11` with `{"title":"…","purpose":"Team summit","status":"paid","total":1}` returned `200` with `"status":"paid"`, and a later GET still showed `paid` (`total` was ignored).
- Reproduced: 2 times (claims 11 and 12), and the paid state was confirmed with GET.

### F2: Managers can approve or reject claims from other teams, including claims they cannot see
- Severity: high
- Request: `curl -s -X POST "$B/claims/3/review" -H "Authorization: Bearer $FRANK" -H 'Content-Type: application/json' -d '{"decision":"approve"}'`
- Expected: "Only a manager of the claim owner's team can review it." A claim you cannot see "behaves as if it did not exist: every endpoint returns `404`". Frank (mobile) should get `404` for bob's (platform) claim 3.
- Actual: `200` with `"status":"approved","reviewed_by":"frank"`. Carol (platform) approved erin's (mobile) claim 6: `200`, `"reviewed_by":"carol"`. Frank rejected bob's claim 15: `200`, `"status":"rejected","reviewed_by":"frank"`. Just before that, `GET /claims/15` as frank returned `404`. The role check itself works: dave (finance) got `403 forbidden` from the review endpoint.
- Reproduced: 3 times (claims 3, 6 and 15, by two different managers).

### F3: Paying an already-paid claim records another payment
- Severity: high
- Request: `curl -s -X POST "$B/claims/8/pay" -H "Authorization: Bearer $DAVE"` (sent twice)
- Expected: "If the claim is already `paid`, the call is safe to repeat: it returns `200` with the claim and changes nothing."
- Actual: The first call returned `200` with `"amount_paid":85`. The second returned `200` with `"amount_paid":170` and new `paid_at` and `updated_at` values. On claim 9 (total 37.8), the second pay gave `"amount_paid":75.6` and also replaced `payment_reference` (`PAY-9-A` became `PAY-9-B`).
- Reproduced: 2 times (claims 9 and 8).

### F4: A rejected claim cannot be resubmitted
- Severity: high
- Request: `curl -s -i -X POST "$B/claims/13/submit" -H "Authorization: Bearer $ALICE"` (claim 13 was rejected by carol, then an item was added)
- Expected: Submit is "Allowed from `draft` and from `rejected`". It should return `200` with `status: submitted`.
- Actual: `409 {"error":"invalid_state","message":"claim is rejected; only draft claims can be submitted"}`. The documented reject → submit path does not work.
- Reproduced: 2 times.

### F5: Items with amount 0 are accepted
- Severity: medium
- Request: `curl -s -X POST "$B/claims/16/items" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"date":"2026-11-05","category":"other","description":"zero","amount":0}'`
- Expected: "amount: Greater than 0". The response should be `400 validation_failed`.
- Actual: `201 {"id":27,…,"amount":0}`. Sending the item inside `POST /claims` also gave `201` (claim 17, total 0). A negative amount (-5) is correctly rejected with "amount must be greater than 0".
- Reproduced: 2 times (two endpoints).

### F6: The daily meals limit of 60.00 is not enforced
- Severity: medium
- Request: `curl -s -X POST "$B/claims" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"title":"Meals repro","currency":"EUR","items":[{"date":"2026-11-04","category":"meals","description":"Lunch","amount":30},{"date":"2026-11-04","category":"meals","description":"Dinner","amount":30.01}]}'`
- Expected: "An item that would take that day over 60.00 is rejected with `400`."
- Actual: `201`, total 60.01. On claim 16, meals of 60, then 0.01, then 5 on 2026-11-03 were all accepted (`201`), so that day reached 65.01.
- Reproduced: 3 times.

### F7: A date exactly 90 days ago is rejected
- Severity: low
- Request: `curl -s -X POST "$B/claims/16/items" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"date":"2026-08-12","category":"other","description":"day 90","amount":1}'`
- Expected: "If today is 2026-11-10, the earliest accepted date is 2026-08-12." Today was 2026-11-10, so the item should be accepted with `201`.
- Actual: `400 {"error":"validation_failed","message":"date must not be more than 90 days in the past","field":"date"}`. The date 2026-08-13 is accepted (`201`). The limit is off by one day.
- Reproduced: 2 times (items endpoint, and `POST /claims` with `field: items[0].date`).

### F8: List summaries and `sort=total` use a stale total after an item is removed
- Severity: medium
- Request: `curl -s "$B/claims?q=xylophone" -H "Authorization: Bearer $BOB"` (after `DELETE /claims/15/items/25` returned `204`)
- Expected: The summary `total` is the "Sum of the item amounts". It should match the detail view (40.99).
- Actual: The summary shows `"total":141`, which still includes the deleted 100.01 item. `GET /claims/15` shows `"total":40.99`. With `sort=total&per_page=2`, claim 15 was placed between 85 and 204.8, as if its total were 141. Claim 11 has the same problem: the summary shows 62.75 and the detail shows 50.25. The stale value appeared in the default list, `q` search, the `status`/`owner` filters (as carol) and dave's list. Adding items does update the summary (claim 13 showed 30.6).
- Reproduced: 2 claims (11 and 15), seen in 5+ list responses.

### F9: Search (`q`) does not match item descriptions
- Severity: medium
- Request: `curl -s "$B/claims?q=Release" -H "Authorization: Bearer $DAVE"`
- Expected: "A claim matches if its title or any of its item descriptions contains the text." Seed claim 8 has the item "Release It!", and dave can see claim 8.
- Actual: `200 {"data":[],"meta":{…,"total_count":0}}`. `q=ferry` and `q=FERRY` also returned nothing, although claim 15 has the item "Ferry crossing". Title search works, including case-insensitive non-ASCII: `q=ÜNÏCODE` found "Xylophone Ünïcode retreat".
- Reproduced: 3 times.

### F10: The default `per_page` is 10, not 20
- Severity: low
- Request: `curl -s "$B/claims" -H "Authorization: Bearer $DAVE"`
- Expected: "`per_page` … Default 20."
- Actual: `200` with 10 items and `"meta":{"page":1,"per_page":10,"total_count":11,"next_page":2}`.
- Reproduced: in every list request without `per_page` (5+).

### F11: `meta.next_page` points to an empty page on the last page
- Severity: low
- Request: `curl -s "$B/claims?per_page=4" -H "Authorization: Bearer $BOB"` (bob has 4 claims)
- Expected: "`meta.next_page` is the number of the next page that has results, or `null` on the last page."
- Actual: `"meta":{"page":1,"per_page":4,"total_count":4,"next_page":2}`. With `sort=total&per_page=2&page=2`, the response said `next_page: 3`, but page 3 returned `"data":[]`.
- Reproduced: 2 times.

## Questions
- F2 shows that the review endpoint skips the visibility check. I did not test whether a manager from another team can use other endpoints on claims they cannot see, such as pay or items.
- The 403 message for finance on review says "only a manager of the claimant's team can review this claim". So a team check seems to exist somewhere, but it does not stop managers from other teams.
- After F1, is it possible to PATCH a claim back from `paid` to `draft`? I did not try this. If so, items could be edited after payment.
- F8: I did not check whether the stale total also affects `amount_paid` when a claim is paid. That would require a claim whose summary and detail totals differ to be approved properly, and resubmit is blocked (F4).
- I did not check whether three-decimal amounts that are floating-point artefacts (for example 0.1+0.2-type values) are handled. `1.005` was correctly rejected.

## Coverage
- Charter 1 (requests 1–31): login for all six users; create with items; add and remove item; PATCH; submit; reject without and with comment; add item while rejected; resubmit; approve; pay; pay again; submit an empty claim (`400`, correct); delete a draft (`204`) then GET (`404`), both correct.
- Charter 2 (32–50): one distinctive claim (non-ASCII title and item text) traced through detail, `q` search (title and item), status+owner filter as manager, `sort=total`, pagination, default page size, and the views of the owner, manager of the team, manager of another team (`404`, correct), another employee (`404`, correct) and finance.
- Charter 3 (51–71): amounts 0, 0.01, 10000.00, 1.005, -5 and the string "12.50"; dates at 90 and 89 days ago, tomorrow and 2026-09-31; the meals limit; a 200-character description; an extra field; a whitespace-only title; an array body. Not covered: null fields, 201+ character descriptions, purpose > 500, lowercase currency on its own (its request also had a blank title, so only the title error was reported), invalid JSON, 413.
- Charter 4 (72–80): no token and bogus token (`401`, correct); review of other teams' claims; PATCH of another user's claim (`404`, correct); finance review (`403`, correct); delete of an approved claim (`409`, correct); employee paying another user's claim (`404`, correct). Not covered: lowercase `bearer`, ids like `007`/`0`/`abc`, an item id from a different claim, 405 and the `Allow` header, the trailing slash, a manager editing a claim (`403`), and paying a submitted claim (`409`).
- Requests used: 80 of 80.
