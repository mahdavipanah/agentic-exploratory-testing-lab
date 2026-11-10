# Exploration report

## Charters

Risks (most damaging to a client first):
1. Authorization / visibility leaks: a manager of another team, another employee or finance seeing or acting on claims (drafts, other teams), self-approval.
2. Money integrity: totals wrong (float sums), paying twice recording a second payment, `amount_paid` not equal to `total`, items changed after submission/approval.
3. Lifecycle state machine: actions accepted from the wrong status (edit/add item after submit, approve twice, reject without comment, resubmit flow).
4. Item validation: date window boundaries (90 days, future, invalid calendar dates), amount limits/decimals/strings, meals daily limit at 60.00, atomicity of POST /claims with items.
5. Listing: pagination meta (`total_count`, `next_page`), sorting and ties, search in item descriptions, invalid query params.

Charters:
- C1 (Saboteur tour, ~20 requests): Explore roles and visibility with the six seed users, other users' claim ids and missing/bad tokens to discover authorization leaks and wrong 403/404 choices.
- C2 (Obsessive-compulsive tour, ~18 requests): Explore the claim lifecycle (submit/review/pay) with repeated and reordered actions to discover state-machine violations and duplicate or wrong payments.
- C3 (Antisocial tour, ~20 requests): Explore item validation with boundary dates, amounts and meals combos to discover invalid data accepted or valid data rejected, and non-atomic creates.
- C4 (Guidebook tour, ~14 requests): Explore GET /claims with the documented query parameters to discover pagination, sort and search errors.
- Reserve ~8 requests for reproductions and new risks.

Added during C3 (FedEx tour, used part of the reserve): follow an item deletion through the claim detail and the list summary. I added this after `DELETE /claims/11/items/25` removed an item that belongs to a different claim.

Tokens below: `$ALICE`, `$BOB`, `$CAROL`, `$FRANK` (manager, mobile), `$DAVE` (finance), all from `POST /auth/login`. B=http://localhost:3004. Note that the claim ids depend on state: the seed data plus the claims created in this session (ids 11–13).

## Findings

### F1: A manager can approve or reject claims from another team
- Severity: high
- Request: `curl -s -i -X POST "$B/claims/3/review" -H "Authorization: Bearer $FRANK" -H 'Content-Type: application/json' -d '{"decision":"approve"}'` (claim 3 belongs to bob, team platform. Frank manages mobile.)
- Expected: `404 not_found`. Per the docs, a manager can only see claims of their own team and only "a manager of the owner's team" can review. `GET /claims/3` as frank does return 404.
- Actual: `200`, `"status":"approved","reviewed_by":"frank"`. The same happened with `POST /claims/9/review` `{"decision":"reject","comment":"cross-team test"}` on alice's platform claim 9: `200`, `"status":"rejected","reviewed_by":"frank"`. Frank can review a claim he cannot see. Finance and the claim owner correctly get 403.
- Reproduced: 2 times (claims 3 and 9)

### F2: Paying an already-paid claim records another payment
- Severity: high
- Request: `curl -s -i -X POST "$B/claims/8/pay" -H "Authorization: Bearer $DAVE" -H 'Content-Type: application/json' -d '{"reference":"PAY-2"}'` (claim 8 had just been paid with reference PAY-1, `amount_paid` 85)
- Expected: `200` with the claim unchanged. The docs say "If the claim is already `paid`, the call is safe to repeat: it returns `200` with the claim and changes nothing."
- Actual: `200` with `"amount_paid":170`, `"payment_reference":"PAY-2"`, and new `paid_at`/`updated_at`. On seed claim 2 (total 399, already paid), `POST /claims/2/pay` with no body returned `"amount_paid":798,"payment_reference":null` and a new `paid_at`.
- Reproduced: 2 times (claims 8 and 2)

### F3: DELETE /claims/{id}/items/{itemId} deletes items from other users' claims, including paid ones
- Severity: high
- Request: `curl -s -i -X DELETE "$B/claims/11/items/14" -H "Authorization: Bearer $ALICE"` (claim 11 is alice's draft. Item 14 belongs to bob's **paid** claim 8.)
- Expected: `404`. The docs say "The item must belong to the claim in the path"; otherwise the result is 404 "no such item in this claim".
- Actual: `204 No Content`. After that, `GET /claims/8` (as dave) shows item 14 is gone, `"total":38.7` (was 85) while `"amount_paid":170`, and `updated_at` has not changed. Earlier, `DELETE /claims/11/items/25` also returned 204 and removed item 25 from bob's draft claim 12.
- Reproduced: 2 times (items 25 and 14)

### F4: A rejected claim cannot be resubmitted
- Severity: medium
- Request: `curl -s -i -X POST "$B/claims/5/submit" -H "Authorization: Bearer $BOB"` (claim 5 is bob's seed claim in `rejected`)
- Expected: `200`, status `submitted`. The lifecycle says `rejected ──submit──▶ submitted`, and submit is "Allowed from `draft` and from `rejected`".
- Actual: `409 {"error":"invalid_state","message":"claim is rejected; only draft claims can be submitted"}`. The same happened for alice's claim 9 after it was rejected.
- Reproduced: 2 times (claims 9 and 5)

### F5: The meals daily limit (60.00 per date per claim) applies to each item, not to the day's sum
- Severity: medium
- Request: `curl -s -i -X POST "$B/claims/11/items" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"date":"2026-11-08","category":"meals","description":"meal B","amount":20}'` (claim 11 already had a 50.00 meals item on 2026-11-08)
- Expected: `400`. The docs say "meals items that share a date may add up to at most 60.00".
- Actual: `201`. The day's meals now add up to 70. Other cases accepted: 30.01 + 29.99 + 0.01 = 60.01 on 2026-11-10 (201), and `POST /claims` with two meals items of 50 + 20 on the same date (201, claim 12, total 70). A single 61.00 meals item is correctly rejected ("meals are limited to 60.00 per day").
- Reproduced: 3 times

### F6: An item dated exactly 90 days ago (the documented earliest date) is rejected
- Severity: low
- Request: `curl -s -i -X POST "$B/claims/11/items" -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"date":"2026-08-12","category":"travel","description":"edge","amount":1}'` (today is 2026-11-10 UTC)
- Expected: `201`. The docs say: "If today is 2026-11-10, the earliest accepted date is 2026-08-12".
- Actual: `400 {"message":"date must not be more than 90 days in the past","field":"date"}`. `POST /claims` with an item dated 2026-08-12 gave the same error (`items[0].date`). 2026-08-13 is accepted.
- Reproduced: 2 times

### F7: The `total` in GET /claims summaries is not updated when an item is removed
- Severity: medium
- Request: `curl -s "$B/claims?status=draft" -H "Authorization: Bearer $BOB"`
- Expected: The summary `total` matches the claim's `total` ("Sum of the item amounts").
- Actual: The summary shows claim 12 with `"total":10070`, but `GET /claims/12` shows `"total":10020` (item 25, 50.00, was removed). For alice, the summary shows claim 11 with `"total":130.31`, but its detail shows `80.31` after item 23 (50.00) was deleted. Adding items does update the summary. Removing them does not. This also affects `sort=total`.
- Reproduced: 2 times (claims 11 and 12)

### F8: The `q` search does not match item descriptions
- Severity: medium
- Request: `curl -s "$B/claims?q=flight" -H "Authorization: Bearer $DAVE"` (claim 3 has an item "Flight Hamburg to Munich")
- Expected: Claim 3 is in the results. The docs say "A claim matches if its title or any of its item descriptions contains the text."
- Actual: `200 {"data":[],"meta":{...,"total_count":0}}`. Searching `q=FLIGHT` (dave) and `q=Hotel` (alice; claim 1 has the item "Hotel, 1 night") also returned nothing. Title search works and ignores case (`q=MUNICH` finds claim 3).
- Reproduced: 3 times

### F9: An invalid `sort` value causes a 500 instead of a 400
- Severity: medium
- Request: `curl -s -i "$B/claims?sort=title" -H "Authorization: Bearer $DAVE"`
- Expected: `400 validation_failed`. The docs say "Any other value returns `400`."
- Actual: `500 {"error":"internal_error","message":"unexpected server error"}`. `sort=-owner` (as alice) gave the same result.
- Reproduced: 2 times

### F10: The default `per_page` is 10, not 20
- Severity: low
- Request: `curl -s "$B/claims" -H "Authorization: Bearer $DAVE"`
- Expected: `meta.per_page` is 20 ("Default 20").
- Actual: `"meta":{"page":1,"per_page":10,...}`. Every list request without `per_page` showed 10 (carol, bob, dave, alice). With only 8 visible claims I could not check whether the server really cuts the page at 10.
- Reproduced: 6+ times

## Questions
- F2: The server clearly adds to `amount_paid` on every repeat. Is `payment_reference` also being wiped? Re-paying claim 2 without a body returned `"payment_reference":null`, but I did not record its value beforehand.
- F3: Can a user who isn't the owner also *add* items to someone else's claim, or delete through a claim path that isn't theirs (for example a non-draft one)? I did not test this. Also, after the foreign delete, paid claim 8 keeps its old `updated_at`.
- F1: Frank gets 404 on `GET /claims/3` but can review it, so the review endpoint seems to skip the visibility check. I did not test whether frank could also review a mobile claim, or whether carol can review erin's claims. I expect so.
- Item ids: the seed probably holds ids 1–17, and new items started at 18. I did not confirm that the failed `POST /claims` used no ids.

## Coverage
- Explored: login for all six users; visibility in the list and detail for employee, manager and finance; cross-user PATCH/items/submit/pay (correctly 404/403); bad token (401); lowercase `bearer`; review for another team, own claim and as finance; double approve; reject with a blank comment; bad decision; pay twice; pay a submitted claim; edit, add items to and delete items from non-editable claims (correctly 409); resubmitting a rejected claim; item date boundaries, future date, invalid calendar date, amount decimals, string amount, max amount, meals limit; atomicity of `POST /claims` (correct); totals in detail and list; list pagination, `next_page`, ascending `sort=total`, `per_page`/`page`/`status`/`sort` validation, `q` search; zero-padded id; 405 with `Allow`; invalid JSON; lowercase currency; ignored extra fields on create; submitting with no items; PATCH with a null title.
- Not explored: the 1 MB body limit (413); `invalid_body` (array body); `invalid_url`; trailing slash; deleting whole claims (DELETE /claims/{id}); currency change on PATCH; `purpose`/`title`/`description`/`reference` length limits; ties in `sort=created_at`; `owner` filter for an unknown user; erin's draft (claim 7) visibility for the mobile manager.
- Requests used: 75 of 80. This counts every curl that got a response. Two earlier batched commands were blocked by the tool's permission check before they ran, so they are not counted.
