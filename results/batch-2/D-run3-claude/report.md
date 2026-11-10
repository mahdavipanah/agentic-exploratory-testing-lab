# Exploration report

## Environment
- Target: Claimdesk API at http://localhost:3004 (black box, docs in api.md only).
- Server clock: `Date: Tue, 10 Nov 2026 16:10:21 GMT`, so "today" is 2026-11-10 UTC, the same date as the docs' worked example for the 90-day window.
- State check: `GET /ping` returned 200 `{"status":"ok"}`. All six seed users logged in, and their `user` objects matched the docs' table (roles and teams). As finance, `GET /claims?per_page=50` listed 8 seed claims (ids 1,2,3,5,6,8,9,10). Claims 4 and 7 are drafts (alice's and erin's) and were correctly hidden. Seed totals matched the docs' example (claim 1 = 251.4).
- Tokens: one per user, with a fresh login at the start of the session. Requests were sent with plain `curl`. In the commands below, `$ALICE`, `$BOB`, `$CAROL`, `$FRANK` and `$DAVE` stand for each user's bearer token, and `B=http://localhost:3004`.

## Risks
1. Money paid wrongly: double payment, paid amount not matching the total, totals changed after approval or payment.
2. Access control: approving or changing claims across teams or users, self-approval, or skipping the review.
3. State machine bypassed (edits or deletes in the wrong state, status changed through PATCH).
4. Item validation rules (meals daily limit, amount > 0, 90-day window, description length) not enforced on one or both paths.
5. List, search and pagination results that disagree with the docs or with the claim detail.
6. Error contract (status codes, error shapes, `Allow` header).

## Charters
- C1: Explore review and visibility across roles and teams, using the six seed users, to find out whether anyone can act on claims they can't see or don't own. Tour: Saboteur + Landmark. Budget: 15.
- C2: Explore the pay endpoint and claim totals, using approved and paid seed claims and new claims with decimal amounts, to find out whether money is created, lost or recorded twice. Tour: Money + Obsessive-compulsive. Budget: 10.
- C3: Explore the item rules on both POST /claims and POST /claims/{id}/items, using boundary values for date, amount, meals-per-day and description, to find out whether the documented limits hold on every path. Tour: Antisocial + Guidebook. Budget: 20.
- C4: Explore the lifecycle state table with PATCH, DELETE, item add/remove and submit in each status, plus server-owned fields in bodies, to find out whether the state machine can be bypassed. Tour: Back alley + Saboteur. Budget: 15.
- C5: Explore GET /claims (sort, q, owner, pagination, defaults) against the claim detail, to find out whether lists agree with the docs and with each claim. Tour: Guidebook + FedEx. Budget: 12.
- C6 (added mid-session, after F2): Follow claims damaged by the cross-claim item delete through list and detail to see the knock-on effects. Tour: FedEx. Budget: 4.

## Findings

### F1: PATCH /claims/{id} lets the owner set `status` to anything, including `approved` (self-approval, skipping review)
- Kind: bug
- Severity: high
- Steps:
  ```
  # claim 9 (alice) was rejected
  curl -s -X PATCH "$B/claims/9" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' \
    -d '{"currency":"USD","status":"approved","total":99999,"owner":"bob","amount_paid":5,"purpose":""}'
  curl -s -X POST "$B/claims/9/pay" -H "Authorization: Bearer $DAVE"
  # claim 12 (alice), a draft that was never submitted
  curl -s -X PATCH "$B/claims/12" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"status":"approved","total":1}'
  # claim 11 (alice), a draft
  curl -s -X PATCH "$B/claims/11" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"status":"bogus"}'
  ```
- Expected: `status` is ignored. The docs say: "Only these fields can be changed: any other field in the body, such as `status`, `owner` or `total`, is ignored." Status should only change through submit, review and pay (Never rule: an employee never approves their own claim).
- Actual: 200 every time, and the status was stored. Claim 9 became `"status":"approved"` (`total`, `owner` and `amount_paid` were correctly ignored). Finance then paid it: 200, `"status":"paid","amount_paid":37.8`. Claim 12 went from draft to `"status":"approved"` with `"submitted_at":null,"reviewed_by":null`. Claim 11 took `"status":"bogus"`. That made the draft visible to finance (`GET /claims/11` as dave returned 200, and it appears in dave's list with `"status":"bogus"`). Any later item change is then blocked with `409 "claim is bogus; only draft or rejected claims can be changed"`.
- Reproduced: 3 times (claims 9, 12, 11), plus a GET read-back of claim 9 as carol.

### F2: DELETE /claims/{id}/items/{itemId} deletes any item in any claim, whatever its owner or status
- Kind: bug
- Severity: high
- Steps:
  ```
  # claim 14 is alice's draft. Item 1 belongs to alice's APPROVED claim 1; item 5 belongs to bob's PAID claim 3.
  curl -s -i -X DELETE "$B/claims/14/items/1" -H "Authorization: Bearer $ALICE"
  curl -s "$B/claims/1" -H "Authorization: Bearer $ALICE"
  curl -s -i -X DELETE "$B/claims/14/items/5" -H "Authorization: Bearer $ALICE"
  curl -s "$B/claims/3" -H "Authorization: Bearer $BOB"
  ```
- Expected: 404. The docs say "The item must belong to the claim in the path" and give "404 … no such item in this claim". Items of approved or paid claims must never change, and one user must never change another's data.
- Actual: `HTTP/1.1 204 No Content` both times. Claim 1 (approved) lost item 1: total 251.4 → `"total":161.5`, and `updated_at` stayed at `2026-10-09T14:03:00.000Z`. Bob's paid claim 3 lost item 5 (Flight, 154.2): now `"total":50.6` with `"amount_paid":409.6`. Claim 14 itself was unchanged (`"total":100`).
- Reproduced: 2 times (items 1 and 5, two different owners).

### F3: A manager can approve or reject claims of another team, which they cannot even see
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -s -i "$B/claims/3" -H "Authorization: Bearer $FRANK"          # frank = mobile manager, claim 3 = bob/platform
  curl -s -i -X POST "$B/claims/3/review" -H "Authorization: Bearer $FRANK" -H 'Content-Type: application/json' -d '{"decision":"approve"}'
  curl -s -i -X POST "$B/claims/9/review" -H "Authorization: Bearer $FRANK" -H 'Content-Type: application/json' -d '{"decision":"reject","comment":"cross-team test"}'
  ```
- Expected: 404, because "A claim you are not allowed to see behaves as if it did not exist: every endpoint returns 404 for it". Only "a manager of the owner's team" can review.
- Actual: GET returns `404 claim not found`, but review returns `200`, with `"status":"approved","reviewed_by":"frank"` on claim 3 and `"status":"rejected","reviewed_by":"frank"` on claim 9 (both platform claims).
- Reproduced: 2 times (approve on claim 3, reject on claim 9).

### F4: Paying an already-paid claim records the payment again (amount_paid doubles) and overwrites paid_at and the reference
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -s -X POST "$B/claims/3/pay" -H "Authorization: Bearer $DAVE" -H 'Content-Type: application/json' -d '{"reference":"REF-1"}'
  curl -s -X POST "$B/claims/3/pay" -H "Authorization: Bearer $DAVE" -H 'Content-Type: application/json' -d '{"reference":"REF-2"}'
  curl -s -X POST "$B/claims/2/pay" -H "Authorization: Bearer $DAVE"     # seed claim 2, already paid
  ```
- Expected: "If the claim is already paid, the call is safe to repeat: it returns 200 with the claim and changes nothing." `amount_paid` should equal `total`.
- Actual: The first pay gave `"amount_paid":204.8,"payment_reference":"REF-1","paid_at":"…16:11:00.053Z"`. The second gave `"amount_paid":409.6,"payment_reference":"REF-2","paid_at":"…16:11:00.061Z"`, and `updated_at` changed. Seed claim 2 (total 399, already paid): `"amount_paid":798,"payment_reference":null`, with `paid_at` reset to now.
- Reproduced: 2 times (claims 3 and 2).

### F5: The meals limit of 60.00 per day is only checked per item, not as a daily sum
- Kind: bug
- Severity: medium
- Steps:
  ```
  # claim 11 already had meals 30 + 30 on 2026-11-10
  curl -s -X POST "$B/claims/11/items" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"date":"2026-11-10","category":"meals","description":"Snack","amount":0.01}'
  curl -s -X POST "$B/claims/11/items" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"date":"2026-11-10","category":"meals","description":"Big dinner","amount":50}'
  curl -s -X POST "$B/claims" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' \
    -d '{"title":"Meals create","currency":"EUR","items":[{"date":"2026-11-09","category":"meals","description":"A","amount":30},{"date":"2026-11-09","category":"meals","description":"B","amount":30.01}]}'
  ```
- Expected: 400 for each. "The meals items that share a date may add up to at most 60.00. An item that would take that day over 60.00 is rejected."
- Actual: 201 each time. Claim 11's meals on 2026-11-10 now add up to 110.01, and claim 12 was created with 60.01 of meals on 2026-11-09. A single meals item of 60.01 is rejected (`"meals are limited to 60.00 per day"`), so only the per-item check runs.
- Reproduced: 3 times (two on the items endpoint, one on POST /claims).

### F6: An item amount of 0 is accepted
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -s -X POST "$B/claims/12/items" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"date":"2026-11-08","category":"other","description":"x","amount":0}'
  curl -s -X POST "$B/claims" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"title":"Zero","currency":"GBP","items":[{"date":"2026-11-08","category":"other","description":"zero","amount":0}]}'
  ```
- Expected: 400. The docs say amounts must be "Greater than 0", and the server's own message for -5 is `"amount must be greater than 0"`.
- Actual: 201 for both (`"amount":0`). Claim 13 was then submitted with `"total":0`.
- Reproduced: 2 times (both paths).

### F7: The earliest allowed item date is off by one day (2026-08-12 is rejected)
- Kind: bug
- Severity: low
- Steps:
  ```
  curl -s -X POST "$B/claims/11/items" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"date":"2026-08-12","category":"travel","description":"Bus","amount":1}'
  ```
  The same date was also sent inside `POST /claims` `items[2]`.
- Expected: Accepted. The docs say: "If today is 2026-11-10, the earliest accepted date is 2026-08-12." The server date was 2026-11-10 UTC.
- Actual: 400 `{"error":"validation_failed","message":"date must not be more than 90 days in the past","field":"date"}` (and `"field":"items[2].date"` on create). 2026-08-13 is accepted, and 2026-11-11 is correctly rejected as in the future.
- Reproduced: 2 times (both paths).

### F8: A 199-character item description is rejected as over 200 characters
- Kind: bug
- Severity: low
- Steps: send an item whose `description` is 199 × `d` (length checked locally with `wc -c` = 199), on both paths:
  ```
  curl -s -X POST "$B/claims/14/items" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"date":"2026-11-05","category":"other","description":"<199 x d>","amount":1}'
  curl -s -X POST "$B/claims" -H "Authorization: Bearer $BOB" -H 'Content-Type: application/json' -d '{"title":"Desc199","currency":"EUR","items":[{"date":"2026-11-05","category":"other","description":"<199 x d>","amount":1}]}'
  ```
- Expected: Accepted ("1 to 200 characters after trimming").
- Actual: 400 `"description must be at most 200 characters"` (`"field":"items[0].description"` on create). A 198-character description was accepted (201).
- Reproduced: 2 times (both paths). Not tested: exactly 200 and 201 characters.

### F9: Search `q` does not match item descriptions
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -s "$B/claims?q=Hamburg&per_page=50" -H "Authorization: Bearer $DAVE"
  curl -s "$B/claims?q=dinner&per_page=50"  -H "Authorization: Bearer $DAVE"
  curl -s "$B/claims?q=TAXI&per_page=50"    -H "Authorization: Bearer $DAVE"
  ```
- Expected: "A claim matches if its title or any of its item descriptions contains the text." `Hamburg` should match claims 1, 3 and 9 ("ICE train Hamburg to Berlin", "Flight Hamburg to Munich", "Taxi to Hamburg airport"). `dinner` should match claims 1 and 11. `TAXI` should match claims 9 and 3 ("Taxi to client office").
- Actual: `Hamburg` and `dinner` return `"total_count":0`. `TAXI` returns only claim 9, which matches on its title. Title search is case-insensitive and works (`q=probe` and `q=berlin` found their claims).
- Reproduced: 4 times (HAMBURG, Hamburg, dinner, TAXI).

### F10: The default page size is 10, not the documented 20
- Kind: bug (docs or code: someone needs to decide which is right)
- Severity: low
- Steps: `curl -s "$B/claims" -H "Authorization: Bearer $DAVE"`
- Expected: "`per_page` … Default 20."
- Actual: `"meta":{"page":1,"per_page":10,"total_count":11,"next_page":2}` with 10 rows. Page 2 held the 11th claim, with `next_page:null`.
- Reproduced: 4 times (default list, page=2, q=probe, owner=bob, all showing `per_page":10`).

### F11: After the cross-claim item delete, the list summary `total` disagrees with the claim detail
- Kind: bug (follow-on effect of F2, but a separate inconsistency)
- Severity: medium
- Steps:
  ```
  curl -s "$B/claims/?owner=bob" -H "Authorization: Bearer $CAROL"
  curl -s "$B/claims?q=berlin"   -H "Authorization: Bearer $ALICE"
  ```
- Expected: The summary `total` equals the detail `total` (both are "Sum of the item amounts").
- Actual: The list shows claim 3 as `"total":204.8` while `GET /claims/3` shows `"total":50.6`. The list shows claim 1 as `"total":251.4` while `GET /claims/1` shows `"total":161.5`. For normal item adds the list stays correct (claim 14 shows 101 in both).
- Reproduced: 2 times (claims 3 and 1).

## Questions
- A zero-total claim (claim 13, `"total":0`) can be submitted. This follows from F6. Should a submit require a positive total?
- After the repeat pay on seed claim 2, `payment_reference` is `null`. I didn't read claim 2 before paying it, so I can't tell whether a seed reference was wiped or there never was one.
- Item ids skip 17 (seed items end at 16 or 17, and the first new item got 18). Probably an unseen seed item on a draft. Not checked.
- PATCH on a rejected claim with `purpose:""` gave `purpose:null`, as documented. I didn't check whether `updated_at` changes on an empty-object PATCH.
- F8: the limit may actually be 198 or "< 200". Sending exactly 200 and 201 characters would show the real boundary.

## Coverage
- C1 (access): role lists for all four roles were correct (drafts hidden, team scoping correct). Cross-team GET returns 404 correctly. Owner self-review returns 403. Cross-team review is broken (F3). Not done: employee reviewing a teammate's claim, manager/finance PATCH or DELETE, finance review.
- C2 (money): first pay is correct (amount_paid = total). Repeat pay is broken (F4). Totals for decimal items are exact (0.1 + 0.2 + 30 + 30 = 60.3). Pay as non-finance and pay from submitted (409) were not tested.
- C3 (items): string amount, 3 decimals, 10000.01, -5, whitespace-only description, future date and a single 60.01 meals item are all rejected correctly. Broken: daily meals sum (F5), 0 (F6), earliest date (F7), description length (F8). Not tested: invalid calendar dates (2026-02-30), bad category, 10000.00 exactly, title and purpose length limits.
- C4 (state): submitted claims correctly refuse PATCH, add item, delete item (409). Rejected claims refuse DELETE (409). An empty claim can't be submitted (400). PATCH `title:null` gives 400. Broken: status mass assignment (F1), cross-claim item delete (F2). Not tested: resubmitting a rejected claim, deleting a draft, approving or paying from wrong states.
- C5 (list): numeric sort on `total` in both directions is correct, regex-like `q=.*` is treated literally, a page past the end returns an empty array, the trailing slash works, and the owner filter works. Broken: item-description search (F9), default per_page (F10). Not tested: invalid sort/status/page/per_page values, per_page 51, tie ordering.
- C6: stale list totals (F11).
- Error contract: the `{error,message,field}` shape is consistent. `405` lists `Allow: GET, PATCH, DELETE`. `invalid_json` is returned for a truncated body. 401 without a token. The lowercase `bearer` scheme works. `/claims/007` returns 404. Not tested: 413, invalid_body, invalid_url, login errors.
- Budget: 80 of 80 HTTP requests used (including 6 logins and 1 ping).
