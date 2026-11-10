# Exploration report

## Charters
- Check role-based visibility and permissions (who can see, review, pay, edit, delete).
- Check the claim lifecycle (submit, review, re-submit, pay, repeated pay).
- Check item validation rules (dates, amounts, meals limit) on both `POST /claims` and `POST /claims/{id}/items`.
- Check list features (search, sort, paging, query validation).

Tokens used below (from `POST /auth/login`): ALICE=`00c136c8ed40f8853789a408e4819925a353eaced886f4d2`, BOB=`433d2c609d91fe802401a56b506ecab56c19157d1aa88eb1`, ERIN=`488556f940d36959cf604df6d0f88bc1fa6991d8cac183e7`, CAROL=`bafa428a91ea11511b4f1f85b84e477f979c3ff3d6e97299`, FRANK=`55695c0565a528c97420e6222d5ce853a21c1d25e85245a3`, DAVE=`d88fbafd00a9fe2e037a93c660c7ce3ffd2fffc3ac93bd34`.

## Findings

### F1: A manager can review claims from another team, which they cannot even see
- Severity: high
- Request: `curl -s -X POST http://localhost:3004/claims/3/review -H 'Authorization: Bearer 55695c0565a528c97420e6222d5ce853a21c1d25e85245a3' -H 'Content-Type: application/json' -d '{"decision":"approve"}'` (frank, a mobile manager, on bob's platform claim 3)
- Expected: `404 not_found`. The docs say managers see only their own team's claims, a claim you cannot see "behaves as if it did not exist: every endpoint returns 404", and only "a manager of the owner's team" may review. (`GET /claims/6` as carol correctly returns 404.)
- Actual: `200`, claim 3 `"status":"approved"`. Also: frank rejected alice's claim 9 → `200`, `"status":"rejected","reviewed_by":"frank"`. Carol (platform) approved erin's mobile claim 6 → `200`, `"status":"approved"`.
- Reproduced: 3 times (claims 3, 9, 6; both directions)

### F2: PATCH accepts `status`, so an owner can approve or "pay" their own claim
- Severity: high
- Request: `curl -s -X PATCH http://localhost:3004/claims/12 -H 'Authorization: Bearer 00c136c8ed40f8853789a408e4819925a353eaced886f4d2' -H 'Content-Type: application/json' -d '{"status":"approved"}'`
- Expected: Docs: "any other field in the body, such as `status`, `owner` or `total`, is ignored". Status should stay `draft`.
- Actual: `200` with `"status":"approved"`. Then `POST /claims/12/pay` as dave → `200`, `"status":"paid","amount_paid":60.01,"reviewed_by":null`. The claim was paid without any submission or review. Earlier, `PATCH /claims/11` with `{"status":"paid",...}` → `200`, `"status":"paid"` with `paid_at:null`, `amount_paid:null`. (`owner` and `total` were ignored correctly.)
- Reproduced: 2 times (claims 11 and 12)

### F3: Deleting an item does not check that it belongs to the claim in the path; any employee can delete items from other users' approved claims
- Severity: high
- Request: `curl -s -X DELETE http://localhost:3004/claims/11/items/5 -H 'Authorization: Bearer 00c136c8ed40f8853789a408e4819925a353eaced886f4d2'` (claim 11 is alice's draft; item 5 belongs to bob's approved claim 3)
- Expected: `404` — docs: "The item must belong to the claim in the path" / "no such item in this claim".
- Actual: `204`. Afterwards `GET /claims/3` (as carol) shows `"status":"approved"`, item 5 gone, `"total":50.6` (was 204.8). Earlier `DELETE /claims/11/items/27` (item of alice's claim 13) → `204` and item 27 removed from claim 13.
- Reproduced: 2 times

### F4: Paying an already-paid claim records another payment
- Severity: high
- Request: `curl -s -X POST http://localhost:3004/claims/2/pay -H 'Authorization: Bearer d88fbafd00a9fe2e037a93c660c7ce3ffd2fffc3ac93bd34'`
- Expected: Docs: "If the claim is already paid, the call is safe to repeat: it returns 200 with the claim and changes nothing." `amount_paid` should stay equal to `total`.
- Actual: `200` with `"total":399,"amount_paid":798`, and new `paid_at`/`updated_at`. On claim 8: first pay → `amount_paid:85, payment_reference:"PAY-1"`; second pay → `amount_paid:170, payment_reference:"PAY-2"`, `paid_at` changed.
- Reproduced: 2 times (claims 8 and 2)

### F5: A rejected claim cannot be submitted again
- Severity: medium
- Request: `curl -s -X POST http://localhost:3004/claims/5/submit -H 'Authorization: Bearer 433d2c609d91fe802401a56b506ecab56c19157d1aa88eb1'`
- Expected: `200`, status `submitted`. Docs: submit is "Allowed from `draft` and from `rejected`".
- Actual: `409 {"error":"invalid_state","message":"claim is rejected; only draft claims can be submitted"}`
- Reproduced: 3 times (claim 5 twice, claim 9 once)

### F6: Meals daily limit of 60.00 is only checked per item, not per day
- Severity: medium
- Request: `curl -s -X POST http://localhost:3004/claims -H 'Authorization: Bearer 00c136c8ed40f8853789a408e4819925a353eaced886f4d2' -H 'Content-Type: application/json' -d '{"title":"meals","currency":"EUR","items":[{"date":"2026-11-04","category":"meals","description":"a","amount":50},{"date":"2026-11-04","category":"meals","description":"b","amount":50}]}'`
- Expected: `400` — "meals items that share a date may add up to at most 60.00".
- Actual: `201`, claim 13 with two meals items on 2026-11-04 totalling 100. Via `POST /claims/13/items`, two 50.00 meals on 2026-11-05 → both `201`. Via `POST /claims/12/items`, 40 + 20 + 0.01 on 2026-11-02 → all `201`. A single 60.01 item is rejected (`400 "meals are limited to 60.00 per day"`).
- Reproduced: 3 times

### F7: Item amount 0 is accepted
- Severity: medium
- Request: `curl -s -X POST http://localhost:3004/claims/11/items -H 'Authorization: Bearer 00c136c8ed40f8853789a408e4819925a353eaced886f4d2' -H 'Content-Type: application/json' -d '{"date":"2026-11-01","category":"other","description":"d","amount":0}'`
- Expected: `400` — amount must be "Greater than 0". (-5 is rejected correctly with "amount must be greater than 0".)
- Actual: `201 {"id":20,...,"amount":0}`. Also in `POST /claims` with an item of `amount:0` → `201` (claim 12, total 0).
- Reproduced: 2 times

### F8: Search `q` does not match item descriptions
- Severity: medium
- Request: `curl -s 'http://localhost:3004/claims?q=Hotel' -H 'Authorization: Bearer d88fbafd00a9fe2e037a93c660c7ce3ffd2fffc3ac93bd34'`
- Expected: Claim 1 (approved, item "Hotel, 1 night") is returned — docs: "A claim matches if its title or any of its item descriptions contains the text."
- Actual: `200`, `"total_count":0`. Same for `q=HOTEL` (0) and `q=Release` (0; claim 8 has item "Release It!"). `q=taxi` returns only claim 9 (title match), not claim 3 (item "Taxi to client office").
- Reproduced: 4 times

### F9: Earliest allowed item date (today − 90 days) is rejected
- Severity: low
- Request: `curl -s -X POST http://localhost:3004/claims/11/items -H 'Authorization: Bearer 00c136c8ed40f8853789a408e4819925a353eaced886f4d2' -H 'Content-Type: application/json' -d '{"date":"2026-08-12","category":"travel","description":"d","amount":1}'`
- Expected: `201` — docs: "If today is 2026-11-10, the earliest accepted date is 2026-08-12". Server date is 2026-11-10 (from `Date` header and timestamps).
- Actual: `400 {"message":"date must not be more than 90 days in the past","field":"date"}`. Same in `POST /claims` (`field: items[0].date`). 2026-08-13 is accepted.
- Reproduced: 2 times

### F10: Default `per_page` is 10, not 20
- Severity: low
- Request: `curl -s 'http://localhost:3004/claims' -H 'Authorization: Bearer d88fbafd00a9fe2e037a93c660c7ce3ffd2fffc3ac93bd34'`
- Expected: `meta.per_page` 20 (docs: "Default 20").
- Actual: `200`, 10 claims, `"meta":{"page":1,"per_page":10,"total_count":10,"next_page":2}`
- Reproduced: 5 times (every list request without `per_page`)

### F11: `next_page` points to an empty page when the total is an exact multiple of `per_page`
- Severity: low
- Request: `curl -s 'http://localhost:3004/claims?per_page=5&page=2' -H 'Authorization: Bearer d88fbafd00a9fe2e037a93c660c7ce3ffd2fffc3ac93bd34'`
- Expected: `next_page: null` — 10 claims, page 2 of 5 is the last. Docs: "next_page is the number of the next page that has results, or null on the last page."
- Actual: `200`, 5 claims, `"meta":{"page":2,"per_page":5,"total_count":10,"next_page":3}`. Also default request: `total_count:10, per_page:10, next_page:2`, and `?page=2` returns an empty `data`. (With `per_page=3`, page 4 correctly gives `null`.)
- Reproduced: 2 times

## Questions
- F3: I only tried it as an employee who owns a draft. It may also work for paths through claims in other states, or for other roles.
- F2: Can PATCH also change `reviewed_by`, `amount_paid` or `submitted_at`? Not tested; `owner` and `total` were ignored.
- After F1, a manager can review a claim they cannot `GET`. I didn't check whether other actions (e.g. pay) have the same visibility gap for out-of-team users.
- Not tested: tie ordering by id, `owner` filter, invalid JSON / non-object bodies, 413, 405 with `Allow` header, trailing slash, `bearer` lower-case scheme, `reference` > 64 chars, comment > 500 chars, title/purpose length limits.

## Coverage
Explored: login for all six users; list visibility per role; GET visibility (cross-team, drafts, other employees); review/pay permissions; pay and repeated pay; item validation (date bounds, invalid calendar date, amount bounds/decimals/type, empty description, meals limit) on both endpoints; item delete; PATCH including forbidden fields, null title and lower-case currency on a non-editable claim; submit (empty claim, draft, rejected); rejection comment validation; non-owner PATCH/DELETE; list paging, sort by total, search, query validation, `001` id.
Not reached: items listed under Questions.
Requests used: 78 of 80.
