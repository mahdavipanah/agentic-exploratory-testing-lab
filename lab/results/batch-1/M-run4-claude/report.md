# Prediction report

## Findings
### F1: POST /auth with wrong credentials returns 200 instead of 401
- Expected wrong behaviour: `{"username":"admin","password":"wrong"}` gets HTTP 200 with body `{"reason":"Bad credentials"}`, not a 401/403.
- Why: from prior knowledge. This is Restful-Booker, and it is known to do this.
- Confidence: high

### F2: POST /auth with a missing or empty body returns 200 "Bad credentials" instead of 400
- Expected wrong behaviour: `{}`, a missing password, or a non-JSON body gets 200 `{"reason":"Bad credentials"}`. There is no validation error.
- Why: from prior knowledge (Restful-Booker)
- Confidence: high

### F3: DELETE /booking/:id returns 201 Created on success
- Expected wrong behaviour: a successful delete returns `201 Created`. It should be 200 or 204. The docs even say "Success 200" and then show 201.
- Why: from the docs (they contradict themselves) and from prior knowledge
- Confidence: high

### F4: GET /ping returns 201 Created instead of 200
- Expected wrong behaviour: the health check returns 201 with body "Created".
- Why: from the docs and from prior knowledge
- Confidence: high

### F5: DELETE of a booking that does not exist returns 405 Method Not Allowed instead of 404
- Expected wrong behaviour: `DELETE /booking/999999` with valid auth returns 405 "Method Not Allowed".
- Why: from prior knowledge (Restful-Booker)
- Confidence: high

### F6: PUT/PATCH of a booking that does not exist returns 405 instead of 404
- Expected wrong behaviour: `PUT /booking/999999` or `PATCH /booking/999999` with valid auth and a valid body returns 405.
- Why: from prior knowledge
- Confidence: medium

### F7: Missing or invalid auth on PUT/PATCH/DELETE returns 403 instead of 401
- Expected wrong behaviour: no Cookie or Authorization header, or `Cookie: token=bogus`, returns 403 Forbidden. It should be 401 Unauthorized.
- Why: from prior knowledge
- Confidence: high

### F8: POST /booking with required fields missing returns 500 Internal Server Error instead of 400
- Expected wrong behaviour: leaving out `firstname`, `bookingdates`, etc. (or sending `{}`) gives a 500.
- Why: from prior knowledge (Restful-Booker validation throws a server error)
- Confidence: high

### F9: PUT /booking/:id with an incomplete body returns 400, or 500, with no useful error message
- Expected wrong behaviour: a missing required field gives a bare "Bad Request" with no detail, or a 500.
- Why: from prior knowledge
- Confidence: medium

### F10: POST /booking accepts wrong types for totalprice or depositpaid and silently coerces them
- Expected wrong behaviour: `"totalprice":"abc"` is stored as null or NaN. `"depositpaid":"no"` or `"depositpaid":"abc"` is stored as true. The response is still 200.
- Why: from prior knowledge (the Mongoose/JS-style coercion in Restful-Booker)
- Confidence: high

### F11: POST /booking accepts a negative or zero totalprice
- Expected wrong behaviour: `"totalprice": -100` is accepted with 200.
- Why: from prior knowledge or a general guess. There is no range validation.
- Confidence: high

### F12: POST /booking accepts a checkout date before the checkin date
- Expected wrong behaviour: `checkin 2020-01-10` and `checkout 2020-01-01` are accepted with 200.
- Why: from prior knowledge. There is no cross-field validation.
- Confidence: high

### F13: Invalid dates are accepted and stored as garbage, such as "0NaN-aN-aN" or "1970-01-01"
- Expected wrong behaviour: `"checkin":"notadate"` or `"2020-13-45"` returns 200 and echoes `"0NaN-aN-aN"`, or a rolled-over or epoch date.
- Why: from prior knowledge (Restful-Booker date formatting)
- Confidence: high

### F14: Unsupported Accept header returns 418 I'm a teapot
- Expected wrong behaviour: `Accept: text/plain` (or another unsupported type) on POST /booking or GET /booking/:id returns 418 instead of 406.
- Why: from prior knowledge (Restful-Booker returns 418)
- Confidence: high

### F15: An unsupported or missing Content-Type on POST/PUT gives a 500 or 400 with no message, not 415
- Expected wrong behaviour: `Content-Type: text/plain` with a JSON body gives a 500 Internal Server Error (or 400). It should be 415.
- Why: from prior knowledge
- Confidence: medium

### F16: Malformed JSON body returns 400 with an HTML stack trace, or a 500
- Expected wrong behaviour: a truncated JSON body produces an Express default error page that leaks the stack trace or paths.
- Why: from prior knowledge (Express body-parser default handler)
- Confidence: medium

### F17: GET /booking/:id for an ID that does not exist or is not numeric returns a plain-text "Not Found" and no JSON error
- Expected wrong behaviour: `GET /booking/abc` returns 404 "Not Found" as text/plain whatever the Accept header says. A non-numeric ID might give 500 instead.
- Why: from prior knowledge
- Confidence: medium

### F18: GET /booking name filter is case-sensitive, so the docs' own example returns nothing
- Expected wrong behaviour: `?firstname=sally&lastname=brown` (lowercase, as in the docs) does not match the booking "Sally Brown" and returns `[]`.
- Why: from the docs (the example uses lowercase while the data uses capitals)
- Confidence: medium

### F19: GET /booking checkin/checkout filters do not follow the documented ">= " rule
- Expected wrong behaviour: the checkin filter uses a strict ">" and leaves out bookings whose checkin equals the given date. The checkout filter may be reversed (<=) or ignored.
- Why: from prior knowledge (Restful-Booker's date filters are known to be off-by-one and exclusive)
- Confidence: medium

### F20: GET /booking with an invalid date filter returns 500 or silently ignores the filter
- Expected wrong behaviour: `?checkin=notadate` gives a 500, or returns every ID with 200 instead of a 400.
- Why: from prior knowledge or a general guess
- Confidence: medium

### F21: PATCH /booking/:id accepts invalid types and corrupts the stored booking
- Expected wrong behaviour: `{"totalprice":"abc"}` or `{"bookingdates":{"checkin":"bad"}}` is accepted with 200 and writes null or NaN values into the booking.
- Why: from prior knowledge. PATCH does no validation.
- Confidence: medium

### F22: PATCH or PUT with unknown extra fields is accepted silently, or stores them
- Expected wrong behaviour: unknown fields are ignored and the response is still 200, or they persist and show up in GET.
- Why: general guess
- Confidence: low

### F23: Strings are not length-limited and not sanitised (stored XSS, oversized payloads)
- Expected wrong behaviour: `firstname: "<script>alert(1)</script>"` or a 10k-character name is stored and echoed back unescaped with 200.
- Why: from prior knowledge or a general guess
- Confidence: medium

### F24: additionalneeds is documented as required but can be left out without error
- Expected wrong behaviour: a POST without `additionalneeds` returns 200, and the response does not include the field. This contradicts the docs, which mark it required in both request and response.
- Why: from the docs plus prior knowledge
- Confidence: medium

### F25: Auth tokens never expire and are not invalidated
- Expected wrong behaviour: a token from POST /auth stays valid forever. Every call issues a new valid token, and there is no logout or revocation.
- Why: from prior knowledge
- Confidence: low

### F26: Hardcoded default credentials admin/password123 are accepted
- Expected wrong behaviour: the documented Basic auth credentials (`YWRtaW46cGFzc3dvcmQxMjM=` = admin:password123) give full write and delete access.
- Why: from the docs
- Confidence: high

### F27: POST /booking returns 200 instead of 201 Created
- Expected wrong behaviour: creating a resource returns 200 OK, while DELETE returns 201. The status codes are mixed up.
- Why: from the docs and from prior knowledge
- Confidence: high

### F28: A deleted booking stays reachable, or the delete is not idempotent
- Expected wrong behaviour: a second DELETE of the same ID returns 405 instead of 404. GET after delete returns 404 as text.
- Why: from prior knowledge
- Confidence: medium

### F29: XML and urlencoded input is parsed inconsistently (types are lost)
- Expected wrong behaviour: with XML or form input, totalprice and depositpaid come back as strings ("111", "true") in JSON responses. A form request with `Accept: application/x-www-form-urlencoded` may give a 418 or a malformed response.
- Why: from the docs (several formats) plus prior knowledge
- Confidence: low

### F30: GET /booking/:id with no Accept header, or `*/*`, returns 418 or the wrong format
- Expected wrong behaviour: a plain `curl` with no explicit Accept fails, or returns a format other than JSON, even though the docs list Accept as required.
- Why: from the docs plus prior knowledge
- Confidence: low

### F31: A float or very large totalprice is truncated or rounded
- Expected wrong behaviour: `totalprice: 111.99` is stored as 111. A very large number loses precision.
- Why: from prior knowledge (Restful-Booker stores totalprice as an integer)
- Confidence: medium

## Questions

## Coverage
I based these predictions on every endpoint in the docs: POST /auth, GET /booking/:id, POST /booking, PUT /booking/:id, PATCH /booking/:id, DELETE /booking/:id, GET /booking (the name and date filters) and GET /ping. That includes the header tables (Accept, Content-Type, Cookie, Authorization), the request and response field tables, and the status codes in the examples. I recognised the API as Restful-Booker and used what I know about its known bugs.
