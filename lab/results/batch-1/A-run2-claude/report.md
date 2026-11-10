# Exploration report

## Charters
none

## Findings

### F1: `checkout` search filter is inverted (returns bookings with checkout on or before the date)
- Severity: high
- Request: `curl -s 'http://localhost:3003/booking?checkout=2025-01-01'`
- Expected: The docs say "Return bookings that have a checkout date greater than or equal to the set checkout date". Booking 5 (checkout 2025-07-02) should be in the results. Booking 7 (checkout 2017-02-19) should not.
- Actual: 200 `[1,2,3,4,6,7,9,10,11,12,13,14,15]`. Booking 7 is included and booking 5 is left out. With `?checkout=2019-02-01` the results also included 7 (2017-02-19), 12 (2018-01-01) and 14/15 (2019-01-01), and left out 5 (2025-07-02). The filter behaves like `<=`.
- Reproduced: 2 (two different dates)

### F2: `checkin` search filter leaves out bookings whose checkin equals the date (behaves like `>` instead of `>=`)
- Severity: medium
- Request: `curl -s 'http://localhost:3003/booking?checkin=2015-03-12'`
- Expected: The docs say "checkin date greater than or equal to". Booking 7 has checkin 2015-03-12, so it should be returned.
- Actual: 200. Every booking except 7 is returned. In the same way, `?checkin=2018-02-01` left out booking 11 (checkin 2018-02-01), but `?checkin=2018-01-31` included it.
- Reproduced: 2

### F3: `depositpaid=false` sent as XML or form-urlencoded is stored as `true`
- Severity: high
- Request: `curl -s -X POST http://localhost:3003/booking -H 'Content-Type: text/xml' -H 'Accept: application/json' -d '<booking><firstname>Xml2</firstname><lastname>User</lastname><totalprice>99</totalprice><depositpaid>false</depositpaid><bookingdates><checkin>2018-01-01</checkin><checkout>2019-01-01</checkout></bookingdates><additionalneeds>Dinner</additionalneeds></booking>'`
- Expected: `"depositpaid": false`. XML and urlencoded bodies are documented as supported formats.
- Actual: 200 `{"bookingid":17,"booking":{... "depositpaid":true ...}}`. GET on the booking also shows `true`. The same thing happens with urlencoded `depositpaid=false` (booking 18) and with an XML PUT on booking 16. In JSON, the strings `"false"` and `"maybe"` are also stored as `true`, which looks like truthy coercion of any non-empty string.
- Reproduced: 5 (XML POST ×2, XML PUT ×1, form POST ×1, JSON string "false" ×1)

### F4: PATCH with a partial `bookingdates` object corrupts the other date
- Severity: high
- Request: `curl -si -X PATCH http://localhost:3003/booking/12 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d '{"bookingdates":{"checkout":"2020-05-05"}}'`
- Expected: The docs mark all PATCH fields as optional, including `bookingdates.checkin`. Only checkout should change, and checkin should stay as it was.
- Actual: 200 `"bookingdates":{"checkin":"0NaN-aN-aN","checkout":"2020-05-05"}`. The corrupted value is persisted. GET /booking/11, after the same kind of PATCH on checkin only, showed `"checkout":"0NaN-aN-aN"`.
- Reproduced: 2 (booking 11 checkin-only, booking 12 checkout-only)

### F5: POST /booking returns 500 Internal Server Error when a field is missing or has the wrong type
- Severity: medium
- Request: `curl -si -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Repro","totalprice":10,"depositpaid":true,"bookingdates":{"checkin":"2018-01-01","checkout":"2019-01-01"}}'`
- Expected: A 4xx validation error. PUT with an incomplete body returns 400 Bad Request, so POST should behave the same way.
- Actual: 500 `Internal Server Error`. A numeric `firstname` (123) or `lastname` (42) also gives a 500 on POST, and a numeric `firstname` gives a 500 on PUT.
- Reproduced: 5 (missing lastname ×2, numeric firstname POST, numeric lastname POST, numeric firstname PUT)

### F6: Invalid dates and a non-numeric price are accepted and stored as garbage
- Severity: medium
- Request: `curl -si -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Str","lastname":"Price","totalprice":"abc","depositpaid":"maybe","bookingdates":{"checkin":"not-a-date","checkout":"2018-13-45"},"additionalneeds":"x"}'`
- Expected: A 400 rejection. `totalprice` is a Number and the dates are Dates.
- Actual: 200 `"totalprice":null,"depositpaid":true,"bookingdates":{"checkin":"0NaN-aN-aN","checkout":"0NaN-aN-aN"}`. PUT on booking 19 with `"totalprice":"ten"` and `"checkin":"garbage"` also returned 200 with `null` / `0NaN-aN-aN`. `2020-02-30` was silently rolled over to `2020-03-01`. The garbage booking (13) then matches every date filter.
- Reproduced: 2 (POST, PUT)

### F7: Decimal `totalprice` is silently truncated to an integer
- Severity: medium
- Request: `curl -s -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Dec2","lastname":"Price","totalprice":99.99,"depositpaid":false,"bookingdates":{"checkin":"2020-06-10","checkout":"2020-06-01"},"additionalneeds":"x"}'`
- Expected: `totalprice` is documented as a Number, so 99.99 should be stored, or rejected if only integers are allowed.
- Actual: 200 `"totalprice":99`. Earlier, 12.75 was stored as 12.
- Reproduced: 2

### F8: Negative prices and checkout dates before checkin are accepted
- Severity: medium
- Request: `curl -si -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Neg","lastname":"Price","totalprice":-500,"depositpaid":true,"bookingdates":{"checkin":"2019-01-01","checkout":"2018-01-01"},"additionalneeds":"x"}'`
- Expected: A 400 rejection. A booking can't have a negative total price or check out before it checks in.
- Actual: 200 `{"bookingid":12,"booking":{"totalprice":-500,...,"checkin":"2019-01-01","checkout":"2018-01-01"}}`
- Reproduced: 3 (−500 with reversed dates; −1; reversed dates 2020-06-10 → 2020-06-01)

### F9: POST /auth with bad credentials returns 200 OK
- Severity: low
- Request: `curl -si -X POST http://localhost:3003/auth -H 'Content-Type: application/json' -d '{"username":"admin","password":"wrong"}'`
- Expected: A 401 (or other 4xx) for failed authentication.
- Actual: 200 `{"reason":"Bad credentials"}`
- Reproduced: 2 (wrong password, wrong username)

### F10: PUT/PATCH/DELETE on a booking that doesn't exist returns 405 Method Not Allowed instead of 404
- Severity: low
- Request: `curl -si -X DELETE http://localhost:3003/booking/9999 -H 'Cookie: token=7f0ab057e906688'`
- Expected: 404 Not Found. GET on the same id returns 404, and the method is allowed on this route.
- Actual: 405 `Method Not Allowed`
- Reproduced: 3 (DELETE 9999, PUT 9999, PATCH on deleted booking 15)

### F11: XML responses are sent with `Content-Type: text/html`
- Severity: low
- Request: `curl -si http://localhost:3003/booking/7 -H 'Accept: application/xml'`
- Expected: `Content-Type: application/xml` (or text/xml), since the client asked for XML.
- Actual: 200 `Content-Type: text/html; charset=utf-8` with an XML body
- Reproduced: 2 (GET, POST with Accept: application/xml)

## Questions
- Name filters are case-sensitive: `?firstname=basic` returns `[]` and `?firstname=Eric&lastname=jackson` returns `[]`. The docs' own example uses lowercase `firstname=sally&lastname=brown` while the stored data is "Sally Brown". This suggests matching was meant to be case-insensitive, but the docs don't say so explicitly.
- DELETE and /ping return `201 Created`. The docs show this, but the field table calls it "Success 200". The status is semantically wrong, but it matches the documented example.
- Tokens: I didn't test whether they expire or whether older tokens are revoked when a new one is issued.

## Coverage
- Explored: /ping; /auth (valid, wrong password, wrong username); GET /booking with no filter and with firstname, lastname, checkin, checkout and case variants; GET /booking/:id (existing, missing, non-numeric, XML Accept); POST /booking in JSON, XML and urlencoded, with missing fields, wrong types, decimals, negatives, reversed and invalid dates; PUT (cookie, Basic, no auth, invalid token, wrong Basic, nonexistent id, incomplete body, invalid values, XML); PATCH (top-level, nested partial dates, no auth, empty token, uppercased Basic, deleted id); DELETE (no auth, cookie, Basic, Bearer, nonexistent) and verifying that deletion removes the booking from GET and search.
- Not covered: Accept `application/x-www-form-urlencoded` responses, very large or injection payloads, token expiry and reuse, concurrency, and combined filters with dates.
- Requests used: 69 of 80.
