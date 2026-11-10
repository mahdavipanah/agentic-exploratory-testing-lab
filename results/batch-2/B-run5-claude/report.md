# Exploration report

Tokens below: `$ALICE`, `$BOB`, `$ERIN`, `$CAROL`, `$FRANK`, `$DAVE` = tokens from `POST /auth/login` for each seed user. `B=http://localhost:3002`.

## Charters
1. Explore the claim lifecycle (create, add and remove items, edit, submit, reject, resubmit, approve, pay, then read again) with the seed users of each role to discover whether every step does what the docs say and returns the documented status code. (Tour: Guidebook)
2. Explore one claim's data across every view (detail, list summaries, search, status and owner filters, sorting, pagination, and each role's view of it) with a single distinctive claim to discover data that changes, disappears or disagrees between views. (Tour: FedEx)
3. Explore creating claims and adding items with bad and boundary data (missing, extra, null and wrong-type fields; amounts at 0, 0.01, 10000.00 and with three decimals; dates at the 90-day limit, in the future and impossible; the meals limit; very long and non-ASCII text) to discover what the API wrongly accepts and what it rejects badly. (Tour: Antisocial)
4. Explore authorization and the claim rules with each role acting on other users' and other teams' claims, missing and wrong tokens, unknown ids, and actions from statuses the docs don't allow to discover who can see and change what, and whether the documented rules hold. (Tours: Saboteur and Back alley)

## Findings

### F1: PATCH /claims/{id} applies the `status` field, so an owner can set their own claim to approved or paid
- Severity: high
- Request: `curl -s -X PATCH "$B/claims/18" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"status":"approved","owner":"bob"}'`
- Expected: Docs say "any other field in the body, such as `status`, `owner` or `total`, is ignored". Status should stay `draft`.
- Actual: 200 with `"status":"approved"` (`owner` was ignored correctly). Then `curl -s -X POST "$B/claims/18/pay" -H "Authorization: Bearer $DAVE"` returned 200 `"status":"paid","amount_paid":0,"reviewed_by":null`. The claim was paid without a review and with no items. Earlier, `PATCH /claims/11` with `{"title":"...","purpose":"","currency":"GBP","status":"paid","total":1}` returned 200 `"status":"paid"` (with `paid_at`/`amount_paid` null). The change was saved: GET as alice and as dave both showed it as paid, and submitting it then returned 409 "claim is paid".
- Reproduced: 2 times (claims 11 and 18)

### F2: Paying an already-paid claim records another payment
- Severity: high
- Request: `curl -s -X POST "$B/claims/9/pay" -H "Authorization: Bearer $DAVE" -H 'Content-Type: application/json' -d '{"reference":"PAY-2"}'` (claim 9 already paid with total 37.8)
- Expected: "If the claim is already `paid`, the call is safe to repeat: it returns `200` with the claim and changes nothing."
- Actual: 200 with `"amount_paid":75.6`, a new `paid_at`, `"payment_reference":"PAY-2"`. A third call with no body returned `"amount_paid":113.4,"payment_reference":null`. GET as alice confirms `amount_paid` 113.4 with `total` 37.8.
- Reproduced: 2 times (2nd and 3rd pay calls)

### F3: A rejected claim cannot be resubmitted
- Severity: high
- Request: `curl -s -X POST "$B/claims/5/submit" -H "Authorization: Bearer $BOB"` (seed claim 5, status rejected)
- Expected: Submit is allowed from `draft` and `rejected` (lifecycle table and the POST /claims/{id}/submit section).
- Actual: 409 `{"error":"invalid_state","message":"claim is rejected; only draft claims can be submitted"}`
- Reproduced: 2 times (alice's claim 12 after it was rejected and edited, and bob's seed claim 5)

### F4: Managers can review claims from other teams
- Severity: high
- Request: `curl -s -X POST "$B/claims/3/review" -H "Authorization: Bearer $FRANK" -H 'Content-Type: application/json' -d '{"decision":"approve"}'` (claim 3 belongs to bob, team platform. Frank manages mobile.)
- Expected: "Only a manager of the claim owner's team can review it." Frank can't see claim 3, so the response should be 404. `GET /claims/3` as frank does return 404.
- Actual: 200, and claim 3 became `"status":"approved"`. Same the other way round: `curl -s -X POST "$B/claims/6/review" -H "Authorization: Bearer $CAROL" ... -d '{"decision":"reject","comment":"cross-team"}'` on erin's mobile claim 6 returned the claim, and erin now sees claim 6 as `rejected`.
- Reproduced: 2 times (frank→claim 3, carol→claim 6)

### F5: The `owner` list filter ignores visibility, so anyone can list another user's claims, including drafts
- Severity: high
- Request: `curl -s "$B/claims?owner=alice" -H "Authorization: Bearer $BOB"`
- Expected: `owner` narrows the list "among the claims you can see". Bob should get an empty list, frank should get an empty list (alice isn't on his team), and dave should never see drafts.
- Actual: 200 with all 7 of alice's claims, including drafts 13 and 4 (`total_count":7`). Frank with `?owner=alice` got the same 7, including drafts. Frank with `?owner=bob` got bob's 3 platform claims. Dave with `?owner=alice&status=draft` got drafts 13 and 4. (The unfiltered list for carol correctly hides drafts.)
- Reproduced: 4 times (frank, frank/bob, dave, bob)

### F6: List summary `total` still counts deleted items
- Severity: medium
- Request: create claim 13 with items of 10 and 20, then `curl -s -X DELETE "$B/claims/13/items/24" -H "Authorization: Bearer $ALICE"` (204), then `curl -s "$B/claims?q=walrus" -H "Authorization: Bearer $ALICE"`
- Expected: The summary `total` is the "Sum of the item amounts", which should match the detail view (10).
- Actual: The list shows `"total":30`. Claim 11 has the same problem: the detail total is 50.25 but the list shows 62.75, which still includes the deleted item of 12.5. Every role's list shows the wrong value, and it also affects `sort=total` (claim 11 is sorted as 62.75).
- Reproduced: 2 times (claims 11 and 13)

### F7: Search `q` doesn't match item descriptions
- Severity: medium
- Request: `curl -s "$B/claims?q=Footrest" -H "Authorization: Bearer $ALICE"` (claim 11 has an item "Footrest")
- Expected: "A claim matches if its title or any of its item descriptions contains the text."
- Actual: 200 `{"data":[],"meta":{...,"total_count":0}}`. `q=Hotel%20Quokka` and `q=QUOKKA%20NIGHT` (claim 12 has the item "Hotel Quokka night") also returned nothing. Searching titles works (`q=xylophone` found claim 12, `q=quokka` found claim 11 by its title).
- Reproduced: 3 times

### F8: Items with amount 0 are accepted
- Severity: medium
- Request: `curl -s -X POST "$B/claims/13/items" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"date":"2026-11-01","category":"other","description":"zero","amount":0}'`
- Expected: 400. The amount must be "Greater than 0".
- Actual: 201 `{"id":25,...,"amount":0}`. Also through `POST /claims` with `items:[{...,"amount":0}]`, which returned 201 for claim 16 with `"total":0`.
- Reproduced: 2 times (both endpoints)

### F9: The meals limit of 60.00 per day isn't enforced
- Severity: medium
- Request: `curl -s -X POST "$B/claims" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"title":"Meals way over","currency":"EUR","items":[{"date":"2026-11-03","category":"meals","description":"L","amount":50},{"date":"2026-11-03","category":"meals","description":"D","amount":50}]}'`
- Expected: 400. An item that takes a day's meals over 60.00 is rejected.
- Actual: 201 (claim 17, 100.00 of meals on one day). Also 201 for 30 + 30.01 (claim 15). On `POST /claims/14/items`, adding a 0.01 meal to a day that already had 60.00 returned 201 (item 34).
- Reproduced: 3 times (both endpoints)

### F10: An item dated exactly 90 days ago (2026-08-12) is rejected
- Severity: low
- Request: `curl -s -X POST "$B/claims/13/items" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"date":"2026-08-12","category":"other","description":"d90","amount":1}'`
- Expected: 201. Docs: "If today is 2026-11-10, the earliest accepted date is 2026-08-12". The server date was 2026-11-10 (response `Date` header and `created_at`).
- Actual: 400 `{"error":"validation_failed","message":"date must not be more than 90 days in the past","field":"date"}`. 2026-08-13 is accepted (201), so the limit is off by one day.
- Reproduced: 2 times (items endpoint and `POST /claims`, where the field was `items[0].date`)

### F11: The default `per_page` is 10, not 20
- Severity: low
- Request: `curl -s "$B/claims?q=xylophone" -H "Authorization: Bearer $ALICE"`
- Expected: `per_page` "Default 20."
- Actual: `"meta":{"page":1,"per_page":10,...}`. Every list request without `per_page` showed 10 (for alice, frank, dave and bob).
- Reproduced: more than 5 times

## Questions
- After F1, claim 11 is `paid` with `paid_at` and `amount_paid` null, and `GET /claims` puts it in the paid lists. I didn't check whether finance would pay it again or what the docs expect here.
- Carol's cross-team rejection of claim 6 (F4): the HTTP status code was cut from my output. The body was the claim, and erin's later GET showed `rejected`, so it almost certainly succeeded, but I didn't see the status code.
- A meal over 60.00 in a single item (for example one meal of 60.01) wasn't tested separately. F9 suggests the daily limit isn't checked at all.
- I didn't check whether `updated_at` changes when a repeat pay is "safe". It changed in F2, which also contradicts "changes nothing".
- Payment `reference` length (64) and comment length (500) limits weren't tested.

## Coverage
- Explored: the full lifecycle (create with items, add and remove item, PATCH including ignored fields, submit, reject without and with comment, edit while rejected, resubmit, approve, pay, repeat pay, read back); claim views (detail for every role, list for each role, `q`, `status` and `owner` filters, `sort=total` and `-total`, pagination including the last page and the `per_page` limit); item validation (amounts 0, 0.01, 10000, 10000.01, 1.005, string; dates at 90 and 91 days, in the future, 2026-09-31; meals limit through both endpoints; null title and lowercase currency; non-ASCII title; whitespace purpose); authorization (no token, bad token, manager PATCH (403), cross-team review, finance review (403), deleting a rejected claim (409), id `007` (404)).
- Not covered: `invalid_json`, `invalid_body` and 413 bodies; 405 and `Allow`; trailing slash; the lowercase `bearer` scheme; very long title or description (over 120/200 characters); extra and unknown fields in items; DELETE of an item that belongs to another claim; bob or erin acting on alice's claims by id; `sort=created_at` ties; `page=0` and invalid `page`; pay from submitted (409); `PATCH` on a submitted claim (409); a manager or finance doing `POST /claims` (403).
- Requests used: 80 of 80 (including 6 logins).
