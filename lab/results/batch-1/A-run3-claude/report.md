# Exploration report

## Charters
Explore GET /booking search filters (name, checkin, checkout) at date boundaries to check they follow the documented ">=" rules.
Explore auth (token, Basic, cookie) on PUT/PATCH/DELETE to check that unauthorised changes are rejected.
Explore input validation and data integrity on POST/PUT/PATCH (missing fields, wrong types, negative/decimal prices, reversed dates, partial nested updates).
Explore content negotiation (XML / URL-encoded) and error handling for missing or invalid ids.

## Findings

### F1: PATCH with a partial `bookingdates` object corrupts the other date to "0NaN-aN-aN"
- Severity: high
- Request: `curl -s -X PATCH http://localhost:3001/booking/11 -H 'Content-Type: application/json' -H 'Cookie: token=4be98197b47bd77' -d '{"bookingdates":{"checkout":"2020-05-05"}}'`
- Expected: PATCH is a partial update; every PATCH body field is optional in the docs, including `bookingdates.checkin` and `bookingdates.checkout` separately. Fields you don't send should stay the same (checkin should stay "2018-02-01").
- Actual: 200 `{"...","bookingdates":{"checkin":"0NaN-aN-aN","checkout":"2020-05-05"},...}`. The bad value is saved: a later GET /booking/11 (JSON and XML) returns `checkin: 0NaN-aN-aN`.
- Reproduced: 2 times (booking 11 with checkout only; booking 19 with `{"bookingdates":{"checkin":"2020-02-28"}}`, which gave `"checkout":"0NaN-aN-aN"`).

### F2: The `checkout` search filter works backwards (<= instead of >=)
- Severity: medium
- Request: `curl -s "http://localhost:3001/booking?firstname=After&checkout=2020-01-04"` (booking 15 has checkout 2020-01-05)
- Expected: Docs: "Return bookings that have a checkout date greater than or equal to the set checkout date." 2020-01-05 >= 2020-01-04, so booking 15 should be returned.
- Actual: 200 `[]`. But `?firstname=After&checkout=2020-01-06` (a date *after* the booking's checkout) returns `[{"bookingid":15}]`. Also, `?firstname=Jim&checkout=2019-01-01` returned booking 11 (checkout 2019-01-01) but not booking 4 (checkout 2026-10-31).
- Reproduced: 3 times (bookings 11 and 15, and booking 4 missing).

### F3: The `checkin` search filter leaves out bookings whose checkin equals the filter date (> instead of >=)
- Severity: medium
- Request: `curl -s "http://localhost:3001/booking?firstname=After&checkin=2020-01-01"` (booking 15 has checkin 2020-01-01)
- Expected: Docs: "checkin date greater than or equal to the set checkin date", so booking 15 should be included.
- Actual: 200 `[]`. With `checkin=2019-12-31` it returns `[{"bookingid":15}]`. Same for booking 11: `?firstname=Jim&checkin=2018-01-01` returned only `[{"bookingid":4}]`, while `checkin=2017-12-31` returned `[4, 11]`.
- Reproduced: 2 times (bookings 11 and 15).

### F4: POST /booking with a missing required field returns 500 Internal Server Error
- Severity: medium
- Request: `curl -s -i -X POST http://localhost:3001/booking -H 'Content-Type: application/json' -d '{"firstname":"No","totalprice":111,"depositpaid":true,"bookingdates":{"checkin":"2018-01-01","checkout":"2019-01-01"}}'`
- Expected: A 4xx client error (e.g. 400). A required field is missing, and PUT with an incomplete body already returns `400 Bad Request`.
- Actual: `500 Internal Server Error`.
- Reproduced: 2 times (missing firstname; missing lastname).

### F5: Values with the wrong type are accepted and saved as null / "0NaN-aN-aN"
- Severity: medium
- Request: `curl -s -X POST http://localhost:3001/booking -H 'Content-Type: application/json' -d '{"firstname":"Type2","lastname":"Bad","totalprice":"ten","depositpaid":true,"bookingdates":{"checkin":"2021-13-45","checkout":"garbage"}}'`
- Expected: 400, because totalprice must be a Number and the dates must be valid dates.
- Actual: 200 and booking 21 is created with `"totalprice":null,"bookingdates":{"checkin":"0NaN-aN-aN","checkout":"0NaN-aN-aN"}`. PATCH does the same: `{"totalprice":"free"}` on booking 15 returned 200 with `"totalprice":null`.
- Reproduced: 3 times (POST bookings 14 and 21, PATCH booking 15).

### F6: The string "false" for depositpaid is saved as true
- Severity: medium
- Request: `curl -s -X POST http://localhost:3001/booking -H 'Content-Type: application/json' -d '{"firstname":"Dep","lastname":"False","totalprice":100,"depositpaid":"false","bookingdates":{"checkin":"2020-01-01","checkout":"2020-01-05"}}'`
- Expected: Either reject it as a non-boolean (400) or read it as false. Turning "false" into true flips the meaning.
- Actual: 200 `"depositpaid":true` (booking 18).
- Reproduced: 2 times (bookings 18 and 20).

### F7: Decimal prices are silently cut to whole numbers
- Severity: medium
- Request: `curl -s -X POST http://localhost:3001/booking -H 'Content-Type: application/json' -d '{"firstname":"Dec","lastname":"Price","totalprice":99.99,"depositpaid":false,"bookingdates":{"checkin":"2020-01-01","checkout":"2020-01-05"},"additionalneeds":"None"}'`
- Expected: totalprice is documented as a Number, so 99.99 should be stored as 99.99, or rejected if only whole numbers are allowed.
- Actual: 200 `"totalprice":99`. GET /booking/17 confirms 99 is what was saved. PATCH `{"totalprice":250.75}` returned `"totalprice":250`.
- Reproduced: 2 times (POST and PATCH).

### F8: Negative prices and checkout dates before checkin are accepted
- Severity: low
- Request: `curl -s -X POST http://localhost:3001/booking -H 'Content-Type: application/json' -d '{"firstname":"Neg2","lastname":"Rev","totalprice":-1,"depositpaid":"false","bookingdates":{"checkin":"2021-05-10","checkout":"2021-05-01"}}'`
- Expected: Reject (400). A booking can't cost less than zero or end before it starts.
- Actual: 200, booking 20 created with `"totalprice":-1` and checkout before checkin. Same for POST bookings 12 (-50) and 13 (reversed dates), and PUT /booking/20 (`totalprice:-99`, reversed dates → 200).
- Reproduced: 4 times.

### F9: XML responses are sent with Content-Type text/html
- Severity: low
- Request: `curl -s -i http://localhost:3001/booking/11 -H 'Accept: application/xml'`
- Expected: `Content-Type: application/xml` (the client asked for application/xml and the body is XML).
- Actual: 200, `Content-Type: text/html; charset=utf-8` with an XML body.
- Reproduced: 2 times (GET /booking/11, POST /booking with XML body and Accept: application/xml).

### F10: Updating or deleting a booking that doesn't exist returns 405 instead of 404
- Severity: low
- Request: `curl -s -i -X PUT http://localhost:3001/booking/99999 -H 'Content-Type: application/json' -H 'Cookie: token=4be98197b47bd77' -d '{"firstname":"Ghost","lastname":"Brown","totalprice":1,"depositpaid":true,"bookingdates":{"checkin":"2018-01-01","checkout":"2019-01-01"}}'`
- Expected: 404 Not Found (GET of the same id gives 404). 405 means the HTTP method itself isn't supported on that URL, which is wrong here.
- Actual: `405 Method Not Allowed`.
- Reproduced: 3 times (PUT 99999, PATCH 99999, DELETE of already-deleted 14).

### F11: Booking ids with extra characters on the end are accepted
- Severity: low
- Request: `curl -s -i http://localhost:3001/booking/17xyz`
- Expected: 404 (`/booking/abc` already gives 404); "17xyz" isn't a valid id.
- Actual: 200 with booking 17's data.
- Reproduced: 2 times (`/booking/15abc`, `/booking/17xyz`).

### F12: Failed login returns 200 OK
- Severity: low
- Request: `curl -s -i -X POST http://localhost:3001/auth -H 'Content-Type: application/json' -d '{"username":"admin","password":"wrong"}'`
- Expected: 401 (or another 4xx) so clients can tell the login failed from the status code.
- Actual: `200 OK` with `{"reason":"Bad credentials"}`.
- Reproduced: 4 times (wrong password, missing password, uppercase username, password with an extra character).

## Questions
- Name filters are case-sensitive (`?firstname=jim` → `[]`, `?firstname=Jim` → matches). The docs example uses lowercase `firstname=sally&lastname=brown`, which suggests matching should ignore case. It's unclear whether this is intended.
- DELETE returns `201 Created`, and the docs' response table also says "Success 200" while the example shows 201. The docs contradict themselves, and 201 is semantically wrong for a delete. I didn't log it as a finding because the docs show 201.
- /ping returns 201 Created, which is the documented behaviour but semantically odd.
- Getting a new token doesn't invalidate the old one, and I didn't see tokens expire within the session. It may be intended, but I couldn't check expiry.
- DELETE and PUT examples in the docs send JSON. I didn't check whether XML/URL-encoded PUT/PATCH behaves the same as JSON.

## Coverage
Explored: /ping; /auth (valid, wrong password, missing field, case changes); GET /booking list and filters (firstname, lastname, combined, checkin/checkout at and around the boundaries); GET /booking/:id (valid, missing, non-numeric, trailing characters, XML Accept); POST /booking (JSON, XML, URL-encoded, missing fields, wrong types, negative/decimal price, reversed dates, string boolean); PUT (no auth, bad token, valid token, incomplete body, missing id, bad values); PATCH (Basic auth, bad Basic, no auth, empty token, nested partial dates, string price, decimal, missing id); DELETE (no auth, bad token, bad Basic, cookie, Basic, deleting twice); id reuse after delete (not reused).
Not covered: URL-encoded Accept responses, XML/URL-encoded PUT/PATCH, very long or special-character strings / injection, token expiry, concurrency, and combined name+date filters on more of the seed data.
Requests used: 71 of 80.
