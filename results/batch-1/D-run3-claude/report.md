# Exploration report

## Environment
- Target: http://localhost:3003 (docs say 3001; run instructions say 3003). Express server (`X-Powered-By: Express`). No version endpoint.
- Server clock/timezone: `Date: Mon, 09 Nov 2026 15:57 GMT` headers.
- State check: `GET /ping` → `201 Created`. Seed state: `GET /booking` listed ids 1–10. I created booking 11 (`Zed Probe`), read it back with identical values, and got a token from `POST /auth` with admin/password123 (`{"token":"9374b1385d7e82e"}`). Basic auth `YWRtaW46cGFzc3dvcmQxMjM=` also works.
- Black box only. Only api.md was read.

## Risks
1. Data corruption or loss in updates (PUT/PATCH) and in server-owned fields such as the booking id.
2. Wrong money, dates or booleans being stored (truncation, silent coercion, impossible dates).
3. Access control on PUT/PATCH/DELETE.
4. Search filters returning the wrong set of bookings (date boundaries, name matching).
5. Wrong status codes, or false success/failure reported to the client (a client that retries or gives up because of these).
6. Alternate formats (XML, URL-encoded) treated differently from JSON.

## Charters
- C1: Explore PUT/PATCH/DELETE with missing, empty, wrong and doc-example credentials to discover access-control gaps. Tour: Saboteur. Budget: 10.
- C2: Explore PATCH/PUT with partial and extra fields (incl. server-owned `bookingid`) to discover data corruption and mass assignment. Tour: FedEx + Antisocial. Budget: 20.
- C3: Explore POST/PUT field validation with negative, decimal, wrong-type, impossible and reversed dates and missing fields to discover bad data being stored. Tour: Antisocial. Budget: 20.
- C4: Explore GET /booking filters with a known booking at exact boundaries to discover filter logic errors. Tour: Guidebook + Intellectual. Budget: 12.
- C5: Explore XML and URL-encoded request/response formats to discover inconsistencies with JSON. Tour: FedEx + Guidebook. Budget: 8.
- (Added during C2) C2b: Follow the id-reassignment surprise to collisions with existing ids, PUT, POST and DELETE. Reason: PATCH moved a booking to a new id.

## Findings

### F1: PATCH/PUT with `bookingid` in the body silently moves the booking to a new id, and can duplicate an existing id
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -X PATCH http://localhost:3003/booking/15 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=9374b1385d7e82e' -d '{"totalprice":"free","depositpaid":"no","bookingid":999,"admin":true}'
  curl http://localhost:3003/booking/15      # 404
  curl http://localhost:3003/booking/999     # 200, the old booking 15
  curl -X PATCH http://localhost:3003/booking/16 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=9374b1385d7e82e' -d '{"bookingid":12}'
  curl http://localhost:3003/booking         # ... {"bookingid":12}, ..., {"bookingid":12}
  curl http://localhost:3003/booking/16      # 404
  curl -X PUT http://localhost:3003/booking/17 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=9374b1385d7e82e' -d '{"bookingid":4242,"firstname":"Quentin","lastname":"Filterson","totalprice":-1,"depositpaid":true,"bookingdates":{"checkin":"2030-06-15","checkout":"2030-06-20"},"additionalneeds":"Dinner"}'
  curl http://localhost:3003/booking/4242    # 200; /booking/17 → 404
  ```
- Expected: `bookingid` is server-owned and not in the PUT/PATCH request body table. It should be ignored or rejected, as POST does (POST with `"bookingid":1` was ignored and got id 21). Ids must stay unique (Familiar problems: mass assignment; Consistency with POST).
- Actual: Each request returned `405 Method Not Allowed`, but the change was applied. The booking disappeared from its old id and showed up at the id the client chose. Moving booking 16 to id 12 made the list contain `{"bookingid":12}` twice. `GET /booking/12` returned only the first one, so the moved booking could not be reached. After `DELETE /booking/12`, `GET /booking/12` returned the other ("Victim One") booking.
- Reproduced: 3 times (PATCH→999, PATCH→12 collision, PUT→4242).

### F2: PATCH with only one booking date overwrites the other date with "0NaN-aN-aN"
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -X PATCH http://localhost:3003/booking/11 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=9374b1385d7e82e' -d '{"bookingdates":{"checkin":"2020-05-05"}}'
  curl -X PATCH http://localhost:3003/booking/1 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d '{"bookingdates":{"checkout":"2021-06-06"}}'
  ```
- Expected: The docs mark `bookingdates.checkin` and `bookingdates.checkout` as optional on PATCH ("partial payload"), so the date that isn't sent should stay as it was.
- Actual: `200` with `"bookingdates":{"checkin":"2020-05-05","checkout":"0NaN-aN-aN"}` (booking 11, originally checkout 2019-01-01) and `"checkin":"0NaN-aN-aN","checkout":"2021-06-06"` (booking 1). The corruption was saved: GET in JSON and in XML both show `0NaN-aN-aN`.
- Reproduced: 2 times (checkin-only and checkout-only), plus read-backs.

### F3: Decimal totalprice is silently truncated to an integer
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Dec","lastname":"Price","totalprice":99.99,"depositpaid":false,"bookingdates":{"checkin":"2021-01-01","checkout":"2021-01-02"},"additionalneeds":"Ünïcødé 🎉"}'
  curl -X PUT http://localhost:3003/booking/15 ... -d '{..."totalprice":150.75,...}'
  ```
- Expected: `totalprice` is documented as a Number, so 99.99 should be stored as 99.99 or rejected. It should not quietly lose money (Familiar problems: precision loss).
- Actual: `200`, `"totalprice":99` (and on read-back). The PUT returned `"totalprice":150`.
- Reproduced: 2 times (POST, PUT).

### F4: Invalid totalprice / depositpaid values are coerced instead of rejected (non-numeric price → null, any string → true)
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Str","lastname":"Price","totalprice":"abc","depositpaid":"maybe","bookingdates":{"checkin":"2021-02-29","checkout":"2020-12-31"},"additionalneeds":"x"}'
  ```
  and the PATCH in F1 with `"totalprice":"free","depositpaid":"no"`.
- Expected: A 400 for values that aren't a Number or Boolean, as the docs' types state.
- Actual: `200`, `"totalprice":null,"depositpaid":true`. Read-back of id 14 is the same. The PATCH stored `"totalprice":null,"depositpaid":true` on booking 999, so `"no"` became `true`.
- Reproduced: 2 times.

### F5: depositpaid=false sent as XML or URL-encoded is stored as true
- Kind: bug
- Severity: high (deposit status is wrong)
- Steps:
  ```
  curl -X POST http://localhost:3003/booking -H 'Content-Type: text/xml' -H 'Accept: application/xml' -d '<booking>...<depositpaid>false</depositpaid>...</booking>'
  curl -X PUT http://localhost:3003/booking/18 -H 'Content-Type: text/xml' -H 'Accept: application/json' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d '<booking>...<depositpaid>false</depositpaid>...</booking>'
  curl -X POST http://localhost:3003/booking -H 'Content-Type: application/x-www-form-urlencoded' -H 'Accept: application/json' -d 'firstname=Ursula&lastname=Url2&totalprice=111&depositpaid=false&bookingdates%5Bcheckin%5D=2018-01-01&bookingdates%5Bcheckout%5D=2018-01-02'
  ```
- Expected: `depositpaid` false, the same as JSON `false` (which is kept: booking 15 stayed `false`). Oracle: Consistency across formats.
- Actual: `<depositpaid>true</depositpaid>` (XML POST), `"depositpaid":true` (XML PUT), `"depositpaid":true` (URL-encoded POST).
- Reproduced: 3 times.

### F6: Impossible or unparseable dates are silently rolled over or stored as "0NaN-aN-aN"
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Bad","lastname":"Date","totalprice":10,"depositpaid":true,"bookingdates":{"checkin":"2019-02-30","checkout":"not-a-date"},"additionalneeds":"x"}'
  ```
  plus the F4 request with `"checkin":"2021-02-29"`.
- Expected: A 400 for invalid dates (Familiar problems: date handling; User expectations).
- Actual: `200`. `2019-02-30` was stored as `2019-03-02`, `2021-02-29` as `2021-03-01`, and `not-a-date` as `0NaN-aN-aN`.
- Reproduced: 2 times (rollover); NaN storage seen on create once, and also through F2.

### F7: Checkout before checkin and negative totalprice are accepted
- Kind: needs a decision
- Severity: medium
- Steps:
  ```
  curl -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Neg","lastname":"Rev","totalprice":-500,"depositpaid":true,"bookingdates":{"checkin":"2019-01-10","checkout":"2019-01-01"},"additionalneeds":"x"}'
  ```
- Expected: A booking can't end before it starts and a price can't be negative (User expectations, Purpose). The docs say nothing about this.
- Actual: `200`, stored as sent (id 12). Reversed dates were accepted again in the F4 request (2021-03-01 → 2020-12-31). A negative price was accepted again via PUT (`"totalprice":-1`, id 4242).
- Reproduced: 2 times each.

### F8: GET /booking?checkin= excludes bookings whose checkin equals the filter date
- Kind: bug
- Severity: medium
- Steps: create booking 17 with checkin 2030-06-15, checkout 2030-06-20, then
  ```
  curl 'http://localhost:3003/booking?checkin=2030-06-15'   # []
  curl 'http://localhost:3003/booking?checkin=2030-06-14'   # [{"bookingid":17}]
  curl 'http://localhost:3003/booking?checkin=2030-06-15&checkout=2030-06-20'  # []
  ```
- Expected: Docs: "Return bookings that have a checkin date greater than or equal to the set checkin date".
- Actual: `[]` at equality, so the comparison is strictly greater-than.
- Reproduced: 2 times.

### F9: GET /booking?checkout= returns bookings that check out on or before the date (reverse of the docs)
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl 'http://localhost:3003/booking?checkout=2030-06-20'  # all bookings, incl. 12 (checkout 2019-01-01)
  curl 'http://localhost:3003/booking?checkout=2030-06-21'  # includes 17 (checkout 2030-06-20)
  curl 'http://localhost:3003/booking?checkout=2025-01-01'  # excludes 17, includes 2019-era bookings
  ```
- Expected: Docs: "Return bookings that have a checkout date greater than or equal to the set checkout date". `checkout=2030-06-21` should not return a booking that checks out on 2030-06-20.
- Actual: The filter behaves as "checkout ≤ date". It also returns bookings whose dates are `0NaN-aN-aN` (ids 1, 11).
- Reproduced: 3 times.

### F10: Malformed date in a filter, or missing fields on create, give 500 instead of 400
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl 'http://localhost:3003/booking?checkin=15-06-2030'
  curl 'http://localhost:3003/booking?checkout=garbage'
  curl -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Missing"}'
  curl -X POST http://localhost:3003/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"lastname":"NoFirst","totalprice":5,"depositpaid":true,"bookingdates":{"checkin":"2021-01-01","checkout":"2021-01-02"}}'
  ```
- Expected: 400 for client errors (Standards). PUT with missing fields does return `400 Bad Request`, and so does malformed JSON on POST (Consistency).
- Actual: `500 Internal Server Error` in all four cases.
- Reproduced: 2 times each (filters, create).

### F11: PUT/PATCH/DELETE on a non-existent booking return 405 instead of 404
- Kind: bug
- Severity: low
- Steps:
  ```
  curl -X PUT http://localhost:3003/booking/5555 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=9374b1385d7e82e' -d '{...full valid body...}'
  curl -X DELETE http://localhost:3003/booking/5555 -H 'Cookie: token=9374b1385d7e82e'
  curl -X PATCH http://localhost:3003/booking/5555 -H 'Content-Type: application/json' -H 'Cookie: token=9374b1385d7e82e' -d '{"firstname":"Ghost"}'
  ```
- Expected: 404 Not Found, as GET returns. 405 means the method isn't supported (Standards).
- Actual: `405 Method Not Allowed` for all three. The same 405 is also returned for successful id-changing updates (F1), so clients can't tell failure from success.
- Reproduced: 4+ times (also PATCH on the moved id 15).

### F12: Accept: application/x-www-form-urlencoded returns a leaked internal error with 200, and the booking is still created
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -X POST http://localhost:3003/booking -H 'Content-Type: application/x-www-form-urlencoded' -H 'Accept: application/x-www-form-urlencoded' -d 'firstname=Ursula&lastname=Url&totalprice=111&depositpaid=false&bookingdates%5Bcheckin%5D=2018-01-01&bookingdates%5Bcheckout%5D=2018-01-02'
  curl http://localhost:3003/booking/18 -H 'Accept: application/x-www-form-urlencoded'
  curl 'http://localhost:3003/booking?firstname=Ursula'
  ```
- Expected: The URL-encoded response shown in the docs ("Response example: URL Response"), or a 406. Never an internal error message sent with 200.
- Actual: `200`, `Content-Type: text/html`, body `formurlencoded is not a function`. The POST still created booking 19, which the name search lists. A client that sees the error and retries would create a duplicate.
- Reproduced: 2 times (POST and GET).

### F13: XML responses are labelled Content-Type text/html
- Kind: bug
- Severity: low
- Steps: `curl -i http://localhost:3003/booking/11 -H 'Accept: application/xml'`, plus the XML POST in F5.
- Expected: `application/xml` (or `text/xml`), as requested with Accept (Standards).
- Actual: `Content-Type: text/html; charset=utf-8` with an XML body.
- Reproduced: 2 times.

### F14: POST /auth with bad credentials returns 200 OK
- Kind: needs a decision
- Severity: low
- Steps:
  ```
  curl -i -X POST http://localhost:3003/auth -H 'Content-Type: application/json' -d '{"username":"admin","password":"wrong"}'
  curl -i -X POST http://localhost:3003/auth -H 'Content-Type: application/json' -d '{"username":"nobody","password":""}'
  ```
- Expected: 401 by HTTP convention. The docs only describe the 200 success case.
- Actual: `200 OK` `{"reason":"Bad credentials"}`.
- Reproduced: 2 times.

### F15: Success statuses are 201 Created for DELETE and /ping
- Kind: needs a decision
- Severity: low
- Steps: `curl -i -X DELETE http://localhost:3003/booking/13 -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM='`; `curl -i http://localhost:3003/ping`
- Expected: Convention is 200/204 for DELETE and 200 for a health check. The docs contradict themselves: the table heading says "Success 200" but the field reads "Default HTTP 201 response" and the example shows 201.
- Actual: `201 Created` / `Created` (DELETE twice, ping once). The deletion itself worked (GET → 404).
- Reproduced: 2 times (DELETE).

### F16: Name filter is case-sensitive, so the documented example would not match
- Kind: needs a decision
- Severity: low
- Steps: `curl 'http://localhost:3003/booking?firstname=Quentin&lastname=Filterson'` → `[{"bookingid":17}]`; `curl 'http://localhost:3003/booking?firstname=quentin&lastname=filterson'` → `[]`; `curl 'http://localhost:3003/booking?firstname=quentin'` → `[]`.
- Expected: The docs example uses `firstname=sally&lastname=brown` for a guest shown as "Sally Brown", which implies case-insensitive matching.
- Actual: Exact-case match only.
- Reproduced: 2 times.

## Questions
- Is there token expiry or invalidation? I used one token for the whole session and never saw it expire. Confirm by waiting, or by issuing a new token and retrying the old one.
- Does `additionalneeds: null` count as valid? A PATCH stored `"additionalneeds":null`, and the docs mark the field as non-optional in responses. I saw this once and didn't follow it up.
- Doc errors (not system behaviour): the PATCH examples use `curl -X PUT`; the Content-Type header table lists only json/xml while the examples use URL-encoded; the docs base URL is 3001. These should be corrected in the docs.
- Concurrency and double-submit (two simultaneous PATCHes, or a duplicate POST) were not tested.

## Coverage
- C1 (auth): no credentials, empty cookie token, doc example token `abc123`, and wrong Basic auth all return 403 on PUT/PATCH/DELETE. Valid cookie and Basic auth both work. No bypass found. Bad-credential login status → F14.
- C2/C2b (update integrity): partial date PATCH (F2), server-owned `bookingid` on PATCH/PUT/POST (F1; POST ignores it), PUT with missing fields (400, and the booking was not changed: verified), null field via PATCH, non-existent ids (F11), DELETE of a duplicated id.
- C3 (validation): negative or decimal price, string price/boolean, impossible and reversed dates, missing fields, malformed JSON, Unicode/emoji in additionalneeds (round-tripped correctly).
- C4 (filters): checkin/checkout boundaries on both sides, combined filters, name case, malformed date formats.
- C5 (formats): XML create/update, URL-encoded create, Accept xml / x-www-form-urlencoded on GET and POST.
- Not reached: huge payloads, injection strings in filters, concurrency, token lifecycle, XML with missing/extra elements, PATCH via XML/URL-encoded, GET /booking/:id with leading zeros or negative ids.
- Budget: 75 of 80 requests used.
