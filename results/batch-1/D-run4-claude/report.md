# Exploration report

## Environment
- Target: http://localhost:3001, Express (`X-Powered-By: Express`). Server `Date` header was in GMT (2026-11-09 15:45). No version endpoint.
- Seed state: ids 1–10 existed. New bookings got ids that kept counting up from 11.
- How I checked it: `GET /ping` → `201 Created`. I created booking 11 with non-ASCII names (`Zoë Ørsted`) and read it back in JSON and XML. Both matched what I sent.
- Auth: `POST /auth` with admin/password123 returned token `e9dda1192924590`. That token worked as a cookie, and Basic `YWRtaW46cGFzc3dvcmQxMjM=` also worked.

## Risks
1. Data corruption or loss on update (PUT/PATCH): ids, dates, prices
2. Wrong money values: price precision, negative prices, deposit flag
3. Invalid booking data accepted: impossible dates, checkout before checkin, wrong types
4. Search filters return the wrong bookings (date boundaries, direction)
5. Access control on PUT/PATCH/DELETE
6. Error handling: 500s, misleading status codes

## Charters
- C1: Explore PUT/PATCH/DELETE auth with missing, bad and empty credentials to discover access-control gaps. Tour: Saboteur. Budget: 12.
- C2: Explore PATCH/PUT with partial, wrong-type and server-owned fields to discover data corruption. Tour: FedEx + Antisocial. Budget: 20.
- C3: Explore POST /booking with missing, invalid and boundary values to discover validation gaps and money errors. Tour: Antisocial + Money. Budget: 20.
- C4: Explore GET /booking filters with boundary dates and name case to discover wrong search results. Tour: Guidebook + Intellectual. Budget: 12.
- C5 (added after F6): Explore XML and urlencoded payloads to discover whether data stays the same across formats. Tour: FedEx. Budget: 8.

## Findings

### F1: PATCH/PUT with a `bookingid` in the body returns 405 but still changes the booking's id
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -X PATCH http://localhost:3001/booking/13 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=e9dda1192924590' -d '{"bookingid":999,"firstname":"Ghost"}'
  curl http://localhost:3001/booking/999
  curl http://localhost:3001/booking/13
  ```
- Expected: `bookingid` is owned by the server. The server should ignore it or reject it with 400, and leave the booking unchanged. A failed request should never change data (Standards: an error status means no effect; Familiar problems: mass assignment).
- Actual: The PATCH returned `405 Method Not Allowed`, but the change was saved. `GET /booking/999` → 200 `{"firstname":"Ghost","lastname":"Wards",...}`. `GET /booking/13` → 404. Setting `bookingid:1` on bookings 11 and 12 gave `GET /booking` duplicate entries `{"bookingid":1},{"bookingid":1}`. `GET /booking/1` still returns the seeded booking (Eric), so bookings 11 and 12 can no longer be reached by id. PUT did the same: `PUT /booking/14` with `"bookingid":3` → 405, and the list then showed a second `{"bookingid":3}`.
- Reproduced: 4 times (PATCH on 11, 12 and 13; PUT on 14). Create (`POST`) correctly ignores `bookingid`: it assigned 18.

### F2: A PATCH that sends only one booking date overwrites the other with `0NaN-aN-aN`
- Kind: bug
- Severity: high
- Steps: `curl -X PATCH http://localhost:3001/booking/12 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=e9dda1192924590' -d '{"bookingdates":{"checkout":"2020-01-09"}}'`
- Expected: The docs mark `bookingdates.checkin` and `.checkout` as optional on PATCH, so the date you didn't send should stay as it was (Claims).
- Actual: 200 `"bookingdates":{"checkin":"0NaN-aN-aN","checkout":"2020-01-09"}`. Reading the booking back showed the corrupted value was saved.
- Reproduced: 2 times (sending only checkin on booking 11 → checkout became `0NaN-aN-aN`; sending only checkout on booking 12 → checkin became `0NaN-aN-aN`).

### F3: A non-numeric `totalprice` on PATCH is saved as `null`
- Kind: bug
- Severity: medium
- Steps: `curl -X PATCH http://localhost:3001/booking/12 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=e9dda1192924590' -d '{"totalprice":"abc"}'`
- Expected: 400. The docs say totalprice is a Number.
- Actual: 200 `"totalprice":null`. A GET afterwards shows `null`, so the real price is lost.
- Reproduced: 2 times (bookings 11 and 12).

### F4: Decimal prices are cut down to whole numbers without warning
- Kind: bug
- Severity: high
- Steps: `curl -X POST http://localhost:3001/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Dec","lastname":"Price","totalprice":99.99,"depositpaid":true,"bookingdates":{"checkin":"2020-01-01","checkout":"2020-01-05"},"additionalneeds":"None"}'`
- Expected: The docs give totalprice as a Number. The server should store 99.99, or reject the value if it only allows whole numbers (User expectations; Familiar problems: precision loss).
- Actual: 200 `"totalprice":99`, and reading back shows 99. `10.5` → `10`. `0.99` → `0`. Values are truncated, not rounded.
- Reproduced: 3 times.

### F5: Invalid dates are accepted: impossible dates roll over and text becomes `0NaN-aN-aN`
- Kind: bug
- Severity: medium
- Steps: `curl -X POST http://localhost:3001/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Bad","lastname":"Date","totalprice":10,"depositpaid":true,"bookingdates":{"checkin":"2020-02-30","checkout":"notadate"},"additionalneeds":"None"}'`
- Expected: 400 for dates that don't exist or can't be parsed (Familiar problems: date handling).
- Actual: 200 `"checkin":"2020-03-01","checkout":"0NaN-aN-aN"`. Also `2021-02-29` → `2021-03-01`, `2021-13-01` → `0NaN-aN-aN`, and `2022-04-31` → `2022-05-01`.
- Reproduced: 3 times.

### F6: `depositpaid` "false" is saved as `true` for string, XML, urlencoded and XML PATCH input
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -X POST http://localhost:3001/booking -H 'Content-Type: application/x-www-form-urlencoded' -H 'Accept: application/json' -d 'firstname=Url&lastname=Enc&totalprice=111&depositpaid=false&bookingdates%5Bcheckin%5D=2018-01-01&bookingdates%5Bcheckout%5D=2018-01-02'
  ```
- Expected: `depositpaid=false` should be saved as false (Claims: the docs list urlencoded and XML as supported formats; Purpose: a deposit that wasn't paid must not show as paid).
- Actual: 200 `"depositpaid":true`, and a GET afterwards shows true. The same happened with XML `<depositpaid>false</depositpaid>` (booking 21), with JSON `"depositpaid":"false"` (booking 22), and with an XML PATCH on booking 19, which turned a real `false` into `true`. JSON boolean `false` is stored correctly. This means XML and urlencoded clients can't record an unpaid deposit at all.
- Reproduced: 4 times.

### F7: Booking checkout before checkin and negative prices are accepted
- Kind: needs a decision
- Severity: medium
- Steps: `curl -X POST http://localhost:3001/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Neg2","lastname":"Rev","totalprice":-1,"depositpaid":false,"bookingdates":{"checkin":"2025-12-31","checkout":"2025-01-01"},"additionalneeds":"None"}'`
- Expected: Reject with 400. A stay that ends before it starts, or that has a negative price, makes no sense (User expectations, Purpose). The docs don't state these rules.
- Actual: 200. Booking 24 was saved with `totalprice:-1` and checkout before checkin.
- Reproduced: 2 times (also bookings 13 and 14).

### F8: The `checkout` search filter runs the wrong way (≤ instead of ≥)
- Kind: bug
- Severity: medium
- Steps: Create booking 19 with checkin 2030-05-01 and checkout 2030-05-10, then:
  ```
  curl 'http://localhost:3001/booking?firstname=Filter&checkout=2030-05-01'   # → []
  curl 'http://localhost:3001/booking?firstname=Filter&checkout=2030-05-20'   # → [{"bookingid":19}]
  ```
- Expected: The docs say checkout returns bookings with "a checkout date greater than or equal to the set checkout date". So the first query should return 19 and the second should return nothing.
- Actual: The results are the other way round. Also, `?checkout=2020-01-05` left out booking 999, whose checkout is 2020-02-01.
- Reproduced: 2 times.

### F9: The `checkin` search filter leaves out bookings whose checkin equals the given date (> instead of ≥)
- Kind: bug
- Severity: medium
- Steps: `curl 'http://localhost:3001/booking?firstname=Filter&checkin=2030-05-01'` (booking 19 has checkin 2030-05-01)
- Expected: Booking 19 is included. The docs say "greater than or equal to".
- Actual: `[]`. With `checkin=2030-04-30` it returns `[{"bookingid":19}]`. Also, `?checkin=2020-01-01` left out bookings 15, 18 and 3, whose checkin is exactly 2020-01-01.
- Reproduced: 2 times.

### F10: POST /booking with a required field missing returns 500 instead of 400
- Kind: bug
- Severity: medium
- Steps: `curl -X POST http://localhost:3001/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"lastname":"One","totalprice":200,"depositpaid":true,"bookingdates":{"checkin":"2020-01-01","checkout":"2020-01-05"},"additionalneeds":"None"}'`
- Expected: 400. PUT with missing fields already returns `400 Bad Request` (Consistency, Standards).
- Actual: `500 Internal Server Error`. The same happened with `totalprice` missing.
- Reproduced: 3 times.

### F11: A badly formatted date in a search filter returns 500
- Kind: bug
- Severity: low
- Steps: `curl 'http://localhost:3001/booking?checkin=garbage'`
- Expected: 400. The docs say "Format must be CCYY-MM-DD", so bad input is a client error.
- Actual: `500 Internal Server Error`. `?checkout=garbage` also returns 500.
- Reproduced: 2 times.

### F12: PUT and DELETE on a booking that doesn't exist return 405 instead of 404
- Kind: bug
- Severity: low
- Steps: `curl -X PUT http://localhost:3001/booking/7777 -H 'Content-Type: application/json' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d '{...valid booking...}'` and `curl -X DELETE http://localhost:3001/booking/7777 -H 'Cookie: token=e9dda1192924590'`
- Expected: 404, the same as `GET /booking/7777`. 405 means the method isn't supported, which is wrong here (Standards, Consistency).
- Actual: `405 Method Not Allowed` for both. Deleting an already-deleted booking (16) also returned 405.
- Reproduced: 2 times for PUT (5000, 7777) and 2 times for DELETE (16, 7777).

### F13: POST /auth with wrong credentials returns 200
- Kind: needs a decision
- Severity: low
- Steps: `curl -X POST http://localhost:3001/auth -H 'Content-Type: application/json' -d '{"username":"admin","password":"nope"}'`
- Expected: 401, or another 4xx code (Standards). The docs only describe the success response.
- Actual: `200 {"reason":"Bad credentials"}`.
- Reproduced: 3 times (wrong password, empty body, `Admin` in the wrong case).

### F14: Name filters are case-sensitive, but the docs example uses lowercase names
- Kind: needs a decision
- Severity: low
- Steps: `curl 'http://localhost:3001/booking?firstname=dec&lastname=price'` compared with `?firstname=Dec&lastname=Price`
- Expected: The docs example `?firstname=sally&lastname=brown` uses lowercase, while the stored names are capitalised, which suggests matching ignores case (Claims).
- Actual: The lowercase query returns `[]`. The capitalised query returns `[{"bookingid":15}]`.
- Reproduced: 1 time with each casing. The behaviour is deterministic, but a human should decide which is intended.

## Questions
- Do the docs agree with the status codes? DELETE success returns `201 Created`, which matches the example but is unusual (200 or 204 would be normal). The docs' PATCH examples use `curl -X PUT`, which is a typo in the docs.
- The urlencoded create left out `additionalneeds` and still got 200, even though the docs mark it as required. I didn't check whether JSON create also accepts a booking without `additionalneeds`.
- Is a token ever invalidated? I didn't test whether tokens expire or whether calling `/auth` again revokes the old one.
- What does `GET /booking/1` return after a DELETE when there are duplicate id-1 entries (see F1)? Which record gets deleted is unknown, and I didn't test it so I wouldn't destroy evidence.
- I didn't test XML injection or entity handling. `&amp;` round-tripped correctly.

## Coverage
- C1 (auth): Without auth, with a bad cookie token, with bad Basic credentials and with an empty token, PUT/PATCH/DELETE all returned 403. A valid token and valid Basic auth both worked. I found no gap in access control. /auth status codes are covered in F13.
- C2 (updates): PATCH with partial dates, a wrong type and server-owned ids; PUT with missing fields, a server-owned id and a booking that doesn't exist. Findings F1–F3 and F12.
- C3 (create): Missing fields, malformed JSON (correctly 400), reversed dates, negative price, decimal price, invalid dates, string boolean. Findings F4–F7 and F10.
- C4 (search): checkin and checkout boundaries in both directions, name case, malformed dates. Findings F8, F9, F11 and F14. I didn't test combining a date filter with a name filter beyond the probes above.
- C5 (formats): Created bookings with urlencoded and XML bodies, read back with an XML Accept header, and sent an XML PATCH. Finding F6. I didn't test requesting a urlencoded response (`Accept: application/x-www-form-urlencoded`) or unsupported Accept and Content-Type values.
- Not reached: very large or huge payloads, concurrency and double submits, token expiry, unicode in search filters, HEAD/OPTIONS.
- Budget: 79 of 80 HTTP requests used.
