# Exploration report

## Environment
- Target: Claimdesk API at http://localhost:3001, black box, docs in `api.md` only.
- Date/time at start: 2026-11-10 16:23:50 UTC (from the server's `Date` header and the local `date -u`). So "today" = 2026-11-10 and the earliest valid item date = 2026-08-12.
- Health and state check: `GET /ping` → `200 {"status":"ok"}`. All six seed users logged in (ids 1–6, roles and teams match the docs). Finance's list showed 8 non-draft seed claims with the statuses the docs describe. Alice's list showed her 4 claims, including draft 4. No version endpoint exists.
- Tokens below are the ones issued in this session: alice `e736…`, bob `d69d…`, erin `f21e…`, carol `7ade…`, frank `cd17…`, dave `609b…`. The steps show them in full.

## Risks
1. Access control: a manager or employee acts on claims outside their team or ownership.
2. Money: a claim is paid twice, paid without approval, or amounts are changed when saved.
3. Lifecycle bypass: a claim reaches approved or paid without the documented transitions, or is changed after it is locked.
4. Validation rules not enforced (meals limit, date window, amount precision) on one of the two item paths.
5. Read models disagree with detail (list totals, search, paging).

## Charters
- C1: Explore review/read/edit endpoints with all six roles to discover cross-team or cross-owner access. Tour: Saboteur. Budget: 15.
- C2: Explore submit/review/pay with finance and managers to discover double payment and lifecycle bypasses. Tour: Money + Obsessive-compulsive. Budget: 15.
- C3: Explore item rules on `POST /claims` and `POST /claims/{id}/items` with boundary dates, amounts and meals totals to discover validation gaps. Tour: Antisocial + Intellectual. Budget: 20.
- C4: Explore edits in locked states (PATCH, item add/delete, delete claim), including server-owned fields, to discover state-table holes. Tour: Back alley. Budget: 15.
- C5: Explore `GET /claims` (search, filter, sort, paging) after writes to discover stale or wrong read models. Tour: FedEx + Guidebook. Budget: 10.

## Findings

### F1: A manager can approve or reject claims from another team, even claims they cannot see
- Kind: bug
- Severity: high
- Steps:
  ```
  # frank (mobile manager) cannot see bob's platform claim 3...
  curl -s http://localhost:3001/claims/3 -H "Authorization: Bearer cd17ff3660a47045d837212a9266e55303c0c5970e2b1aae"
  # ...but can approve it
  curl -s -X POST http://localhost:3001/claims/3/review -H "Authorization: Bearer cd17ff3660a47045d837212a9266e55303c0c5970e2b1aae" -H 'Content-Type: application/json' -d '{"decision":"approve"}'
  # carol (platform) approves erin's mobile claim 6
  curl -s -X POST http://localhost:3001/claims/6/review -H "Authorization: Bearer 7ade32042829e9a52b71802b9da8ab10a319a5960713a68d" -H 'Content-Type: application/json' -d '{"decision":"approve"}'
  ```
- Expected: `404` (docs: "A claim you are not allowed to see behaves as if it did not exist: every endpoint returns 404"; only "a manager of the owner's team" can review).
- Actual: GET → `404 not_found`; review → `200` with `"status":"approved","reviewed_by":"frank"` (claim 3) and `"reviewed_by":"carol"` (claim 6).
- Reproduced: 3 times. Also on a new claim: erin created and submitted claim 11, carol's GET returned 404, and carol's reject returned `200` with `"status":"rejected","reviewed_by":"carol"`. Employees (alice on her own claim) and finance correctly got `403` on review.

### F2: Paying an already-paid claim pays it again (amount_paid doubles)
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -s -X POST http://localhost:3001/claims/8/pay -H "Authorization: Bearer 609bb8d2d8970582dc245d6c0bee69b662ac2a986df44ff3" -H 'Content-Type: application/json' -d '{"reference":"PAY-1"}'
  curl -s -X POST http://localhost:3001/claims/8/pay -H "Authorization: Bearer 609bb8d2d8970582dc245d6c0bee69b662ac2a986df44ff3" -H 'Content-Type: application/json' -d '{"reference":"PAY-2"}'
  ```
- Expected: the second call returns `200` and "changes nothing" / "records nothing new" (docs, Pay section and lifecycle).
- Actual: first call `amount_paid: 85` (total 85). Second call `200`, `amount_paid: 170`, `payment_reference` overwritten to `"PAY-2"`, and `paid_at` and `updated_at` moved forward.
- Reproduced: 3 times. Claim 1 (total 251.4) went to `amount_paid` 251.4, then 502.8. Seed paid claim 2 (total 399) went to `amount_paid: 798` on one repeat pay.

### F3: An owner can set `status` with PATCH, skipping review; finance then pays the claim
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -s -X PATCH http://localhost:3001/claims/13 -H "Authorization: Bearer e73628e4e7d05f0386fd31b38e0d94b734e4d03e1e90a199" -H 'Content-Type: application/json' -d '{"status":"approved"}'
  curl -s -X POST http://localhost:3001/claims/13/pay -H "Authorization: Bearer 609bb8d2d8970582dc245d6c0bee69b662ac2a986df44ff3"
  ```
- Expected: `status` is ignored (docs: "any other field in the body, such as `status`, `owner` or `total`, is ignored"). The claim stays `draft`, and pay returns `409`.
- Actual: PATCH `200` with `"status":"approved"`, `submitted_at: null`, `reviewed_by: null`. Pay then returned `200`, `"status":"paid","amount_paid":70`. Alice paid herself for a claim nobody submitted or reviewed. That claim also breaks the meals limit (see F6).
- Reproduced: 2 times. The other was bob's empty draft 14: PATCH `{"status":"approved","total":5000,"owner":"erin","team":"mobile","amount_paid":1}` returned `200` with `"status":"approved"` and 0 items. `owner`, `team`, `total` and `amount_paid` were correctly ignored.

### F4: DELETE /claims/{id}/items/{itemId} removes items from other claims, including other users' locked claims
- Kind: bug
- Severity: high
- Steps:
  ```
  # alice's draft 4 owns neither item; item 7 belongs to bob's approved claim 3
  curl -s -i -X DELETE http://localhost:3001/claims/4/items/7 -H "Authorization: Bearer e73628e4e7d05f0386fd31b38e0d94b734e4d03e1e90a199"
  curl -s http://localhost:3001/claims/3 -H "Authorization: Bearer 609bb8d2d8970582dc245d6c0bee69b662ac2a986df44ff3"
  ```
- Expected: `404` ("The item must belong to the claim in the path"; "no such item in this claim").
- Actual: `204`. Bob's approved claim 3 lost item 7 (Lunch 18.9), and its total went from 204.8 to 185.9 without any state check. `updated_at` did not change.
- Reproduced: 2 times. `DELETE /claims/4/items/16` also returned `204` and emptied alice's submitted claim 9 (now `items: []`, `total: 0`, still `submitted`). The direct `DELETE /claims/9/items/16` had correctly returned `409`.

### F5: Item amounts lose a cent when saved (19.99 → 19.98)
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -s -X POST http://localhost:3001/claims/4/items -H "Authorization: Bearer e73628e4e7d05f0386fd31b38e0d94b734e4d03e1e90a199" -H 'Content-Type: application/json' -d '{"date":"2026-11-01","category":"other","description":"a","amount":19.99}'
  curl -s -X POST http://localhost:3001/claims -H "Authorization: Bearer e73628e4e7d05f0386fd31b38e0d94b734e4d03e1e90a199" -H 'Content-Type: application/json' -d '{"title":"cents","currency":"EUR","items":[{"date":"2026-11-02","category":"other","description":"x","amount":4.35},{"date":"2026-11-02","category":"other","description":"y","amount":0.29},{"date":"2026-11-02","category":"other","description":"z","amount":19.99}]}'
  ```
- Expected: amounts stored exactly as sent (two decimals are valid per the docs). Oracle: never lose money.
- Actual: `201` with `"amount":19.98`. The second request stored 4.35→4.34, 0.29→0.28 and 19.99→19.98 (claim total 24.6 instead of 24.63). This looks like truncation after a floating-point multiply by 100. Values such as 1, 10000, 40 and 60.0 were stored correctly.
- Reproduced: 4 values on both item paths.

### F6: The meals daily limit (60.00) is checked per item, not per day
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -s -X POST http://localhost:3001/claims -H "Authorization: Bearer e73628e4e7d05f0386fd31b38e0d94b734e4d03e1e90a199" -H 'Content-Type: application/json' -d '{"title":"meals","currency":"EUR","items":[{"date":"2026-11-03","category":"meals","description":"lunch","amount":40},{"date":"2026-11-03","category":"meals","description":"dinner","amount":30}]}'
  ```
- Expected: `400`. Docs: "the meals items that share a date may add up to at most 60.00. An item that would take that day over 60.00 is rejected".
- Actual: `201`, claim 13 with 70.00 of meals on 2026-11-03. A single 61.00 meal is rejected ("meals are limited to 60.00 per day").
- Reproduced: 3 times. On `POST /claims/12/items`, 40 + 20 + 5 on 2026-11-03 were all `201`. On 2026-11-05, 60 and then 0.5 were both `201`.

### F7: An item dated exactly 90 days ago (2026-08-12) is rejected
- Kind: bug
- Severity: low
- Steps:
  ```
  curl -s -X POST http://localhost:3001/claims/4/items -H "Authorization: Bearer e73628e4e7d05f0386fd31b38e0d94b734e4d03e1e90a199" -H 'Content-Type: application/json' -d '{"date":"2026-08-12","category":"other","description":"earliest","amount":1}'
  ```
- Expected: `201`. Docs: "If today is 2026-11-10, the earliest accepted date is 2026-08-12".
- Actual: `400 {"message":"date must not be more than 90 days in the past","field":"date"}`. 2026-08-13 is accepted. 2026-08-11 and 2026-11-11 are correctly rejected, 2026-11-10 is accepted, and 2026-09-31 is rejected as invalid.
- Reproduced: 2 times, on both paths (`POST /claims` gives `field: items[0].date`).

### F8: List totals are not updated when an item is removed
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -s -i -X DELETE http://localhost:3001/claims/12/items/33 -H "Authorization: Bearer e73628e4e7d05f0386fd31b38e0d94b734e4d03e1e90a199"
  curl -s "http://localhost:3001/claims?q=cents" -H "Authorization: Bearer e73628e4e7d05f0386fd31b38e0d94b734e4d03e1e90a199"
  curl -s http://localhost:3001/claims/12 -H "Authorization: Bearer e73628e4e7d05f0386fd31b38e0d94b734e4d03e1e90a199"
  ```
- Expected: the summary `total` equals the detail `total` ("Sum of the item amounts" in both objects).
- Actual: after the `204` delete, the list still shows `"total":150.1` but the detail shows `"total":149.6`. Adding items does update the list total.
- Reproduced: 3 claims. Claim 3: list 204.8 vs detail 185.9, seen in 2 lists (finance `sort=total` and `status=approved`). Claim 9: list 37.8 vs detail 0. `sort=total` also orders by the stale value.

### F9: Search `q` does not match item descriptions
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -s "http://localhost:3001/claims?q=Hamburg" -H "Authorization: Bearer 609bb8d2d8970582dc245d6c0bee69b662ac2a986df44ff3"
  ```
- Expected: claims 1 ("ICE train Hamburg to Berlin") and 3 ("Flight Hamburg to Munich"). Docs: "A claim matches if its title or any of its item descriptions contains the text."
- Actual: `200 {"data":[],"meta":{...,"total_count":0}}`. Title search works (`q=berlin` finds claim 1, `q=cents` finds claim 12).
- Reproduced: 2 times (`q=HAMBURG`, `q=Hamburg`).

### F10: Default `per_page` is 10, not 20
- Kind: bug
- Severity: low
- Steps:
  ```
  curl -s "http://localhost:3001/claims?status=approved" -H "Authorization: Bearer 609bb8d2d8970582dc245d6c0bee69b662ac2a986df44ff3"
  ```
- Expected: `meta.per_page: 20` (docs: "Default 20").
- Actual: `"meta":{"page":1,"per_page":10,...}`.
- Reproduced: 6+ times across `q`, `status` and `q=cents` lists, for both finance and alice. I did not check directly whether more than 10 results would be cut off.

## Questions
- **Resubmitting a rejected claim returns 409.** Erin added an item to rejected claim 11 (`201`, so editing works), then `POST /claims/11/submit` returned `409 {"message":"claim is rejected; only draft claims can be submitted"}`. The docs say submit is allowed from `rejected`. I saw this once (it was the last request of the budget), so it needs a reproduction.
- **`updated_at` after item removal.** It did not change after the cross-claim deletion (F4). I did not check whether a normal item delete updates it.
- After the repeat pay of seed claim 2, `payment_reference` was `null`. The seed value before that was never read, so I can't say whether a stored reference was wiped.
- Could a manager approve a claim of a user with no team, or approve a draft through the cross-team gap? Not tried.

## Coverage
- C1 (access, 15 req): cross-team GET (404 OK), cross-team review (F1), employee self-review and finance review (403 OK), employee reading another's claim and manager reading a draft (404 OK).
- C2 (money/lifecycle, ~10 req): pay and repeat pay (F2), pay after PATCH-approval (F3), submit without items (400 OK). Not tested: paying a submitted claim (409), non-finance pay (403), `reference` over 64 characters.
- C3 (items, ~20 req): date boundaries (F7; future and invalid dates OK), amounts (F5; 0, negative, string, 1.005 and 10000.01 rejected OK; 10000 accepted), meals limit (F6). Not tested: description length/trim, invalid category, item validation in a rejected claim vs a draft.
- C4 (locked states, ~12 req): PATCH, add item, delete item and delete claim on submitted/paid claims all returned 409 OK. Mass assignment (F3) and cross-claim item delete (F4). Whitespace trimming of title and `""` purpose → null work. `currency:"usd"` was rejected OK.
- C5 (lists, ~10 req): paging and `next_page` correct (11 claims, 5 per page → pages 2/3, `next_page` 3/null), `per_page=51` → 400 OK, sort by total, stale totals (F8), search (F9), default page size (F10). Not tested: `owner` filter, invalid `page`, `sort` ties, the manager's list view.
- Not reached: malformed JSON, non-object bodies, 413, 405/`Allow` headers, trailing slash, `007`-style ids, lower-case `bearer`, unknown token, and concurrency.
- Budget: 80 of 80 requests used (7 environment/login, 73 exploration).
