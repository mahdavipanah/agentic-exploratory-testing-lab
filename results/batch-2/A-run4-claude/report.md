# Exploration report

## Charters
- Check visibility and authorization rules (who can see, edit, review and pay what) for every role.
- Check the claim lifecycle state machine, including idempotent pay.
- Check item validation rules (dates, amounts, meals limit) at their boundaries.
- Check list filtering, search, sorting and pagination against the docs.

Tokens used below: ALICE=17bc4c80…, BOB=2f34d85e…, ERIN=7388c6cb…, CAROL=144e21b2…, FRANK=83fa6a07…, DAVE=da2cf69a… (each from `POST /auth/login`). Server date was 2026-11-10 (confirmed via `created_at` of new claims).

## Findings

### F1: Manager of another team can approve or reject claims they cannot even see
- Severity: high
- Request: `curl -s -X POST http://localhost:3003/claims/9/review -H "Authorization: Bearer $FRANK" -H 'Content-Type: application/json' -d '{"decision":"approve"}'`
- Expected: 404. Claim 9 belongs to alice (team platform). Frank manages mobile, so he cannot see it ("A claim you are not allowed to see behaves as if it did not exist: every endpoint returns 404"). Only "a manager of the owner's team" may review.
- Actual: 200, `"status":"approved","reviewed_by":"frank"`. `GET /claims/3` as frank returns 404, but `POST /claims/3/review` as frank with `{"decision":"reject","comment":"cross-team"}` returned 200 with `"status":"rejected","reviewed_by":"frank"`.
- Reproduced: 2 times (claim 9 approve, claim 3 reject)

### F2: The owner can set `status` with PATCH and approve their own claim
- Severity: high
- Request: `curl -s -X PATCH http://localhost:3003/claims/5 -H "Authorization: Bearer $BOB" -H 'Content-Type: application/json' -d '{"title":"Team lunch v2","status":"approved","total":1}'`
- Expected: `status` is ignored ("any other field in the body, such as `status`, `owner` or `total`, is ignored"). The claim stays `rejected`.
- Actual: 200, `"status":"approved"` (total was correctly ignored). Finance then paid it: `POST /claims/5/pay` returned 200 with `"status":"paid","amount_paid":58`. So an employee can skip manager review and get paid.
- Reproduced: 2 times (claim 5, and claim 3 with `{"status":"approved"}` → 200 `"status":"approved"`)

### F3: Paying an already paid claim records another payment
- Severity: high
- Request: `curl -s -X POST http://localhost:3003/claims/2/pay -H "Authorization: Bearer $DAVE"`
- Expected: 200, nothing changed ("If the claim is already `paid`, the call is safe to repeat: it returns `200` with the claim and changes nothing.")
- Actual: 200 with `"amount_paid":798` (total 399), and new `paid_at`/`updated_at`. On claim 9 the second pay with `{"reference":"REF-2"}` changed `amount_paid` from 37.8 to 75.6 and `payment_reference` from REF-1 to REF-2.
- Reproduced: 2 times (claims 9 and 2)

### F4: DELETE item does not check that the item belongs to the claim in the path
- Severity: high
- Request: `curl -s -X DELETE http://localhost:3003/claims/11/items/9 -H "Authorization: Bearer $ALICE"`
- Expected: 404 ("The item must belong to the claim in the path"; "no such item in this claim"). Item 9 is in bob's claim 5.
- Actual: 204. Bob's claim 5 (status `paid`) now has `"items":[],"total":0`. The same happened with `DELETE /claims/11/items/1`, which removed an item from alice's **approved** claim 1 (total 251.4 → 161.5), and `DELETE /claims/13/items/16`, which emptied the paid claim 9. Anyone with an editable draft can delete items from any claim, in any status, owned by any user.
- Reproduced: 3 times

### F5: `owner` filter on GET /claims bypasses visibility, exposing other users' claims and drafts
- Severity: high
- Request: `curl -s "http://localhost:3003/claims?owner=alice" -H "Authorization: Bearer $BOB"`
- Expected: Only claims bob can see that belong to alice, which is none ("Narrows the list to that user's claims, among the claims you can see").
- Actual: 200, `total_count":7`, all of alice's claims including drafts 4, 11, 12, 13. Also `?owner=erin` as carol (platform manager) returned erin's mobile claims including draft 7, and `?owner=erin&status=draft` as dave (finance) returned draft 7.
- Reproduced: 3 times

### F6: Meals limit of 60.00 per day is not applied across items
- Severity: medium
- Request: `curl -s -X POST http://localhost:3003/claims -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"title":"Meals","currency":"EUR","items":[{"date":"2026-11-09","category":"meals","description":"a","amount":40},{"date":"2026-11-09","category":"meals","description":"b","amount":30}]}'`
- Expected: 400. Meals items on the same date in one claim may add up to at most 60.00.
- Actual: 201, total 70. Only a single item over 60 is rejected (61 → 400 "meals are limited to 60.00 per day"). Via `POST /claims/11/items`, meals on 2026-11-10 reached 40+20+5 = 65 with all items accepted (201).
- Reproduced: 2 times (POST /claims and POST /claims/{id}/items)

### F7: Amount 0 is accepted
- Severity: medium
- Request: `curl -s -X POST http://localhost:3003/claims -H "Authorization: Bearer $ERIN" -H 'Content-Type: application/json' -d '{"title":"Zero","currency":"USD","items":[{"date":"2026-11-01","category":"other","description":"free","amount":0}]}'`
- Expected: 400. Amount must be "Greater than 0" (negative -5 is correctly rejected with "amount must be greater than 0").
- Actual: 201, item with `"amount":0`.
- Reproduced: 2 times (also `POST /claims/11/items` with amount 0 → 201)

### F8: Earliest allowed item date (today − 90 days) is rejected
- Severity: medium
- Request: `curl -s -X POST http://localhost:3003/claims/11/items -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"date":"2026-08-12","category":"travel","description":"edge","amount":5}'`
- Expected: 201. Docs: "If today is 2026-11-10, the earliest accepted date is 2026-08-12".
- Actual: 400 `{"error":"validation_failed","message":"date must not be more than 90 days in the past","field":"date"}`. 2026-08-13 is accepted, so the boundary is off by one day.
- Reproduced: 2 times (POST /claims and POST /claims/{id}/items)

### F9: Search `q` does not match item descriptions
- Severity: medium
- Request: `curl -s "http://localhost:3003/claims?q=Dinner" -H "Authorization: Bearer $DAVE"`
- Expected: Claim 1 is returned, because its item "Dinner" contains the text ("A claim matches if its title or any of its item descriptions contains the text").
- Actual: 200 `{"data":[],"meta":{...,"total_count":0}}`. Same for `q=hotel` and `q=HOTEL` (claim 1 item "Hotel, 1 night"). Title search works (`q=TAXI` finds claim 9).
- Reproduced: 3 times

### F10: Default `per_page` is 10, not 20
- Severity: low
- Request: `curl -s "http://localhost:3003/claims" -H "Authorization: Bearer $DAVE"`
- Expected: `meta.per_page` 20 (docs: "Default 20").
- Actual: 200, `"meta":{"page":1,"per_page":10,...}`.
- Reproduced: many times (every list call without `per_page`)

## Questions
- After F4 removed items from approved/paid claims, `updated_at` of those claims did not change (claim 1 still `2026-10-09T14:03:00.000Z`). This follows from F4. I did not check whether `updated_at` changes correctly for normal item add/remove.
- Paid claims can end up with `amount_paid` ≠ `total` (e.g. claim 9: total 0, amount_paid 75.6). This is a result of F3/F4, not checked separately.
- I did not check whether `POST /claims` fails atomically when a later item is invalid. Also not checked: `invalid_json`, `invalid_body`, the 413 limit, and trailing-slash handling.

## Coverage
Explored: login for all six users; list visibility per role; GET visibility (drafts, other teams, other employees); pagination and `sort=total`; validation for `page`, `per_page` and `q`; `owner` filter; item date, amount, description and meals rules; PATCH (mass assignment, null title, non-owner 403, wrong state 409); review permissions; pay and repeat pay; DELETE claim in wrong state; DELETE item; submit with no items; id `007` → 404; PUT → 405 with Allow header.
Not covered: `sort=created_at`/`-total`, status filter validation, reject without comment, review comment length, pay reference length, unauthenticated requests (401), malformed JSON/body types, 413, currency PATCH, purpose rules, resubmitting a rejected claim.
Requests used: 76.
