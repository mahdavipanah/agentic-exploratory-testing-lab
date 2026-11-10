# Exploration report

## Charters
1. Explore the claim lifecycle (create, add and remove items, edit, submit, reject, resubmit, approve, pay, then read again) with the seed users of each role to discover whether every step does what the docs say and returns the documented status code. *Tour: Guidebook.*
2. Explore one claim's data across every view (detail, list summaries, search, status and owner filters, sorting, pagination, and each role's view of it) with a single distinctive claim to discover data that changes, disappears or disagrees between views. *Tour: FedEx.*
3. Explore creating claims and adding items with bad and boundary data (missing, extra, null and wrong-type fields; amounts at 0, 0.01, 10000.00 and with three decimals; dates at the 90-day limit, in the future and impossible; the meals limit; very long and non-ASCII text) to discover what the API wrongly accepts and what it rejects badly. *Tour: Antisocial.*
4. Explore authorization and the claim rules with each role acting on other users' and other teams' claims, missing and wrong tokens, unknown ids, and actions from statuses the docs don't allow to discover who can see and change what, and whether the documented rules hold. *Tours: Saboteur and Back alley.*

Tokens below: `$ALICE`, `$BOB`, `$ERIN`, `$CAROL`, `$FRANK`, `$DAVE` are tokens from `POST /auth/login` for each seed user. `B=http://localhost:3003`.

## Findings

### F1: PATCH /claims/{id} lets the owner set `status` directly (skips submit, review and approval)
- Severity: high
- Request: `curl -s -X PATCH "$B/claims/12" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"status":"approved"}'`
- Expected: `status` is ignored ("any other field in the body, such as `status`, `owner` or `total`, is ignored"); claim stays `draft`.
- Actual: `200`, body has `"status":"approved"` with `submitted_at`, `reviewed_by` and `reviewed_at` all `null`. Earlier, `PATCH /claims/11` with `{"title":...,"status":"paid","owner":"bob","total":1}` returned `"status":"paid"` (owner and total were ignored), and a later `GET /claims/11` still showed `paid` with `paid_at: null`, `amount_paid: null`. Then finance paid the self-approved claim: `POST /claims/12/pay` as dave → `200`, `"status":"paid","amount_paid":5`, `reviewed_by: null`. An employee can get money paid out without any manager review.
- Reproduced: 2 times (claims 11 and 12), persisted on re-read; follow-on payment seen once.

### F2: A rejected claim cannot be resubmitted
- Severity: high
- Request: `curl -s -X POST "$B/claims/5/submit" -H "Authorization: Bearer $BOB"`
- Expected: `200`, status `submitted` ("Allowed from `draft` and from `rejected`"; lifecycle diagram shows `rejected ──submit──▶ submitted`).
- Actual: `409 {"error":"invalid_state","message":"claim is rejected; only draft claims can be submitted"}`. Adding an item to the rejected claim first (allowed, `201`) does not help.
- Reproduced: 3 times (new claim 13 twice, seed claim 5 once).

### F3: Paying an already-paid claim records another payment
- Severity: high
- Request: `curl -s -X POST "$B/claims/8/pay" -H "Authorization: Bearer $DAVE"` (run twice; claim 8 was `approved`)
- Expected: second call returns `200` and "changes nothing" / "records nothing new".
- Actual: first call `amount_paid: 85`, second call `200` with `"amount_paid":170`, and `paid_at`/`updated_at` moved to the new time. On claim 3 (total 204.8) the second pay gave `"amount_paid":409.6` and replaced `payment_reference` `PAY-3` with `PAY-3-again`.
- Reproduced: 2 times (claims 3 and 8).

### F4: List summary `total` does not go down when an item is removed
- Severity: high
- Request: `curl -s -X DELETE "$B/claims/14/items/25" -H "Authorization: Bearer $ALICE"` then `curl -s "$B/claims?owner=alice&status=draft" -H "Authorization: Bearer $ALICE"`
- Expected: summary `total` = sum of item amounts, same as `GET /claims/14`.
- Actual: `GET /claims/14` → `"total":40.04` (one item left); list → `"total":60.02` (still counts the removed 19.98 item). After adding a 1.14 item the detail showed 41.18 and the list 61.16 (adding updates it, removing doesn't). Claim 11: detail `115.85`, list `128.35` (difference = removed 12.5 item). Sorting by `total` uses the stale value too. See Questions for an observed overpayment caused by this.
- Reproduced: 2 claims (11 and 14), seen in 4 list responses.

### F5: Item amounts are silently changed (rounded down by a cent) on save
- Severity: high
- Request: `curl -s -X POST "$B/claims/14/items" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"date":"2026-11-04","category":"other","description":"Stamp","amount":1.15}'`
- Expected: `201` with `"amount":1.15` (valid amount, two decimals).
- Actual: `201` with `"amount":1.14`. In `POST /claims`, `40.05` was stored as `40.04` and `19.99` as `19.98`. Looks like floating-point truncation (`floor(x*100)`).
- Reproduced: 3 amounts across 2 endpoints.

### F6: Item amount 0 is accepted
- Severity: medium
- Request: `curl -s -X POST "$B/claims" -H "Authorization: Bearer $ERIN" -H 'Content-Type: application/json' -d '{"title":"Zero repro","currency":"EUR","items":[{"date":"2026-11-05","category":"travel","description":"free","amount":0}]}'`
- Expected: `400 validation_failed`, field `items[0].amount` ("Greater than 0").
- Actual: `201`, item with `"amount":0`, claim `"total":0`. Same via `POST /claims/15/items` with `amount: 0` → `201`.
- Reproduced: 2 times (both endpoints).

### F7: Meals limit of 60.00 per day is not enforced
- Severity: medium
- Request: `curl -s -X POST "$B/claims" -H "Authorization: Bearer $ERIN" -H 'Content-Type: application/json' -d '{"title":"Meals repro","currency":"EUR","items":[{"date":"2026-11-07","category":"meals","description":"Lunch","amount":50},{"date":"2026-11-07","category":"meals","description":"Dinner","amount":50}]}'`
- Expected: `400` — meals on one date may add up to at most 60.00.
- Actual: `201`, both items stored, `"total":100`. Via `POST /claims/15/items`, meals on 2026-11-06 of 40, 20.01, 20 and 0.01 (sum 80.02) all returned `201`.
- Reproduced: 2 times (both endpoints).

### F8: Earliest allowed item date (today − 90 days) is rejected
- Severity: low
- Request: `curl -s -X POST "$B/claims" -H "Authorization: Bearer $ERIN" -H 'Content-Type: application/json' -d '{"title":"Date repro","currency":"EUR","items":[{"date":"2026-08-12","category":"travel","description":"edge","amount":3}]}'`
- Expected: `201`. Docs: "If today is 2026-11-10, the earliest accepted date is 2026-08-12" (today is 2026-11-10).
- Actual: `400 {"error":"validation_failed","message":"date must not be more than 90 days in the past","field":"items[0].date"}`. Same via `POST /claims/15/items`. Off by one day.
- Reproduced: 2 times (both endpoints).

### F9: A manager can review claims of another team
- Severity: high
- Request: `curl -s -X POST "$B/claims/18/review" -H "Authorization: Bearer $FRANK" -H 'Content-Type: application/json' -d '{"decision":"reject","comment":"cross-team"}'` (claim 18 is bob's, team platform, submitted; frank manages mobile)
- Expected: `404` — managers can only see their own team's claims, and "a claim you are not allowed to see behaves as if it did not exist". (Frank's `GET /claims/14`, a platform claim, does return `404`.)
- Actual: `200`, `"status":"rejected","reviewed_by":"frank"`. Also `POST /claims/9/review` `{"decision":"approve"}` as frank → `200`, `"status":"approved","reviewed_by":"frank"` on alice's platform claim.
- Reproduced: 2 times (claims 9 and 18).

### F10: Default page size is 10, not 20
- Severity: low
- Request: `curl -s "$B/claims" -H "Authorization: Bearer $DAVE"`
- Expected: `meta.per_page` 20 ("`per_page` ... Default 20"), so all 11 claims on page 1.
- Actual: `200`, 10 items, `"meta":{"page":1,"per_page":10,"total_count":11,"next_page":2}`.
- Reproduced: 4+ times (several list calls without `per_page`).

## Questions
- **Overpayment from stale total (seen once).** After removing an item from claim 14, finance paid it: `POST /claims/14/pay` → `"total":41.18` but `"amount_paid":61.16`. This looks like F4's stale total being used for the payment, but I did not have budget to reproduce it.
- Claim 11, set to `paid` through PATCH (F1), shows `paid_at: null` and `amount_paid: null`; I did not check whether finance's paid lists/totals count it.
- `POST /claims/9/review` by alice (owner, employee) correctly gave `403`, but the message says "only a manager of the claimant's team can review" — while frank, from another team, could (F9). Team check seems missing only for managers.
- Description of 201 characters was rejected with a clear message; I did not test exactly 200 characters or non-ASCII descriptions. A non-ASCII title request failed on `items` being a string first, so non-ASCII title handling is untested.

## Coverage
- **Charter 1 (lifecycle):** create with items, add item, remove item, PATCH, submit, reject, resubmit (broken), approve, pay, pay again, delete draft, read deleted (404). All six logins worked.
- **Charter 2 (one claim across views):** detail vs list summary vs `q` search (case-insensitive, matching on title; removed item's description no longer matches), `status`/`owner` filters, `sort=total`/`created_at`, `page=2`, visibility for owner, same-team manager, other-team manager, other employee (404s correct).
- **Charter 3 (bad data):** amounts 0, 0.01, 10000.00, 10000.01, 12.345, `"12.50"`; dates −90, −91, tomorrow, 2026-09-31; meals limit; 201-char description; whitespace title; lowercase currency; `items` not an array. Validation messages and `field` names were good where validation existed.
- **Charter 4 (authorization):** no token / bad token (401 OK), cross-team review (broken), owner reviewing own claim (403 OK), manager PATCH (403 OK), manager creating claim (403 OK), zero-padded id `009` (404 OK), finance paying a PATCH-approved claim.
- **Not reached:** invalid JSON / array bodies, 405 + `Allow` header, 413, trailing slash, deleting an item through the wrong claim id, PATCH validation (null title, long purpose), review comment length and missing comment on reject, invalid `page`/`per_page`/`sort`/`status` values, `bearer` lowercase scheme, deleting non-draft claims, paying from `submitted`.
- **Requests used:** 80 of 80.
