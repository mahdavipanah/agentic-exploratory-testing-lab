# Exploration report

## Charters
- Explore authorization and visibility rules across roles and teams (employee / manager / finance) to find access-control gaps.
- Explore item validation rules (date window, amount format, meals limit) to find boundary errors.
- Explore the claim lifecycle (submit / review / pay), including idempotent pay, to find state and money errors.
- Explore list search, sort and pagination to find mismatches with the docs.

Tokens used below: alice `3caf140cf4887622370652792e5643d7c5cae5107e51d10b`, carol (manager, platform) `18af724770ce8c10f82a53a92ee889dfb3056d6c25a7173d`, frank (manager, mobile) `e83b9352d2130d9fc350eac35ebc965430a1d0cbc1130e2e`, dave (finance) `7f141a5c68de34bf225ad11a687236216a214c1a68afff81`, erin `5b544426f02f5b20b136ce34d94ff6aa97f9f050af3a520d`.

## Findings

### F1: DELETE /claims/{id}/items/{itemId} deletes items that belong to other claims, including other users' claims and submitted or approved claims
- Severity: high
- Request: `curl -s -X DELETE http://localhost:3004/claims/11/items/7 -H 'Authorization: Bearer 3caf140cf4887622370652792e5643d7c5cae5107e51d10b'` (claim 11 is alice's draft; item 7 belongs to bob's **submitted** claim 3)
- Expected: `404`. The docs say: "The item must belong to the claim in the path" and the endpoint returns 404 when there is "no such item in this claim". Also, only the owner may change items, and only while the claim is `draft`/`rejected`.
- Actual: `204`. Afterwards `GET /claims/3` (as dave) shows item 7 is gone and the total drops from 204.8 to 185.9. bob's claim was changed by alice while it was under review. The same request with item 1 (alice's **approved** claim 1) returned `204`: claim 1 lost the item, and its total dropped from 251.4 to 161.5 after approval. Item 22 (alice's draft claim 12) also returned `204` and the item was removed. In that case the `updated_at` of claim 11 (the claim in the path) changed, and the `updated_at` of claim 12 (the claim that actually changed) did not.
- Reproduced: 3 times (items 22, 1, 7)

### F2: A manager can approve or reject claims from another team
- Severity: high
- Request: `curl -s -X POST http://localhost:3004/claims/9/review -H 'Authorization: Bearer e83b9352d2130d9fc350eac35ebc965430a1d0cbc1130e2e' -H 'Content-Type: application/json' -d '{"decision":"approve"}'` (frank, mobile manager; claim 9 belongs to alice, platform team)
- Expected: `404`. frank cannot see platform claims: `GET /claims/3` as frank returns 404, and per the docs every endpoint returns 404 for a claim you can't see. Docs: "Only a manager of the claim owner's team can review it."
- Actual: `200`, `"status":"approved","reviewed_by":"frank"`. frank also rejected bob's claim 3 (`200`, `"status":"rejected","reviewed_by":"frank"`). carol (platform) approved erin's mobile claim 6 (`200`, `"reviewed_by":"carol"`). Finance and owners are correctly refused with 403.
- Reproduced: 3 times (claims 9, 3, 6)

### F3: Paying a claim that is already paid records another payment
- Severity: high
- Request: `curl -s -X POST http://localhost:3004/claims/10/pay -H 'Authorization: Bearer 7f141a5c68de34bf225ad11a687236216a214c1a68afff81'`
- Expected: `200` with the claim unchanged. Docs: "If the claim is already `paid`, the call is safe to repeat: it returns `200` with the claim and changes nothing."
- Actual: `200`, but `amount_paid` goes from 299 to **598** (total is 299). `paid_at` and `updated_at` are reset to now, and `payment_reference` changes from `"PAY-2026-1006-02"` to `null`. On claim 8, paying with `PAY-1` and then `PAY-2` gave `amount_paid` 85, then **170**, and the reference was overwritten with `PAY-2`.
- Reproduced: 2 times (claims 8 and 10)

### F4: The meals limit only checks single items, not the total for a day
- Severity: medium
- Request: `curl -s -X POST http://localhost:3004/claims/11/items -H 'Authorization: Bearer 3caf140cf4887622370652792e5643d7c5cae5107e51d10b' -H 'Content-Type: application/json' -d '{"date":"2026-11-05","category":"meals","description":"Big dinner","amount":50}'` (claim 11 already had 60.00 + 0.01 of meals on 2026-11-05)
- Expected: `400`. Docs: "the `meals` items that share a date may add up to at most 60.00. An item that would take that day over 60.00 is rejected."
- Actual: `201`. Claim 11 now has 110.01 of meals on 2026-11-05. On 2026-11-07, two meals of 40 were both accepted (80 total). `POST /claims` with meals of 30 + 30.01 on the same date returned `201` (claim 12). A single meal of 61 is correctly rejected ("meals are limited to 60.00 per day").
- Reproduced: 4 times (0.01 add, 50 add, 40+40, create with 30+30.01)

### F5: Item amounts are silently truncated to a lower value
- Severity: medium
- Request: `curl -s -X POST http://localhost:3004/claims/12/items -H 'Authorization: Bearer 3caf140cf4887622370652792e5643d7c5cae5107e51d10b' -H 'Content-Type: application/json' -d '{"date":"2026-11-09","category":"other","description":"repro","amount":4.35}'`
- Expected: `201` with `"amount":4.35`. It is a valid amount with two decimal places.
- Actual: `201` with `"amount":4.34`. `1.13` was stored as `1.12`. The claim total uses the truncated values, so the employee is under-reimbursed. This looks like floating-point truncation (`floor(x*100)/100`).
- Reproduced: 2 times (1.13 and 4.35)

### F6: An item dated exactly 90 days ago is rejected
- Severity: low
- Request: `curl -s -X POST http://localhost:3004/claims/12/items -H 'Authorization: Bearer 3caf140cf4887622370652792e5643d7c5cae5107e51d10b' -H 'Content-Type: application/json' -d '{"date":"2026-08-12","category":"lodging","description":"edge","amount":2}'` (today is 2026-11-10)
- Expected: `201`. Docs: "If today is 2026-11-10, the earliest accepted date is 2026-08-12."
- Actual: `400 {"error":"validation_failed","message":"date must not be more than 90 days in the past","field":"date"}`. 2026-08-13 is accepted. This is an off-by-one error.
- Reproduced: 2 times

### F7: The `q` search does not match item descriptions
- Severity: medium
- Request: `curl -s 'http://localhost:3004/claims?q=Hotel' -H 'Authorization: Bearer 7f141a5c68de34bf225ad11a687236216a214c1a68afff81'`
- Expected: claims 1 and 6, which both have an item "Hotel, 1 night" and are visible to finance. Docs: "A claim matches if its title or any of its item descriptions contains the text."
- Actual: `200 {"data":[],"meta":{...,"total_count":0}}`. `q=HOTEL` gives the same result. `q=Taxi` returns only claim 9 (title match) and leaves out claim 3, whose item is "Taxi to client office". Title matching is case-insensitive and works.
- Reproduced: 3 times (`HOTEL`, `Hotel`, `Taxi`)

### F8: The default `per_page` is 10, but the docs say 20
- Severity: low
- Request: `curl -s 'http://localhost:3004/claims?q=Hotel' -H 'Authorization: Bearer 7f141a5c68de34bf225ad11a687236216a214c1a68afff81'`
- Expected: `meta.per_page` is 20 when `per_page` is not given. Docs: "Claims per page, 1 to 50. Default 20."
- Actual: `"meta":{"page":1,"per_page":10,...}`
- Reproduced: 5 times (every list request without `per_page`)

## Questions
- F8: I could not check whether lists without `per_page` really stop at 10 items, because no user could see more than 10 claims. Only `meta.per_page` was confirmed.
- F2: frank gets 404 on `GET /claims/3` but can review it. The review endpoint seems to skip both the visibility check and the team check. I did not test whether a manager can review a draft claim of another team (it should get 404 or 409).
- PATCH with a `title` key and an unchanged state: I did not check whether `updated_at` changes on an empty `{}` PATCH.
- I did not test resubmitting a rejected claim (no bob token was used, and alice had no rejected claim), oversized bodies (413), or `invalid_url`.

## Coverage
- Explored: login, listing per role (visibility of drafts and other teams), GET by id (including `004`), claim creation (trimming, empty purpose becoming null, empty items, manager forbidden), item validation (date window edges, an invalid calendar date, future dates, amount bounds and decimals, string amounts, blank description), the meals limit, deleting items across claims, PATCH (null title, lower-case currency, non-editable state, cross-user 404 and 403), DELETE of a non-draft, submit without items, review (cross-team, finance, owner, wrong state), pay (first payment, repeat, rejected claim, non-finance), list pagination/search/sort/bounds, and 405 with the `Allow` header, invalid JSON, a non-object body, and a bad token.
- Not explored: resubmit after rejection, the 413 body limit, `invalid_url`, the `owner` filter, `-total` sort ties, `next_page` with more data, the reference length limit on pay, review comment length.
- Requests used: 79 of 80.
