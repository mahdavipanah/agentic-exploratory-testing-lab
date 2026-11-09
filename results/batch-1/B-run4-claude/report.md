# Exploration report

## Charters
1. Explore the booking lifecycle (create, read, full update, partial update, delete, then read again) with JSON payloads and the admin token to discover whether every step does what the docs say and returns the documented status code. Tour: Guidebook.
2. Explore one booking's data across every endpoint and format (JSON, XML, URL-encoded; different Accept and Content-Type pairs) with a single distinctive booking to discover data that changes, disappears or is formatted differently along the way. Tour: FedEx.
3. Explore create, full update and partial update with bad and boundary data (missing or extra fields, wrong types, negative or huge prices, checkout before checkin, invalid dates, very long and non-ASCII names) to discover what the API wrongly accepts and what it rejects badly. Tour: Antisocial.
4. Explore authorization and search with no credentials, wrong tokens, Basic auth versus cookie, unknown ids, and the GET /booking filters to discover who can change what, and whether search follows the docs. Tours: Saboteur and Back alley.

## Findings

### F1: PATCH with a partial `bookingdates` object corrupts the other date to "0NaN-aN-aN"
- Severity: high
- Request: `curl -X PATCH http://localhost:3003/booking/12 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d '{"bookingdates":{"checkin":"2021-01-02"}}'`
- Expected: The docs mark every PATCH field optional, including `bookingdates.checkin` and `bookingdates.checkout` separately. So only checkin should change, and checkout should stay 2021-01-05.
- Actual: 200 `{"...","bookingdates":{"checkin":"2021-01-02","checkout":"0NaN-aN-aN"},...}`. A later GET returns the same corrupted value, so it was saved.
- Reproduced: 2 times (booking 11 patching only checkout corrupted checkin; booking 12 patching only checkin corrupted checkout).

### F2: `depositpaid=false` is saved as `true` for XML and URL-encoded payloads
- Severity: high
- Request: `curl -X POST http://localhost:3003/booking -H 'Content-Type: text/xml' -H 'Accept: application/json' -d '<booking><firstname>Dep</firstname><lastname>False</lastname><totalprice>5</totalprice><depositpaid>false</depositpaid><bookingdates><checkin>2025-01-01</checkin><checkout>2025-01-02</checkout></bookingdates><additionalneeds>x</additionalneeds></booking>'`
- Expected: `"depositpaid": false`, the same as the JSON path, which keeps false correctly.
- Actual: 200 `{"bookingid":16,"booking":{...,"depositpaid":true,...}}`. GET shows the stored value is `true`.
- Reproduced: 5 times: XML POST (bookings 14 and 16), URL-encoded POST (booking 15), XML PUT on booking 13, and URL-encoded PATCH on booking 13.

### F3: `depositpaid` accepts any non-boolean value and stores it as `true`
- Severity: medium
- Request: `curl -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Num","lastname":"Name","totalprice":5,"depositpaid":"no","bookingdates":{"checkin":"2025-01-01","checkout":"2025-01-02"},"additionalneeds":"x"}'`
- Expected: 400, because the docs say `depositpaid` is a Boolean.
- Actual: 200 `"depositpaid":true`.
- Reproduced: 2 times (POST with `"no"`; PATCH with `"maybe"` on booking 12).

### F4: Decimal prices are silently truncated to whole numbers
- Severity: medium
- Request: `curl -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Zoë & Co","lastname":"Ohara-Ünal","totalprice":123.45,"depositpaid":false,"bookingdates":{"checkin":"2025-12-31","checkout":"2026-01-02"},"additionalneeds":"Late <checkout>"}'`
- Expected: `totalprice` is a Number in the docs, so 123.45 should come back unchanged (or be rejected).
- Actual: 200 `<totalprice>123</totalprice>`. GET in JSON also shows `"totalprice":123`.
- Reproduced: 4 times (JSON, XML and URL-encoded POST gave 123; XML PUT with 99.99 gave 99, truncated rather than rounded).

### F5: Very large prices in exponent form are stored as 1
- Severity: medium
- Request: `curl -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Huge2","lastname":"Price","totalprice":1e21,"depositpaid":true,"bookingdates":{"checkin":"2025-01-01","checkout":"2025-01-02"},"additionalneeds":"x"}'`
- Expected: Either the value is kept or the request is rejected with 400.
- Actual: 200 `"totalprice":1`. By contrast, `12345678901234567890` was stored as `12345678901234567000`.
- Reproduced: 2 times (1e308 and 1e21 both became 1).

### F6: Non-numeric `totalprice` is accepted and stored as `null`
- Severity: medium
- Request: `curl -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Str","lastname":"Price","totalprice":"abc","depositpaid":true,"bookingdates":{"checkin":"2025-01-01","checkout":"2025-01-02"},"additionalneeds":"x"}'`
- Expected: 400, because `totalprice` is a Number.
- Actual: 200 `"totalprice":null`.
- Reproduced: 3 times (POST `"abc"`, PATCH `"lots"`, PATCH `"free"`).

### F7: PATCH stores wrong types for name fields (a number or an object as the name)
- Severity: medium
- Request: `curl -X PATCH http://localhost:3003/booking/12 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d '{"lastname":{"x":1},"totalprice":"free"}'`
- Expected: 400, because the names are Strings.
- Actual: 200 `{"firstname":42,"lastname":{"x":1},"totalprice":null,...}`. GET returns the same values, so they were saved.
- Reproduced: 2 times (firstname 42 in one PATCH, lastname object in another), plus a GET confirming storage.

### F8: Checkout before checkin and negative prices are accepted
- Severity: medium
- Request: `curl -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Back","lastname":"Dates","totalprice":10,"depositpaid":true,"bookingdates":{"checkin":"2025-06-10","checkout":"2025-01-01"},"additionalneeds":"x"}'`
- Expected: 400. A stay can't end before it starts, and a price can't be negative (reasoning; the docs don't state validation rules).
- Actual: 200 with checkout earlier than checkin stored. POST with `"totalprice":-500` also returned 200 and stored -500.
- Reproduced: 2 times each (POST and PUT on booking 12: `totalprice:-1`, checkin 2030-01-01 and checkout 2020-01-01, returned 200).

### F9: Invalid dates are silently rolled over or stored as "0NaN-aN-aN"
- Severity: medium
- Request: `curl -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Bad","lastname":"Date","totalprice":10,"depositpaid":true,"bookingdates":{"checkin":"2025-02-30","checkout":"not-a-date"},"additionalneeds":"x"}'`
- Expected: 400 for an impossible or non-date value.
- Actual: 200 `"checkin":"2025-03-02","checkout":"0NaN-aN-aN"`.
- Reproduced: 1 time for this request. The "0NaN-aN-aN" output itself was seen 3 times (see F1).

### F10: POST with a missing required field returns 500 instead of 400
- Severity: medium
- Request: `curl -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"lastname":"NoFirst","totalprice":1,"depositpaid":true,"bookingdates":{"checkin":"2025-01-01","checkout":"2025-01-02"},"additionalneeds":"x"}'`
- Expected: 400 Bad Request. PUT with missing fields does return 400.
- Actual: `500 Internal Server Error`.
- Reproduced: 3 times (missing firstname, missing bookingdates, missing totalprice).

### F11: Accept `application/x-www-form-urlencoded` returns an error body with 200, but the write still happens
- Severity: medium
- Request: `curl -X PUT http://localhost:3003/booking/13 -H 'Content-Type: application/x-www-form-urlencoded' -H 'Accept: application/x-www-form-urlencoded' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d 'firstname=Jim&lastname=Brown&totalprice=111&depositpaid=true&bookingdates%5Bcheckin%5D=2018-01-01&bookingdates%5Bcheckout%5D=2018-01-02'` (this is the docs' own example)
- Expected: 200 with a URL-encoded body, as in the docs' "URL Response" examples.
- Actual: `200`, `Content-Type: text/html`, body `formurlencoded is not a function`. The update was still saved (a later GET shows the new data). A POST with the same Accept still created booking 17.
- Reproduced: 3 times (GET /booking/13, POST /booking, PUT /booking/13).

### F12: Wrong credentials on POST /auth return 200 OK
- Severity: low
- Request: `curl -X POST http://localhost:3003/auth -H 'Content-Type: application/json' -d '{"username":"admin","password":"wrong"}'`
- Expected: A 4xx status (401 or 400) for failed authentication.
- Actual: `200 {"reason":"Bad credentials"}`.
- Reproduced: 3 times (wrong password, empty body `{}`, username `Admin`).

### F13: PUT, PATCH or DELETE on a non-existent booking returns 405 instead of 404
- Severity: low
- Request: `curl -X DELETE http://localhost:3003/booking/99999 -H 'Cookie: token=<valid token>'`
- Expected: 404 Not Found, which is what GET returns for the same id.
- Actual: `405 Method Not Allowed`.
- Reproduced: 5 times (DELETE on a deleted id, DELETE on 99999, PUT and PATCH on a deleted id, PATCH on `abc`).

### F14: The `checkout` search filter returns bookings on or before the date, the opposite of the docs
- Severity: high
- Request: `curl 'http://localhost:3003/booking?checkout=2100-01-01'`
- Expected: Docs: "Return bookings that have a checkout date greater than or equal to the set checkout date". No booking checks out after 2100, so the result should be `[]`.
- Actual: 200 with every booking that has a valid date (1–10, 12–19, 21–26). `?checkout=2026-01-02` also returned booking 13 (checkout 2018-01-02) and booking 12 (checkout 2020-01-01).
- Reproduced: 2 times.

### F15: The `checkin` search filter excludes bookings on the exact date (strictly greater, not "greater than or equal")
- Severity: medium
- Request: `curl 'http://localhost:3003/booking?checkin=2025-12-31'`
- Expected: Should include bookings 14 and 15 (checkin exactly 2025-12-31), per "greater than or equal to".
- Actual: `[{"bookingid":12}]`. With `?checkin=2025-12-30`, 14 and 15 are returned.
- Reproduced: 2 times (`?checkin=2030-01-01` returned `[]` even though booking 12 checks in on 2030-01-01).

### F16: An invalid date in the search filters returns 500
- Severity: low
- Request: `curl 'http://localhost:3003/booking?checkin=garbage'`
- Expected: 400. The docs say "Format must be CCYY-MM-DD".
- Actual: `500 Internal Server Error`.
- Reproduced: 2 times (`checkin=garbage`, `checkout=2025-13-45x`).

### F17: PUT (full update) keeps the old `additionalneeds` when it is left out
- Severity: low
- Request: `curl -X PUT http://localhost:3003/booking/12 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d '{"firstname":"Put","lastname":"Neg","totalprice":-1,"depositpaid":false,"bookingdates":{"checkin":"2030-01-01","checkout":"2020-01-01"}}'`
- Expected: `additionalneeds` is listed as not optional for PUT, so either 400 or a full replacement that clears it.
- Actual: 200 with `"additionalneeds":"None"` carried over from the old booking.
- Reproduced: 2 times (JSON PUT on booking 12, URL-encoded PUT on booking 13, which kept "Late <checkout>").

## Questions
- XML responses are sent with `Content-Type: text/html; charset=utf-8` instead of `application/xml`. Seen on every XML response; this is arguably a finding, but the docs show no headers.
- An unsupported Accept (`text/plain`) returns `418 I'm a Teapot` (seen once). A 406 would be the usual response.
- In the XML output `>` is not escaped (`Late &lt;checkout>`). That is valid XML, but the escaping is inconsistent.
- The docs disagree with themselves: DELETE and /ping say "Success 200" but the examples show `201 Created`. The API returns 201 for both, and also 201 for a successful DELETE, where 200 or 204 would be normal.
- The PATCH examples in the docs use `curl -X PUT`, which is a docs error.
- Extra unknown fields (e.g. `"isAdmin":true`) are silently dropped. That looks fine, but I did not check every path.
- There is no length limit on names (a 300-character firstname was accepted). I couldn't send 10,000+ characters because of tooling limits.
- Name search is case-sensitive (`firstname=jim` gives `[]`, `Jim` gives results), while the docs example uses lowercase `sally&lastname=brown`. It's unclear whether that's intended.
- Seed booking 5 has no `additionalneeds` field, even though GET docs list it as not optional.
- Token lifetime and expiry were not tested.

## Coverage
- Charter 1 (requests 1–20): auth, create, GET, PUT, PATCH (top-level and nested), DELETE with cookie, GET after delete, a second DELETE, PUT and PATCH on a deleted id, ping, list.
- Charter 2 (21–37): one distinctive booking (non-ASCII, `&`, `<`, decimal price, depositpaid false) created through JSON, XML and URL-encoded. Read back as JSON, XML, URL-encoded and text/plain. Updated with XML PUT, URL-encoded PATCH and URL-encoded PUT; searched by name.
- Charter 3 (38–56): missing fields, wrong types, negative, decimal and huge prices, reversed and invalid dates, malformed JSON (correct 400), long and non-ASCII names, empty additionalneeds, extra field, PUT missing fields (400), PATCH wrong types.
- Charter 4 (57–79): PUT, PATCH and DELETE with no auth, a wrong cookie, wrong Basic, empty cookie, garbage Basic, and a Bearer token (all correctly 403). Bad-credential auth variants, unknown and non-numeric ids, and search by name (case), checkin and checkout boundaries, combined name filter and invalid date filters.
- Not covered: token expiry and reuse after logout, XML or URL-encoded validation of bad data, malformed XML, concurrent or double submits, very large bodies, DELETE with Basic auth on an existing booking (only the cookie path was tested successfully).
- Requests used: 79 of 80.
