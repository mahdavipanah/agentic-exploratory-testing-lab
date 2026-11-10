# Exploration report

## Environment
- Target: http://localhost:3004 (Express, `X-Powered-By: Express`). The docs say port 3001; the run instructions say 3004.
- Server clock (Date header): Mon, 09 Nov 2026 ~16:05 GMT. No version endpoint was available.
- Seed state: bookings 1–10 existed before testing. Booking 1 = Jim Brown, 2015-10-11 → 2016-05-08 (no additionalneeds).
- Environment check: `GET /ping` returned 201. I created booking 11 with non-ASCII names ("Zoë", "Ünïcode") and read it back unchanged in both JSON and XML, and it appeared in `GET /booking`.
- Auth: `POST /auth` with admin/password123 returned the token `eff47e5d3b69d93`. Basic auth `YWRtaW46cGFzc3dvcmQxMjM=` also works.

## Risks
1. Updates corrupt or lose stored bookings (PATCH merge, PUT, server-owned fields such as `bookingid`).
2. Money and deposit values stored wrongly (`totalprice` precision, `depositpaid` coercion across JSON, XML and form input).
3. Invalid dates and input accepted silently (impossible dates, reversed ranges, wrong types).
4. Access control on PUT, PATCH and DELETE (no token, a wrong token, wrong Basic credentials).
5. Search filters return the wrong set of bookings (date boundaries, case).
6. Error handling and protocol conventions (status codes, content types, unsupported Accept values).

## Charters
- C1: Explore PATCH/PUT with partial and nested bodies and server-owned fields to discover data loss or corruption. Tour: FedEx + Back alley. Budget: 20.
- C2: Explore create/update validation with wrong-type, missing, negative, impossible and reversed values in JSON, XML and urlencoded to discover silent acceptance or crashes. Tour: Antisocial. Budget: 25.
- C3: Explore auth on PUT/PATCH/DELETE and /auth with missing or wrong credentials to discover access-control gaps. Tour: Saboteur. Budget: 8.
- C4: Explore GET /booking filters at date and name boundaries to discover filters that contradict the docs. Tour: Guidebook + Intellectual. Budget: 10.
- C5: Explore delete, repeated delete and update of deleted or missing ids, plus Accept/Content-Type variants, to discover state and protocol problems. Tour: Obsessive-compulsive + Guidebook. Budget: 10.

## Findings

### F1: PATCH that sets only one booking date overwrites the other date with "0NaN-aN-aN"
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -si -X PATCH http://localhost:3004/booking/11 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=eff47e5d3b69d93' -d '{"bookingdates":{"checkout":"2019-06-01"}}'
  curl -si -X PATCH http://localhost:3004/booking/12 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d '{"bookingdates":{"checkin":"2020-01-02"}}'
  ```
- Expected: the docs list every PATCH field, including `bookingdates.checkin` and `bookingdates.checkout`, as optional, so a field that isn't sent should keep its stored value (checkin 2018-01-01 for booking 11, checkout 2020-01-05 for booking 12).
- Actual: 200. Booking 11 returned `"bookingdates":{"checkin":"0NaN-aN-aN","checkout":"2019-06-01"}`, and a later GET returned the same. Booking 12 returned `"checkout":"0NaN-aN-aN"`. The stored date is lost. Patching a top-level field alone (`{"firstname":"Renamed"}` on booking 17) kept both dates.
- Reproduced: 2 (one per date field, with cookie and Basic auth), plus a GET read-back.

### F2: `bookingid` in a PUT/PATCH body reassigns the booking's id, so the booking disappears and duplicate ids appear in the list
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -si -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Vanish","lastname":"Test","totalprice":50,"depositpaid":false,"bookingdates":{"checkin":"2024-05-01","checkout":"2024-05-02"},"additionalneeds":"x"}'   # -> bookingid 22
  curl -si -X PUT http://localhost:3004/booking/22 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=eff47e5d3b69d93' -d '{"bookingid":1,"firstname":"Vanish","lastname":"Test","totalprice":50,"depositpaid":false,"bookingdates":{"checkin":"2024-05-01","checkout":"2024-05-02"},"additionalneeds":"x"}'
  curl -si http://localhost:3004/booking/22
  curl -si 'http://localhost:3004/booking'
  ```
- Expected: `bookingid` is server-owned and isn't a documented request field. The server should ignore it or reject it with 400, and booking 22 should stay at /booking/22.
- Actual: the PUT returns `405 Method Not Allowed`, but the write still happens. `GET /booking/22` then returns 404. `GET /booking` lists `{"bookingid":1}` three times: `[...,{"bookingid":17},{"bookingid":1},{"bookingid":19},{"bookingid":20},{"bookingid":21},{"bookingid":1},{"bookingid":1}]`. `GET /booking?firstname=Ctrl&lastname=Test` returns `[{"bookingid":1}]`, but `GET /booking/1` still returns the original Jim Brown. The moved bookings can no longer be reached by id. A control PUT with an unknown field (`"foo":1`) on booking 23 returned 200 and worked normally, so `bookingid` specifically triggers this.
- Reproduced: 3 (PUT on 18, PUT on 22, PATCH `{"bookingid":1}` on 23). Each time the booking returned 404 afterwards.

### F3: `depositpaid` false is stored as true when sent as XML, form data or the JSON string "false"
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -si -X POST http://localhost:3004/booking -H 'Content-Type: text/xml' -H 'Accept: application/xml' -d '<booking><firstname>Xml</firstname><lastname>Path</lastname><totalprice>120.50</totalprice><depositpaid>false</depositpaid><bookingdates><checkin>2024-03-01</checkin><checkout>2024-03-05</checkout></bookingdates><additionalneeds>Lunch</additionalneeds></booking>'
  curl -si -X PUT http://localhost:3004/booking/20 -H 'Content-Type: text/xml' -H 'Accept: application/json' -H 'Authorization: Basic YWRtaW46cGFzc3dvcmQxMjM=' -d '<booking>...<depositpaid>false</depositpaid>...</booking>'
  curl -si -X PATCH http://localhost:3004/booking/18 -H 'Content-Type: application/x-www-form-urlencoded' -H 'Accept: application/json' -H 'Cookie: token=eff47e5d3b69d93' -d 'depositpaid=false'
  curl -si -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Str","lastname":"False","totalprice":"150","depositpaid":"false",...}'
  ```
- Expected: false in, false stored. The docs' own XML and urlencoded examples send `depositpaid` as text, so "false" must mean false. (The JSON boolean `false` is stored correctly, as on booking 17.)
- Actual: every response, and the JSON read-back (`GET /booking/20`, `GET /booking/21`), shows `"depositpaid":true`. "maybe" and "no" also become true.
- Reproduced: 6 (XML POST, XML PUT, form POST, form PATCH, JSON string ×2).

### F4: Decimal `totalprice` is truncated to a whole number
- Kind: bug
- Severity: high
- Steps:
  ```
  curl -si -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"bookingid":999,"firstname":"Mass","lastname":"Assign","totalprice":99.99,"depositpaid":false,"bookingdates":{"checkin":"2024-01-01","checkout":"2024-01-02"},"additionalneeds":"none","isAdmin":true}'
  curl -si -X PUT http://localhost:3004/booking/17 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=eff47e5d3b69d93' -d '{"firstname":"Mass","lastname":"Assign","totalprice":149.75,"depositpaid":false,"bookingdates":{"checkin":"2024-01-01","checkout":"2024-01-02"},"additionalneeds":"none"}'
  ```
- Expected: `totalprice` is documented as a Number, so 99.99 should be stored as 99.99, or the request rejected if only integers are allowed. A price shouldn't change silently.
- Actual: 200 with `"totalprice":99`, and `GET /booking/17` also returns 99. The PUT returned `"totalprice":149`. The XML create with 120.50 returned 120. The price is truncated, not rounded.
- Reproduced: 3 (JSON POST, JSON PUT, XML POST), plus a read-back.

### F5: Non-numeric `totalprice` is accepted and stored as null
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -si -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Str2","lastname":"False2","totalprice":"twelve","depositpaid":"false","bookingdates":{"checkin":"2023-04-01","checkout":"2023-04-31"},"additionalneeds":"none"}'
  curl -si -X PATCH http://localhost:3004/booking/13 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=eff47e5d3b69d93' -d '{"totalprice":"free","depositpaid":"no","firstname":""}'
  ```
- Expected: 400. `totalprice` is a required Number.
- Actual: 200 with `"totalprice":null`. `GET /booking/14` (created with "abc") also returns `"totalprice":null`.
- Reproduced: 3 ("abc", "twelve" on POST, "free" on PATCH).

### F6: Impossible calendar dates are silently rolled over to the next month
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -si -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Str","lastname":"False","totalprice":"150","depositpaid":"false","bookingdates":{"checkin":"2023-02-29","checkout":"2023-03-01"},"additionalneeds":"none"}'
  ```
- Expected: 400 for a date that doesn't exist. Silently storing a different date than the client sent breaks user expectations.
- Actual: 200 with `"checkin":"2023-03-01"`. "2021-02-30" became "2021-03-02", and "2023-04-31" became "2023-05-01". In the 2023-02-29 case, checkin now equals checkout.
- Reproduced: 3.

### F7: A missing required field causes 500 Internal Server Error instead of 400
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -si -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Miss","totalprice":100,"depositpaid":true,"bookingdates":{"checkin":"2021-05-01","checkout":"2021-05-03"}}'
  ```
- Expected: 4xx. This is a client error, and PUT with a partial body does return `400 Bad Request`, as does malformed JSON on POST. Consistency and HTTP conventions both point to 400.
- Actual: `500 Internal Server Error`. No booking was created (checked with the list).
- Reproduced: 3 (missing lastname ×2, missing totalprice ×1).

### F8: The `checkin` filter leaves out bookings whose checkin equals the given date
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -si 'http://localhost:3004/booking?checkin=2024-01-01'   # booking 17 has checkin 2024-01-01
  curl -si 'http://localhost:3004/booking?checkin=2023-12-31'
  curl -si 'http://localhost:3004/booking?checkin=2026-09-16'   # booking 7 has checkin 2026-09-16
  ```
- Expected: the docs say "Return bookings that have a checkin date greater than or equal to the set checkin date", so 17 and 7 should be included.
- Actual: `checkin=2024-01-01` returned `[7,9,10]` without 17, and `checkin=2023-12-31` included 17. `checkin=2026-09-16` returned `[10]` without 7. The filter compares with strictly greater than.
- Reproduced: 2.

### F9: The `checkout` filter returns bookings that check out on or before the date, the opposite of the docs
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -si 'http://localhost:3004/booking?checkout=2000-01-01'
  curl -si 'http://localhost:3004/booking?checkout=2099-01-01'
  ```
- Expected: the docs say "checkout date greater than or equal to the set checkout date". 2000-01-01 should match almost every booking and 2099-01-01 none.
- Actual: `checkout=2000-01-01` returned `[{"bookingid":12}]`, the only booking whose checkout is the corrupted "0NaN-aN-aN". `checkout=2099-01-01` returned every booking. `checkout=2026-11-02` also included booking 1, which checks out on 2016-05-08.
- Reproduced: 3 queries.

### F10: `Accept: application/x-www-form-urlencoded` returns 200 with the body "formurlencoded is not a function"
- Kind: bug
- Severity: medium
- Steps:
  ```
  curl -si -X POST http://localhost:3004/booking -H 'Content-Type: application/x-www-form-urlencoded' -H 'Accept: application/x-www-form-urlencoded' -d 'firstname=Form&lastname=Path&totalprice=111&depositpaid=false&bookingdates%5Bcheckin%5D=2024-04-01&bookingdates%5Bcheckout%5D=2024-04-02&additionalneeds=Dinner'
  curl -si http://localhost:3004/booking/21 -H 'Accept: application/x-www-form-urlencoded'
  ```
- Expected: the URL response format shown in the docs, or an error status (406, or 500) if it isn't supported. Returning 200 with an error message breaks HTTP conventions, and the message exposes an internal JavaScript error.
- Actual: `200 OK`, `Content-Type: text/html`, body `formurlencoded is not a function`. The POST still created booking 21 (found by search), but the client never received the new id.
- Reproduced: 2 (POST and GET).

### F11: Negative prices and checkout before checkin are accepted
- Kind: needs a decision
- Severity: medium
- Steps:
  ```
  curl -si -X POST http://localhost:3004/booking -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"firstname":"Neg","lastname":"Price","totalprice":-500,"depositpaid":true,"bookingdates":{"checkin":"2021-05-10","checkout":"2021-05-01"},"additionalneeds":"none"}'
  curl -si -X PUT http://localhost:3004/booking/15 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=eff47e5d3b69d93' -d '{"firstname":"Neg","lastname":"Again","totalprice":-1,"depositpaid":false,"bookingdates":{"checkin":"2025-06-10","checkout":"2025-06-01"},"additionalneeds":"x"}'
  ```
- Expected: the docs state no rule, but a booking that ends before it starts, or that has a negative total, isn't meaningful (purpose oracle).
- Actual: 200 on both, and the values are stored as sent.
- Reproduced: 2 (POST and PUT).

### F12: XML responses are sent with `Content-Type: text/html`
- Kind: bug
- Severity: low
- Steps: `curl -si http://localhost:3004/booking/11 -H 'Accept: application/xml'`
- Expected: `application/xml` (or `text/xml`). The client asked for XML and the body is XML. With `text/html`, a browser could render stored, user-supplied markup as HTML.
- Actual: `Content-Type: text/html; charset=utf-8` with an XML body. The content is escaped correctly (`Tom &amp; &lt;b>Jerry&lt;/b>`).
- Reproduced: 4 (GET 11, GET 19, XML POST, and the urlencoded case).

### F13: POST /auth with wrong or missing credentials returns 200 OK
- Kind: needs a decision
- Severity: low
- Steps: `curl -si -X POST http://localhost:3004/auth -H 'Content-Type: application/json' -d '{"username":"admin","password":"wrong"}'`
- Expected: 401 is the convention for failed authentication. The docs only describe the success case.
- Actual: `200 OK` with `{"reason":"Bad credentials"}`. Clients that only check the status code will treat this as a login.
- Reproduced: 2 (wrong password, empty body `{}`).

### F14: PUT/PATCH/DELETE on a booking that doesn't exist returns 405 Method Not Allowed
- Kind: needs a decision
- Severity: low
- Steps:
  ```
  curl -si -X PATCH http://localhost:3004/booking/9999 -H 'Content-Type: application/json' -H 'Accept: application/json' -H 'Cookie: token=eff47e5d3b69d93' -d '{"firstname":"Ghost"}'
  ```
- Expected: 404, as GET returns for the same id. 405 means the method isn't supported for the resource.
- Actual: `405 Method Not Allowed` for PATCH 9999, a second DELETE of 16, and PUT on the deleted 16.
- Reproduced: 3.

## Questions
- **The unparseable date "not-a-date" is stored as "0NaN-aN-aN" on create.** I saw this once (POST booking 14, read back with GET). A separate request would confirm it. The same value from F1 is confirmed.
- **Corrupted dates and the checkout filter.** Booking 12 (checkout "0NaN-aN-aN" from a PATCH) matched `checkout=2000-01-01`, but booking 14 (the same string from POST) did not, and 14 was also missing from `checkout=2026-11-02`. The two paths may store the invalid date differently. Reading both bookings as XML, or filtering by other dates, could confirm this.
- **The name filter is case-sensitive.** `firstname=renamed&lastname=assign` returned `[]`, and the capitalised names returned `[17]`. The docs example uses lowercase (`firstname=sally&lastname=brown`), which suggests case-insensitive matching was intended. Seen once.
- **An empty `firstname` is accepted via PATCH** (`"firstname":""`, 200). Seen once, and not tried on POST or PUT.
- **DELETE returns `201 Created`, and /ping returns 201.** This matches the docs, but the convention is 200 or 204. Seen once for DELETE.
- **Tokens never seemed to expire.** The token from the start of the session worked throughout (~3 minutes). I didn't test expiry or reuse after logout.
- **Unknown fields (`isAdmin`, `foo`) are ignored on POST and PUT.** That looks fine. I didn't check whether they're stored internally.

## Coverage
- C1 (update integrity): PATCH with a single nested date (both fields), a top-level PATCH, PUT with a partial body (400), PUT/PATCH with `bookingid`, and PUT with an unknown field. This found F1 and F2.
- C2 (validation): missing fields, wrong types, decimals, negatives, reversed and impossible dates, malformed JSON, XML and urlencoded bodies, and XML-special characters (escaping is correct). This found F3–F7, F10 and F11. Not covered: very long strings, null values, arrays or objects in scalar fields, XML with missing or extra elements.
- C3 (auth): no auth, a wrong cookie, an empty cookie, wrong Basic credentials (all 403, correct), and /auth with wrong or empty credentials (F13). Not covered: a token used with a different Authorization scheme, case variations of the username, token expiry.
- C4 (filters): checkin and checkout boundaries, name case. This found F8 and F9. Not covered: combined name and date filters, badly formatted dates in the query.
- C5 (delete and protocol): delete, read back, delete again, update a deleted id, a non-numeric id (404), id reuse after delete (no reuse, correct), Accept variants (F10, F12, F14).
- Not reached: concurrency or double-submit on POST, very large payloads, DELETE with Basic auth, HEAD and OPTIONS methods.
- Budget: 73 of 80 HTTP requests used.
