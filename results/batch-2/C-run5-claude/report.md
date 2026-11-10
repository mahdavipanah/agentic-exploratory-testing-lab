# Exploration report

## Charters

Risks (most harmful to a client first):
- R1 Access control: employees/managers seeing or acting on claims of other users/teams (data leak, self-approval, wrong-team approval).
- R2 Lifecycle/money: double payment, paying unapproved claims, editing claims after submit/approve so the paid amount differs from the approved one, amount_paid != total.
- R3 Item validation: date window boundaries (90 days, future, invalid dates), amount decimals/limits, meals-per-day limit, float rounding of totals.
- R4 Lists: visibility filtering in the list, pagination meta (total_count, next_page), sort ties, search across item descriptions.
- R5 Input robustness: malformed JSON, wrong content types, odd ids (`007`, `0`), trailing slash, 405 Allow header.

Charters (written before any request):
- C1 (Saboteur tour, ~20 requests): Explore claim visibility and authorization with all six seed users and the seed claims to discover leaks, wrong 403/404 choices, and actions allowed to the wrong role/team.
- C2 (Obsessive-compulsive tour, ~20 requests): Explore the claim lifecycle with double submits, re-reviews, repeated pays and edits in each state to discover illegal transitions, duplicate payments and inconsistent amount_paid/timestamps.
- C3 (Antisocial tour, ~20 requests): Explore item validation with boundary dates, odd amounts and meals combinations to discover accepted invalid data or wrong totals.
- C4 (Guidebook + FedEx tour, ~15 requests): Explore GET /claims with documented parameters and a freshly created claim followed through every endpoint to discover pagination/meta errors, sort/search errors and data that changes in transit.
- Reserve: ~5 requests for reproduction.

Added during exploration:
- C5 (Back alley + Saboteur tour, ~8 requests from reserve): Explore the `owner` list filter and PATCH with undocumented fields, with manager/employee tokens, to discover visibility bypasses and mass-assignment. Added because `status=draft&owner=alice` as a manager returned drafts, which suggested the filters skip the visibility rules.

Tokens below: ALICE, BOB, CAROL, FRANK, DAVE = tokens from `POST /auth/login` for those users. `B=http://localhost:3001`.

## Findings

### F1: PATCH accepts `status`, so an owner can approve their own claim and get it paid
- Severity: high
- Request: `curl -s -X PATCH "$B/claims/12" -H "Authorization: Bearer $BOB" -H 'Content-Type: application/json' -d '{"status":"approved"}'` followed by `curl -s -X POST "$B/claims/12/pay" -H "Authorization: Bearer $DAVE"`
- Expected: Docs (PATCH /claims/{id}): "any other field in the body, such as `status`, `owner` or `total`, is ignored." The status should stay `draft`, and pay should return 409.
- Actual: 200, `"status":"approved","submitted_at":null,"reviewed_by":null`. Pay then returned 200 `"status":"paid","amount_paid":114.84`. The claim was never submitted or reviewed. `owner` and `total` were ignored as documented. Only `status` gets through.
- Reproduced: 2 times (claim 11 as alice: draft → approved; claim 12 as bob: draft → approved → paid).

### F2: Paying an already-paid claim records another payment (amount_paid doubles)
- Severity: high
- Request: `curl -s -X POST "$B/claims/2/pay" -H "Authorization: Bearer $DAVE"`
- Expected: "If the claim is already `paid`, the call is safe to repeat: it returns `200` with the claim and changes nothing."
- Actual: 200, `"amount_paid":798` (total is 399), with `paid_at` and `updated_at` reset to now and `payment_reference` overwritten (to null). On claim 8, the first pay gave `amount_paid:85, payment_reference:"PAY-1"`. The second gave `amount_paid:170, payment_reference:"PAY-2"`.
- Reproduced: 2 times (claim 8 and seed claim 2).

### F3: Any manager can review claims from other teams
- Severity: high
- Request: `curl -s -X POST "$B/claims/3/review" -H "Authorization: Bearer $FRANK" -H 'Content-Type: application/json' -d '{"decision":"approve"}'`
- Expected: "Only a manager of the claim owner's team can review it." Frank (mobile) cannot see platform claim 3 (`GET /claims/9` as frank returned 404), so the response should be 404.
- Actual: 200, `"status":"approved"` on bob's platform claim 3. Frank also rejected alice's claim 9 (`"reviewed_by":"frank"`), and carol (platform) approved erin's mobile claim 6 (`"reviewed_by":"carol"`).
- Reproduced: 3 times (claims 3, 9, 6).

### F4: The `owner` filter skips visibility, so managers see other teams' claims, drafts included
- Severity: high
- Request: `curl -s "$B/claims?owner=erin" -H "Authorization: Bearer $CAROL"`
- Expected: "`owner`: Narrows the list to that user's claims, among the claims you can see." Carol (platform manager) should get an empty list for erin (mobile). Managers should never see drafts.
- Actual: 200, all 3 of erin's claims, including draft id 7 "USB-C dock" (`total_count:3`). `status=draft&owner=alice` as carol returned alice's drafts 11 and 4. Without `owner`, `status=draft` as carol returns `[]`.
- Reproduced: 3 times (carol owner=alice, carol owner=erin, frank owner=erin).

### F5: Amounts are stored rounded down (1.15 becomes 1.14)
- Severity: high
- Request: `curl -s -X POST "$B/claims/11/items" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"date":"2026-11-01","category":"other","description":"float","amount":1.15}'`
- Expected: 1.15 has two decimals and is valid, so it should be stored as 1.15.
- Actual: 201, `"amount":1.14`. The claim total also uses 1.14.
- Reproduced: 2 times (1.15 → 1.14 via the items endpoint; 4.35 → 4.34 via POST /claims).

### F6: The daily meals limit is not enforced across items
- Severity: medium
- Request: `curl -s -X POST "$B/claims" -H "Authorization: Bearer $BOB" -H 'Content-Type: application/json' -d '{"title":"repro","currency":"GBP","items":[{"date":"2026-11-05","category":"meals","description":"lunch","amount":30},{"date":"2026-11-05","category":"meals","description":"dinner","amount":30.5}]}'`
- Expected: "the `meals` items that share a date may add up to at most 60.00. An item that would take that day over 60.00 is rejected with `400`."
- Actual: 201, both items accepted (day sum 60.5). Adding another 50 meal on 2026-11-05 via POST /claims/12/items also returned 201 (day sum 110.5). On claim 11, 40 + 20 + 0.01 = 60.01 was accepted. Only a single item above 60 is rejected (60.01 alone → 400 "meals are limited to 60.00 per day").
- Reproduced: 3 times.

### F7: The earliest allowed item date (today − 90 days) is rejected
- Severity: medium
- Request: `curl -s -X POST "$B/claims/11/items" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"date":"2026-08-12","category":"travel","description":"d","amount":1}'`
- Expected: "If today is 2026-11-10, the earliest accepted date is 2026-08-12." Today is 2026-11-10 (response `Date` header), so this should return 201.
- Actual: 400 `{"error":"validation_failed","message":"date must not be more than 90 days in the past","field":"date"}`. 2026-08-13 is accepted.
- Reproduced: 2 times (POST /claims as `items[0].date`, and POST /claims/11/items).

### F8: Search (`q`) does not match item descriptions
- Severity: medium
- Request: `curl -s "$B/claims?q=hotel" -H "Authorization: Bearer $ALICE"`
- Expected: "A claim matches if its title or any of its item descriptions contains the text." Alice's claim 1 has the item "Hotel, 1 night".
- Actual: 200 `{"data":[],"meta":{...,"total_count":0}}`. As dave, `q=Release` and `q=RELEASE` also return nothing, although claim 8 has the item "Release It!". Title search works and ignores case (`q=TAXI` finds claim 9, `q=library` finds claim 8).
- Reproduced: 3 times.

### F9: Default `per_page` is 10, not 20
- Severity: low
- Request: `curl -s "$B/claims?q=TAXI" -H "Authorization: Bearer $DAVE"`
- Expected: "`per_page` ... Default 20."
- Actual: 200, `"meta":{"page":1,"per_page":10,...}`
- Reproduced: 5+ times (every list without `per_page`).

### F10: `next_page` points to an empty page when the last page is exactly full
- Severity: low
- Request: `curl -s "$B/claims?per_page=4" -H "Authorization: Bearer $BOB"`
- Expected: "`meta.next_page` is the number of the next page that has results, or `null` on the last page." With 4 results and per_page=4 it should be null.
- Actual: 200, 4 items, `"meta":{"page":1,"per_page":4,"total_count":4,"next_page":2}`. Partial last pages are correct (`per_page=3&page=2` → `next_page:null`).
- Reproduced: 2 times (alice per_page=5 with 5 claims, bob per_page=4 with 4 claims).

### F11: An invalid `sort` value returns 500 instead of 400
- Severity: medium
- Request: `curl -s "$B/claims?sort=title" -H "Authorization: Bearer $DAVE"`
- Expected: "Any other value returns `400`."
- Actual: 500 `{"error":"internal_error","message":"unexpected server error"}`
- Reproduced: 2 times (`sort=title` as dave, `sort=-id` as alice).

## Questions
- F1: Does PATCH also accept other undocumented fields, such as `submitted_at`, `reviewed_by` or `amount_paid`? I only tested `status`, `owner`, `total` and `currency`.
- F2: Did the second pay create a second payment record, or did it only overwrite `amount_paid`? The API has no payments endpoint to check.
- F3: Can a manager also review claims from their own team that they own, or claims of other managers? The seed data has no claims owned by managers.
- F4: Does `owner=<user>` also let an employee see other employees' claims? I only tried it with manager tokens.
- F5: Is the rounding down a float truncation (e.g. `Math.floor(x*100)`)? It hits exactly the values whose ×100 result is just below an integer. Totals may drift the same way.
- When a claim is paid a second time, `payment_reference` is overwritten with null if no reference is sent. This is part of F2 but could be its own issue.

## Coverage
- Explored: visibility of lists and GETs per role (all 6 users); cross-user write actions (items, PATCH, review, pay); review by the owner (403), pay by a manager (403); state guards on approved/rejected claims (PATCH, add/remove item, re-review, delete → all 409 as documented); repeated pay; item validation (date window, future date, impossible date, decimals, max amount, string amount, meals limit, trimming); POST /claims with items; pagination, sort, search, invalid list params; 401 without token; invalid JSON; array body; id `007`; lower-case `bearer`; 405 with `Allow` header; PATCH with ignored fields.
- Not covered: submitting empty claims (400), deleting items from another claim's path, the 1 MB body limit (413), trailing slash, `reference` length validation, PATCH validation for title/purpose/currency, the rejected → edit → resubmit flow, wrong Content-Type, login error cases, and sort ties.
- Requests used: 77 of 80 (no `/ping`; one blocked shell command sent no requests).
