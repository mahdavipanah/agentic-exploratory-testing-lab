# Exploration report

## Environment
- Target: Claimdesk API at http://localhost:3003 (black box, docs in `api.md` only).
- Server date (from the `Date` header): Tue, 10 Nov 2026 16:10 GMT, so "today" = 2026-11-10 UTC, which matches the docs' date example (earliest item date 2026-08-12).
- State check: `GET /ping` returned 200 `{"status":"ok"}`. All six seed users logged in, with the roles and teams the docs list. Finance's list showed the 8 non-draft seed claims (ids 1,2,3,5,6,8,9,10). Alice's list showed her 4 claims, including draft 4. That matches the seed described in the docs (claim 7 is a draft that alice and dave cannot see).
- Tokens below are written as `$ALICE`, `$BOB`, `$ERIN`, `$CAROL`, `$FRANK`, `$DAVE` (each from `POST /auth/login`). B=http://localhost:3003.

## Risks
Ranked:
1. Access control: someone outside the owner/team/role acts on or reads a claim (IDOR, cross-team review, leaks through filters).
2. Money: payments recorded twice, totals that don't match items, paid claims whose contents change.
3. Lifecycle bypass: a claim reaching approved/paid without the documented transitions (mass assignment, wrong-state actions).
4. Expense rules not enforced: meals daily limit, date window, amount limits, and differences between `POST /claims` and `POST /claims/{id}/items`.
5. Lists and search that hide or show the wrong claims: pagination metadata, defaults, search scope.
6. Protocol and error handling: auth scheme, malformed bodies, 405/Allow, id parsing.

Never/Always rules: a claim is paid at most once; `amount_paid` never exceeds `total`; one user never sees or changes another user's claims beyond what their role allows; only a manager of the owner's team approves; status changes only through the documented actions; `total` always equals the sum of the items.

## Charters
1. Explore claim visibility and write actions across users, teams and roles with all six tokens to discover access-control leaks. Tour: Saboteur + Back alley. Budget: 15.
2. Explore payment, totals and item rules with alice's and dave's tokens to discover lost/duplicated money and rule gaps between create and add-item. Tour: Money + Antisocial. Budget: 20.
3. Explore the claim lifecycle state table (draft/submitted/approved/rejected/paid × edit/submit/review/pay/delete/PATCH) to discover illegal or blocked transitions. Tour: Landmark + Obsessive-compulsive. Budget: 20.
4. Explore `GET /claims` paging, sorting and search with finance's token to discover wrong metadata and missing results. Tour: Guidebook. Budget: 12.
5. (Added after the access-control findings) Explore malformed requests, auth variants and cross-claim ids to discover error-handling gaps. Tour: Saboteur. Budget: 13.

## Findings

### F1: An owner can delete any item of any claim by giving that item's id under one of their own draft claims
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -s -w ' %{http_code}\n' -X DELETE $B/claims/13/items/14 -H "Authorization: Bearer $ALICE"   # 13 = alice's draft, 14 = item of bob's paid claim 8
  curl -s $B/claims/8 -H "Authorization: Bearer $DAVE"
  curl -s -w ' %{http_code}\n' -X DELETE $B/claims/13/items/5 -H "Authorization: Bearer $ALICE"    # 5 = item of bob's approved claim 3
  curl -s $B/claims/3 -H "Authorization: Bearer $DAVE"
  ```
- Expected: `404`. The docs say "The item must belong to the claim in the path" and "404 … no such item in this claim". Items of submitted, approved or paid claims must never change (Never/Always rule).
- Actual: Both deletes returned `204`. Claim 8 (bob, **paid**) now has only item 15, and `total` is `38.7` while `amount_paid` is `170`. Claim 3 (bob, approved) lost item 5 (154.2 flight), so its total dropped from 204.8 to `50.6`. `updated_at` did not change on either victim claim.
- Reproduced: 2 times (items 14 and 5).

### F2: PATCH accepts `status`, so an owner can set their own claim to approved without submitting it or having it reviewed, and finance then pays it
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -s -X PATCH $B/claims/11 -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' \
    -d '{"status":"approved","owner":"bob","total":1,"team":"mobile"}'
  curl -s $B/claims/11 -H "Authorization: Bearer $ALICE"
  curl -s -X POST $B/claims/11/pay -H "Authorization: Bearer $DAVE"
  curl -s -X PATCH $B/claims/12 -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"status":"approved"}'
  ```
- Expected: `status` is ignored. The docs say "any other field in the body, such as `status`, `owner` or `total`, is ignored". Status changes only through submit, review and pay.
- Actual: `200`, and draft claim 11 became `"status":"approved"` with `submitted_at:null` and `reviewed_by:null`. It appeared in carol's `?status=approved` list. Dave's pay call returned the claim, and finance's list later showed claim 11 as `"status":"paid"` with total `10130.01`. `owner`, `team` and `total` were ignored. Draft claim 12 was also set to `approved` the same way.
- Reproduced: 2 times (claims 11 and 12).

### F3: A manager can approve or reject claims from another team (claims they cannot even see)
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -s -X POST $B/claims/3/review -H "Authorization: Bearer $FRANK" -H 'Content-Type: application/json' -d '{"decision":"approve"}'
  curl -s -X POST $B/claims/9/review -H "Authorization: Bearer $FRANK" -H 'Content-Type: application/json' -d '{"decision":"reject","comment":"cross team"}'
  curl -s -w ' %{http_code}\n' $B/claims/9 -H "Authorization: Bearer $FRANK"
  ```
- Expected: `404`. Frank is the mobile manager and claims 3 (bob) and 9 (alice) belong to the platform team. "Only a manager of the claim owner's team can review it", and a claim you cannot see returns `404` on every endpoint.
- Actual: `200`. Claim 3 became `approved` with `"reviewed_by":"frank"`, and claim 9 became `rejected`. `GET /claims/9` as frank right afterwards returned `404 not_found`, so the review endpoint skips the visibility check that GET applies.
- Reproduced: 2 times (claims 3 and 9).

### F4: Paying an already-paid claim records a second payment and overwrites the payment details
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -s -X POST $B/claims/8/pay -H "Authorization: Bearer $DAVE" -H 'Content-Type: application/json' -d '{"reference":"REF-1"}'
  curl -s -X POST $B/claims/8/pay -H "Authorization: Bearer $DAVE" -H 'Content-Type: application/json' -d '{"reference":"REF-2"}'
  curl -s -X POST $B/claims/10/pay -H "Authorization: Bearer $DAVE"
  ```
- Expected: The repeat call returns `200` and "changes nothing" / "records nothing new" (docs, pay section and lifecycle section). `amount_paid` must equal `total`.
- Actual: Claim 8 (total 85): the first pay set `amount_paid: 85`, and the second set `amount_paid: 170`, a new `paid_at` and `payment_reference: "REF-2"`. Seed claim 10 (total 299, paid 2026-10-06, reference `PAY-2026-1006-02`): one repeat pay set `amount_paid: 598`, `paid_at` to now and `payment_reference: null`.
- Reproduced: 2 times (claims 8 and 10).

### F5: The `owner` filter on `GET /claims` lists other users' claims, including drafts
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -s "$B/claims?owner=alice" -H "Authorization: Bearer $BOB"
  curl -s "$B/claims?owner=bob" -H "Authorization: Bearer $ERIN"
  curl -s "$B/claims?owner=alice&status=draft" -H "Authorization: Bearer $ERIN"
  ```
- Expected: `owner` "narrows the list to that user's claims, among the claims you can see". An employee sees only their own claims, so these lists should be empty.
- Actual: `200`. Bob got all 4 of alice's claims (including draft 4 "Office chair"). Erin (mobile team) got bob's claims 3, 8 and 5. Erin got alice's drafts 13 and 4. Without `owner`, the same users see only their own claims (for example bob's `q=chair` returned nothing).
- Reproduced: 3 times.

### F6: A rejected claim cannot be resubmitted
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -s -w ' %{http_code}\n' -X POST $B/claims/5/submit -H "Authorization: Bearer $BOB"
  curl -s -w ' %{http_code}\n' -X POST $B/claims/9/submit -H "Authorization: Bearer $ALICE"
  ```
- Expected: `200` and status `submitted`. The docs allow submit "from `draft` and from `rejected`", and the lifecycle diagram shows `rejected ──submit──▶ submitted`.
- Actual: `409 {"error":"invalid_state","message":"claim is rejected; only draft claims can be submitted"}`. Editing a rejected claim does work (adding an item to claim 5 returned 201), so the only way forward for a rejected claim is blocked.
- Reproduced: 3 times (claim 5 twice, claim 9 once).

### F7: The meals limit of 60.00 per day applies to each item, not to the day's total
- Kind: bug
- Severity: medium
- Steps:
  ```
  # claim 11 already had meals 0.1 + 0.2 on 2026-11-10
  curl -s -X POST $B/claims/11/items -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"date":"2026-11-10","category":"meals","description":"c","amount":59.7}'
  curl -s -X POST $B/claims/11/items -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"date":"2026-11-10","category":"meals","description":"d","amount":0.01}'
  curl -s -X POST $B/claims/11/items -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"date":"2026-11-02","category":"meals","description":"f","amount":50}'
  curl -s -X POST $B/claims/11/items -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"date":"2026-11-02","category":"meals","description":"g","amount":20}'
  curl -s -X POST $B/claims -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' \
    -d '{"title":"meals","currency":"EUR","items":[{"date":"2026-11-01","category":"meals","description":"x","amount":30},{"date":"2026-11-01","category":"meals","description":"y","amount":30.01}]}'
  ```
- Expected: `400`. "The meals items that share a date may add up to at most 60.00. An item that would take that day over 60.00 is rejected."
- Actual: All accepted (`201`). That gives 60.01 on 2026-11-10 and 70.00 on 2026-11-02 in claim 11, and claim 12 was created with 60.01 on 2026-11-01. A single 61.00 meal is rejected (`"meals are limited to 60.00 per day"`), so only the per-item check runs. Both paths (create and add item) behave the same.
- Reproduced: 3 times.

### F8: The earliest allowed item date (today minus 90 days) is rejected
- Kind: bug
- Severity: low
- Steps:
  ```
  curl -s -X POST $B/claims -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' \
    -d '{"title":"x","currency":"EUR","items":[{"date":"2026-08-12","category":"travel","description":"edge","amount":10000}]}'
  curl -s -X POST $B/claims/11/items -H "Authorization: Bearer $ALICE" -H 'Content-Type: application/json' -d '{"date":"2026-08-12","category":"other","description":"e","amount":1}'
  ```
- Expected: Accepted. The docs say: "If today is 2026-11-10, the earliest accepted date is 2026-08-12", and the server date was 2026-11-10.
- Actual: `400 {"error":"validation_failed","message":"date must not be more than 90 days in the past","field":"items[2].date"}` (and `"field":"date"` on the items endpoint). 2026-08-13 is accepted.
- Reproduced: 2 times (both paths).

### F9: Text search `q` does not search item descriptions
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -s "$B/claims?q=TAXI" -H "Authorization: Bearer $DAVE"      # claim 3 has item "Taxi to client office"
  curl -s "$B/claims?q=release" -H "Authorization: Bearer $DAVE"   # claim 8 has item "Release It!"
  curl -s "$B/claims?q=Release" -H "Authorization: Bearer $DAVE"
  curl -s "$B/claims?q=Hotel" -H "Authorization: Bearer $ALICE"    # claim 1 has item "Hotel, 1 night"
  ```
- Expected: Claims whose "title or any of its item descriptions contains the text" (case-insensitive) are returned.
- Actual: `q=TAXI` returned only claim 9 (title match), not claim 3. `release`, `Release` and `Hotel` returned `total_count: 0`. Title matching works and is case-insensitive (`q=TAXI` → claim 9, `q=prÄs` → "Präsentation Malley").
- Reproduced: 4 times.

### F10: `meta.next_page` points to an empty page when the results fill the last page exactly
- Kind: bug
- Severity: low
- Steps:
  ```
  curl -s "$B/claims" -H "Authorization: Bearer $DAVE"                      # total_count 10
  curl -s "$B/claims?page=2" -H "Authorization: Bearer $DAVE"
  curl -s "$B/claims?per_page=5&page=2" -H "Authorization: Bearer $DAVE"
  ```
- Expected: `next_page: null` on the last page. The docs say it is "the number of the next page that has results, or null on the last page".
- Actual: With 10 results and per_page 10, `"next_page":2`, but page 2 returns `"data":[]` with `next_page:null`. With per_page=5, page 2 says `"next_page":3`. With per_page=3 (10 results), page 3 → `next_page: 4` is correct and page 4 → `null`, so the bug only shows when the total is an exact multiple of the page size.
- Reproduced: 2 times.

### F11: The default page size is 10, not the documented 20
- Kind: bug (or a docs error; needs a decision on which is right)
- Severity: low
- Steps: `curl -s "$B/claims" -H "Authorization: Bearer $FRANK"` (also as bob, erin and dave)
- Expected: "`per_page` … Default 20."
- Actual: `"meta":{"page":1,"per_page":10,...}`. Dave's 10 results were split across pages (`next_page: 2` shown).
- Reproduced: 4+ times (frank, bob, erin, dave).

## Questions
- `POST /claims/11/pay` on the self-approved claim (F2): my output was truncated before the status code. The body was the claim, and the list later showed it as `paid`, so it almost certainly returned 200, but I did not see the code.
- When F1 removes items, the victim claims' `updated_at` stays the same. That conflicts with "updated_at … an item added or removed", but it follows from F1 and I did not test it separately on a legitimate delete.
- I did not test whether a manager can review a claim in their own team that they own (managers cannot create claims, so this may not be reachable), or whether the review `comment` limit of 500 characters and the pay `reference` limit of 64 are enforced.
- I did not check whether a whitespace-only rejection comment is treated as missing (the probe hit `409` because the claim was rejected).

## Coverage
- **Charter 1 (access):** Cross-team and draft GETs correctly return 404 (carol→6, carol→4, bob→4, dave→7). Bob adding an item to alice's claim returns 404. Leaks: review endpoint (F3) and `owner` filter (F5). `q` did not leak.
- **Charter 2 (money/items):** Validation works for amount 1.005, "12.50", 10000.01, 61 meals in one item, future date 2026-11-11, and invalid date 2026-09-31. `total` was correct for 0.1+0.2+10000 (10000.3). Title is trimmed, `purpose:""` becomes null, and `status`/`owner` in `POST /claims` are ignored. Bugs: F4, F7, F8.
- **Charter 3 (lifecycle):** Deleting a rejected claim → 409 (correct). Submitting an empty draft → 400 `field: items` (correct). Adding an item to a rejected claim works. Bugs: F2, F6. Not reached: approve/reject twice, pay from submitted/rejected, PATCH on submitted, finance or owner calling review (403 paths).
- **Charter 4 (lists):** `sort=total` ascending order was correct, per_page=51 → 400, a page past the end → empty `data`, and the trailing slash works. Bugs: F9, F10, F11. Not reached: `-total` ties, invalid `status`/`sort`/`page=0` values.
- **Charter 5 (protocol):** A lowercase `bearer` works, a missing token → 401, malformed JSON → `invalid_json`, an array body → `invalid_body`, PUT → 405 with `Allow: GET, PATCH, DELETE`, and `/claims/001` → 404. All matched the docs. Found F1 here.
- Not reached: the 1 MB body limit (413), `invalid_url`, currency change via PATCH with a valid value, removing items from submitted claims through the correct path, and concurrent double-pay.
- Budget: 80 of 80 requests used (ping and 6 logins included).
