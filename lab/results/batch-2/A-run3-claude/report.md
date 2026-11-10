# Exploration report

## Charters
- Visibility and access control: can users see or change claims that are not theirs (list filters, GET, writes, review, item routes)?
- Claim lifecycle: submit, review, resubmit, pay, and repeated pay.
- Item validation rules: dates, amounts, meals limit, at the boundaries.
- List query parameters: search, filters, sort, pagination and defaults.

Tokens used below (from `POST /auth/login`): alice=`7445fb01e55c6d5f881832bb611c49978c42df962564d919`, bob=`266a8845c4cb5015ffe2f3f689d179beab00389f7230d51d`, erin=`a962dc5686bdd1ff5c3f55b58077e428dfb8079db240cc3e`, carol=`d1d1b5396312a32a79766412359829bbfafe1886b0ddd3df`, frank=`a9e8b0d1d07d6f1854635df1b243c0bd3ff3cc7ba2358d70`, dave=`5a1cd492ea7a9dd52edbecd0c8ef6b362c541bc99db7a26d`.

## Findings

### F1: PATCH lets the owner set `status` directly, so they can approve their own claim and get it paid
- Severity: high
- Request: `curl -s -X PATCH http://localhost:3003/claims/12 -H "Authorization: Bearer 7445fb01e55c6d5f881832bb611c49978c42df962564d919" -H 'Content-Type: application/json' -d '{"status":"approved"}'`
- Expected: `status` is ignored and the claim stays `draft` (docs: "any other field in the body, such as `status`, `owner` or `total`, is ignored").
- Actual: `200`, `"status":"approved"` with `reviewed_by: null`, `submitted_at: null`. Dave could then pay it: `POST /claims/12/pay` returned `200`, `"status":"paid","amount_paid":10065`. (`total` in the body was ignored.)
- Reproduced: 2 times (bob on rejected claim 5 with `{"status":"approved","total":1}` → `approved`; alice on draft claim 12 → `approved`, then paid).

### F2: Paying an already-paid claim records another payment
- Severity: high
- Request: `curl -s -X POST http://localhost:3003/claims/1/pay -H "Authorization: Bearer 5a1cd492ea7a9dd52edbecd0c8ef6b362c541bc99db7a26d"` (sent twice)
- Expected: Second call returns `200` and changes nothing (docs: "it returns 200 with the claim and changes nothing").
- Actual: `200`, `amount_paid` doubled to `502.8` (total `251.4`), and `paid_at`/`updated_at` changed. On claim 8, the second call also replaced `payment_reference` (`PAY-1` → `PAY-2`) and `amount_paid` went `85` → `170`. Seed paid claim 2: `amount_paid` `798` for total `399`.
- Reproduced: 3 times (claims 8, 1, 2).

### F3: A manager can review claims from another team
- Severity: high
- Request: `curl -s -X POST http://localhost:3003/claims/6/review -H "Authorization: Bearer d1d1b5396312a32a79766412359829bbfafe1886b0ddd3df" -H 'Content-Type: application/json' -d '{"decision":"approve"}'`
- Expected: `404`. Carol (platform) cannot see erin's mobile claim 6 (`GET /claims/6` as carol returns 404). Only a manager of the owner's team may review.
- Actual: `200`, `"status":"approved","reviewed_by":"carol"`.
- Reproduced: 2 times (also frank (mobile) rejected bob's platform claim 3 → `200`, `"reviewed_by":"frank"`).

### F4: Any user can delete items from another user's claim through their own claim's path
- Severity: high
- Request: `curl -s -X DELETE http://localhost:3003/claims/13/items/18 -H "Authorization: Bearer 266a8845c4cb5015ffe2f3f689d179beab00389f7230d51d"`
- Expected: `404` (item 18 belongs to alice's claim 11, not bob's claim 13; docs: "The item must belong to the claim in the path").
- Actual: `204`. `GET /claims/11` as alice then showed items 18 and 19 gone from alice's draft claim (total dropped to 66.01).
- Reproduced: 2 times (items 18 and 19).

### F5: `owner` filter on GET /claims bypasses visibility, exposing other users' and other teams' claims, including drafts
- Severity: high
- Request: `curl -s "http://localhost:3003/claims?owner=bob" -H "Authorization: Bearer 7445fb01e55c6d5f881832bb611c49978c42df962564d919"`
- Expected: Empty list. Alice (employee) can see only her own claims (docs: owner "narrows the list ... among the claims you can see").
- Actual: `200` with bob's claims 3, 8, 5. As carol (platform manager), `?owner=erin` returned erin's mobile claims including draft 7. As carol, `?owner=alice` included alice's draft 4. As dave (finance), `?owner=erin` included draft 7.
- Reproduced: 4 times.

### F6: Rejected claims cannot be resubmitted
- Severity: medium
- Request: `curl -s -X POST http://localhost:3003/claims/9/submit -H "Authorization: Bearer 7445fb01e55c6d5f881832bb611c49978c42df962564d919"` (after carol rejected claim 9)
- Expected: `200`, status `submitted` (docs: submit is allowed "from `draft` and from `rejected`").
- Actual: `409 {"error":"invalid_state","message":"claim is rejected; only draft claims can be submitted"}`
- Reproduced: 2 times (claims 3 and 9).

### F7: Cumulative meals limit (60.00 per day per claim) is not enforced
- Severity: medium
- Request: `curl -s -X POST http://localhost:3003/claims -H "Authorization: Bearer 7445fb01e55c6d5f881832bb611c49978c42df962564d919" -H 'Content-Type: application/json' -d '{"title":"Meals create","currency":"EUR","items":[{"date":"2026-11-08","category":"meals","description":"M1","amount":40},{"date":"2026-11-08","category":"meals","description":"M2","amount":25}]}'`
- Expected: `400`. 40 + 25 = 65 is over 60.00 for one day.
- Actual: `201`, claim created with `total: 65`. Through `POST /claims/11/items`: adding meals 0.01 on a day that already had 60.00 → `201`; 40 then 25 on 2026-11-09 → both `201`. Only a single item over 60 (amount 61) is rejected.
- Reproduced: 3 times.

### F8: Amount 0 is accepted
- Severity: medium
- Request: `curl -s -X POST http://localhost:3003/claims/12/items -H "Authorization: Bearer 7445fb01e55c6d5f881832bb611c49978c42df962564d919" -H 'Content-Type: application/json' -d '{"date":"2026-11-07","category":"other","description":"zero","amount":0}'`
- Expected: `400` (docs: amount "Greater than 0").
- Actual: `201`, item with `"amount":0`.
- Reproduced: 2 times (also inside `POST /claims` as bob, claim 13).

### F9: Earliest allowed item date (today − 90 days) is rejected
- Severity: low
- Request: `curl -s -X POST http://localhost:3003/claims/11/items -H "Authorization: Bearer 7445fb01e55c6d5f881832bb611c49978c42df962564d919" -H 'Content-Type: application/json' -d '{"date":"2026-08-12","category":"travel","description":"Earliest","amount":1}'`
- Expected: `201`. The docs say that when today is 2026-11-10, "the earliest accepted date is 2026-08-12". Today is 2026-11-10 (server `Date` header).
- Actual: `400 {"message":"date must not be more than 90 days in the past","field":"date"}`. 2026-08-13 is accepted.
- Reproduced: 2 times.

### F10: Search `q` does not match item descriptions
- Severity: medium
- Request: `curl -s "http://localhost:3003/claims?q=hotel" -H "Authorization: Bearer 7445fb01e55c6d5f881832bb611c49978c42df962564d919"`
- Expected: Claim 1 is returned. Its item "Hotel, 1 night" matches (docs: "A claim matches if its title or any of its item descriptions contains the text").
- Actual: `200`, `data: []`, `total_count: 0`. `q=dinner` and `q=Dinner` as dave also returned nothing, even though claims 1 and 6 have "Dinner" items. Title search works (`q=TAXI` → claim 9).
- Reproduced: 3 times.

### F11: Default `per_page` is 10, not 20
- Severity: low
- Request: `curl -s "http://localhost:3003/claims" -H "Authorization: Bearer 7445fb01e55c6d5f881832bb611c49978c42df962564d919"`
- Expected: `meta.per_page` is 20 (docs: "Default 20").
- Actual: `200`, `"meta":{"page":1,"per_page":10,...}`
- Reproduced: many times (every list call without `per_page`).

### F12: Invalid `sort` value causes a 500
- Severity: medium
- Request: `curl -s "http://localhost:3003/claims?sort=bogus" -H "Authorization: Bearer 7445fb01e55c6d5f881832bb611c49978c42df962564d919"`
- Expected: `400 validation_failed` (docs: "Any other value returns 400").
- Actual: `500 {"error":"internal_error","message":"unexpected server error"}`
- Reproduced: 2 times (`sort=bogus` as alice, `sort=amount` as dave).

## Questions
- `updated_at` on alice's claim 11 did not change after bob removed its items through `/claims/13/items/...` (F4). A normal item removal (bob on his own claim 13) did update `updated_at`. This is probably a side effect of F4.
- I did not check that `GET /claims/{id}` for other users' claims stays 404 once F5 has exposed the ids. It did stay 404 for the drafts I tried before.
- Error precedence is not documented. When a manager PATCHes a claim that is not in an editable state, should it return 403 or 409? I did not test this.

## Coverage
Explored: login for all six users; list visibility per role; `status`/`owner`/`q`/`sort`/`page`/`per_page` parameters; GET visibility of drafts and other teams' claims; create with items; item validation (date bounds, invalid calendar date, future date, amount bounds, decimals, string amount, zero, meals limit); cross-user PATCH, item add and item delete; review (cross-team, rejection without a comment); resubmitting rejected claims; submitting an empty claim; pay (approved, repeated, already paid, wrong state); manager creating a claim; id `007`.

Behaved as documented: draft visibility via GET, per_page > 50 → 400, `007` → 404, manager create → 403, empty-claim submit → 400, reject without a comment → 400, pay on a submitted claim → 409, title trimming, empty purpose → null, float total 0.1 + 0.2 = 0.3.

Not explored: DELETE /claims/{id}; PATCH validation (title/purpose length, currency, null title); description length and trimming; invalid category; `invalid_json`/`invalid_body`/413 handling; 405 with `Allow` header; trailing slash; lowercase `bearer` scheme; missing or invalid tokens; `reference` length on pay; `status` filter; `-total` sort ordering and ties; `page=0` or invalid page.

Requests used: 80 of 80.
