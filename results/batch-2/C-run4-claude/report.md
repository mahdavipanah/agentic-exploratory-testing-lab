# Exploration report

## Charters
Risks (most harmful to a client first):
- R1 Access control: employees/managers seeing or acting on claims outside their scope (other owners, other teams, drafts), self-approval, finance reviewing. Leaks via list filters (`q`, `owner`) are easy to miss.
- R2 Lifecycle/money: paying twice records a second payment or changes `amount_paid`/reference; edits allowed after submit/approve change the total after approval; illegal transitions accepted.
- R3 Item validation and arithmetic: float totals (0.1+0.2), 2-decimal rule, amount 10000 boundary, meals 60.00/day limit (boundary, per-claim not per-request), 90-day date window, impossible dates, partial creation when one item invalid.
- R4 Listing: pagination (`next_page`, `total_count`), sort with tie-break, filter validation (status/sort/page/per_page bounds).

Charters:
1. Explore claim visibility and permissions with the six seed users' tokens (Saboteur + Back alley tour) to discover leaks of other users' claims or actions allowed to the wrong role. Budget: 22 requests.
2. Explore the claim lifecycle with submit/review/pay repeated and reordered (Obsessive-compulsive tour) to discover illegal transitions, double payments and stale totals. Budget: 18 requests.
3. Explore item and claim validation with boundary and malformed values (Antisocial tour) to discover accepted invalid money/dates, wrong totals and partial writes. Budget: 20 requests.
4. Explore GET /claims with the documented query parameters (Guidebook tour) to discover wrong pagination, sorting and filter behaviour. Budget: 15 requests.
Reserve: 5 requests for reproduction.

Tokens below: `$ALICE`, `$BOB`, `$ERIN`, `$CAROL`, `$FRANK`, `$DAVE` from `POST /auth/login`. `B=http://localhost:3003`.

## Findings

### F1: A manager can approve or reject claims from another team
- Severity: high
- Request: `curl -s -X POST "$B/claims/3/review" -H "Authorization: Bearer $FRANK" -H 'Content-Type: application/json' -d '{"decision":"approve"}'`
- Expected: 404 (frank is the mobile manager and cannot see bob's platform claim; `GET /claims/9` as frank does return 404). Docs: "Only a manager of the claim owner's team can review it", and hidden claims return 404 on every endpoint.
- Actual: 200, claim 3 `"status":"approved","reviewed_by":"frank"`. Same for frank rejecting alice's claim 9 (200, `"status":"rejected","reviewed_by":"frank"`) right after `GET /claims/9` as frank returned 404, and carol (platform) approving erin's mobile claim 6 (200, `"reviewed_by":"carol"`).
- Reproduced: 3 times (claims 3, 9, 6)

### F2: Deleting an item through your own claim's path removes an item from someone else's claim
- Severity: high
- Request: `curl -s -i -X DELETE "$B/claims/4/items/11" -H "Authorization: Bearer $ALICE"`
- Expected: 404. Docs: "The item must belong to the claim in the path"; item 11 belongs to erin's claim 6, not alice's draft 4.
- Actual: 204. Afterwards `GET /claims/6` (erin, and dave) shows item 11 gone and `"total":100` (was 245) on an **approved** claim. Same with `DELETE /claims/4/items/7` → 204, bob's approved claim 3 lost "Lunch" and its total went from 204.8 to 185.9. Claim 4 itself is unchanged except `updated_at` was bumped.
- Reproduced: 2 times

### F3: PATCH lets the owner set `status`, so the claim skips review and finance pays it
- Severity: high
- Request: `curl -s -X PATCH "$B/claims/12" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"status":"approved","owner":"bob","total":1,"currency":"GBP"}'`
- Expected: 200 with `status` unchanged (`draft`). Docs: "any other field in the body, such as `status`, `owner` or `total`, is ignored."
- Actual: 200 with `"status":"approved"`, `"submitted_at":null`, `"reviewed_by":null` (`owner` and `total` were ignored). Then `POST /claims/12/pay` as dave → 200 `"status":"paid","amount_paid":70`. Repeated with `PATCH /claims/11 {"status":"approved"}` → 200 `"status":"approved"` on a draft totalling 10130.31.
- Reproduced: 2 times

### F4: Paying an already-paid claim records another payment
- Severity: high
- Request: `curl -s -X POST "$B/claims/8/pay" -H "Authorization: Bearer $DAVE" -H 'Content-Type: application/json' -d '{"reference":"PAY-2"}'` (after a first pay with `PAY-1`)
- Expected: 200 with the claim unchanged. Docs: "If the claim is already `paid`, the call is safe to repeat: it returns 200 with the claim and changes nothing."
- Actual: 200 with `"amount_paid":170` (total 85), `"payment_reference":"PAY-2"` (was PAY-1), and new `paid_at`/`updated_at`. Seed paid claim 2 (total 399): a single `POST /claims/2/pay` → `"amount_paid":798`, `paid_at` overwritten.
- Reproduced: 2 times

### F5: A rejected claim cannot be resubmitted
- Severity: medium
- Request: `curl -s -X POST "$B/claims/5/submit" -H "Authorization: Bearer $BOB"`
- Expected: 200, status `submitted`. Docs: Submit is "Allowed from `draft` and from `rejected`".
- Actual: 409 `{"error":"invalid_state","message":"claim is rejected; only draft claims can be submitted"}`. Same for alice's rejected claim 9 (sent twice).
- Reproduced: 3 times (claim 9 twice, claim 5)

### F6: The meals limit of 60.00 per day is checked per item, not per day
- Severity: medium
- Request: `curl -s -X POST "$B/claims" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"title":"meals in create","currency":"EUR","items":[{"date":"2026-11-07","category":"meals","description":"a","amount":40},{"date":"2026-11-07","category":"meals","description":"b","amount":30}]}'`
- Expected: 400. Docs: "the `meals` items that share a date may add up to at most 60.00".
- Actual: 201, `"total":70`. Through `POST /claims/11/items`: 30+30+0.01 on 2026-11-06 accepted (201), and 50+20 on 2026-11-07 accepted (201). A single 60.01 meals item is rejected (400 "meals are limited to 60.00 per day"), so only the single-item check exists.
- Reproduced: 3 times

### F7: The documented earliest item date (today − 90 days) is rejected
- Severity: low
- Request: `curl -s -X POST "$B/claims/11/items" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"date":"2026-08-12","category":"other","description":"edge","amount":1}'`
- Expected: 201. Docs: "If today is 2026-11-10, the earliest accepted date is 2026-08-12" (today is 2026-11-10).
- Actual: 400 `{"error":"validation_failed","message":"date must not be more than 90 days in the past","field":"date"}`. Off by one day. 2026-08-11 is also 400, which is correct.
- Reproduced: 2 times

### F8: The list's `total` disagrees with the claim's `total` after items are removed
- Severity: medium
- Request: `curl -s "$B/claims" -H "Authorization: Bearer $DAVE"` compared with `curl -s "$B/claims/6" -H "Authorization: Bearer $DAVE"`
- Expected: same total. Docs: the summary `total` is the "Sum of the item amounts".
- Actual: the list shows claim 6 `"total":245` and claim 3 `"total":204.8`. `GET /claims/6` shows `"total":100` and `GET /claims/3` shows `"total":185.9`. I only saw this on claims that lost items through F2, so sorting by total and finance's overview use stale amounts.
- Reproduced: 2 times (claims 6 and 3)

### F9: The default `per_page` is 10, not 20
- Severity: low
- Request: `curl -s "$B/claims" -H "Authorization: Bearer $DAVE"`
- Expected: `meta.per_page` 20 and all 10 visible claims on page 1. Docs: "Default 20."
- Actual: 200 `"meta":{"page":1,"per_page":10,"total_count":10,"next_page":2}`
- Reproduced: 5 times (every list call without `per_page`: alice ×2, carol, bob, dave)

## Questions
- `next_page` may point to an empty page. `GET /claims` (default per_page 10, total_count 10) returned `next_page: 2`, but `?page=2` returned `data: []` with `next_page: null`. Docs say `next_page` is "the next page that has results". I saw this once and did not reproduce it with another page size. With `per_page=3` pages 1, 3 and 4, `next_page` was correct.
- F2 also bumps `updated_at` on the claim in the path (claim 4), even though nothing on it changed. That claim's own item was not removed.
- Reviewing with a missing or blank comment could not be tested: the only submitted claims had been reviewed by then, and F5 stopped resubmission. Both attempts returned 409 instead of 400.
- Some things I didn't test: submitting a draft with no items (400 `items`), 405 with the `Allow` header, 413 for bodies over 1 MB, `invalid_url`, ids such as `007`/`0`, non-JSON content types, and `sort=created_at` tie-breaking.

## Coverage
- Charter 1 (permissions): cross-user and cross-team GETs (all 404 as documented), reviewing as finance, owner and other-team manager, PATCH by manager (403), adding an item to another user's claim (404), deleting an item through another claim's path, lower-case `bearer`, unknown token (401), `q` search for hidden titles (no leak).
- Charter 2 (lifecycle): pay, repeat pay, pay as manager (403), pay a rejected claim (409), PATCH an approved claim (409), review an approved claim (409), resubmit rejected claims.
- Charter 3 (validation): float total (0.1+0.2 → 60.3 correct), amount bounds 10000 / 10000.01, 3 decimals, string amount, date window edges, Feb 30, future date, meals limit, invalid JSON, array body, atomic create (an invalid second item creates nothing, correct), trimmed title, empty purpose → null, PATCH validation (lower-case currency, null title).
- Charter 4 (listing): sort=total pagination, past-the-end page, invalid status/per_page/page, trailing slash, default page size.
- Not covered: see Questions. Requests used: 78 of 80 (one blocked tool call may have sent 2 more; at most 80).
