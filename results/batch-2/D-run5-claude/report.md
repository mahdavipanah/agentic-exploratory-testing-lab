# Exploration report

## Environment
- Target: Claimdesk API at http://localhost:3002 (the docs say 3001; the run instructions say 3002). No version endpoint.
- Server clock: `Date: Tue, 10 Nov 2026 16:15:01 GMT`. "Today" (UTC) = 2026-11-10, the same date as the docs' worked example. So the documented date window is 2026-08-12 .. 2026-11-10.
- State check: `GET /ping` returned 200 `{"status":"ok"}`. All 6 seed users logged in and got the documented roles and teams. Dave (finance) saw 8 non-draft claims, alice saw 4 (including draft 4), and ids 1–10 matched the seed description. Creating claim 11 and reading it back confirmed that writes persist.
- Tokens were obtained once per user and reused all session.

## Risks
Ranked by harm:
1. Money paid twice or wrongly: pay is not idempotent, amounts get corrupted, totals don't match their items.
2. Access control: a user changes or reviews claims they can't see or don't own; cross-team actions.
3. Workflow bypass: a claim reaches approved or paid without a manager review.
4. Item rules not enforced: date window, meals limit, amount bounds and precision.
5. Lists, search and pagination disagree with the detail view (stale totals, wrong next_page, search misses).
6. Error contract: status codes, 405 + Allow, invalid JSON, id formats.

Never/Always rules used:
- A claim is paid at most once, and amount_paid == total.
- A user never changes data on a claim they can't see or don't own.
- Only a manager of the owner's team moves a claim to approved/rejected.
- A list total always equals the detail total.

## Charters
1. Explore claim visibility and actions across roles and teams with the 6 seed tokens, to discover access-control leaks. Tour: Saboteur + Back alley. Budget: 20.
2. Explore paying and the claim lifecycle with finance, manager and owner tokens, to discover double payment and workflow bypass. Tour: Obsessive-compulsive + Landmark. Budget: 20.
3. Explore item validation (dates, amounts, meals limit) on both create paths, to discover rule gaps and money corruption. Tour: Antisocial + Intellectual. Budget: 20.
4. Explore GET /claims search, sort and pagination as several users, to discover lists that disagree with details or docs. Tour: Guidebook + FedEx. Budget: 12.

## Findings

Tokens used below: ALICE=ff973b15…586a, BOB=e0a93e88…8974, CAROL=ff0adcac…7765, FRANK=598c2234…0039, DAVE=f524e602…d1. Base `B=http://localhost:3002`.

### F1: Paying an already-paid claim pays it again (amount_paid accumulates)
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -s -X POST $B/claims/8/pay -H "Authorization: Bearer $DAVE" -H 'Content-Type: application/json' -d '{"reference":"REF-1"}'
  curl -s -X POST $B/claims/8/pay -H "Authorization: Bearer $DAVE" -H 'Content-Type: application/json' -d '{"reference":"REF-2"}'
  curl -s -X POST $B/claims/8/pay -H "Authorization: Bearer $DAVE"
  ```
- Expected: the docs say that if the claim is already paid, the call "is safe to repeat: it returns 200 with the claim and changes nothing". amount_paid should stay 85 (the total). Oracle: Claims, plus the Never rule "paid at most once".
- Actual: all three calls returned 200. amount_paid went from 85 to 170 to 255, with total still 85. Each repeat also overwrote paid_at, updated_at and payment_reference (REF-1 → REF-2 → null).
- Reproduced: 3 times (2 repeat pays).

### F2: Owner can approve their own claim by PATCHing `status`, and finance then pays it
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -s -X PATCH $B/claims/12 -H "Authorization: Bearer $BOB" -H 'Content-Type: application/json' -d '{"status":"approved","owner":"alice","total":1,"amount_paid":5,"purpose":"x"}'
  curl -s -X POST $B/claims/12/pay -H "Authorization: Bearer $DAVE" -H 'Content-Type: application/json' -d '{"reference":"SELF-APPROVED"}'
  ```
- Expected: the docs say "any other field in the body, such as `status`, `owner` or `total`, is ignored". The claim should stay `draft`. Oracle: Claims, plus the Never rule that only a manager approves (mass assignment).
- Actual: the PATCH returned 200 with `"status":"approved"`, `reviewed_by: null` and `submitted_at: null`. owner, total and amount_paid were correctly ignored. Finance then paid it: 200, `"status":"paid","amount_paid":141.41`. The claim was never submitted or reviewed.
- Reproduced: 2 times (claim 12; claim 13 with `{"status":"approved","owner":"erin"}` → approved, owner still bob).

### F3: Any owner can delete items of any other claim, in any status, through their own draft claim's URL
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -s -X DELETE $B/claims/4/items/1 -H "Authorization: Bearer $ALICE"   # item 1 belongs to approved claim 1
  curl -s -X DELETE $B/claims/4/items/7 -H "Authorization: Bearer $ALICE"   # item 7 belongs to bob's submitted claim 3
  curl -s $B/claims/3 -H "Authorization: Bearer $BOB"
  ```
- Expected: 404, because "The item must belong to the claim in the path". Oracles: Claims, the Never rule about changing others' data, and the state rule that approved/submitted claims can't be edited.
- Actual: both returned 204. Item 1 disappeared from approved claim 1 (total 251.4 → 161.5). Item 7 (Lunch 18.9) disappeared from bob's submitted claim 3 (total 204.8 → 185.9). Neither claim's updated_at changed. A non-existent item (`/claims/11/items/999`) correctly returns 404.
- Reproduced: 2 times (different victim claims and owners).

### F4: Managers can approve or reject claims from other teams
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -s -X POST $B/claims/3/review -H "Authorization: Bearer $FRANK" -H 'Content-Type: application/json' -d '{"decision":"approve"}'
  curl -s -X POST $B/claims/6/review -H "Authorization: Bearer $CAROL" -H 'Content-Type: application/json' -d '{"decision":"approve"}'
  curl -s -X POST $B/claims/9/review -H "Authorization: Bearer $FRANK" -H 'Content-Type: application/json' -d '{"decision":"reject","comment":"x"}'
  ```
- Expected: 404. These claims are invisible to these managers (`GET /claims/3` as frank and `GET /claims/6` as carol both return 404), and "Only a manager of the claim owner's team can review it". Oracles: Claims, plus consistency (GET says 404, review succeeds).
- Actual: all three returned 200. Frank (mobile) approved bob's platform claim 3 and rejected alice's claim 9. Carol (platform) approved erin's mobile claim 6. `reviewed_by` was set to the foreign manager. An employee reviewing their own claim correctly gets 403, and so does finance.
- Reproduced: 3 times.

### F5: A rejected claim cannot be resubmitted
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -s -X POST $B/claims/9/submit -H "Authorization: Bearer $ALICE"
  curl -s -X POST $B/claims/5/submit -H "Authorization: Bearer $BOB"
  ```
- Expected: 200 `submitted`. The docs say submit is "Allowed from `draft` and from `rejected`". Oracle: Claims (lifecycle diagram and table).
- Actual: 409 `{"error":"invalid_state","message":"claim is rejected; only draft claims can be submitted"}`. Rejected claims are stuck and can only be edited.
- Reproduced: 3 times (claim 9 twice, seed claim 5 once).

### F6: Daily meals limit is checked only per item, not per day
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -s -X POST $B/claims/12/items -H "Authorization: Bearer $BOB" -H 'Content-Type: application/json' -d '{"date":"2026-11-03","category":"meals","description":"Lunch","amount":40}'
  curl -s -X POST $B/claims/12/items -H "Authorization: Bearer $BOB" -H 'Content-Type: application/json' -d '{"date":"2026-11-03","category":"meals","description":"Dinner","amount":40}'
  curl -s -X POST $B/claims -H "Authorization: Bearer $BOB" -H 'Content-Type: application/json' -d '{"title":"Repro","currency":"USD","items":[{"date":"2026-11-05","category":"meals","description":"A","amount":50},{"date":"2026-11-05","category":"meals","description":"B","amount":50}]}'
  ```
- Expected: the second item should get 400. "meals items that share a date may add up to at most 60.00. An item that would take that day over 60.00 is rejected." Oracle: Claims.
- Actual: both returned 201 (80.00 of meals on 2026-11-03). POST /claims accepted 50+50 (and 30+30.01 in another claim). Only a single meals item above 60 is rejected (`{"amount":61}` → 400 "meals are limited to 60.00 per day").
- Reproduced: 4 times (two on the items endpoint, two on create).

### F7: Amounts are silently truncated by one cent (1.13 → 1.12)
- Kind: bug
- Severity: high (wrong money, no error)
- Steps:
  ```
  curl -s -X POST $B/claims/12/items -H "Authorization: Bearer $BOB" -H 'Content-Type: application/json' -d '{"date":"2026-11-04","category":"other","description":"Stamp","amount":1.13}'
  curl -s -X POST $B/claims/12/items -H "Authorization: Bearer $BOB" -H 'Content-Type: application/json' -d '{"date":"2026-11-04","category":"other","description":"Pen","amount":0.29}'
  ```
- Expected: the item is stored with the amount sent (1.13, 0.29). These are valid two-decimal amounts. Oracles: Claims, user expectations, and the familiar floating-point truncation bug.
- Actual: 201 with `"amount":1.12` and `"amount":0.28`. A 4.35 sent in POST /claims came back as 4.34. Claim totals include the wrong values. Other values such as 30.01, 0.1 and 0.2 were stored correctly.
- Reproduced: 3 times (1.13, 0.29, 4.35; on both create paths).

### F8: An amount of 0 is accepted
- Kind: bug
- Severity: low
- Steps:
  ```
  curl -s -X POST $B/claims/12/items -H "Authorization: Bearer $BOB" -H 'Content-Type: application/json' -d '{"date":"2026-11-04","category":"other","description":"Zero","amount":0}'
  ```
- Expected: 400. The amount must be "Greater than 0". The message for -5 even says "amount must be greater than 0". Oracle: Claims.
- Actual: 201 `{"id":29,...,"amount":0}`. POST /claims with an item of amount 0 also returned 201.
- Reproduced: 2 times (both create paths).

### F9: The earliest allowed item date (today − 90 days) is rejected
- Kind: bug
- Severity: low
- Steps:
  ```
  curl -s -X POST $B/claims/11/items -H "Authorization: Bearer $BOB" -H 'Content-Type: application/json' -d '{"date":"2026-08-12","category":"travel","description":"Old ticket","amount":5}'
  ```
- Expected: 201. The docs say "If today is 2026-11-10, the earliest accepted date is 2026-08-12", and the server date is 2026-11-10. Oracle: Claims (an off-by-one at the boundary).
- Actual: 400 `{"message":"date must not be more than 90 days in the past","field":"date"}`. 2026-08-13 is accepted, and 2026-11-10 and 2026-11-11 behave as documented.
- Reproduced: 2 times (POST /claims `items[0].date` and POST /claims/{id}/items).

### F10: The list shows stale totals after an item is removed
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -s -X DELETE $B/claims/11/items/22 -H "Authorization: Bearer $BOB"   # removes the 10000 item
  curl -s "$B/claims?q=edge" -H "Authorization: Bearer $BOB"
  curl -s $B/claims/11 -H "Authorization: Bearer $BOB"
  ```
- Expected: the list `total` equals the detail `total` (the sum of the items). Oracles: the Always rule that totals match their parts, and consistency.
- Actual: the list shows `"total":10060.31` and the detail shows `"total":60.31`. The same happened for claims 1 (list 251.4 vs detail 161.5) and 3 (list 204.8 vs 185.9) after the F3 deletions. Adding items does update the list total (claim 11's list total included the later 0.01 item).
- Reproduced: 3 claims.

### F11: `meta.next_page` points to an empty page when the count is an exact multiple of per_page
- Kind: bug
- Severity: low
- Steps:
  ```
  curl -s "$B/claims?per_page=5&page=2&sort=total" -H "Authorization: Bearer $DAVE"
  curl -s "$B/claims?per_page=5&page=3&sort=total" -H "Authorization: Bearer $DAVE"
  curl -s "$B/claims" -H "Authorization: Bearer $DAVE"
  ```
- Expected: `next_page: null` on the last page. The docs say "the number of the next page that has results, or `null` on the last page". Oracle: Claims.
- Actual: total_count 10 with per_page 5, page 2 → `"next_page":3`, and page 3 is `{"data":[]}`. Default page 1 with total_count 10 and per_page 10 → `"next_page":2`.
- Reproduced: 2 times.

### F12: Default page size is 10, not 20
- Kind: bug (or a docs error, so it needs a decision)
- Severity: low
- Steps: `curl -s "$B/claims" -H "Authorization: Bearer $DAVE"`
- Expected: `per_page` 20 by default (docs: "Default 20").
- Actual: `"meta":{"page":1,"per_page":10,...}`. With more than 10 visible claims, only 10 are returned.
- Reproduced: 5+ times (every list call without per_page).

### F13: Search `q` does not match item descriptions
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -s "$B/claims?q=hotel" -H "Authorization: Bearer $CAROL"
  curl -s "$B/claims?q=Dinner" -H "Authorization: Bearer $CAROL"
  curl -s "$B/claims?q=taxi" -H "Authorization: Bearer $DAVE"
  ```
- Expected: claim 1 (item "Hotel, 1 night", item "Dinner") is returned for carol. Dave's search for "taxi" returns claim 9 (title) and claim 3 (item "Taxi to client office"). The docs say: "A claim matches if its title or any of its item descriptions contains the text." Oracle: Claims.
- Actual: carol's searches returned empty `data` with total_count 0. Dave's returned only claim 9 (a title match). Case-insensitive title matching works.
- Reproduced: 3 times.

## Questions
- **Docs port.** The docs give `localhost:3001`; the API runs on 3002. This probably only reflects the run setup.
- **updated_at not bumped.** F3 deletions didn't change the victim claim's `updated_at`. I didn't check whether a legitimate own-claim item delete bumps it. On claim 11, updated_at did change (16:17:49) after deleting item 22, so it probably does.
- **Rejected claims elsewhere.** Because of F5, I couldn't test the edit → resubmit → re-review path, or whether old review fields are kept or cleared.
- **Pay with no body.** A repeat pay with no body cleared payment_reference to null (part of F1). I didn't test what a first pay without a body records.
- **Item id gap.** Item id 17 was skipped between seed data and my first create (probably a seed item of claim 7 or 10). This looks harmless but is unverified.

## Coverage
- **Charter 1 (access control), ~20 requests.** Working as documented:
  - GET returns 404 for other users' drafts and other teams' claims.
  - Lists are correctly scoped for every role.
  - An employee reviewing their own claim gets 403, and so does finance reviewing.
  - A manager paying gets 403.
  - A non-existent item gets 404.

  Broken: F3 and F4. Not tested: a manager or other employee PATCHing, deleting, or adding items on someone else's visible claim; an employee calling GET on another same-team employee's non-draft claim.
- **Charter 2 (pay and lifecycle), ~15 requests.** Working: submitting an empty claim gives 400 (`field: items`); deleting an approved claim gives 409; adding an item to an approved claim gives 409; PATCH title:null on an approved claim gives 409. Broken: F1, F2, F5. Not tested: paying a non-approved claim (409), a reference over 64 characters, rejecting with no comment or a comment over 500 characters, an invalid decision value, DELETE on a draft (204), and whether the deleted claim's items vanish.
- **Charter 3 (item rules), ~20 requests.** Working:
  - A future date is rejected, and so is 2026-02-30.
  - 1.005 (three decimals) is rejected, and so are the string "12.50", 10000.01 and -5.
  - A whitespace-only description is rejected.
  - 10000 is accepted.
  - Title trimming works ("  Edge claim  " → "Edge claim").
  - An empty purpose becomes null.
  - Unicode and apostrophes in purpose round-trip ("O'Malley café ı").

  Broken: F6, F7, F8, F9. Not tested: description length 200/201, invalid category, item-level validation on PATCH, and the all-or-nothing rule for an invalid item in the middle of POST /claims.
- **Charter 4 (list), ~14 requests.** Working: sort=total ascending is ordered; per_page=51 gives 400; trailing slash and a lower-case `bearer` scheme work; title search is case-insensitive. Broken: F10, F11, F12, F13. Not tested: tie ordering by id, `owner` and `status` filters, page=0, invalid sort.
- **Error contract.** Working: invalid JSON gives 400 `invalid_json`; `/claims/007` gives 404; a missing token gives 401; PUT gives 405 with `Allow: GET, PATCH, DELETE` and a JSON content type. Not tested: 413, `invalid_body` (array body), `invalid_url`.
- **Budget:** 79 of 80 HTTP requests used.
