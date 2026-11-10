# Exploration report

## Charters
1. Explore the claim lifecycle (create, add and remove items, edit, submit, reject, resubmit, approve, pay, then read again) with the seed users of each role to discover whether every step does what the docs say and returns the documented status code. *Tour: Guidebook.*
2. Explore one claim's data across every view (detail, list summaries, search, status and owner filters, sorting, pagination, and each role's view of it) with a single distinctive claim to discover data that changes, disappears or disagrees between views. *Tour: FedEx.*
3. Explore creating claims and adding items with bad and boundary data (missing, extra, null and wrong-type fields; amounts at 0, 0.01, 10000.00 and with three decimals; dates at the 90-day limit, in the future and impossible; the meals limit; very long and non-ASCII text) to discover what the API wrongly accepts and what it rejects badly. *Tour: Antisocial.*
4. Explore authorization and the claim rules with each role acting on other users' and other teams' claims, missing and wrong tokens, unknown ids, and actions from statuses the docs don't allow to discover who can see and change what, and whether the documented rules hold. *Tours: Saboteur and Back alley.*

Tokens below: `$ALICE`, `$BOB`, `$ERIN`, `$CAROL`, `$FRANK`, `$DAVE` = tokens from `POST /auth/login` for each seed user. `B=http://localhost:3001`. Today = 2026-11-10.

## Findings

### F1: PATCH /claims/{id} lets the owner set `status` (e.g. draft → paid) and skip review and payment
- Severity: high
- Request: `curl -s -X PATCH "$B/claims/11" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"title":"Zanzibar Quokka summit 2026","purpose":"","status":"paid","total":1}'`
- Expected: Docs (PATCH): "any other field in the body, such as `status`, `owner` or `total`, is ignored." Status should stay `draft`.
- Actual: `200`, `"status":"paid"` (with `submitted_at`, `reviewed_by`, `paid_at` and `amount_paid` all null). `total` was ignored. A later `GET /claims/11` by finance (dave) also returns `"status":"paid"`.
- Reproduced: 2 times. Also `PATCH /claims/12` by bob with `{"status":"approved"}` on a rejected claim returned `200` with `"status":"approved"`.

### F2: Paying an already paid claim records a second payment
- Severity: high
- Request: `curl -s -X POST "$B/claims/8/pay" -H "Authorization: Bearer $DAVE"` (sent twice)
- Expected: Docs: "If the claim is already `paid`, the call is safe to repeat: it returns `200` with the claim and changes nothing." `amount_paid` should stay equal to `total`.
- Actual: The first call returned `200` with `amount_paid: 85`. The second returned `200` with `"amount_paid":170`, and `paid_at` and `updated_at` were set to new times. On claim 9 (total 37.8), a second pay with `{"reference":"PAY-2"}` gave `"amount_paid":75.6` and changed `payment_reference` from `PAY-1` to `PAY-2`.
- Reproduced: 2 times (claims 9 and 8).

### F3: A manager of another team can approve or reject a claim
- Severity: high
- Request: `curl -s -X POST "$B/claims/3/review" -H "Authorization: Bearer $FRANK" -H 'Content-Type: application/json' -d '{"decision":"approve"}'`
- Expected: Docs: "Only a manager of the claim owner's team can review it." Frank (mobile) can't see claims from the platform team, so the response should be `404`.
- Actual: `200`, claim 3 (bob, platform) became `"status":"approved","reviewed_by":"frank"`. However, `GET /claims/17` by frank returns `404`, so the visibility check exists for GET but not for review.
- Reproduced: 2 times (approve on claim 3; reject on new claim 17 with `{"decision":"reject","comment":"cross-team"}` → `200`, `reviewed_by":"frank"`).

### F4: DELETE /claims/{id}/items/{itemId} removes items from other claims, including other users' claims
- Severity: high
- Request: `curl -s -X DELETE "$B/claims/14/items/36" -H "Authorization: Bearer $ALICE"` (item 36 belongs to bob's claim 17)
- Expected: Docs: "The item must belong to the claim in the path." The response should be `404` ("no such item in this claim").
- Actual: `204`. Then `GET /claims/17` by bob shows `"items":[],"total":0`. Bob's item was removed by alice. Claim 17's `updated_at` was not changed.
- Reproduced: 3 times. Alice removed item 32 (claim 15) through claim 14, item 33 (claim 15) through claim 16, and bob's item 36 through claim 14. Each returned `204`, and later GETs confirmed the items were gone.

### F5: A rejected claim cannot be resubmitted
- Severity: high
- Request: `curl -s -X POST "$B/claims/12/submit" -H "Authorization: Bearer $BOB"` (claim 12 rejected by carol, then an item was added)
- Expected: Docs: submit is "Allowed from `draft` and from `rejected`" → `200`, status `submitted`.
- Actual: `409 {"error":"invalid_state","message":"claim is rejected; only draft claims can be submitted"}`
- Reproduced: 2 times.

### F6: List summaries show a stale `total` after an item is removed
- Severity: medium
- Request: `curl -s "$B/claims?q=xylophone" -H "Authorization: Bearer $ERIN"` (after creating claim 13 with items 300.33 + 20 and deleting the 20 item)
- Expected: The summary `total` is the "Sum of the item amounts" and should match the detail.
- Actual: The list shows `"total":320.33`. `GET /claims/13` shows `"total":300.33`. Claim 11 shows the same thing: the list total is 62.75 and the detail total is 50.25, a difference of 12.5, which is the removed item. Frank's list after submit still shows 320.33. Sorting by `total` probably uses the wrong value as well.
- Reproduced: 4 times across claims 11 and 13 (carol's list, dave's list, erin's search, frank's filtered list).

### F7: `q` search does not match item descriptions
- Severity: medium
- Request: `curl -s "$B/claims?q=release" -H "Authorization: Bearer $DAVE"` (claim 8 has item "Release It!")
- Expected: Docs: "A claim matches if its title or any of its item descriptions contains the text."
- Actual: `200 {"data":[],"meta":{...,"total_count":0}}`. Title search works (`q=xylophone` finds claim 13).
- Reproduced: 3 times (`q=WOMBAT`, `q=Wombat` for item "Flugzeug Wombat" on claim 13; `q=release`).

### F8: `meta.next_page` points to an empty page when the last page is exactly full
- Severity: medium
- Request: `curl -s "$B/claims?per_page=4&page=2&sort=total" -H "Authorization: Bearer $CAROL"`
- Expected: Docs: `next_page` is "the number of the next page that has results, or `null` on the last page". 8 claims / 4 per page → page 2 is last → `null`.
- Actual: `"meta":{"page":2,"per_page":4,"total_count":8,"next_page":3}`. Similarly, dave's default list showed `total_count":10,"per_page":10,"next_page":2`, and `?page=2` returned `"data":[]`.
- Reproduced: 2 times.

### F9: Items dated exactly 90 days ago (2026-08-12) are rejected
- Severity: medium
- Request: `curl -s -X POST "$B/claims/14/items" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"date":"2026-08-12","category":"travel","description":"edge","amount":1}'`
- Expected: Docs: "If today is 2026-11-10, the earliest accepted date is 2026-08-12."
- Actual: `400 {"error":"validation_failed","message":"date must not be more than 90 days in the past","field":"date"}`. 2026-08-13 is accepted.
- Reproduced: 2 times (in `POST /claims` with `field: items[0].date`, and in `POST /claims/{id}/items`).

### F10: The meals daily limit is checked per item, not per day
- Severity: medium
- Request: `curl -s -X POST "$B/claims" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"title":"Meals","currency":"EUR","items":[{"date":"2026-11-08","category":"meals","description":"a","amount":40},{"date":"2026-11-08","category":"meals","description":"b","amount":30}]}'`
- Expected: Docs: meals items that share a date "may add up to at most 60.00. An item that would take that day over 60.00 is rejected with `400`."
- Actual: `201`. Claim 15 has 70.00 of meals on 2026-11-08. A single 60.01 meals item is rejected ("meals are limited to 60.00 per day").
- Reproduced: 3 times. In addition to the request above, `POST /claims/14/items` accepted meals of 0.01 and then 50 on 2026-11-09, when that day already had 60.00, which brought the day to 110.01.

### F11: An amount of 0 is accepted
- Severity: medium
- Request: `curl -s -X POST "$B/claims/15/items" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"date":"2026-11-07","category":"travel","description":"zero","amount":0}'`
- Expected: Docs: amount "Greater than 0" → `400`. A negative amount (-5) is correctly rejected with "amount must be greater than 0".
- Actual: `201 {"id":34,...,"amount":0}`
- Reproduced: 2 times (also `POST /claims` with an item amount of 0 → `201`, claim 16 with total 0).

### F12: The default `per_page` is 10, not 20
- Severity: low
- Request: `curl -s "$B/claims" -H "Authorization: Bearer $DAVE"`
- Expected: Docs: `per_page` "Default 20."
- Actual: `"meta":{"page":1,"per_page":10,"total_count":10,"next_page":2}`. Only 10 claims are returned.
- Reproduced: 6+ times (every list call without `per_page`).

## Questions
- When an item was deleted through the wrong claim (F4), the `updated_at` of the claim that owns the item was not changed (claims 15 and 17). This follows from F4, but it also means the audit trail is wrong.
- Claim 11, which was set to `paid` through F1, has `amount_paid: null` and `paid_at: null`. Finance can see it as paid, and I did not test whether `pay` on it would add a payment.
- I did not check exact title/description length limits with non-ASCII text: I could not build exact-length bodies. A 130-character title was correctly rejected. A lowercase currency `usd` was rejected before the title was checked.
- I did not check whether the stale summary total (F6) affects `sort=total` order.
- In the frank case, review succeeds but GET returns 404. Can frank see other actions on claims from the platform team (for example pay or delete)? Not tested.

## Coverage
- Lifecycle: create (with Location header), add item, remove item, PATCH (including ignored fields), submit, reject without/with comment, edit while rejected, resubmit, approve, pay, double pay, read back.
- Views: detail vs list summary, `q` on title and item text, status+owner filters, `sort=total`, pagination (`page`, `per_page`, `next_page`), views of one claim as owner, own-team manager, other-team manager and finance, and whether drafts are hidden from finance.
- Bad data: amounts 0, 0.01, 10000, 10000.01, -5, 12.345, "12.50"; dates 90/89 days back, future, 2026-09-31; meals single-item and per-day sums; whitespace description; 130-char title; null title; lowercase currency; array body; malformed JSON.
- Authorization: missing token, unknown token with lowercase `bearer`, employee reading another user's draft, other-team manager review, finance review, manager PATCH, review from approved (409), delete non-draft (409), cross-claim and cross-owner item delete, id `007`.
- Not covered: extra/unknown fields on items, purpose > 500, description > 200 exact, 1 MB body limit, 405 / `Allow` header, trailing slash, `invalid_url`, login error cases, manager/finance `POST /claims`, finance paying non-approved claims, employee reviewing, invalid `sort`/`status`/`page` values, deleting draft claims.
- Requests used: 80 of 80 (6 logins + 74 API calls).
