# Exploration report

## Environment
- Target: http://localhost:3004 (Express, `X-Powered-By: Express`). No version endpoint is exposed.
- Server clock (Date header): Mon, 09 Nov 2026 ~16:00 GMT.
- State check: `GET /ping` returned 201 Created. `POST /auth` with admin/password123 returned a token (`0d812c9433c1267`). I created booking 11 and read it back unchanged with `GET /booking/11`. The seed data had bookings 1–10.
- Auth used: Cookie `token=0d812c9433c1267` and Basic `admin:password123`. Both work.

## Risks
1. Data corruption on update. Partial updates and null or odd values can damage stored bookings.
2. Wrong money and wrong flags. `totalprice` precision and the `depositpaid` boolean are coerced incorrectly.
3. Invalid dates accepted and stored. This includes rollover, NaN, and checkout before checkin.
4. Search returns wrong results. The date filter semantics differ from the docs, and filters are case sensitive.
5. Writes possible without valid auth (PUT/PATCH/DELETE).
6. Formats (JSON/XML/urlencoded) handle the same data differently.
7. Error handling: 500s, error text returned with 200, and status codes for missing resources.

## Charters
- C1: Explore PUT/PATCH/DELETE auth with missing, invalid, empty and wrong credentials to discover writes that bypass auth. Tour: Saboteur. Budget: 10.
- C2: Explore PUT/PATCH with partial, null and edge payloads to discover data loss or corruption. Tour: FedEx + Antisocial. Budget: 20.
- C3: Explore create/update validation (price, booleans, dates, types, missing fields) to discover bad data accepted or crashes. Tour: Antisocial. Budget: 20.
- C4: Explore GET /booking filters at date boundaries and with name case to discover wrong search results. Tour: Guidebook. Budget: 15.
- C5: Explore XML/urlencoded input and Accept output and DELETE flows to discover format inconsistencies. Tour: Guidebook + Back alley. Budget: 15.

## Findings

### F1: PATCH with `bookingdates: null` permanently corrupts the booking, and it breaks date search for all users
- Kind: bug
- Severity: high
- Steps:
  1. `curl -s -i -X PATCH http://localhost:3004/booking/20 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=0d812c9433c1267' -d '{"bookingdates":null,"firstname":null}'`
  2. `curl -s -i http://localhost:3004/booking/20 -H 'Accept: application/json'` (also tried with `Accept: application/xml`)
  3. `curl -s -i 'http://localhost:3004/booking?checkin=2000-01-01'`
  4. Delete the corrupted bookings, then repeat step 3.
- Expected: a 400 rejecting null, with the record unchanged. One bad record should never affect other users' searches (purpose and conventions oracles).
- Actual: the PATCH returns `200 OK`, `Content-Type: text/html`, body `Cannot read properties of null (reading 'checkin')`. After that, `GET /booking/20` always returns 200 with the same error text, in both JSON and XML, so the booking can no longer be read. `GET /booking?checkin=2000-01-01` returns `500 Internal Server Error` for everyone. After deleting the corrupted bookings 19 and 20, the same search returned 200 with the full list.
- Reproduced: 2 (booking 20 and booking 19). Both stayed unreadable on read-back.

### F2: PATCH with only one booking date turns the other date into "0NaN-aN-aN"
- Kind: bug
- Severity: high
- Steps:
  - `curl -s -X PATCH http://localhost:3004/booking/11 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=0d812c9433c1267' -d '{"bookingdates":{"checkout":"2019-06-06"}}'`
  - `curl -s -X PATCH http://localhost:3004/booking/1 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=0d812c9433c1267' -d '{"bookingdates":{"checkin":"2017-03-03"}}'`
- Expected: the docs list `bookingdates.checkin` and `bookingdates.checkout` as separately optional for PATCH, so the omitted date should keep its value.
- Actual: 200. Booking 11 became `"checkin":"0NaN-aN-aN","checkout":"2019-06-06"`, and GET read-back showed the same. Booking 1 became `"checkin":"2017-03-03","checkout":"0NaN-aN-aN"`.
- Reproduced: 2 (one per date field), plus one GET read-back.

### F3: Decimal `totalprice` is silently truncated to an integer
- Kind: bug
- Severity: high
- Steps: `curl -s -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Dec","lastname":"Only","totalprice":150.75,"depositpaid":true,"bookingdates":{"checkin":"2019-01-01","checkout":"2019-01-05"},"additionalneeds":"x"}'`
- Expected: the type is Number, so 150.75 should be stored as is or rejected. Losing money silently is a known bug pattern (familiar problems oracle).
- Actual: 200 with `"totalprice":150`. GET /booking/14 also showed 150. The same happened on create with 99.99→99, on JSON PATCH with 200.5→200, and on urlencoded PATCH with 12.5→12.
- Reproduced: 4.

### F4: depositpaid sent as the string "false" (JSON, XML or urlencoded) is stored as true
- Kind: bug
- Severity: high
- Steps:
  - `curl -s -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"StrBool","lastname":"Only","totalprice":100,"depositpaid":"false","bookingdates":{"checkin":"2019-01-01","checkout":"2019-01-05"},"additionalneeds":"x"}'`
  - The XML create example from the docs with `<depositpaid>false</depositpaid>`, the XML PUT, the urlencoded create with `depositpaid=false`, and the urlencoded PATCH with `depositpaid=false`.
- Expected: depositpaid=false. The XML and form formats are documented, and they can only carry the value as text.
- Actual: every case returns `"depositpaid":true` (XML: `<depositpaid>true</depositpaid>`, also seen on GET read-back). JSON boolean `false` is stored correctly (control).
- Reproduced: 6 (JSON PATCH, JSON create, XML create, XML PUT, form create, form PATCH).

### F5: Invalid dates are accepted with 200 and stored as "0NaN-aN-aN" or rolled over to another date
- Kind: bug
- Severity: medium
- Steps:
  - `curl -s -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"BadDate","lastname":"Only","totalprice":100,"depositpaid":true,"bookingdates":{"checkin":"2019-01-01","checkout":"not-a-date"},"additionalneeds":"x"}'`
  - `curl -s -i -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"NoNeeds","lastname":"Only","totalprice":100,"depositpaid":true,"bookingdates":{"checkin":"2021-02-29","checkout":"2021-03-05"}}'`
- Expected: 400 for dates that don't exist (docs: Date type, CCYY-MM-DD).
- Actual: `"not-a-date"` and `"2019-13-01"` were stored as `"0NaN-aN-aN"` (also via PUT on booking 14). `"2021-02-29"` was stored as `"2021-03-01"` and `"2019-02-30"` as `"2019-03-02"`, silently moved to a different day.
- Reproduced: NaN 3 times (2 creates, 1 PUT). Rollover 2 times.

### F6: Booking accepted with checkout before checkin and a negative total price
- Kind: needs a decision
- Severity: medium
- Steps: `curl -s -i -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Neg","lastname":"Price","totalprice":-500,"depositpaid":true,"bookingdates":{"checkin":"2019-01-10","checkout":"2019-01-01"},"additionalneeds":"x"}'`
- Expected: 400. A stay can't end before it starts, and a price can't be negative (user expectations oracle). The docs say nothing either way.
- Actual: 200, booking 12 stored as sent. PUT on booking 14 with `"totalprice":-1` also returned 200 and stored -1.
- Reproduced: 2.

### F7: Non-numeric totalprice is accepted and stored as null
- Kind: bug
- Severity: medium
- Steps: `curl -s -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Str2","lastname":"Price","totalprice":"ten","depositpaid":true,"bookingdates":{"checkin":"2019-01-01","checkout":"2019-01-05"},"additionalneeds":"x"}'`
- Expected: 400 (totalprice is Number and required).
- Actual: 200 with `"totalprice":null`. The same happened with `"abc"` on create and with `"xyz"` on PATCH.
- Reproduced: 3.

### F8: Create returns 500 for missing required fields or a non-string name
- Kind: bug
- Severity: medium
- Steps:
  - `curl -s -i -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"NoPrice","lastname":"Only","depositpaid":true,"bookingdates":{"checkin":"2019-01-01","checkout":"2019-01-05"},"additionalneeds":"x"}'`
  - `curl -s -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":67890,"lastname":"Only","totalprice":100,"depositpaid":false,"bookingdates":{"checkin":"2019-01-01","checkout":"2019-01-05"},"additionalneeds":"x"}'`
- Expected: 400 for client input errors (HTTP conventions). PUT with missing fields does return 400, and malformed JSON returns 400 too.
- Actual: `500 Internal Server Error` for a missing totalprice (seen twice) and for a numeric firstname (seen twice).
- Reproduced: 4.

### F9: PATCH accepts a numeric firstname/lastname that create rejects, and stores it as a number
- Kind: bug
- Severity: low
- Steps: `curl -s -X PATCH http://localhost:3004/booking/18 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=0d812c9433c1267' -d '{"totalprice":"xyz","lastname":999}'`
- Expected: the same validation as create (consistency oracle). The fields are documented as String.
- Actual: 200 with `"lastname":999` (a JSON number). Earlier, a PATCH on booking 14 with `"firstname":12345` returned `"firstname":12345`.
- Reproduced: 2.

### F10: Search `checkout` filter is inverted (it acts as <=), and `checkin` excludes the boundary date
- Kind: bug
- Severity: medium
- Steps (booking 11: Put/Quix, checkin 2020-01-01, checkout 2020-02-01):
  - `curl -s 'http://localhost:3004/booking?checkin=2020-01-01&firstname=Put'` → `[]`
  - `curl -s 'http://localhost:3004/booking?checkin=2019-12-31&firstname=Put'` → `[{"bookingid":11}]`
  - `curl -s 'http://localhost:3004/booking?checkout=2020-01-31&firstname=Put'` → `[]`
  - `curl -s 'http://localhost:3004/booking?checkout=2030-01-01&firstname=Put'` → `[{"bookingid":11}]`
- Expected: the docs say both filters return bookings with a date "greater than or equal to" the given date. So checkin=2020-01-01 should match booking 11, checkout=2020-01-31 should match it, and checkout=2030-01-01 should not.
- Actual: checkin uses strict `>`, and checkout matches dates on or before the given date. The unfiltered `?checkout=2020-02-01` also returned bookings whose checkout is in 2019 (12, 17, 18, 19).
- Reproduced: checkin boundary 2 times (booking 11, and booking 1 with control 2017-03-02 → [1]). Checkout inversion 3 times.

### F11: Invalid date in a search filter returns 500
- Kind: bug
- Severity: low
- Steps: `curl -s -i 'http://localhost:3004/booking?checkin=garbage'` and `curl -s -i 'http://localhost:3004/booking?checkout=2020-13-45'`
- Expected: 400 (docs: "Format must be CCYY-MM-DD").
- Actual: `500 Internal Server Error`.
- Reproduced: 2.

### F12: `Accept: application/x-www-form-urlencoded` returns an internal JS error with status 200
- Kind: bug
- Severity: medium
- Steps: `curl -s -i http://localhost:3004/booking/11 -H 'Accept: application/x-www-form-urlencoded'`
- Expected: the documented "URL Response" (`firstname=...&lastname=...`), or a 406.
- Actual: `200 OK`, `Content-Type: text/html`, body `formurlencoded is not a function`. This leaks internals and reports an error as success.
- Reproduced: 2 (bookings 21 and 11).

### F13: XML responses are sent with Content-Type text/html
- Kind: bug
- Severity: low
- Steps: `curl -s -i http://localhost:3004/booking/20 -H 'Accept: application/xml'` (and the XML POST create)
- Expected: `Content-Type: application/xml` (or text/xml) when XML is requested and returned.
- Actual: `Content-Type: text/html; charset=utf-8` with an XML body.
- Reproduced: 2.

### F14: PUT/PATCH/DELETE on a non-existent booking return 405 instead of 404
- Kind: needs a decision
- Severity: low
- Steps: `curl -s -i -X PUT http://localhost:3004/booking/99999 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=0d812c9433c1267' -d '{"firstname":"Ghost","lastname":"Quix","totalprice":1,"depositpaid":true,"bookingdates":{"checkin":"2020-01-01","checkout":"2020-02-01"},"additionalneeds":"x"}'`
- Expected: 404 Not Found (HTTP conventions). GET on the same kind of id returns 404 (consistency).
- Actual: `405 Method Not Allowed` for PUT 99999, PATCH 99999, and a second DELETE of the already deleted booking 22.
- Reproduced: 3.

### F15: Failed login returns 200 OK
- Kind: needs a decision
- Severity: low
- Steps: `curl -s -i -X POST http://localhost:3004/auth -H 'Content-Type: application/json' -d '{"username":"admin","password":"wrong"}'`
- Expected: 401 for bad credentials (HTTP conventions). The docs don't describe the failure case.
- Actual: `200 OK` with `{"reason":"Bad credentials"}`.
- Reproduced: 2 (also with username "nobody" and an empty password).

### F16: DELETE and /ping return 201 Created; docs contradict themselves
- Kind: needs a decision
- Severity: low
- Steps: `curl -s -i -X DELETE http://localhost:3004/booking/22 -H 'Cookie: token=0d812c9433c1267'`
- Expected: 200 or 204 for a delete. The docs table says "Success 200", but the example shows `201 Created`.
- Actual: `201 Created`, body `Created`. GET afterwards returns 404, so the delete works. /ping also returns 201.
- Reproduced: 4 (deletes of 22, 21, 19, 20).

### F17: Empty names and a missing additionalneeds are accepted
- Kind: needs a decision
- Severity: low
- Steps: `curl -s -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"","lastname":"","totalprice":0,"depositpaid":false,"bookingdates":{"checkin":"2019-01-01","checkout":"2019-01-01"},"additionalneeds":"<script>alert(1)</script>"}'`
- Expected: the docs mark firstname, lastname and additionalneeds as not optional.
- Actual: 200, booking 23 created with empty names. Booking 16 was created without additionalneeds, and the field is missing from the response. `<script>` is stored verbatim in JSON, which is fine for JSON but worth checking in any HTML consumer.
- Reproduced: empty names 1 time. Missing additionalneeds 1 time. Each was seen once, but the request is deterministic and the response unambiguous.

## Questions
- Name search is case sensitive (`?firstname=put` → `[]`, `?firstname=sally&lastname=ericsson` → `[]`), yet the docs example uses lowercase `sally&lastname=brown`. Is case-insensitive matching intended? I saw this twice but left it here because the intent is unclear.
- `GET /booking?checkin=...&firstname=Put` still worked while corrupted records existed, but `?checkin=2000-01-01` alone returned 500. I suspect name filters run first and skip the bad records. I didn't confirm this.
- I didn't test token expiry, token reuse after server restart, or whether tokens are bound to anything.
- Whether a PUT with a partial body that is otherwise valid (e.g. only bookingdates missing) also returns 400. I only tried a firstname-only PUT, which returned 400.
- Server-owned `bookingid` and the unknown field `isadmin` in the POST body were ignored (I got id 22). I didn't try them on PUT/PATCH.

## Coverage
- C1 (auth, 7 requests): no auth, invalid token, empty token, and wrong Basic on PUT/PATCH/DELETE all returned 403. Bad /auth login returned 200 (F15). No bypass found.
- C2 (updates, ~14 requests): partial date PATCH (F2), null PATCH (F1), full PUT, partial PUT (400), type and precision on PATCH (F3, F4, F9).
- C3 (validation, ~16 requests): price, booleans, dates, types, missing fields, empty strings, mass assignment on create (F3–F8, F17).
- C4 (search, ~13 requests): name filter, case sensitivity, checkin/checkout boundaries, invalid filter dates (F10, F11), and the effect of corrupted records on search.
- C5 (formats and delete, ~14 requests): XML create/PUT/read, urlencoded create/PATCH/Accept (F12, F13), delete with cookie and basic auth, double delete, GET after delete, non-existent ids (F14, F16).
- Not reached: PUT/PATCH mass assignment, huge payloads and length limits, unicode in JSON round-trip (XML round-trip of `&` and `Ünï` was fine), concurrent updates, token lifetime, PUT validation for each missing field, HEAD/OPTIONS and other methods.
- Budget: 76 of 80 HTTP requests used. Test data was left modified: bookings 1, 11–18 and 23 hold odd values, and 19–22 are deleted.
