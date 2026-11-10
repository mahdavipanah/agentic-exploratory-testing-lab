# Exploration report

## Environment
- Target: Claimdesk API at http://localhost:3003 (docs say 3001; the run instructions say 3003). Black box: only HTTP via curl, plus api.md.
- Version: none exposed (no version endpoint or header). Server `Date` header and local `date -u` both read Tue, 10 Nov 2026 ~16:19 UTC, so "today" = 2026-11-10 and the documented date window is 2026-08-12..2026-11-10.
- State check: `GET /ping` returned 200 `{"status":"ok"}`. All six seed users logged in. As finance (dave), `GET /claims?per_page=50` listed exactly 8 non-draft seed claims. As alice, it listed 4 claims, including draft #4. That matches "ten sample claims in every status" (drafts #4 and #7 are hidden from finance), so the seed state was fresh.
- Headers: responses carry `Content-Type: application/json; charset=utf-8` as documented.

## Risks
Ranked, most harmful first:
1. Money paid that should not be: double payment, payment of claims that were never approved, wrong `amount_paid`.
2. Access control: a manager acting on another team's claims, employees approving their own claims, one user changing another's data.
3. Lifecycle state machine: actions allowed from wrong states, or documented transitions blocked.
4. Totals and derived data getting out of step (detail vs list, sort by total).
5. Item rules (date window, meals limit, amount limits) not enforced the same way on every path.
6. List and pagination contract (defaults, `next_page`, `total_count`).

## Charters
- C1: Explore review/visibility with users of every role and team to discover whether managers, finance and employees can act on claims outside their remit. Tour: Saboteur. Budget: 15.
- C2: Explore payment with the finance user to discover whether money can be paid twice or for unreviewed claims. Tour: Money + Obsessive-compulsive. Budget: 12.
- C3: Explore the claim lifecycle by trying every action in draft/rejected/paid states, plus PATCH with server-owned fields, to discover illegal or blocked transitions. Tour: Landmark + Antisocial. Budget: 18.
- C4: Explore item rules (date window, meals limit, amount limits) on both create and add-item paths to discover validation gaps. Tour: Antisocial + Intellectual. Budget: 15.
- C5 (added after F4 showed totals can change outside the normal path): Explore list/search/sort/pagination after item changes to discover stale or inconsistent derived data. Tour: FedEx + Guidebook. Budget: 10.

## Findings

Token values below were issued by `POST /auth/login` in this session: alice=`da2267fbfe47f431a50168c417214aa9d6523e30c1500c38`, bob=`0ebb474fe51ccb2089b7fff0af6906dc234e22c1adee2092`, erin=`7851094ca9a56c7a089ae297a31e1d947163903e604141a9`, carol=`b0a84e16783ba966be272e8b85df53360eabbd657b3d3c2d`, frank=`89202983f6c42bddca06ebca6ae1f8b28a4674bf327b9044`, dave=`79ae1394a7c7ae72cdd6d11c12d3d614cd59211a1953e791`.

### F1: A manager can approve or reject claims from another team, even though they can't see those claims
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -s http://localhost:3003/claims/3 -H "Authorization: Bearer <frank>"          # 404 claim not found
  curl -s -X POST http://localhost:3003/claims/3/review -H "Authorization: Bearer <frank>" \
    -H 'Content-Type: application/json' -d '{"decision":"approve"}'
  ```
- Expected: 404, because frank is the mobile team's manager and claim 3 belongs to bob (platform). The docs say: "Only a manager of the claim owner's team can review it" and "A claim you are not allowed to see behaves as if it did not exist: every endpoint returns 404 for it."
- Actual: `200`, `"status":"approved","reviewed_by":"frank"`. Repeated on claim 9 (alice, platform) with `{"decision":"reject","comment":"x-team"}`: `200`, `"status":"rejected","reviewed_by":"frank"`. Straight after that, `GET /claims/9` as frank returned `404`. The team check does work for non-managers: dave (finance) reviewing claim 6 got `403 forbidden`.
- Reproduced: 2 times (claims 3 and 9)

### F2: Paying a claim that is already paid adds the payment again and overwrites the payment details
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -s -X POST http://localhost:3003/claims/1/pay -H "Authorization: Bearer <dave>" -H 'Content-Type: application/json' -d '{"reference":"REF-A"}'
  curl -s -X POST http://localhost:3003/claims/1/pay -H "Authorization: Bearer <dave>" -H 'Content-Type: application/json' -d '{"reference":"REF-B"}'
  ```
- Expected: the second call returns 200 and changes nothing. The docs say: "If the claim is already `paid`, the call is safe to repeat: it returns 200 with the claim and changes nothing." Never/Always rule: money is paid only once, and `amount_paid` equals `total`.
- Actual: the first call returned `amount_paid: 251.4, payment_reference: "REF-A"`. The second returned `200` with `amount_paid: 502.8` (twice the total), `payment_reference: "REF-B"` and a new `paid_at`. On seed claim 2, which was already paid, `POST /claims/2/pay` with no body returned `amount_paid: 798` (total 399), `payment_reference: null` and a new `paid_at`.
- Reproduced: 2 times (claims 1 and 2)

### F3: The owner can PATCH `status` and `reviewed_by`, so an employee can approve their own claim and get it paid
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -s -X PATCH http://localhost:3003/claims/4 -H "Authorization: Bearer <alice>" -H 'Content-Type: application/json' \
    -d '{"status":"approved","owner":"bob","team":"mobile","total":1,"amount_paid":5,"id":99,"reviewed_by":"carol","purpose":""}'
  curl -s -X POST http://localhost:3003/claims/4/pay -H "Authorization: Bearer <dave>"
  ```
- Expected: `status` and the other server-owned fields are ignored, and the claim stays `draft`. The docs say: "any other field in the body, such as `status`, `owner` or `total`, is ignored."
- Actual: `200` with `"status":"approved","reviewed_by":"carol","submitted_at":null,"reviewed_at":null`. `owner`, `team`, `total` and `id` were ignored. Finance then paid it: `200`, `"status":"paid","amount_paid":249`. The claim was never submitted or reviewed. On claim 11 (bob, draft), `PATCH {"status":"paid"}` returned `200` with `"status":"paid","amount_paid":null,"paid_at":null`. That claim now shows as paid to finance in `GET /claims` although no payment was recorded. POST /claims correctly ignored `"status":"approved"` (it created a draft).
- Reproduced: 2 times (claims 4 and 11)

### F4: DELETE /claims/{id}/items/{itemId} deletes items from other users' claims
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -s -i -X DELETE http://localhost:3003/claims/9/items/20 -H "Authorization: Bearer <alice>"   # item 20 is in bob's claim 11
  curl -s http://localhost:3003/claims/11 -H "Authorization: Bearer <bob>"
  ```
- Expected: 404. The docs say: "The item must belong to the claim in the path" and "404 … or no such item in this claim".
- Actual: `204`, and item 20 disappeared from bob's claim 11. That claim's total fell from 60.01 to 30.11, while its `updated_at` stayed the same. The claim was in status `paid` at the time (see F3), so the state check was bypassed too. Repeated across teams: `DELETE /claims/9/items/23` as alice returned `204`, and item 23 vanished from erin's draft claim 12.
- Reproduced: 2 times (items 20 and 23)

### F5: The per-day meals limit of 60.00 is only checked per item, never as a daily sum
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -s -X POST http://localhost:3003/claims -H "Authorization: Bearer <erin>" -H 'Content-Type: application/json' \
    -d '{"title":"Meals test","currency":"USD","items":[{"date":"2026-11-09","category":"meals","description":"Lunch","amount":40},{"date":"2026-11-09","category":"meals","description":"Dinner","amount":30}]}'
  curl -s -X POST http://localhost:3003/claims/12/items -H "Authorization: Bearer <erin>" -H 'Content-Type: application/json' -d '{"date":"2026-11-08","category":"meals","description":"Coffee","amount":5}'
  curl -s -X POST http://localhost:3003/claims/12/items -H "Authorization: Bearer <erin>" -H 'Content-Type: application/json' -d '{"date":"2026-11-08","category":"meals","description":"Dinner","amount":56}'
  ```
- Expected: 400. The docs say: "the meals items that share a date may add up to at most 60.00. An item that would take that day over 60.00 is rejected."
- Actual: create returned `201` with total 70 for one day. Create with 35+35 (bob, claim 13) was also accepted. On the add-item path, 5 + 56 on one day were both `201`, and on claim 11, 30.1 + 29.9 + 0.01 = 60.01 was `201`. A single meals item of 61 is rejected (`400 "meals are limited to 60.00 per day"`), so only the per-item check exists.
- Reproduced: create path 2 times, add-item path 2 times

### F6: The `total` in the claim list doesn't update after an item is removed, and sort by total uses the old value
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -s -X DELETE http://localhost:3003/claims/9/items/27 -H "Authorization: Bearer <alice>"   # removes the 10000 item
  curl -s 'http://localhost:3003/claims?q=taxi' -H "Authorization: Bearer <alice>"
  curl -s http://localhost:3003/claims/9 -H "Authorization: Bearer <alice>"
  curl -s 'http://localhost:3003/claims?sort=-total&per_page=2' -H "Authorization: Bearer <alice>"
  ```
- Expected: the list `total` equals the detail `total` (the sum of item amounts). Oracles: consistency within the product, and "totals always match their parts".
- Actual: detail `total: 39.9` (items 37.8, 0.1, 2). The list summary still shows `total: 10039.9`, and `sort=-total` puts claim 9 first with 10039.9 ahead of claim 2 (399). Also seen on claim 11: the list showed `total: 60.01` while the detail showed `30.11` after item 20 was removed. Adding items does update the list total (claim 11 showed 60.01 after the 0.01 item was added).
- Reproduced: 2 times (claims 9 and 11)

### F7: A rejected claim cannot be resubmitted
- Kind: bug
- Severity: high (no claim that has been rejected can ever reach approval or payment)
- Steps:
  ```
  curl -s -X POST http://localhost:3003/claims/5/submit -H "Authorization: Bearer <bob>"
  ```
- Expected: 200, status `submitted`. The lifecycle diagram shows `rejected ──submit──▶ submitted`, and the docs say: "Allowed from `draft` and from `rejected`."
- Actual: `409 {"error":"invalid_state","message":"claim is rejected; only draft claims can be submitted"}`. The same happened for alice's claim 9 after it was rejected (and edited). Editing a rejected claim works (adding an item to claim 9 returned 201).
- Reproduced: 2 times (claims 5 and 9)

### F8: The oldest accepted item date is off by one: 2026-08-12 is rejected
- Kind: bug
- Severity: low
- Steps:
  ```
  curl -s -X POST http://localhost:3003/claims/9/items -H "Authorization: Bearer <alice>" -H 'Content-Type: application/json' -d '{"date":"2026-08-12","category":"travel","description":"Bus","amount":2}'
  ```
- Expected: 201. The docs say: "If today is 2026-11-10, the earliest accepted date is 2026-08-12." Today in UTC was 2026-11-10.
- Actual: `400 "date must not be more than 90 days in the past"`. Also rejected on the create path (`field: items[0].date`). 2026-08-13 is accepted, 2026-08-11 is rejected, and 2026-11-11 is rejected as a future date (correct).
- Reproduced: 2 times (add-item and create)

### F9: `next_page` points to an empty page when the last page is exactly full
- Kind: bug
- Severity: low
- Steps:
  ```
  curl -s 'http://localhost:3003/claims' -H "Authorization: Bearer <dave>"
  curl -s 'http://localhost:3003/claims?page=2' -H "Authorization: Bearer <dave>"
  ```
- Expected: `next_page: null` on the last page. The docs say: "`meta.next_page` is the number of the next page that has results, or `null` on the last page."
- Actual: page 1 had `{"per_page":10,"total_count":10,"next_page":2}`, and page 2 returned `data: []` with `next_page: null`. With `per_page=5&page=2`, the response had 5 items, `total_count: 10` and `next_page: 3`.
- Reproduced: 2 times

### F10: Default page size is 10, not the documented 20
- Kind: bug (or a docs fix: needs a decision)
- Severity: low
- Steps: `curl -s 'http://localhost:3003/claims' -H "Authorization: Bearer <dave>"`
- Expected: `per_page` 20 by default (docs: "Default 20").
- Actual: `meta.per_page: 10`, and only 10 of the 10 visible claims on page 1. With `q=taxi` (alice), the response also showed `per_page: 10`.
- Reproduced: 3 times

## Questions
- The submit error message says "only draft claims can be submitted", and the delete message says the same about drafts. That suggests the rejected→submitted path was dropped in code rather than just mis-documented. Confirming would need a source or changelog check. Either way, F7 stands.
- After F4, the victim claim's `updated_at` did not change even though its items changed. I saw this once on claim 11, and only as part of the F4 bug path, so I'm not reporting it separately.
- For seed claim 2 (already paid), I don't know the original `payment_reference`. The repeat pay without a body left it `null`, which may have erased a real reference. Confirming would need a GET before paying on a fresh seed.
- Does a paid claim created by F3 (`amount_paid: null`) break finance reports? There is no report endpoint, so I couldn't check.
- Not tested: whether a cross-team manager (F1) can also reject without the comment rule, or approve claims that are still drafts.

## Coverage
- C1 (access): cross-team GET and list are correctly hidden (404, and filtered out of lists). Finance gets 404 for drafts. Finance and owners get 403 on review. The no-token request got 401. Lowercase `bearer` works. Broken: the cross-team review (F1).
- C2 (money): first payment correct (`amount_paid == total`). The reference length limit of 64 is enforced. Broken: repeat payment (F2) and payment of self-approved claims (F3).
- C3 (lifecycle): on a paid claim, PATCH, add item, delete item, delete claim and submit all return 409. Deleting a rejected claim returns 409. Submitting a claim with no items returns 400 `field: items`. Reviewing a non-submitted claim returns 409. Rejecting without a comment returns 400. POST /claims ignores `status` and `owner`. Broken: PATCH status (F3) and resubmitting a rejected claim (F7). Not reached: a successful approve by the right manager followed by pay end to end, PATCH validation (title blank or too long, currency case), and DELETE of drafts.
- C4 (items): the future-date check works. An invalid calendar date (2026-09-31) is rejected. Amount 10000 is accepted, 10000.01 is rejected, and 1.005 is rejected for its decimal places. Description trimming worked on the title. Broken: the meals daily sum (F5) and the earliest date (F8). Not reached: string amounts, amount 0 or negative, the 200-character description limit, the category list, the 1 MB body limit, and arrays as bodies.
- C5 (lists): `q` is case-insensitive and searches the title. Ties and `-created_at` order looked right. Broken: stale totals (F6), `next_page` (F9) and the default `per_page` (F10). Not reached: the `owner` filter, invalid `status`/`sort`/`page` values, `per_page` above 50, and searching item descriptions.
- Other checks: `/claims/009` returns 404. PUT returns 405 with `Allow: GET, PATCH, DELETE`. Invalid JSON returns 400 `invalid_json`. A trailing slash on POST /claims/ works.
- Budget: 77 of 80 requests used.
