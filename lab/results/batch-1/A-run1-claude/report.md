# Exploration report

## Charters
- Check that the GET /booking search filters (name, checkin, checkout) work as documented, including boundary dates.
- Check that the PUT/PATCH/DELETE auth checks work (no token, bad token, bad Basic auth, valid cookie and Basic).
- Check input validation and data integrity on create/update: missing fields, wrong types, impossible dates, negative or decimal prices.
- Check content negotiation: JSON, XML and URL-encoded request bodies and Accept headers.
- Check error handling for IDs that don't exist and for bad query input.

## Findings

### F1: `checkin` filter excludes bookings whose checkin equals the filter date (acts as `>` instead of `>=`)
- Severity: medium
- Request: `curl -s "http://localhost:3002/booking?checkin=2030-01-01"` (booking 18 has checkin 2030-01-01)
- Expected: Docs say "Return bookings that have a checkin date greater than or equal to the set checkin date", so booking 18 should be in the result.
- Actual: 200 `[{"bookingid":14},{"bookingid":19}]`. Booking 18 is missing. Booking 19 (checkin 2030-03-02) is included.
- Reproduced: 2 times. Same result with `checkin=2018-01-01`: booking 11 (checkin 2018-01-01) was excluded, while `checkin=2017-12-31` included it.

### F2: `checkout` filter is reversed (returns checkout <= date instead of >= date)
- Severity: high
- Request: `curl -s "http://localhost:3002/booking?checkout=2020-01-01"`
- Expected: Docs say "Return bookings that have a checkout date greater than or equal to the set checkout date". Bookings 2 (checkout 2025-01-21), 3 (2026-08-09) and 10 (2026-06-23) should be returned.
- Actual: 200 `[{"bookingid":1},{"bookingid":11}]`. Those have checkouts 2019-02-10 and 2019-01-01, both earlier than the filter date. Bookings 2, 3 and 10 are missing.
- Reproduced: 3 times. `checkout=2019-01-01` returned only booking 11 and left out booking 1 (2019-02-10). `checkout=2030-01-06` returned booking 18 (checkout 2030-01-05) and left out booking 19.

### F3: PATCH with only part of `bookingdates` corrupts the other date to "0NaN-aN-aN"
- Severity: high
- Request: `curl -s -i -X PATCH http://localhost:3002/booking/18 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=c539d296b35fd8f' -d '{"bookingdates":{"checkout":"2030-01-10"}}'`
- Expected: Docs list `bookingdates.checkin` and `bookingdates.checkout` as optional on their own for PATCH. Fields you leave out should keep their current value (checkin 2030-01-01).
- Actual: 200 `..."bookingdates":{"checkin":"0NaN-aN-aN","checkout":"2030-01-10"}...`. The bad value is saved, and a later GET of booking 11 also shows `"checkout":"0NaN-aN-aN"`.
- Reproduced: 2 times (booking 11 patching checkin only, booking 18 patching checkout only).

### F4: XML, URL-encoded and string `depositpaid` values of "false" are stored as `true`
- Severity: high
- Request: `curl -s -i -X PUT http://localhost:3002/booking/15 -H 'Content-Type: text/xml' -H 'Accept: application/xml' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d '<booking><firstname>Xml</firstname><lastname>User</lastname><totalprice>150</totalprice><depositpaid>false</depositpaid><bookingdates><checkin>2018-01-01</checkin><checkout>2019-01-01</checkout></bookingdates><additionalneeds>Breakfast</additionalneeds></booking>'`
- Expected: `depositpaid` should be `false`. The docs show XML and URL-encoded as supported body formats, and those formats can only send booleans as text.
- Actual: 200 `<depositpaid>true</depositpaid>`
- Reproduced: 4 times: XML POST (booking 15), XML PUT (booking 15), URL-encoded POST `depositpaid=false` (booking 17 → `"depositpaid":true`), JSON `"depositpaid":"false"` (booking 20 → `true`).

### F5: POST /booking with a required field missing returns 500 Internal Server Error
- Severity: medium
- Request: `curl -s -i -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"NoLast","totalprice":111,"depositpaid":true,"bookingdates":{"checkin":"2018-01-01","checkout":"2019-01-01"},"additionalneeds":"x"}'`
- Expected: 400 Bad Request (client error). PUT with a partial body correctly returns 400.
- Actual: 500 `Internal Server Error`
- Reproduced: 2 times (missing `firstname`, missing `lastname`).

### F6: Malformed date in the GET /booking search query returns 500
- Severity: medium
- Request: `curl -s -i "http://localhost:3002/booking?checkin=abc"`
- Expected: 400 (docs: "Format must be CCYY-MM-DD"), or the filter is ignored. Not a server error.
- Actual: 500 `Internal Server Error`
- Reproduced: 3 times (`checkin=notadate`, `checkin=abc`, `checkout=2020-99-99x`).

### F7: Values of the wrong type are accepted and silently changed into bad data
- Severity: medium
- Request: `curl -s -i -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Str","lastname":"Price","totalprice":"abc","depositpaid":"yes","bookingdates":{"checkin":"notadate","checkout":"2018-01-01"},"additionalneeds":"x"}'`
- Expected: 400. Docs give totalprice as Number, depositpaid as Boolean and dates as Date.
- Actual: 200, booking 14 created with `"totalprice":null,"depositpaid":true,"bookingdates":{"checkin":"0NaN-aN-aN",...}`
- Reproduced: 2 times (also PATCH /booking/13 with `{"totalprice":"lots","depositpaid":"no"}` → 200, `"totalprice":null,"depositpaid":true`).

### F8: Impossible calendar dates are silently moved to other dates
- Severity: medium
- Request: `curl -s -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Float2","lastname":"Roll","totalprice":9.75,"depositpaid":false,"bookingdates":{"checkin":"2031-02-31","checkout":"2031-04-31"},"additionalneeds":"x"}'`
- Expected: 400 for invalid dates, or the dates stored as sent. Not a different booking date.
- Actual: 200 `"checkin":"2031-03-03","checkout":"2031-05-01"`
- Reproduced: 2 times (also `2030-02-30` → `2030-03-02`. In that run `2030-13-45` → `0NaN-aN-aN`).

### F9: Decimal `totalprice` is cut to a whole number (price changes without warning)
- Severity: medium
- Request: same as F8 (`"totalprice":9.75`)
- Expected: Docs give totalprice as Number, so 9.75 should be stored as 9.75 (or rejected).
- Actual: 200 `"totalprice":9`
- Reproduced: 2 times (111.99 → 111, 9.75 → 9).

### F10: No business-rule validation: negative price and checkout before checkin are accepted
- Severity: medium
- Request: `curl -s -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Neg2","lastname":"Price","totalprice":-1,"depositpaid":"false","bookingdates":{"checkin":"2020-05-05","checkout":"2020-01-01"},"additionalneeds":"x"}'`
- Expected: 400. A booking can't have a negative price or check out before it checks in.
- Actual: 200, booking 20 created with `"totalprice":-1,"bookingdates":{"checkin":"2020-05-05","checkout":"2020-01-01"}`
- Reproduced: 2 times (booking 13 with -500 and reversed dates, booking 20).

### F11: PUT/PATCH/DELETE on a booking that doesn't exist return 405 instead of 404
- Severity: low
- Request: `curl -s -i -X DELETE http://localhost:3002/booking/9999 -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM='`
- Expected: 404 Not Found, which is what GET /booking/9999 returns. The method is allowed on this route, so 405 is wrong.
- Actual: 405 `Method Not Allowed`
- Reproduced: 4 times (DELETE on deleted booking 12, PUT on 12, PATCH on 9999, DELETE on 9999).

### F12: `Accept: application/x-www-form-urlencoded` returns an internal error message with status 200
- Severity: medium
- Request: `curl -s -i http://localhost:3002/booking/17 -H 'Accept: application/x-www-form-urlencoded'`
- Expected: A URL-encoded body, as in the docs' "URL Response" examples.
- Actual: 200, `Content-Type: text/html`, body `formurlencoded is not a function` (shows an internal error). On POST the booking is still created (booking 16) even though the client gets the error.
- Reproduced: 2 times (POST /booking, GET /booking/17).

### F13: XML responses are sent with `Content-Type: text/html`
- Severity: low
- Request: `curl -s -i http://localhost:3002/booking/11 -H 'Accept: application/xml'`
- Expected: `Content-Type: application/xml`, matching the Accept header.
- Actual: 200 `Content-Type: text/html; charset=utf-8` with an XML body
- Reproduced: 3 times (GET, POST, PUT with XML).

### F14: POST /auth with bad credentials returns 200 OK
- Severity: low
- Request: `curl -s -i -X POST http://localhost:3002/auth -H 'Content-Type: application/json' -d '{"username":"admin","password":"nope"}'`
- Expected: 401 (or 400 for a missing password). Clients that check the status code will think login worked.
- Actual: 200 `{"reason":"Bad credentials"}`
- Reproduced: 4 times (wrong password twice, missing password, `ADMIN` username).

## Questions
- Empty `firstname`/`lastname` were accepted once (POST → 200, booking 22 with `"firstname":"","lastname":""`), even though the docs mark them as required. I saw this only once and did not reproduce it, so it is not listed as a finding.
- Name search is case-sensitive: `?firstname=patched` and `?lastname=brown` return `[]` even though "Patched" and "Brown" exist. The docs' example uses lowercase (`firstname=sally&lastname=brown`), which suggests matching should ignore case. The docs don't say which is intended.
- `?checkin=2030-01-01` returned booking 14, whose checkin is stored as "0NaN-aN-aN". Bookings with corrupted dates seem to match date filters in unpredictable ways. Not investigated further.
- On missing fields, POST returns 500 but PUT returns 400. The two endpoints probably validate in different ways.
- Docs list Content-Type `application/x-www-form-urlencoded` in the examples but only JSON and XML in the header table. It is unclear whether URL-encoded is officially supported.
- I did not check whether tokens expire or are cancelled when a new one is issued.

## Coverage
- Explored: /ping, /auth (valid, invalid, missing fields, wrong case), GET /booking (all, name filters, checkin/checkout boundaries, malformed dates, combined filters), GET /booking/:id (exists, missing, non-numeric, leading zero), POST (JSON/XML/URL-encoded, missing fields, wrong types, invalid dates, decimals, negatives, reversed dates, empty strings, malformed JSON → 400), PUT (valid cookie, partial body, XML with Basic auth, nonexistent ID), PATCH (Basic auth, partial nested dates, wrong types, nonexistent ID), DELETE (no auth, wrong Basic, valid cookie, repeat delete, nonexistent ID).
- Not explored: token lifetime/reuse across sessions, very large payloads/long strings, injection-style payloads in filters, concurrency, XML with malformed/hostile content, and whether `/booking/011` returning booking 11 matters.
- Requests used: 67 of 80.
