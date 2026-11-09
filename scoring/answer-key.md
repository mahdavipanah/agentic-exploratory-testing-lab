# Answer key: Restful-booker at commit 619d031

> Replay every item yourself: `python3 -I scripts/verify-answer-key.py`. The latest output is in [`answer-key-verification.md`](answer-key-verification.md).

Built **after** arm B's charters were committed (see git history), by reading `routes/index.js`, `helpers/*.js` and `models/booking.js`, then reproducing every item against a fresh local server (port 3009, 9 Nov 2026).

- `source`: found by source review. `run`: added from a confirmed finding in a run.
- `behaviour`: the API does something wrong. `contract`: behaviour and docs disagree, or the docs themselves are wrong.
- Auth below = `-H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM='`; JSON = `-H 'Content-Type: application/json'`; a valid body = firstname, lastname, totalprice, depositpaid, bookingdates.checkin/checkout.

## Status codes and errors

| ID | Type | Problem | Reproduction (observed) |
| --- | --- | --- | --- |
| K01 | contract | Health check returns 201 Created; docs table says "Success 200" | `GET /ping` → 201 |
| K02 | contract | Create returns 200 OK, not 201 Created | `POST /booking` valid JSON → 200 |
| K03 | behaviour | Create with a missing required field returns 500, not 400 (PUT returns 400 for the same body) | `POST /booking` without lastname → 500 |
| K04 | behaviour | Non-string name crashes the server | `POST /booking` with `"firstname":123` → 500 |
| K05 | contract | Delete returns 201 Created, not 200 or 204 | `DELETE /booking/2` with auth → 201 |
| K06 | behaviour | Writes to an unknown id return 405 Method Not Allowed, not 404 | `DELETE`, `PUT`, `PATCH /booking/9999` with auth → 405 |
| K07 | behaviour | Bad credentials return 200 with `{"reason":"Bad credentials"}`, not 401 | `POST /auth` wrong password → 200 |

## Validation and data integrity (create and full update)

| ID | Type | Problem | Reproduction (observed) |
| --- | --- | --- | --- |
| K08 | behaviour | totalprice is mangled on output: decimals dropped, huge values corrupted | `totalprice: 111.99` → 111; `totalprice: 1e21` → 1 |
| K09 | behaviour | Wrong-type totalprice accepted and returned as null | `totalprice: "abc"` → 200, `"totalprice":null` |
| K10 | behaviour | Empty or whitespace-only names accepted | `firstname: "   ", lastname: ""` → 200 with empty names |
| K11 | behaviour | Negative totalprice accepted | `totalprice: -500` → 200 |
| K12 | behaviour | Invalid dates accepted and returned garbled | `checkin: "not-a-date"` → 200, `"0NaN-aN-aN"` |
| K13 | behaviour | Checkout before checkin accepted | checkin 2019-01-01, checkout 2018-01-01 → 200 |
| K14 | behaviour | `depositpaid=false` sent in the documented XML or URL-encoded formats comes back `true` (any string is truthy) | URL-encoded `depositpaid=false` → `"depositpaid":true`; same for XML |
| K25 | behaviour | Create returns 500 when the Content-Type isn't one it handles exactly: XML with a charset, `application/xml`, `text/plain` or none (the body never becomes a booking) | `Content-Type: text/xml; charset=utf-8` → 500; `text/plain` → 500 |
| K30 | behaviour | PUT merges instead of replacing: an omitted optional field keeps its old value | PUT without additionalneeds → old "Breakfast" still returned |

## Partial update (PATCH)

| ID | Type | Problem | Reproduction (observed) |
| --- | --- | --- | --- |
| K21 | behaviour | PATCH skips validation entirely | `{"firstname":"","totalprice":"lots"}` → 200, empty name, price null |
| K22 | behaviour | Patching one nested date wipes the other | `{"bookingdates":{"checkin":"2031-01-01"}}` → checkout `"0NaN-aN-aN"` |
| K23 | behaviour | `bookingdates: null` corrupts the booking; every later GET returns 200 with a JavaScript error as the body | `GET /booking/5` → 200 `Cannot read properties of null (reading 'checkin')` |
| K24 | behaviour | `bookingid` in a PATCH or PUT body re-keys the booking: the old id vanishes, ids duplicate, and the response is 405 | PATCH booking 6 with `{"bookingid":7}` → 405; list shows 7 twice, 6 gone |

## Search (GET /booking)

| ID | Type | Problem | Reproduction (observed) |
| --- | --- | --- | --- |
| K15 | behaviour | checkin filter is "greater than", not "greater than or equal" as documented | booking with checkin 2030-01-10 missing from `?checkin=2030-01-10` |
| K16 | behaviour | checkout filter is inverted: returns bookings checking out **before** the date | `?checkout=2030-02-01` returns the 2030-01-20 checkout, not the 2030-02-20 one |
| K17 | behaviour | Invalid date in a filter returns 500 | `?checkin=garbage` → 500 |
| K18 | contract | Name search is case-sensitive; the docs' own example returns nothing | `?firstname=sally&lastname=brown` → `[]` |

## Content negotiation and ids

| ID | Type | Problem | Reproduction (observed) |
| --- | --- | --- | --- |
| K19 | behaviour | Accept must match one string exactly; anything else, including a typical client default, returns 418 I'm a Teapot | `Accept: application/json, text/plain, */*` → 418 |
| K20 | behaviour | With an unsupported Accept, writes succeed but report failure | POST → 418 but booking created; PATCH → 500 but change applied; PUT → 418 but applied |
| K26 | behaviour | Ids are parsed leniently | `/booking/1abc` → booking 1; `/booking/8.9` → booking 8 |
| K27 | behaviour | Basic auth scheme is case-sensitive (RFC 7235 says it isn't) | `Authorization: basic ...` → 403 |

## Documentation

| ID | Type | Problem | Where |
| --- | --- | --- | --- |
| K28 | contract | DELETE is documented with a literal path `/booking/1` | DeleteBooking heading |
| K29 | contract | PATCH examples use `curl -X PUT` with a partial body, which fails with 400 | PartialUpdateBooking examples |

## Added from the pilot runs (`run`)

Each was reproduced on a fresh server after the pilot. None was on the source-review list. K31 sits on a line of code the source review read and passed over.

| ID | Type | Problem | Reproduction (observed) | First reported by |
| --- | --- | --- | --- | --- |
| K31 | behaviour | The documented `Accept: application/x-www-form-urlencoded` returns 200 with the body `formurlencoded is not a function`; writes still apply | `GET /booking/1` with that Accept → 200, text/html, error text | B F8, C F14 |
| K32 | contract | XML responses are sent with `Content-Type: text/html` | `GET /booking/1` with `Accept: application/xml` → text/html | B F14, C F15 |
| K33 | behaviour | Impossible calendar dates roll over silently | checkin `2026-02-30` stored as `2026-03-02` | B F3, C F4 |
| K34 | behaviour | A booking with an unparseable stored date matches every checkin filter | `checkin: "not-a-date"`, then `?checkin=2099-01-01` returns it | B F11, C F13 (A as a question) |
| K35 | contract | additionalneeds is documented as required ("Optional: no") but can be omitted | `POST /booking` without it → 200 | B and C, as questions |
| K36 | contract | Docs: the Authorization header row is garbled (`YWRtaW46cGFzc3dvcmQxMjM=]`) | PUT, PATCH and DELETE header tables | C, as a question |
| K37 | contract | Docs: booking id is typed String for GET and Number everywhere else | URL parameter tables | C, as a question |
| K38 | contract | Docs: Content-Type rows list only JSON and XML, yet the examples send URL-encoded bodies | POST, PUT and PATCH header tables | C, as a question |

**Change to K25 after the pilot:** widened from "XML with a charset or `application/xml`" to any Content-Type the server doesn't handle exactly, after C F9 showed `text/plain` and no Content-Type fail the same way. The root cause is the same: the body never becomes a booking.

## Ceiling

**38 items**: 30 from source review (K01 to K30) and 8 from runs (K31 to K38).

## Environment-dependent (not in the ceiling)

| ID | Type | Problem | Reproduction (observed) |
| --- | --- | --- | --- |
| E01 | behaviour | Dates are formatted in the server's local time, so on a server west of UTC every date shifts back a day | Server with `TZ=America/New_York`: checkin `2018-01-01` is returned as `2017-12-31` |

E01 can't be seen when the server runs in UTC, so a black-box explorer can't find it under this setup. `start-target.sh` pins `TZ=UTC` so that results don't depend on the machine running the experiment. The pilot also ran in UTC.

