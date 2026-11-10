# Sealed answer key: Claimdesk (`targets/claimdesk`)

Held-out target for the exploratory-testing experiment. Domain: team expense claims. Written on 2026-11-10 together with the target, before any exploring run. Do not show it to the experimenter or to exploring agents until scoring is done.

- **Replay:** start a fresh server (`targets/claimdesk/start.sh 3101`), then run `python3 -I verify-key.py 3101`. It starts nothing, changes server state, and expects a fresh start every time. Result on 2026-11-10: `15 of 15 reproduced`, `Happy paths: 91 of 91 checks passed`.
- **Commitment:** `answer-key.sha256` holds the sha256 of this file.
- **Type:** `behaviour` means the API does something wrong. `contract` means the docs (`targets/claimdesk/api.md`) and the behaviour disagree, and either side could be the one to fix.
- **Hidden:** `yes` if the problem only shows after several requests (state, sequence, or a later read-back).

## Count

15 planted problems: 13 behaviour, 2 contract (docs defects: T14, T15).

| Difficulty | Items |
| --- | --- |
| easy (5) | T01, T02, T04, T12, T14 |
| medium (5) | T03, T08, T09, T11, T15 |
| hard (5) | T05, T06, T07, T10, T13 |

Hidden behind state (6): T03, T05, T07, T10, T11, T13.

## Setup for the reproductions

Every reproduction assumes a **fresh server**. Items don't depend on each other unless a note says so.

```bash
B=http://localhost:3101
H='Content-Type: application/json'
tok() { curl -s -X POST "$B/auth/login" -H "$H" -d "{\"username\":\"$1\",\"password\":\"$1-pass\"}" \
        | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])'; }
TA=$(tok alice); TB=$(tok bob); TE=$(tok erin); TC=$(tok carol); TF=$(tok frank); TD=$(tok dave)
day() { python3 -c "import datetime as d; print(d.datetime.now(d.timezone.utc).date() - d.timedelta(days=$1))"; }
D3=$(day 3); D89=$(day 89); D90=$(day 90)
```

Seed facts used below: alice (employee, platform) owns claims 1 (approved, total 251.40), 2 (paid), 4 (draft, item 8 = 249.00) and 9 (submitted). bob (employee, platform) owns 3 (submitted; items 5, 6, 7 = 154.20 + 31.70 + 18.90), 5 (rejected) and 8 (approved). erin (employee, mobile) owns 6 (submitted), 7 (draft) and 10 (paid). carol manages platform, frank manages mobile, dave is finance.

## Planted problems

| ID | Type | Class | Difficulty | Hidden | Problem | Reproduction (fresh server) | Expected | Actual |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T01 | behaviour | validation (numeric boundary) | easy | no | An item amount of `0` is accepted. Docs: amount must be greater than 0. Negative amounts are rejected correctly, with the message "amount must be greater than 0". Same in `POST /claims` inline items. | `curl -s -X POST $B/claims/4/items -H "Authorization: Bearer $TA" -H "$H" -d '{"date":"'$D3'","category":"other","description":"Nothing","amount":0}'` | `400 validation_failed`, `field: amount` | `201`, item with `"amount":0` |
| T02 | behaviour | boundary / off-by-one in pagination | easy | no | `meta.next_page` points past the end when the last page is exactly full (`total_count` a multiple of `per_page`). That next page is empty. Docs: `next_page` is `null` on the last page. | `curl -s "$B/claims?per_page=2&page=2" -H "Authorization: Bearer $TA"`<br>`curl -s "$B/claims?per_page=2&page=3" -H "Authorization: Bearer $TA"` | page 2: `"next_page":null` | page 2: `{"page":2,"per_page":2,"total_count":4,"next_page":3}`; page 3: `"data":[]` |
| T03 | behaviour | state machine (legal transition refused) | medium | yes | A rejected claim cannot be submitted again. Docs: submit is allowed from `draft` and `rejected`. Editing it first (PATCH, add item) doesn't help. Needs a rejected claim: seed claim 5, or submit, then reject as the team manager, then submit. | `curl -s -X POST $B/claims/5/submit -H "Authorization: Bearer $TB"`<br>Longer: alice creates a claim with an item, submits it, carol rejects it with a comment, alice submits it again. | `200`, `"status":"submitted"` | `409 invalid_state` "claim is rejected; only draft claims can be submitted"; status stays `rejected` |
| T04 | behaviour | authorization (data exposure) | easy | no | With the `owner` filter, `GET /claims` lists every claim of that user, ignoring visibility: drafts, other people's and other teams' claims. Works for every role. The same claims return `404` on `GET /claims/{id}`, so the list and the detail disagree. Docs: `owner` narrows "among the claims you can see". | `curl -s "$B/claims?owner=erin" -H "Authorization: Bearer $TA"`<br>Also: carol `?owner=alice` shows alice's draft 4; dave `?owner=erin` shows erin's draft 7. | `200`, empty `data` (alice can see none of erin's claims) | `200`, erin's claims 7 (draft), 6 and 10, with titles, totals and statuses |
| T05 | behaviour | authorization (privilege, missing team check) | hard | yes | Any manager can approve or reject a submitted claim from another team, including claims they can't see. You need an id that is invisible to you: get it from the other team's account, or by guessing. Side effect: for a draft the manager can't see, review returns `409` instead of `404`, which reveals that the draft exists (carol on claim 7). | `curl -s -o /dev/null -w '%{http_code}\n' $B/claims/6 -H "Authorization: Bearer $TC"` → `404`<br>`curl -s -X POST $B/claims/6/review -H "Authorization: Bearer $TC" -H "$H" -d '{"decision":"approve"}'`<br>Also frank on platform claims 3 or 9. | `404` (carol can't see claim 6, which belongs to the mobile team) | `200`, claim 6 `"status":"approved"`, `"reviewed_by":"carol"` |
| T06 | behaviour | money arithmetic and rounding | hard | no | Amounts are converted to cents by truncating, so many two-decimal values lose a cent: 19.99 → 19.98, also 0.29, 0.57, 1.15, 2.30, 4.35, 8.20 (about 6% of the values from 0.01 to 100.00). Round values (12.50, 9.99, 99.99, 0.10) are fine. The claim total and the payment use the stored, reduced amount. | `curl -s -X POST $B/claims/4/items -H "Authorization: Bearer $TA" -H "$H" -d '{"date":"'$D3'","category":"other","description":"Cable","amount":19.99}'`<br>`curl -s $B/claims/4 -H "Authorization: Bearer $TA"` | item `"amount":19.99`; claim total 268.99 | item `"amount":19.98`; claim total 268.98 |
| T07 | behaviour | validation (business rule, money limit) | hard | yes | The meals limit (meals items of one claim on the same date may add up to at most 60.00) is checked per item, not per day. A single meal over 60.00 is rejected correctly, but any number of meals of up to 60.00 each on one date are accepted. Same with separate `POST /claims/{id}/items` calls. | `curl -s -X POST $B/claims -H "Authorization: Bearer $TA" -H "$H" -d '{"title":"Meals","currency":"EUR","items":[{"date":"'$D3'","category":"meals","description":"Lunch","amount":40},{"date":"'$D3'","category":"meals","description":"Dinner","amount":35}]}'` | `400 validation_failed`, `field: items[1].amount` | `201`, claim with `"total":75` and 75.00 of meals on one date |
| T08 | behaviour | dates (boundary of a relative date rule) | medium | no | An item dated exactly 90 days ago is rejected. The docs say it is the earliest accepted date ("if today is 2026-11-10, the earliest accepted date is 2026-08-12"). The server compares the date's midnight with now minus 90×24 hours, so day 90 is refused for the whole day. Day 89 is accepted, and day 91 is rejected correctly. | `curl -s -X POST $B/claims/4/items -H "Authorization: Bearer $TA" -H "$H" -d '{"date":"'$D90'","category":"other","description":"Day 90","amount":5}'`<br>Control: same with `$D89` → `201` | `201` | `400 validation_failed` "date must not be more than 90 days in the past" |
| T09 | behaviour | partial update / mass assignment | medium | no | PATCH writes fields the docs call read-only: `status`, `submitted_at`, `reviewed_by`, `reviewed_at` and `review_comment`. Only `id`, `owner`, `team`, `items`, `total`, `created_at` and `updated_at` are protected. The owner can approve their own draft and finance then pays it, skipping review. Junk values are stored too (`"status":"banana"`). `{"status":"draft"}` on a rejected claim is a way around T03. Docs: other fields "are ignored". | `curl -s -X PATCH $B/claims/4 -H "Authorization: Bearer $TA" -H "$H" -d '{"status":"approved"}'`<br>`curl -s -X POST $B/claims/4/pay -H "Authorization: Bearer $TD"` | PATCH `200` with `status` still `draft`; pay `404` (dave can't see a draft) | PATCH `200`, `"status":"approved"`; pay `200`, `"status":"paid"`, `"amount_paid":249` |
| T10 | behaviour | consistency (list vs detail, totals vs items) | hard | yes | Removing an item updates the claim detail's `total` but not the stored total behind the list. So the list summary `total`, `sort=total` and the payment amount keep the old sum, and a paid claim shows `amount_paid` greater than `total`. Adding items keeps both in step; only removal breaks them. T13 causes the same drift on the victim's claim. | `curl -s -X DELETE $B/claims/4/items/8 -H "Authorization: Bearer $TA"` → `204`<br>`curl -s $B/claims/4 -H "Authorization: Bearer $TA"` → `"total":0`<br>`curl -s "$B/claims?q=office" -H "Authorization: Bearer $TA"` → `"total":249`<br>To the payment: add an item of 10, submit as alice, approve as carol (`{"decision":"approve"}`), pay as dave. | List total equals detail total (0, then 10); `amount_paid` equals `total` (10) | List `249` (then `259`); after paying, `"total":10`, `"amount_paid":259` |
| T11 | behaviour | idempotency / duplicates | medium | yes | Paying an already-paid claim records a second payment: `amount_paid` doubles, and `paid_at` and `payment_reference` are overwritten. Docs: repeating pay is safe, returns 200 and changes nothing. Already-paid seed claims 2 and 10 show it with a single call. | `curl -s -X POST $B/claims/1/pay -H "Authorization: Bearer $TD" -H "$H" -d '{"reference":"A"}'`<br>`curl -s -X POST $B/claims/1/pay -H "Authorization: Bearer $TD" -H "$H" -d '{"reference":"B"}'`<br>Or one call: `curl -s -X POST $B/claims/2/pay -H "Authorization: Bearer $TD"` | second call: `200`, `"amount_paid":251.4`, reference still `A`; claim 2: `"amount_paid":399` | second call: `"amount_paid":502.8`, `"payment_reference":"B"`; claim 2: `"amount_paid":798`, reference `null` |
| T12 | behaviour | error handling (500 for a client error) | easy | no | An unknown `sort` value (`title`, `+total`, `TOTAL`, `-`, …) returns `500 internal_error`. Docs: any value other than the four listed returns 400. If fewer than two claims match, it returns `200`, because the sort never runs (for example frank `?sort=title&status=paid`). | `curl -s "$B/claims?sort=title" -H "Authorization: Bearer $TA"` | `400 validation_failed`, `field: sort` | `500 {"error":"internal_error","message":"unexpected server error"}` |
| T13 | behaviour | authorization (object reference on a nested resource) | hard | yes | `DELETE /claims/{id}/items/{itemId}` checks only that the caller owns the claim in the path and that it is editable. It then deletes the item wherever it is, so an employee can remove items from other people's claims in any status, even submitted or approved ones. It shows as `204` for an item id that isn't in your claim. Confirm by reading the other claim as its owner or manager. | `curl -s -i -X DELETE $B/claims/4/items/5 -H "Authorization: Bearer $TA"` → `204`<br>`curl -s $B/claims/3 -H "Authorization: Bearer $TB"` | `404` "item not found"; bob's claim 3 keeps item 5 | `204`; bob's submitted claim 3 lost item 5 ("Flight Hamburg to Munich", 154.20): items now 6 and 7, detail total 50.6 (the list still shows 204.8, see T10) |
| T14 | contract | docs defect (default value) | easy | no | Default `per_page` is 10; the docs say 20. Visible in `meta.per_page` on any list without `per_page`. It changes paging once a user can see more than 10 claims. | `curl -s "$B/claims" -H "Authorization: Bearer $TD"` | `"per_page":20` | `"per_page":10` |
| T15 | contract | docs defect (search scope) | medium | no | `q` matches only the claim title. The docs say it also matches item descriptions. Matching is case-insensitive, as documented. | `curl -s "$B/claims?q=train" -H "Authorization: Bearer $TA"` (claim 1 has item "ICE train Hamburg to Berlin")<br>Control: `?q=berlin` → claim 1 | claim 1 in `data` | `"data":[]`, `total_count` 0 |

## Scoring notes: what counts as the same item

- **T02:** any report that `next_page` is non-null on the last page, or leads to an empty page, when the count divides evenly. On a server with more than 10 visible claims, the default list can show it together with T14 (for example `total_count` 10 with `next_page` 2). Score each part to its own item.
- **T04:** a list leak through `owner` for any role or user pair, and "list shows claims whose detail is 404", are both T04.
- **T05:** frank on platform claims, carol on mobile claims, and "review reveals invisible drafts with 409" are all T05. A report that a manager can review a claim of their **own** team that they can see is correct behaviour, not T05.
- **T06:** any amount stored one cent low, or a total one cent off, is T06. Reports that only use exactly representable values (12.50, 0.10) and say "rounding is fine" are not findings.
- **T09:** setting any of `status`, `submitted_at`, `reviewed_by`, `reviewed_at` or `review_comment` through PATCH, self-approval through PATCH, or skipping review, is T09. Getting a rejected claim back to draft through `{"status":"draft"}` is T09, not a finding against T03.
- **T10:** list total ≠ detail total after removing an item, `sort=total` ordering by the old total, or `amount_paid` ≠ `total`, are all T10. If the removed item came from another user's claim (T13), credit T13 for the authorization problem and T10 for the stale total only when the report describes the stale total.
- **T11:** "amount_paid doubles", "paid_at or payment_reference change on a repeat pay", and "already-paid seed claim gets paid again" are all T11.
- **T12:** any unknown sort value returning 500 is T12.

## Known quirks (intended, NOT bugs)

Rule on these as "not a finding" or "question only" (no credit, and not a false positive if worded as a question).

| ID | Behaviour | Why it is intended |
| --- | --- | --- |
| Q01 | A claim you may not see returns `404`, not `403`, on every endpoint | Documented (visibility section) |
| Q02 | Visible but not allowed returns `403` (finance reviewing, a manager editing, an employee reviewing their own claim) | Documented |
| Q03 | Managers and finance can't create claims (`403`); managers therefore have no claims to review | Documented: only employees create claims |
| Q04 | Managers see their team's claims except drafts; finance sees every claim except drafts; neither can open a draft (`404`), and finance paying a draft gets `404` | Documented |
| Q05 | A page past the end returns `200` with empty `data` and `next_page: null` | Documented |
| Q06 | `Content-Type` isn't checked: a JSON body sent as `text/plain` works. A form-encoded body (curl `-d` without a JSON header) returns `400 invalid_json` | Docs only ask clients to send JSON |
| Q07 | Unknown fields in `POST /claims` are ignored | Documented |
| Q08 | `PATCH {}` returns `200`; `updated_at` changes on every successful write, even one that changes nothing | Documented ("last successful write") |
| Q09 | Changing a claim's currency doesn't convert amounts | Documented |
| Q10 | Tokens never expire; there is no logout; each login issues another valid token | Documented |
| Q11 | Seed items are older than the 90-day window over time; they aren't re-validated | Documented ("Seed data is not re-checked") |
| Q12 | Money is a JSON number, so trailing zeros are dropped (`119`, `89.9`, `251.4`) | Documented |
| Q13 | Usernames, statuses, currencies, categories and sort values are case-sensitive (`eur` → 400, `Alice` → 401, `status=DRAFT` → 400) | Docs give exact lowercase or uppercase values |
| Q14 | An unknown `owner` username gives an empty list | Documented |
| Q15 | Path ids with leading zeros, `0`, signs, decimals or letters return `404` | Documented |
| Q16 | `HEAD`/`OPTIONS` and undocumented methods return `405` with an `Allow` header; `GET /claims/{id}/items` returns `405` (items come with the claim) | Documented 405 behaviour; no item-list endpoint |
| Q17 | Item ids are global across claims | Documented |
| Q18 | Rejecting needs a non-blank comment (whitespace only counts as missing); approving without a comment stores `review_comment: null` and replaces the previous comment | Documented |
| Q19 | State checks come before body validation (for example, reviewing an approved claim with a bad body returns `409`, not `400`) | Ordinary precedence |
| Q20 | Unknown routes return `404` and wrong methods return `405` even without a token; a known route without a token returns `401` | Ordinary precedence |
| Q21 | Submitting a claim with no items returns `400` with `field: items` | Documented |
| Q22 | Repeated query parameters use the first value; a whitespace-only `q` means no filter; an empty `status=` means no filter | Ordinary parsing |
| Q23 | "Today" is the UTC date: an item dated today is accepted, tomorrow (UTC) is rejected as future. Just after local midnight east of UTC, a tester's "today" can be rejected | Documented ("Today always means the current date in UTC") |
| Q24 | Login gives the same `401 invalid_credentials` for an unknown user and a wrong password | Deliberate, to avoid username enumeration |
| Q25 | Amount `10000` is accepted and `10000.01` rejected; `1e21` → "must not exceed 10000.00"; `0.001` or `1e-7` → "at most two decimal places"; `"12.50"` (string) → 400 | Documented |
| Q26 | Text lengths count UTF-16 code units (an emoji counts as 2) | Implementation detail, within reason |
| Q27 | Claims created in the same millisecond tie on `created_at` and are ordered by id ascending, also for `-created_at` | Documented ("Ties are ordered by id, ascending") |
| Q28 | `500` bodies are generic (`unexpected server error`); details go to the server log only | Intended |
| Q29 | A rejected claim stays visible to its team's manager, with the rejection's review fields | Intended |
| Q30 | Bodies over 1 MB return `413 payload_too_large` | Documented |
| Q31 | `PUT` isn't supported (`405`, `Allow: GET, PATCH, DELETE`) | Documented: partial update via PATCH only |
| Q32 | Claims can be created with no items, and an item can be `meals` of exactly 60.00 | Documented (items optional; "at most 60.00") |
| Q33 | A trailing slash is ignored (`/claims/` = `/claims`) | Documented |
| Q34 | Login returns the user's `name`; lists show only usernames | Documented shapes |
| Q35 | The docs' create and add-item examples use fixed dates (2026-11-05, 2026-11-02); after about 2027-02-01 those examples hit the 90-day rule and return `400` | Correct behaviour for an old example date |
