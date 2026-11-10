# Exploration report

## Charters
1. Explore the claim lifecycle (create, add and remove items, edit, submit, reject, resubmit, approve, pay, then read again) with the seed users of each role to discover whether every step does what the docs say and returns the documented status code. Tour: Guidebook.
2. Explore one claim's data across every view (detail, list summaries, search, status and owner filters, sorting, pagination, and each role's view of it) with a single distinctive claim to discover data that changes, disappears or disagrees between views. Tour: FedEx.
3. Explore creating claims and adding items with bad and boundary data (missing, extra, null and wrong-type fields; amounts at 0, 0.01, 10000.00 and with three decimals; dates at the 90-day limit, in the future and impossible; the meals limit; very long and non-ASCII text) to discover what the API wrongly accepts and what it rejects badly. Tour: Antisocial.
4. Explore authorization and the claim rules with each role acting on other users' and other teams' claims, missing and wrong tokens, unknown ids, and actions from statuses the docs don't allow to discover who can see and change what, and whether the documented rules hold. Tours: Saboteur and Back alley.

Tokens below: `$ALICE`, `$BOB`, `$ERIN`, `$CAROL`, `$FRANK`, `$DAVE` from `POST /auth/login`; `B=http://localhost:3002`. Test date (today) was 2026-11-10.

## Findings

### F1: Paying an already-paid claim pays it again (amount_paid doubles, reference and paid_at overwritten)
- Severity: high
- Request: `curl -s -X POST "$B/claims/8/pay" -H "Authorization: Bearer $DAVE" -H 'Content-Type: application/json' -d '{"reference":"PAY-SECOND"}'` (claim 8 had just been paid with reference `PAY-2026-1110-01`)
- Expected: "If the claim is already `paid`, the call is safe to repeat: it returns `200` with the claim and changes nothing." `amount_paid` must equal `total` (85).
- Actual: 200 with `"amount_paid":170`, `"payment_reference":"PAY-SECOND"`, `paid_at` and `updated_at` set to the new time. A later `GET /claims/8` (as bob) shows the same 170. On seed-paid claim 2 (total 399), `POST /claims/2/pay` with no body returned `"amount_paid":798`, `"payment_reference":null` (the original reference was wiped).
- Reproduced: 2 times (claims 8 and 2), plus confirmed by a GET.

### F2: A manager can review claims from another team
- Severity: high
- Request: `curl -s -X POST "$B/claims/9/review" -H "Authorization: Bearer $FRANK" -H 'Content-Type: application/json' -d '{"decision":"reject","comment":"cross-team"}'` (claim 9 belongs to alice, team platform; frank manages mobile)
- Expected: "Only a manager of the claim owner's team can review it." Frank cannot see platform claims, so this should be 404 (the same claim type, claim 3, gives frank 404 on GET).
- Actual: 200, `"status":"rejected","reviewed_by":"frank","review_comment":"cross-team"`. Also: frank approved platform claim 3 (`"status":"approved"`), and carol (platform) approved mobile claim 6 (erin's) with `{"decision":"approve"}`. `GET /claims/3` as frank returns 404, so a manager can change claims they are not allowed to see.
- Reproduced: 3 times (claims 3, 6, 9; both managers).

### F3: A rejected claim cannot be resubmitted
- Severity: medium
- Request: `curl -s -X POST "$B/claims/11/submit" -H "Authorization: Bearer $ALICE"` (claim 11 is alice's, status `rejected`, has 3 items)
- Expected: 200 and status `submitted`. Docs: Submit is "Allowed from `draft` and from `rejected`".
- Actual: 409 `{"error":"invalid_state","message":"claim is rejected; only draft claims can be submitted"}`. Editing the rejected claim (adding an item, PATCH) worked, so the reject → fix → resubmit loop is broken at the last step.
- Reproduced: 2 times.

### F4: List summary total is not reduced when an item is removed (also wrong in sort)
- Severity: medium
- Request: create claim 12 as bob with items 10 + 5, then `curl -s -i -X DELETE "$B/claims/12/items/23" -H "Authorization: Bearer $BOB"` (204), then `curl -s "$B/claims?q=quokka" -H "Authorization: Bearer $BOB"`
- Expected: summary `total` is "Sum of the item amounts", same as the detail (10).
- Actual: detail (`PATCH`/GET) shows `"total":10`, list shows `"total":15`. Same for claim 11: detail 70.25, list 82.75 (the deleted 12.50 item is still counted) in alice's, carol's (filtered) and dave's lists. `sort=total` as dave orders claim 11 by the wrong value 82.75. Adding items and changing currency/title do update the list.
- Reproduced: 2 claims (11 and 12), seen in 6 list responses.

### F5: Meals limit of 60.00 per day is not enforced across items
- Severity: medium
- Request: on draft claim 12, add meals items dated 2026-11-04 of 40, 20, 0.01 and 50:
  `curl -s -X POST "$B/claims/12/items" -H "Authorization: Bearer $BOB" -H 'Content-Type: application/json' -d '{"date":"2026-11-04","category":"meals","description":"Snack","amount":0.01}'`
- Expected: "Within one claim, the `meals` items that share a date may add up to at most 60.00. An item that would take that day over 60.00 is rejected with `400`." The 0.01 and 50 items should be 400.
- Actual: all 201; the day reaches 110.01. Only a single item over 60 is rejected (60.01 alone → 400 "meals are limited to 60.00 per day"). In `POST /claims`, two meals items 40 + 30 on 2026-11-05 also created (201, total 70).
- Reproduced: 3 times (0.01 and 50 via items endpoint, 40+30 via POST /claims).

### F6: Amount 0 is accepted
- Severity: medium
- Request: `curl -s -X POST "$B/claims/12/items" -H "Authorization: Bearer $BOB" -H 'Content-Type: application/json' -d '{"date":"2026-11-01","category":"other","description":"zero","amount":0}'`
- Expected: 400. Rules: amount "Greater than 0" (the server's own message for -5 is "amount must be greater than 0").
- Actual: 201 `{"id":24,...,"amount":0}`. Via `POST /claims` (erin, `"amount":0`) the claim was created with `"total":0` (claim 13).
- Reproduced: 2 times.

### F7: Search does not match item descriptions
- Severity: medium
- Request: `curl -s "$B/claims?q=footrest" -H "Authorization: Bearer $ALICE"` (claim 11 has item "Footrest")
- Expected: claim 11 returned. Docs: "A claim matches if its title or any of its item descriptions contains the text."
- Actual: 200 `{"data":[],"meta":{...,"total_count":0}}`. Same empty result for `q=Footrest`, `q=Zebrafish taxi`, `q=ZEBRAFISH TAXI`, and as dave `q=release` (seed item "Release It!" in claim 8). Title search works (`q=zebrafish` finds claim 11, case-insensitive).
- Reproduced: 5 times.

### F8: The earliest documented valid date (90 days ago) is rejected
- Severity: low
- Request: `curl -s -X POST "$B/claims/12/items" -H "Authorization: Bearer $BOB" -H 'Content-Type: application/json' -d '{"date":"2026-08-12","category":"other","description":"day 90","amount":1}'`
- Expected: 201. Docs: "If today is 2026-11-10, the earliest accepted date is 2026-08-12".
- Actual: 400 `{"error":"validation_failed","message":"date must not be more than 90 days in the past","field":"date"}`. 2026-08-13 is accepted (201), so the limit is off by one day.
- Reproduced: 2 times (items endpoint and `POST /claims` with `field":"items[1].date"`).

### F9: Default page size is 10, not 20
- Severity: low
- Request: `curl -s "$B/claims?q=zebrafish" -H "Authorization: Bearer $ALICE"`
- Expected: `meta.per_page` 20 ("`per_page` … Default 20").
- Actual: `"meta":{"page":1,"per_page":10,...}`. Same in every list request without `per_page` (alice, carol, bob, dave).
- Reproduced: 8+ times.

## Questions
- For the cross-team approvals of claims 3 and 6 (F2) I cut the output and did not capture the status code; the body showed `"status":"approved"`. The 200 code was captured for claim 9.
- After F2, claims 3 and 6 are `approved` by a manager from the wrong team; I did not test whether finance can then pay them (likely yes).
- F4: I did not check whether a stale list total also affects `total` filtering/`-total` paging edges, or whether it persists after the claim is resubmitted/paid (and whether pay uses the detail total).
- F6 makes zero-total claims possible; I did not check if such a claim can be submitted and paid.
- Re-paying (F1) also moves `paid_at`; unclear whether a separate payments record exists — the API exposes only `amount_paid`.

## Coverage
Explored: full lifecycle as alice/carol/dave (create, add/remove item, PATCH, submit, reject, edit while rejected, resubmit, approve, pay, double pay, read back); one claim through detail, list, search, status+owner filters, sort, pagination (per_page=4 pages 2–3 consistent), and the views of alice, bob, carol, frank, dave; item boundaries (0, -5, 0.01, 10000.00, 10000.01, 12.345, "12.50", dates 2026-08-11/12/13, tomorrow, 2026-02-30, meals per-item and per-day, 201-char and 200-char non-ASCII description, null title + lowercase currency, invalid JSON); auth (no token, bad token, lowercase `bearer`), hidden claims (drafts to manager, other team, other employee), cross-team review, owner-only PATCH, owner reviewing own claim, wrong-status delete/pay, non-finance pay, `007` id.

Not covered: 405 + Allow header, 413, `invalid_body` (array), trailing slash, empty PATCH and ignored PATCH fields (`status`, `owner`), DELETE of drafts, submit with no items, `per_page` 0/51 and bad `page`, unknown `owner` filter, invalid `status`/`sort` values, reject without comment, comment/reference length limits, deleting an item via the wrong claim id, extra fields in POST /claims, title 121 chars.

Requests used: 79 of 80.
