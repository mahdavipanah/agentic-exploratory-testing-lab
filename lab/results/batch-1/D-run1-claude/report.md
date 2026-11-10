# Exploration report

## Environment
- Target: http://localhost:3003 (Express, `X-Powered-By: Express`). Docs: api.md (restful-booker style Booking API).
- Server clock: `Date: Mon, 09 Nov 2026 16:05 GMT`. Date-only values appear to be normalised to UTC (see F12).
- State check: `GET /ping` → 201 Created. Created booking 11 (`Zork Quill`) and read it back identical via `GET /booking/11`. Seed data: bookings 1–10 existed before testing; new ids are assigned sequentially (11, 12, …).
- Auth: `POST /auth` admin/password123 → token `255385006a97643`; Basic `YWRtaW46cGFzc3dvcmQxMjM=` also accepted.

## Risks
1. Data corruption on partial update (PATCH) or update (PUT): a booking is silently damaged or lost.
2. Wrong money values: price or deposit flag stored differently from what the client sent (type coercion, decimals, body formats).
3. Access control on PUT/PATCH/DELETE, and clients changing server-owned fields (ids).
4. Invalid bookings accepted (dates in the wrong order, negative price, missing fields, invalid dates).
5. Search filters return the wrong bookings (date boundaries, case).
6. Representation inconsistencies (JSON vs XML vs form-urlencoded) and wrong HTTP status codes.

## Charters
1. Explore PUT/PATCH/DELETE with missing, wrong and empty credentials to discover access-control gaps. Tour: Saboteur. Budget: 10.
2. Explore PATCH/PUT with partial and edge-value bodies, read back in JSON and XML, to discover data corruption. Tour: FedEx. Budget: 20.
3. Explore POST/PUT/PATCH with invalid, missing, wrong-type and extra (server-owned) fields in JSON, XML and form bodies to discover validation gaps and mass assignment. Tour: Antisocial + Back alley. Budget: 25.
4. Explore GET /booking filters at both sides of each date boundary and with name case variants to discover search errors. Tour: Guidebook. Budget: 12.
5. Explore the delete lifecycle and non-existent/odd ids to discover status-code and state problems. Tour: Obsessive-compulsive. Budget: 8.

## Findings

### F1: PATCH/PUT with `bookingid` in the body changes the booking's id: duplicate ids appear and the booking can no longer be reached, while the API returns 405
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -X PATCH http://localhost:3003/booking/22 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=255385006a97643' -d '{"bookingid":500}'
  curl http://localhost:3003/booking/500 -H 'Accept: application/json'
  curl -o /dev/null -w '%{http_code}' http://localhost:3003/booking/22
  ```
- Expected: the id is server-owned and comes from the URL. It should be ignored or rejected, and the response should match what actually happened. Oracles: familiar problems (mass assignment); standards (a 4xx response means nothing changed).
- Actual: the PATCH returns `405 Method Not Allowed`, but the change is still applied. `GET /booking/500` → 200 with booking 22's data (`"firstname":"Form","lastname":"Enc"`), and `GET /booking/22` → 404. First seen with `PATCH /booking/12 {"bookingid":1,...}`: after that, `GET /booking` listed `{"bookingid":1}` twice, booking 12 → 404, and `GET /booking/1` still returned the original Jim Smith. Booking 12's data can no longer be reached by id. PUT does the same: `PUT /booking/21` with `"bookingid":600` → 405, then `GET /booking/600` → 200 with booking 21's data. (POST ignores a client-supplied `bookingid`; booking 18 got a fresh id.)
- Reproduced: 3 times (PATCH ×2, PUT ×1)

### F2: PATCH with only one booking date overwrites the other date with "0NaN-aN-aN"
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -X PATCH http://localhost:3003/booking/11 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=255385006a97643' -d '{"bookingdates":{"checkin":"2018-06-01"}}'
  curl http://localhost:3003/booking/11 -H 'Accept: application/json'
  ```
- Expected: the docs list `bookingdates.checkin` and `bookingdates.checkout` as separately optional for PATCH, so checkout should stay `2019-01-01`. Oracles: claims, user expectations.
- Actual: 200 and stored `"bookingdates":{"checkin":"2018-06-01","checkout":"0NaN-aN-aN"}`, and the read-back shows the same. On booking 12, patching only `checkout` (Basic auth) set `"checkin":"0NaN-aN-aN"`. The damage stayed after a later unrelated PATCH (`{"totalprice":250}`). PATCH with both dates, or with no `bookingdates`, works.
- Reproduced: 2 times (checkin-only and checkout-only, with cookie and with Basic auth)

### F3: `depositpaid=false` sent as XML or form-urlencoded is stored as `true`
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -X POST http://localhost:3003/booking -H 'Content-Type: text/xml' -H 'Accept: application/json' -d '<booking><firstname>Xml</firstname><lastname>Two</lastname><totalprice>150.50</totalprice><depositpaid>false</depositpaid><bookingdates><checkin>2023-08-01</checkin><checkout>2023-08-05</checkout></bookingdates><additionalneeds>none</additionalneeds></booking>'
  ```
- Expected: `"depositpaid": false`. The docs present XML and form-urlencoded as supported formats for the same data. Oracles: claims, consistency (JSON `false` is stored as false).
- Actual: 200 and `"depositpaid":true`. The same happens for XML POST (booking 19), form-urlencoded POST `depositpaid=false` (booking 22), XML PATCH `<depositpaid>false</depositpaid>` on booking 20 (which was false and became true), and form-urlencoded PUT `depositpaid=false` on booking 20. The string "false" is being treated as truthy. A client can never record "deposit not paid" through these formats.
- Reproduced: 5 times across POST/PUT/PATCH

### F4: Decimal prices are silently truncated to integers
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Dec","lastname":"Imal","totalprice":99.99,"depositpaid":false,"bookingdates":{"checkin":"2023-07-01","checkout":"2023-07-05"},"additionalneeds":"x"}'
  ```
- Expected: `totalprice` is documented as a Number, so 99.99 should be stored as 99.99, or rejected if only integers are allowed. Oracles: claims, familiar problems (precision loss).
- Actual: 200 and `"totalprice":99`. Also XML `150.50` → `150`, XML `99.99` → `99`, and PUT JSON `-10.75` → `-10`.
- Reproduced: 4 times (JSON POST, XML POST ×2, PUT)

### F5: Non-numeric/garbage values are coerced instead of rejected (`"12abc"`→12, `"abc"`→null, `"no"`/`"yes"`→true)
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Typo","lastname":"Y","totalprice":"12abc","depositpaid":"no","bookingdates":{"checkin":"2021-02-30","checkout":"garbage"},"additionalneeds":"x"}'
  ```
- Expected: 400 for wrong types. The docs say Number and Boolean. Oracles: claims, user expectations.
- Actual: 200 and `"totalprice":12,"depositpaid":true`. Another create with `"totalprice":"abc","depositpaid":"yes"` gave `"totalprice":null,"depositpaid":true`. PUT with `"depositpaid":"no"` also stored true (booking 13). PATCH `{"totalprice":"abc"}` / `"xyz"` stored null on bookings 18 and 16.
- Reproduced: 4+ times across POST/PUT/PATCH

### F6: Invalid dates are accepted and stored as "0NaN-aN-aN" or rolled over (2021-02-30 → 2021-03-02)
- Kind: bug
- Severity: medium
- Steps: the same request as in F5, plus
  ```
  curl -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Str","lastname":"Price","totalprice":"abc","depositpaid":"yes","bookingdates":{"checkin":"notadate","checkout":"2021-13-45"},"additionalneeds":"x"}'
  ```
- Expected: 400 for dates that are not valid CCYY-MM-DD. Oracles: claims (Date type), image.
- Actual: 200. `"checkin":"0NaN-aN-aN","checkout":"0NaN-aN-aN"` (booking 15, same on read-back). `"checkin":"2021-02-30"` stored as `"2021-03-02"`, and `"checkout":"garbage"` stored as `"0NaN-aN-aN"` (booking 17).
- Reproduced: 2 times

### F7: Checkout filter is inverted: it returns bookings with checkout ≤ the date instead of ≥
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl 'http://localhost:3003/booking?checkout=2030-01-01'
  curl 'http://localhost:3003/booking?checkout=2023-08-05'
  ```
- Expected: per the docs, "Return bookings that have a checkout date greater than or equal to the set checkout date". `checkout=2030-01-01` should return no bookings (none check out after 2030), and `checkout=2023-08-05` should include booking 1 (checkout 2026-09-30). Oracle: claims.
- Actual: `checkout=2030-01-01` returns nearly every booking (1–22). `checkout=2023-08-05` excludes booking 1 but includes booking 22 (checkout 2018-01-02) and 13 (2021-05-01). `checkout=2026-09-30` includes booking 1, consistent with ≤.
- Reproduced: 4 queries, consistent

### F8: Checkin filter excludes bookings whose checkin equals the date (uses > instead of ≥)
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl 'http://localhost:3003/booking?checkin=2023-08-01'
  curl 'http://localhost:3003/booking?checkin=2023-07-31'
  ```
- Expected: booking 21 (checkin 2023-08-01) is in the first result. The docs say "greater than or equal". Oracle: claims.
- Actual: `checkin=2023-08-01` → `[{"bookingid":1},{"bookingid":15}]` (no 21). `checkin=2023-07-31` → includes 21. Likewise `checkin=2023-07-01` excludes bookings 19 and 20, which both check in on 2023-07-01.
- Reproduced: 2 times (bookings 21, 19/20)

### F9: GET with `Accept: application/x-www-form-urlencoded` returns an internal error message with 200 OK
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -i http://localhost:3003/booking/1 -H 'Accept: application/x-www-form-urlencoded'
  ```
- Expected: the documented "URL Response" (`firstname=Jim&lastname=Brown&...`). Oracles: claims, standards (an error should not come back as 200), image (leaks an implementation detail).
- Actual: `200 OK`, `Content-Type: text/html`, body `formurlencoded is not a function`.
- Reproduced: 2 times (bookings 12 and 1)

### F10: POST with a missing required field returns 500 Internal Server Error
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -i -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"NoDates","lastname":"X","totalprice":100,"depositpaid":true,"additionalneeds":"x"}'
  ```
- Expected: 400 Bad Request. PUT returns 400 for an incomplete body, and malformed JSON on POST returns 400. Oracles: standards, consistency.
- Actual: `500 Internal Server Error`. The same happens when `firstname` is missing.
- Reproduced: 2 times

### F11: PATCH can set required fields to null
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -X PATCH http://localhost:3003/booking/16 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d '{"lastname":null,"totalprice":"xyz"}'
  curl http://localhost:3003/booking/16 -H 'Accept: application/xml'
  ```
- Expected: 400. GET documents `lastname`/`totalprice` as non-optional Strings/Numbers, and PUT rejects incomplete bookings. Oracles: claims, consistency.
- Actual: 200 and `"lastname":null,"totalprice":null`. The XML read-back renders these as `<lastname>null</lastname>` and `<totalprice>NaN</totalprice>`, so JSON and XML disagree. Same on booking 18 (`firstname:null`).
- Reproduced: 2 times

### F12: Dates with a timezone offset are shifted to the UTC calendar date
- Kind: needs a decision
- Severity: medium
- Steps:
  ```
  curl -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Tz2","lastname":"Shift","totalprice":100,"depositpaid":true,"bookingdates":{"checkin":"2024-12-31T22:00:00-03:00","checkout":"2025-01-05T08:00:00+10:00"},"additionalneeds":"x"}'
  ```
- Expected: either reject non-CCYY-MM-DD input or keep the guest's local calendar date (2024-12-31 / 2025-01-05). Oracle: familiar problems (timezone shift).
- Actual: 200 and `"checkin":"2025-01-01","checkout":"2025-01-04"`. The booking moves into a different year, and the stay is a day shorter at each end. An earlier booking (`2021-05-01T23:30-05:00` / `2021-05-03T01:00+09:00`) became `2021-05-02` / `2021-05-02`, a zero-night stay.
- Reproduced: 2 times

### F13: Bookings with checkout before checkin, or with a negative price, are accepted
- Kind: needs a decision
- Severity: medium
- Steps:
  ```
  curl -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Back2","lastname":"Wards","totalprice":-1,"depositpaid":true,"bookingdates":{"checkin":"2022-01-31","checkout":"2022-01-01"},"additionalneeds":"x"}'
  ```
- Expected: 400 for a stay that ends before it starts, or for a negative price. The docs don't say so explicitly. Oracle: user expectations.
- Actual: 200, stored as sent (booking 16). Also booking 13 (checkout 2021-05-01 < checkin 2021-05-10), booking 14 (`totalprice:-500`), and PUT on 13 with `-10.75`.
- Reproduced: 3+ times

### F14: Updating or deleting a non-existent booking returns 405 Method Not Allowed instead of 404
- Kind: needs a decision
- Severity: low
- Steps:
  ```
  curl -i -X DELETE http://localhost:3003/booking/99999 -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM='
  ```
- Expected: 404 Not Found. GET on the same id returns 404. Oracles: standards, consistency.
- Actual: `405 Method Not Allowed` for DELETE, PUT and PATCH on deleted booking 14, and for DELETE on 99999.
- Reproduced: 4 times

### F15: Failed login returns 200 OK
- Kind: needs a decision
- Severity: low
- Steps:
  ```
  curl -i -X POST http://localhost:3003/auth -H 'Content-Type: application/json' -d '{"username":"admin","password":"wrong"}'
  ```
- Expected: 401 (or 400 when a field is missing). Oracle: standards.
- Actual: `200 OK` `{"reason":"Bad credentials"}`. A missing password gives the same response.
- Reproduced: 2 times

### F16: XML responses are served with `Content-Type: text/html`
- Kind: bug
- Severity: low
- Steps:
  ```
  curl -i http://localhost:3003/booking/1 -H 'Accept: application/xml'
  ```
- Expected: `Content-Type: application/xml` (what the client asked for). Oracle: standards.
- Actual: `Content-Type: text/html; charset=utf-8` with an XML body.
- Reproduced: 4 times (bookings 1, 16, 18, 19)

### F17: DELETE and /ping return 201 Created
- Kind: needs a decision
- Severity: low
- Steps:
  ```
  curl -i -X DELETE http://localhost:3003/booking/14 -H 'Cookie: token=255385006a97643'
  ```
- Expected: 200 or 204. The docs' tables say "Success 200" but their examples show 201, so the docs contradict themselves. Oracles: standards, claims.
- Actual: `201 Created`, body `Created`. `/ping` gives the same.
- Reproduced: 2 times (DELETE, ping)

## Questions
- `GET /booking/1` with `Accept: text/plain` returned `418 I'm a Teapot` (seen once). A 406 Not Acceptable would be conventional. A second request would confirm it.
- Booking 17 (checkout "garbage" → "0NaN-aN-aN") is missing from every `checkout=` filter result, but bookings 11 and 15, which also show "0NaN-aN-aN", are included. Invalid stored dates seem to be handled inconsistently by the filter. I didn't isolate why.
- Name filters are case-sensitive (`firstname=xml` → `[]`, `firstname=Xml` → `[21]`), but the docs' example uses lowercase `sally`/`brown`, which suggests matching should ignore case. I saw this once; it needs a decision.
- Do tokens expire or get invalidated? Not tested.
- Booking 12's data is now unreachable because its id was changed to 1 (F1). The duplicate id 1 also affects later GET/PUT/DELETE on id 1. Not explored further.

## Coverage
- Charter 1 (access control): PUT/PATCH/DELETE without auth, with a wrong token, an empty token and wrong Basic credentials all returned 403. `/auth` with bad credentials → F15. No bypass found.
- Charter 2 (update integrity): PATCH with a single date (F2), falsy values (OK: 0/false/"" stored correctly), null values (F11), XML read-back (F11, F16), PATCH/PUT with `bookingid` (F1).
- Charter 3 (validation): backwards dates and negative prices (F13), missing fields (F10), wrong types (F5), invalid dates (F6), decimals (F4), XML and form bodies (F3), escaping and unicode via XML (OK: `Zoë 🎉`, `O'Brien & <Co>` round-trip correctly), malformed JSON (OK: 400), mass assignment on POST (OK: ignored), timezone offsets (F12).
- Charter 4 (filters): checkin/checkout boundaries (F7, F8), name case (question).
- Charter 5 (lifecycle): delete, GET/PUT/PATCH/DELETE after delete (F14, no resurrection), non-numeric id (404), id reuse (not reused).
- Not reached: very large or long inputs, concurrent/double submits, token expiry, PUT/PATCH with `Accept: application/xml` responses, combined name+date filters, form-urlencoded PATCH.
- Budget: 75 of 80 HTTP requests used.
