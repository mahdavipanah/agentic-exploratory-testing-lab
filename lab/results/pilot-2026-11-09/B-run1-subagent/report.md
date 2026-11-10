# Exploration report

## Charters
1. Explore the booking lifecycle (create, read, full update, partial update, delete, then read again) with JSON payloads and the admin token to discover whether every step does what the docs say and returns the documented status code. Tour: Guidebook.
2. Explore one booking's data across every endpoint and format (JSON, XML, URL-encoded; different Accept and Content-Type pairs) with a single distinctive booking to discover data that changes, disappears or is formatted differently along the way. Tour: FedEx.
3. Explore create, full update and partial update with bad and boundary data (missing or extra fields, wrong types, negative or huge prices, checkout before checkin, invalid dates, very long and non-ASCII names) to discover what the API wrongly accepts and what it rejects badly. Tour: Antisocial.
4. Explore authorization and search with no credentials, wrong tokens, Basic auth versus cookie, unknown ids, and the GET /booking filters to discover who can change what, and whether search follows the docs. Tours: Saboteur and Back alley.

## Findings

Token used below: `0484833fbe9ada4` (from `POST /auth` with admin/password123). Booking ids refer to bookings created during this session.

### F1: depositpaid "false" is stored as true when sent as XML, URL-encoded, or a JSON string
- Severity: high
- Request:
  ```
  curl -s -i -X POST http://localhost:3002/booking -H 'Content-Type: text/xml' -H 'Accept: application/xml' -d '<booking><firstname>Zoë-Ann</firstname><lastname>O&apos;Brien &amp; Sons</lastname><totalprice>123.45</totalprice><depositpaid>false</depositpaid><bookingdates><checkin>2024-02-29</checkin><checkout>2024-03-01</checkout></bookingdates><additionalneeds>Late &lt;checkout&gt; &amp; cot</additionalneeds></booking>'
  ```
- Expected: depositpaid is a Boolean (docs). `<depositpaid>false</depositpaid>`, the documented XML format, and `depositpaid=false`, the documented URL-encoded format, should be stored as `false`. A JSON string like `"false"` should be stored as false or rejected with 400.
- Actual: `200 OK`, response has `<depositpaid>true</depositpaid>`. A later `GET /booking/14` in JSON returns `"depositpaid":true`.
- Reproduced: 5 times. (1) XML POST above, which created booking 14. (2) XML PUT on booking 13, which had `depositpaid:false`, with `<depositpaid>false</depositpaid>`: the response shows `true`, so the PUT turned false into true. (3) URL-encoded POST with `depositpaid=false`, which created booking 15 with `"depositpaid":true`. (4) JSON POST with `"depositpaid":"false"`, which created booking 19 with `true`. (5) JSON PATCH with `"depositpaid":"no"` on booking 26: `true`.

### F2: PATCH with only one booking date erases the other date and saves "0NaN-aN-aN"
- Severity: high
- Request:
  ```
  curl -s -i -X PATCH http://localhost:3002/booking/11 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=0484833fbe9ada4' -d '{"bookingdates":{"checkin":"2018-03-03"}}'
  ```
- Expected: the docs list `bookingdates.checkin` and `bookingdates.checkout` as separately optional in PATCH. Patching only checkin should leave checkout as it was (`2019-02-01`).
- Actual: `200 OK`, `"bookingdates":{"checkin":"2018-03-03","checkout":"0NaN-aN-aN"}`. A later `GET /booking/11` returns the same broken value, so it was saved.
- Reproduced: 2 times. The mirror case on booking 12 (`{"bookingdates":{"checkout":"2020-02-02"}}`) returned `"checkin":"0NaN-aN-aN"`, and `GET /booking/12` confirmed it was saved.

### F3: Invalid dates are accepted. Impossible dates roll over silently, unparseable ones are saved as "0NaN-aN-aN"
- Severity: medium
- Request:
  ```
  curl -s -i -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Invalid","lastname":"Dates","totalprice":10,"depositpaid":true,"bookingdates":{"checkin":"2023-02-30","checkout":"not-a-date"},"additionalneeds":"x"}'
  ```
- Expected: 400 Bad Request. Checkin and checkout are typed as Date, and the search docs require the format CCYY-MM-DD.
- Actual: `200 OK`, `"bookingdates":{"checkin":"2023-03-02","checkout":"0NaN-aN-aN"}`. The stored date differs from what was sent.
- Reproduced: 2 times. `PATCH /booking/22` with `{"bookingdates":{"checkin":"2025-13-45","checkout":"2025-02-29"}}` returned 200 with `"checkin":"0NaN-aN-aN","checkout":"2025-03-01"`.

### F4: Checkout before checkin is accepted
- Severity: medium
- Request:
  ```
  curl -s -i -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Backwards","lastname":"Dates","totalprice":10,"depositpaid":true,"bookingdates":{"checkin":"2024-05-10","checkout":"2024-05-01"},"additionalneeds":"x"}'
  ```
- Expected: 400. A stay cannot end before it starts.
- Actual: `200 OK`, booking 22 created with `"checkin":"2024-05-10","checkout":"2024-05-01"`.
- Reproduced: 2 times. `PUT /booking/22` with checkin `2025-12-31` and checkout `2025-01-01` returned 200 and echoed the reversed dates.

### F5: Negative totalprice is accepted
- Severity: medium
- Request:
  ```
  curl -s -i -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Neg","lastname":"Price","totalprice":-500,"depositpaid":true,"bookingdates":{"checkin":"2024-01-01","checkout":"2024-01-02"},"additionalneeds":"x"}'
  ```
- Expected: 400. A booking's total price should not be negative.
- Actual: `200 OK`, booking 20 with `"totalprice":-500`.
- Reproduced: 2 times. `PUT /booking/22` with `"totalprice":-1` returned 200 and `"totalprice":-1`.

### F6: Non-numeric totalprice is accepted and saved as NaN. JSON shows null, XML shows "NaN"
- Severity: medium
- Request:
  ```
  curl -s -i -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"StrBool","lastname":"Test","totalprice":"abc","depositpaid":"false","bookingdates":{"checkin":"2024-01-01","checkout":"2024-01-02"},"additionalneeds":"x"}'
  ```
- Expected: 400. totalprice is typed as Number.
- Actual: `200 OK`, booking 19 with `"totalprice":null`.
- Reproduced: 2 times. `PATCH /booking/26` with `"totalprice":"free"` returned 200 with `"totalprice":null`. `GET /booking/26` with `Accept: application/xml` then showed `<totalprice>NaN</totalprice>`. The same PATCH also set `"firstname":null`, which XML rendered as the string `<firstname>null</firstname>` (seen once). So the same booking reads differently in JSON and XML.

### F7: Decimal totalprice is truncated to an integer
- Severity: medium
- Request:
  ```
  curl -s -i -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Zoë-Ann","lastname":"O'"'"'Brien & Sons","totalprice":123.45,"depositpaid":false,"bookingdates":{"checkin":"2024-02-29","checkout":"2024-03-01"},"additionalneeds":"Late <checkout> & cot"}'
  ```
- Expected: totalprice is a Number, and a price of 123.45 should come back as 123.45, or be rejected if only integers are allowed (the docs don't say so).
- Actual: `200 OK`, `"totalprice":123`. 0.45 is lost without any error.
- Reproduced: 3 times. Once each in JSON (booking 13), XML (booking 14, `<totalprice>123</totalprice>`) and URL-encoded (booking 15).

### F8: The documented `Accept: application/x-www-form-urlencoded` returns 200 with the error "formurlencoded is not a function", but the write still happens
- Severity: medium
- Request:
  ```
  curl -s -i -X PATCH http://localhost:3002/booking/13 -H 'Content-Type: application/x-www-form-urlencoded' -H 'Accept: application/x-www-form-urlencoded' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d 'firstname=Zoe&lastname=OBrien'
  ```
- Expected: the docs give a "URL Response" example for GET, POST, PUT and PATCH, so the API should return the booking URL-encoded, for example `firstname=Zoe&lastname=OBrien&...`.
- Actual: `200 OK`, `Content-Type: text/html; charset=utf-8`, body `formurlencoded is not a function`. A later `GET /booking/13` shows that the PATCH was applied (`"firstname":"Zoe","lastname":"OBrien"`). The client gets a success status with an error message as the body.
- Reproduced: 3 times. (1) `GET /booking/13` with this Accept header: same body. (2) The PATCH above. (3) `POST /booking` (JSON body) with this Accept header: same body, but a search for `firstname=Urlacc` shows booking 17 was created. The client never receives the new booking id.

### F9: POST /booking returns 500 Internal Server Error for missing fields or an unsupported XML Content-Type, while PUT returns 400
- Severity: medium
- Request:
  ```
  curl -s -i -X POST http://localhost:3002/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"lastname":"NoFirst","totalprice":10,"depositpaid":true,"bookingdates":{"checkin":"2024-01-01","checkout":"2024-01-02"},"additionalneeds":"x"}'
  ```
- Expected: 400 Bad Request. firstname is not optional (docs), and this is a client error. The same missing field on PUT correctly returns 400.
- Actual: `500 Internal Server Error`, body `Internal Server Error`.
- Reproduced: 4 times. (1) Missing firstname (above). (2) Missing lastname: 500. (3, 4) `POST /booking` twice with `Content-Type: application/xml` and a valid XML body: 500 both times. For comparison, `PUT /booking/26` without lastname returned 400, and `PUT /booking/22` with `Content-Type: application/xml` returned 400.

### F10: PUT, PATCH and DELETE on a missing booking id return 405 Method Not Allowed instead of 404
- Severity: low
- Request:
  ```
  curl -s -i -X PUT http://localhost:3002/booking/999999 -H 'Content-Type: application/json' -H 'Cookie: token=0484833fbe9ada4' -d '{"firstname":"Ghost","lastname":"X","totalprice":1,"depositpaid":true,"bookingdates":{"checkin":"2025-01-01","checkout":"2025-01-02"},"additionalneeds":"x"}'
  ```
- Expected: 404 Not Found, as `GET /booking/999999` returns. The methods are allowed; the resource does not exist.
- Actual: `405 Method Not Allowed`, body `Method Not Allowed`.
- Reproduced: 5 times. DELETE on deleted booking 11 (Basic auth), PUT on deleted booking 11, PATCH on deleted booking 12, PUT on 999999, and DELETE on 999999 all returned 405.

### F11: The GET /booking `checkin` filter leaves out bookings that check in on the filter date, and includes a booking whose checkin is invalid
- Severity: medium
- Request:
  ```
  curl -s 'http://localhost:3002/booking?checkin=2024-01-01'
  ```
- Expected: the docs say "Return bookings that have a checkin date greater than or equal to the set checkin date." Bookings 17–21 and 24–26 check in on exactly 2024-01-01 and should be returned. Booking 22, whose checkin is `0NaN-aN-aN`, should not match any date.
- Actual: `200 OK`, `[{"bookingid":1},{"bookingid":13},{"bookingid":14},{"bookingid":15},{"bookingid":22}]`. All bookings that check in on that exact date are missing, and booking 22 is included.
- Reproduced: 2 times. `?checkin=2024-02-29` returned only `[1, 22]` and left out bookings 13, 14 and 15, which check in on exactly 2024-02-29. Booking 22 was included again.

### F12: The GET /booking `checkout` filter returns bookings that check out on or before the date, not on or after
- Severity: medium
- Request:
  ```
  curl -s 'http://localhost:3002/booking?checkout=2019-01-01'
  ```
- Expected: the docs say "Return bookings that have a checkout date greater than or equal to the set checkout date." All session bookings with checkout in 2024 or 2025 (13–15, 17–22, …) should be returned.
- Actual: `200 OK`, `[{"bookingid":4},{"bookingid":16}]`. Only booking 16 (checkout 2019-01-01) and one seed booking are returned. Every later checkout is left out.
- Reproduced: 2 times. `?checkout=2024-03-01` returned bookings 16 (checkout 2019-01-01) and 17–21 (checkout 2024-01-02), which are before the date. It left out booking 22, whose checkout of 2025-03-01 was after the date at that point.

### F13: POST /auth with wrong credentials returns 200 OK
- Severity: low
- Request:
  ```
  curl -s -i -X POST http://localhost:3002/auth -H 'Content-Type: application/json' -d '{"username":"admin","password":"wrong"}'
  ```
- Expected: 401 Unauthorized, or another 4xx. A failed login should not return a success status. Only 200 with a token is documented.
- Actual: `200 OK`, body `{"reason":"Bad credentials"}`.
- Reproduced: 2 times. Username `nobody` returned the same 200 response.

### F14: XML responses are sent with Content-Type text/html
- Severity: low
- Request:
  ```
  curl -s -i http://localhost:3002/booking/13 -H 'Accept: application/xml'
  ```
- Expected: `Content-Type: application/xml` (or `text/xml`), since the client asked for application/xml and the body is XML.
- Actual: `200 OK`, `Content-Type: text/html; charset=utf-8`, body starts with `<?xml version='1.0'?><booking>…`.
- Reproduced: 4 times: GET /booking/13, POST /booking (XML, booking 14), PUT /booking/13 (XML), and GET /booking/26.

### F15: An unsupported Accept header returns 418 I'm a Teapot
- Severity: low
- Request:
  ```
  curl -s -i http://localhost:3002/booking/14 -H 'Accept: text/plain'
  ```
- Expected: 406 Not Acceptable, or a fallback to JSON.
- Actual: `418 I'm a Teapot`, body `I'm a Teapot`.
- Reproduced: 2 times (`Accept: text/plain` and `Accept: text/csv`).

## Questions
- **Name search is case-sensitive.** The docs example is `?firstname=sally&lastname=brown`, in lowercase, while the sample data is "Sally Brown". `?firstname=Jim&lastname=Brown` returned `[2,16]`, but `?firstname=jim&lastname=brown` returned `[]`. `?firstname=Zoë-Ann` matched but `zoë-ann` did not. The docs never say whether search is case-sensitive, so it is unclear whether this is a bug.
- **DELETE and /ping return 201 Created.** The docs say "Success 200" in the table heading but show `HTTP/1.1 201 Created` in the example. The API matches the example, so the docs contradict themselves. 200 or 204 would be more usual for DELETE.
- **The docs' PATCH examples use `curl -X PUT`.** This is a docs error. Run as written, they would send full updates with partial bodies, which get 400. I used PATCH.
- **additionalneeds missing.** POST without additionalneeds was accepted (booking 18) even though the docs mark it as not optional. Seen once.
- **Required fields that are empty or null.** POST accepted `"firstname":""` (booking 26), and PATCH accepted `"firstname":null`. Each was seen once.
- **POST with several wrong types.** firstname as a number, lastname as a boolean and additionalneeds as an array together returned 500. I did not find out which field causes it.
- **Very large price.** `99999999999999999999` came back as `100000000000000000000` (JavaScript number precision). Seen once.
- **No length limit on names.** A 10,000-character firstname was accepted (200). Whether there should be a limit is not documented.
- **application/xml as the request Content-Type.** The docs list only `text/xml` for request bodies, but `application/xml` is listed for Accept. Supporting both for requests might be expected. Today it gives 500 on POST (see F9) and 400 on PUT.
- **Which credential wins.** A request with a bad cookie token and a valid Basic header succeeded (200). It is not clear which should take priority. Token expiry was not tested.
- **Extra fields are dropped without notice.** `bookingid:999`, `vip:true` and `bookingdates.nights` were all ignored. No harm seen, but it is not documented.

## Coverage
- **Charter 1 (requests 1–20):** auth, ping, POST/GET/PUT/PATCH/DELETE with both cookie and Basic auth, re-read after each step, re-delete, writes to a deleted booking, and the list after delete. This charter found F2 and F10.
- **Charter 2 (requests 21–37):** one booking with unusual values (Zoë-Ann / O'Brien & Sons / 123.45 / false / leap day / `<>&` in additionalneeds), sent through JSON, XML and URL-encoded create; JSON, XML, URL-encoded and text/plain reads; XML PUT; URL-encoded PATCH; the documented XML example run exactly as written; an application/xml request body; and search by non-ASCII and special-character names. Escaping and non-ASCII text survived every format. This charter found F1, F7, F8, F14 and F15.
- **Charter 3 (requests 38–56):** missing, extra, empty, null and wrong-type fields; negative and huge prices; reversed, impossible and garbage dates; 10,000-character and Persian/emoji names; malformed JSON and XML (both correctly got 400); PUT and PATCH with bad data. This charter found F3–F6 and F9.
- **Charter 4 (requests 57–80):** wrong password and unknown user on /auth; PUT, PATCH and DELETE with no credentials, a wrong cookie, an empty cookie, wrong Basic, another user's Basic, and mixed credentials (all bad credentials correctly got 403); unknown and non-numeric ids; name search in both cases; checkin and checkout boundary searches; a combined name and date search (it behaves as AND). This charter found F11, F12 and F13.
- **Not explored:** token expiry and reuse after a long time; `Authorization: Bearer`; HEAD, OPTIONS and other unlisted methods or routes; concurrent or repeated POSTs; invalid date formats in search filters (for example `checkin=abc`); XML-specific attacks (entities or DTDs); very large request bodies; PATCH with an XML body.
- **Requests used:** 80 of 80.
