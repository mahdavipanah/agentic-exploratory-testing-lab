# Exploration report

## Charters

Risks (from the docs, ordered by harm to a client):
- R1 Authorization/visibility leaks: managers/finance seeing drafts, cross-team access, 403 vs 404 leaking existence, non-owners mutating claims, an employee reviewing their own claim.
- R2 Money/lifecycle: double payment, pay of wrong amount, edits after submission/approval changing the paid total, invalid transitions not returning 409.
- R3 Item validation: date boundaries (90 days, future, invalid calendar dates), meals daily limit 60.00 (cross-item, boundary), amount precision (2 decimals, float sums), string amounts, atomicity of POST /claims with a bad item.
- R4 List endpoint: pagination meta (total_count, next_page), sorting ties, filters by status/owner/q, invalid params.
- R5 Protocol: malformed JSON, wrong content types, ids like `007`, trailing slash, 405 with Allow header.

Charters:
- C1 (Saboteur tour, ~20 requests): Explore claim visibility and permissions with all six seed users and the seed claims to discover leaks of drafts, cross-team access, or mutations by non-owners.
- C2 (Obsessive-compulsive tour, ~18 requests): Explore lifecycle actions (submit, review, pay) with repeated and reordered calls to discover double payments, illegal transitions, or stale totals.
- C3 (Antisocial tour, ~22 requests): Explore item validation with boundary dates, amounts, meals totals and wrong types to discover accepted invalid data or rejected valid data.
- C4 (Guidebook tour, ~14 requests): Explore GET /claims with the documented query parameters to discover wrong pagination meta, sort order, or filtering.
- Reserve ~6 requests for reproductions and protocol checks (Back alley tour, R5).

- Added during C4 (Back alley, from reserve): PATCH with forbidden fields (`status`, `owner`, `total`). I added this because PATCH is the one write endpoint that says it "ignores" fields, which is a classic mass-assignment risk.

Tokens below: ALICE=9e888337…, BOB=3c69284a…, ERIN=cfac0b75…, CAROL=3a03d098…, FRANK=157c78a3…, DAVE=240a560e… (full tokens in the commands).

## Findings

### F1: Any employee can approve their own draft by PATCHing `status`, and finance will then pay it
- Severity: high
- Request: `curl -s -X PATCH http://localhost:3001/claims/4 -H "Authorization: Bearer 9e888337eb24988b52ff84653c29bd0f9c053aa245257c06" -H 'Content-Type: application/json' -d '{"status":"approved","total":1,"owner":"bob"}'`
- Expected: 200 with status unchanged (`draft`). Docs (PATCH): "any other field in the body, such as `status`, `owner` or `total`, is ignored."
- Actual: 200, `"status":"approved"` with `submitted_at:null`, `reviewed_by:null`. `owner` and `total` were ignored. A follow-up `POST /claims/4/pay` as dave returned 200 with `"status":"paid","amount_paid":351`, so the claim was paid without being submitted or reviewed.
- Reproduced: 2 times (claim 4, and claim 11 with `{"status":"approved"}` → 200, `"status":"approved"`)

### F2: A manager can review claims from another team
- Severity: high
- Request: `curl -s -X POST http://localhost:3001/claims/3/review -H "Authorization: Bearer 157c78a3f88029382a2b77bda87284aed6a7cd791dc3e5ab" -H 'Content-Type: application/json' -d '{"decision":"approve"}'`
- Expected: 404. Frank manages `mobile`, and claim 3 belongs to bob (`platform`). Docs: "Only a manager of the claim owner's team can review it", and a claim you cannot see gives 404 on every endpoint. `GET /claims/9` as frank does return 404.
- Actual: 200, `"status":"approved","reviewed_by":"frank"`.
- Reproduced: 2 times (claim 3 approve; claim 9 (alice, platform) reject → 200, `"status":"rejected","reviewed_by":"frank"`). In the same session `GET /claims/9` as frank returned 404.

### F3: Paying an already-paid claim pays it again and doubles `amount_paid`
- Severity: high
- Request: `curl -s -X POST http://localhost:3001/claims/8/pay -H "Authorization: Bearer 240a560eed357372f587c11d527bb202136f7faeaf5cb3a1" -H 'Content-Type: application/json' -d '{"reference":"PAY-2"}'` (sent after a first successful pay with `PAY-1`)
- Expected: 200 with no change. Docs: "If the claim is already `paid`, the call is safe to repeat: it returns `200` with the claim and changes nothing."
- Actual: 200, `"amount_paid":170` (total is 85), `payment_reference` overwritten to `"PAY-2"`, and `paid_at`/`updated_at` moved forward.
- Reproduced: 2 times (claim 8: 85 → 170; claim 1: total 251.4, second pay → `"amount_paid":502.8`)

### F4: An owner can delete items from other users' claims, including approved ones, through their own claim's path
- Severity: high
- Request: `curl -s -i -X DELETE http://localhost:3001/claims/4/items/7 -H "Authorization: Bearer 9e888337eb24988b52ff84653c29bd0f9c053aa245257c06"`
- Expected: 404. Docs: "The item must belong to the claim in the path." Item 7 belongs to bob's claim 3, which is `approved` and cannot be edited.
- Actual: 204. A later `GET /claims/3` as bob shows item 7 gone and `total` changed from 204.8 to 185.9 on an approved claim. `updated_at` did not change.
- Reproduced: 2 times (item 13 from erin's draft claim 7 was deleted the same way; claim 7 then had `"items":[],"total":0`)

### F5: The meals limit of 60.00 per day is checked per item, not per day
- Severity: medium
- Request: `curl -s -X POST http://localhost:3001/claims/4/items -H "Authorization: Bearer 9e888337eb24988b52ff84653c29bd0f9c053aa245257c06" -H 'Content-Type: application/json' -d '{"date":"2026-11-08","category":"meals","description":"dinner","amount":50}'` (after a 50.00 meals item on 2026-11-08 in the same claim)
- Expected: 400. Docs: "the `meals` items that share a date may add up to at most 60.00".
- Actual: 201, so meals on that day total 100. A single 60.01 item is rejected (`"meals are limited to 60.00 per day"`), so only the per-item check runs.
- Reproduced: 3 times (POST /claims with meals 40 + 20.01 on one date → 201, total 60.01; claim 12 with an extra 0.01 meal on a day already at 60 → 201; claim 4 with 50 + 50 → 201)

### F6: An item amount of 0 is accepted
- Severity: medium
- Request: `curl -s -X POST http://localhost:3001/claims/11/items -H "Authorization: Bearer 9e888337eb24988b52ff84653c29bd0f9c053aa245257c06" -H 'Content-Type: application/json' -d '{"date":"2026-11-02","category":"travel","description":"zero","amount":0}'`
- Expected: 400. Docs: amount must be "Greater than 0". A negative amount does get 400 with `"amount must be greater than 0"`.
- Actual: 201, `"amount":0`.
- Reproduced: 2 times

### F7: The oldest documented valid date (today − 90 days) is rejected
- Severity: medium
- Request: `curl -s -X POST http://localhost:3001/claims/4/items -H "Authorization: Bearer 9e888337eb24988b52ff84653c29bd0f9c053aa245257c06" -H 'Content-Type: application/json' -d '{"date":"2026-08-12","category":"travel","description":"earliest again","amount":2}'`
- Expected: 201. Docs: "If today is 2026-11-10, the earliest accepted date is 2026-08-12". The server's own timestamps show today is 2026-11-10 UTC.
- Actual: 400, `"date must not be more than 90 days in the past"`. 2026-08-13 and 2026-11-10 are accepted. This is an off-by-one error.
- Reproduced: 2 times

### F8: Search `q` does not match item descriptions
- Severity: medium
- Request: `curl -s "http://localhost:3001/claims?q=Hotel" -H "Authorization: Bearer 240a560eed357372f587c11d527bb202136f7faeaf5cb3a1"`
- Expected: claim 1, which has the item "Hotel, 1 night". Docs: "A claim matches if its title or any of its item descriptions contains the text."
- Actual: 200, `"data":[]`, `total_count:0`. Title search works and ignores case (`q=BERLIN` → claim 1).
- Reproduced: 3 times (`q=HOTEL`, `q=Hotel`, `q=ice%20train` all returned nothing)

### F9: The default `per_page` is 10, not 20
- Severity: low
- Request: `curl -s "http://localhost:3001/claims" -H "Authorization: Bearer 240a560eed357372f587c11d527bb202136f7faeaf5cb3a1"`
- Expected: `meta.per_page: 20`. Docs: "`per_page` … Default 20."
- Actual: 200, `"meta":{"page":1,"per_page":10,...}`. A client that relies on the default and does not follow `next_page` will miss claims.
- Reproduced: 3 times (also seen in the `q=atomic` and `q=HOTEL` responses)

## Questions
- `updated_at` on claims 3 and 7 did not change when F4 removed their items. The docs say an item removal updates it. This was only seen through the F4 bug path; I did not check whether a normal item removal by the owner updates `updated_at`.
- Seed claim 2 is already `paid`. Given F3, paying it again would probably double its amount too. Not tested.
- The cumulative meals total of 0.1 + 0.2 + 59.7 (a floating-point edge case) was accepted. Because of F5, I can't tell whether the sum is compared with rounding.
- When an approved claim is changed (F4), `amount_paid` would differ from what the manager approved. I did not pay claim 3 to confirm.

## Coverage
- C1 (visibility/permissions): lists for an employee, a manager and finance; drafts hidden from managers/finance/other employees; cross-team GET (404 ✓); review by an employee, finance and another team's manager; PATCH by a manager (403 ✓); adding items to another employee's claim (404 ✓); deleting another claim's item through your own claim's path.
- C2 (lifecycle): double pay; PATCH on a submitted claim (409 ✓); review of an approved claim (409 ✓); submit with no items (400 ✓); delete of a rejected claim (409 ✓); pay by an employee (403 ✓).
- C3 (items): date boundaries, future dates, invalid calendar dates, the meals limit (single item and cumulative, both via POST /claims and /items), amount 0/negative/10000/10000.01/3 decimals/string, atomicity of POST /claims with an invalid `items[1]` (✓, nothing created and the field path is correct).
- C4 (list): default page size, pagination meta across pages (✓), sort by total (✓), `q` on titles and item descriptions, invalid `per_page`/`page` (400 ✓).
- Back alley: id `007` → 404 ✓; PUT → 405 with `Allow: GET, PATCH, DELETE` ✓; invalid JSON → 400 ✓; no token → 401 ✓; lowercase `bearer` ✓; PATCH mass-assignment (F1).
- Not covered: login validation errors, `invalid_body` (array bodies), 413 payload limit, trailing slash, PATCH field validation (title length, currency case), the `owner`/`status` list filters, `sort=created_at` ties, the reject comment rules (missing or >500 characters), the pay `reference` length limit, resubmitting a rejected claim, and the `Location` header on 201.
- Requests used: 76 of 80 (including 6 logins; no GET /ping).
