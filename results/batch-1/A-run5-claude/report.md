# Exploration report

## Charters
Explore create/read/update/delete of bookings across JSON, XML and urlencoded formats to find data-integrity bugs.
Explore the GET /booking search filters (name, checkin, checkout) against the documented semantics.
Explore auth (token cookie, Basic auth, /auth) and error handling for missing/invalid input.

## Findings

### F1: PATCH with a partial `bookingdates` object corrupts the other date to "0NaN-aN-aN"
- Severity: high
- Request: `curl -s -i -X PATCH http://localhost:3004/booking/16 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=4576044df8f892a' -d '{"bookingdates":{"checkin":"2018-06-01"}}'`
- Expected: Docs list `bookingdates.checkin` and `bookingdates.checkout` as independently optional for PATCH, so the date you leave out should stay the same.
- Actual: 200, `"bookingdates":{"checkin":"2018-06-01","checkout":"0NaN-aN-aN"}`. The corrupted value is saved and shows up in later GETs.
- Reproduced: 2 (booking 11 patched with only checkout → checkin became `0NaN-aN-aN`; booking 16 patched with only checkin → checkout became `0NaN-aN-aN`)

### F2: `depositpaid=false` is stored as `true` for XML and urlencoded bodies
- Severity: high
- Request: `curl -s -i -X POST http://localhost:3004/booking -H 'Content-Type: application/x-www-form-urlencoded' -H 'Accept: application/json' -d 'firstname=Url2&lastname=Enc&totalprice=111&depositpaid=false&bookingdates%5Bcheckin%5D=2018-01-01&bookingdates%5Bcheckout%5D=2018-01-02'`
- Expected: `depositpaid` should be `false`.
- Actual: 200, `"depositpaid":true`. Same result with XML `<depositpaid>false</depositpaid>`. JSON `"depositpaid":"yes"` is also turned into `true`. It looks like the string "false" is treated as true just because it is a non-empty string.
- Reproduced: 3 (urlencoded booking 15, urlencoded booking 16, XML booking 17)

### F3: The `checkout` filter is inverted: it returns bookings with checkout <= the date
- Severity: high
- Request: `curl -s -i 'http://localhost:3004/booking?checkout=2030-01-01'`
- Expected: Docs: "Return bookings that have a checkout date greater than or equal to the set checkout date". No booking checks out on or after 2030-01-01, so the result should be empty.
- Actual: 200 with every booking ID (1–13). `?checkout=2019-01-01` returned 9 (checkout 2018-10-10), 12 (checkout 2018-01-01) and 13 (checkout 2019-01-01), but not 1 (checkout 2026-02-27).
- Reproduced: 2

### F4: The `checkin` filter leaves out bookings whose checkin equals the filter date (it uses > instead of >=)
- Severity: medium
- Request: `curl -s -i 'http://localhost:3004/booking?checkin=2019-01-01'`
- Expected: Docs say "greater than or equal to", so booking 12 (checkin 2019-01-01) should be included.
- Actual: 200, `[{"bookingid":1},{"bookingid":7},{"bookingid":10}]`, which leaves out 12. Likewise `?checkin=2018-01-01` left out booking 13 (checkin 2018-01-01).
- Reproduced: 2

### F5: POST /booking with a missing required field returns 500 instead of 400
- Severity: medium
- Request: `curl -s -i -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"NoLast","totalprice":111,"depositpaid":true,"bookingdates":{"checkin":"2018-01-01","checkout":"2019-01-01"}}'`
- Expected: 400 Bad Request, which is what PUT returns for an incomplete body.
- Actual: `500 Internal Server Error`
- Reproduced: 3 (missing lastname ×2, missing firstname ×1)

### F6: An invalid date in a GET /booking filter returns 500
- Severity: medium
- Request: `curl -s -i 'http://localhost:3004/booking?checkout=2019-13-45'`
- Expected: 400, or an empty list. Docs say "Format must be CCYY-MM-DD".
- Actual: `500 Internal Server Error`
- Reproduced: 2 (`checkin=notadate`, `checkout=2019-13-45`)

### F7: Accept: application/x-www-form-urlencoded returns an internal error message with status 200
- Severity: medium
- Request: `curl -s -i http://localhost:3004/booking/14 -H 'Accept: application/x-www-form-urlencoded'`
- Expected: A urlencoded body, as in the docs' "URL Response" example (`firstname=Jim&lastname=Brown&...`).
- Actual: `200 OK`, `Content-Type: text/html`, body `formurlencoded is not a function`. This exposes an internal error. On POST, the booking is still created (booking 15) even though the client gets this error back.
- Reproduced: 2 (POST /booking, GET /booking/14)

### F8: Invalid dates are accepted and stored as "0NaN-aN-aN"
- Severity: medium
- Request: `curl -s -i -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Bad","lastname":"Date","totalprice":10,"depositpaid":true,"bookingdates":{"checkin":"garbage","checkout":"2019-01-01"}}'`
- Expected: 400, because `checkin` is typed as Date.
- Actual: 200, booking 18 created with `"checkin":"0NaN-aN-aN"`
- Reproduced: 2 (POST booking 18, PATCH booking 14 with `"checkin":"garbage"`)

### F9: A non-numeric `totalprice` is silently stored as `null`
- Severity: medium
- Request: `curl -s -i -X PUT http://localhost:3004/booking/15 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=4576044df8f892a' -d '{"firstname":"Url","lastname":"Enc","totalprice":"cheap","depositpaid":true,"bookingdates":{"checkin":"2020-05-05","checkout":"2020-01-01"}}'`
- Expected: 400, because totalprice is typed as Number.
- Actual: 200, `"totalprice":null`
- Reproduced: 3 (POST "abc", PUT "cheap", PATCH "free")

### F10: Bookings with checkout before checkin are accepted
- Severity: low
- Request: `curl -s -i -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Rev","lastname":"Dates","totalprice":-50,"depositpaid":true,"bookingdates":{"checkin":"2019-01-01","checkout":"2018-01-01"}}'`
- Expected: Reject (400). A stay can't end before it starts.
- Actual: 200, booking 12 created with checkin 2019-01-01 / checkout 2018-01-01
- Reproduced: 2 (POST booking 12, PUT booking 15 with checkin 2020-05-05 / checkout 2020-01-01)

### F11: Bad credentials on POST /auth return 200 OK
- Severity: low
- Request: `curl -s -i -X POST http://localhost:3004/auth -H 'Content-Type: application/json' -d '{"username":"admin","password":"wrong"}'`
- Expected: 401 (or 4xx) on failed authentication.
- Actual: `200 OK`, `{"reason":"Bad credentials"}`
- Reproduced: 3 (wrong password, wrong-case username, missing password)

### F12: PUT/DELETE on a booking that doesn't exist return 405 instead of 404
- Severity: low
- Request: `curl -s -i -X DELETE http://localhost:3004/booking/9999 -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM='`
- Expected: 404 Not Found (GET on a missing ID returns 404).
- Actual: `405 Method Not Allowed`
- Reproduced: 3 (DELETE an already-deleted ID 13, PUT 9999, DELETE 9999)

### F13: XML responses are sent with Content-Type text/html
- Severity: low
- Request: `curl -s -i http://localhost:3004/booking/11 -H 'Accept: application/xml'`
- Expected: `Content-Type: application/xml`
- Actual: 200, `Content-Type: text/html; charset=utf-8` with an XML body
- Reproduced: 2 (GET /booking/11, POST /booking with XML Accept)

## Questions
- Negative `totalprice` (-50) was accepted on create (seen once, not reproduced). It's probably not intended, but the docs don't define a valid range.
- Combined `checkin` + `checkout` filters return odd results. `?checkin=2014-03-13&checkout=2030-05-21` returned bookings whose checkin is `0NaN-aN-aN` (14, 18) but left out booking 11 (also NaN checkin). `?checkin=2016-01-01&checkout=2018-06-01` returned 12 and 16. Some of this may follow from F3, F4 and F8, but I couldn't tell whether the filters are combined with AND or OR.
- The name filter is case-sensitive (`?firstname=jim` → `[]`, `?firstname=Jim` → 1, 8). The docs' example uses lowercase `firstname=sally&lastname=brown`, which suggests matching should ignore case. The docs don't say so explicitly.
- Seed booking 1 has no `additionalneeds` field, but the docs list it as not optional in the GET response.
- The docs say DELETE and /ping return "Success 200" but the examples show 201 Created. The API returns 201 for both. This is a docs inconsistency.

## Coverage
- Explored: /ping; /auth (valid, wrong password, wrong username case, missing field); GET /booking list plus firstname, lastname, checkin, checkout and combined filters, including boundaries and invalid dates; GET /booking/:id (JSON, XML, urlencoded Accept; missing ID; non-numeric ID); POST in JSON, XML and urlencoded, including missing fields, wrong types, invalid and reversed dates; PUT (auth with cookie, no auth, incomplete body, nonexistent ID); PATCH (Basic auth, bogus/empty token, wrong Basic credentials, nested partial dates, invalid values); DELETE (no auth, token, repeat delete, nonexistent ID).
- Not explored: token expiry or invalidation; whether PUT/PATCH/DELETE accept an XML or urlencoded Content-Type; very large payloads and odd characters in names; concurrency.
- Requests used: 58 of 80.
