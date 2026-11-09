# Prediction report

## Findings
### F1: POST /auth with wrong credentials returns 200 instead of 401
- Expected wrong behaviour: `{"username":"admin","password":"wrong"}` returns HTTP 200 with body `{"reason":"Bad credentials"}`, not a 401.
- Why: from prior knowledge. This API looks like Restful-Booker, which does this.
- Confidence: high

### F2: POST /auth with missing or empty body returns 200 "Bad credentials" instead of 400
- Expected wrong behaviour: `{}`, a missing username/password, or no Content-Type gives 200 `{"reason":"Bad credentials"}` rather than a validation error.
- Why: from prior knowledge (Restful-Booker).
- Confidence: high

### F3: DELETE /booking/:id returns 201 Created on success
- Expected wrong behaviour: a successful delete returns `201 Created` with body "Created", not 200 or 204. The docs even contradict themselves ("Success 200" vs "HTTP/1.1 201 Created").
- Why: from the docs and prior knowledge.
- Confidence: high

### F4: GET /ping returns 201 Created
- Expected wrong behaviour: the health check returns 201 instead of 200.
- Why: from the docs (the example shows 201 under a "Success 200" heading) and prior knowledge.
- Confidence: high

### F5: Missing or invalid auth on PUT/PATCH/DELETE returns 403 instead of 401
- Expected wrong behaviour: a request with no Cookie and no Authorization header, or with a bad token or bad Basic credentials, returns 403 Forbidden rather than 401 Unauthorized.
- Why: from prior knowledge (Restful-Booker).
- Confidence: high

### F6: PUT /booking/:id on a non-existent id returns 405 Method Not Allowed
- Expected wrong behaviour: PUT /booking/999999 with valid auth returns 405 instead of 404.
- Why: from prior knowledge.
- Confidence: high

### F7: PATCH /booking/:id on a non-existent id returns 405
- Expected wrong behaviour: PATCH /booking/999999 with valid auth returns 405 instead of 404.
- Why: from prior knowledge.
- Confidence: high

### F8: DELETE /booking/:id on a non-existent or already deleted id returns 405
- Expected wrong behaviour: deleting the same id twice, or deleting an unknown id, returns 405 instead of 404.
- Why: from prior knowledge.
- Confidence: high

### F9: POST /booking with missing required fields returns 500
- Expected wrong behaviour: leaving out firstname, totalprice, bookingdates, etc. gives 500 Internal Server Error instead of 400.
- Why: from prior knowledge (Restful-Booker's validation fails with 500).
- Confidence: high

### F10: POST /booking accepts wrong field types
- Expected wrong behaviour: `"totalprice":"abc"`, `"depositpaid":"yes"` or numeric names are accepted (200) and stored or coerced (for example, totalprice ends up null or NaN, depositpaid is coerced). Alternatively it gives 500. It should be 400.
- Why: from prior knowledge.
- Confidence: medium

### F11: Invalid dates are accepted and stored as garbage
- Expected wrong behaviour: POST /booking with `checkin:"2018-13-45"` or `"notadate"` returns 200, and the stored date is shown as `"0NaN-aN-aN"` or `"Invalid Date"`.
- Why: from prior knowledge.
- Confidence: high

### F12: Checkout before checkin is accepted
- Expected wrong behaviour: POST, PUT or PATCH with checkout < checkin succeeds with 200.
- Why: from prior knowledge, and there is no rule for it in the docs.
- Confidence: high

### F13: Negative, zero or huge totalprice is accepted
- Expected wrong behaviour: `totalprice:-100` is accepted with 200.
- Why: from prior knowledge.
- Confidence: high

### F14: Decimal totalprice is truncated or rounded
- Expected wrong behaviour: `totalprice:111.99` is stored and returned as 111 (or 112).
- Why: from prior knowledge (the price is coerced to an integer).
- Confidence: medium

### F15: Empty strings are accepted for firstname/lastname
- Expected wrong behaviour: `firstname:""` is accepted (200) even though the field is required.
- Why: from prior knowledge.
- Confidence: medium

### F16: Stored XSS / no sanitisation of string fields
- Expected wrong behaviour: `firstname:"<script>alert(1)</script>"` is stored and returned as-is.
- Why: from prior knowledge.
- Confidence: medium

### F17: GET /booking?checkin= filter uses strict "greater than"
- Expected wrong behaviour: a booking whose checkin equals the filter date is left out, although the docs say >=.
- Why: from the docs and prior knowledge (Restful-Booker uses $gt).
- Confidence: high

### F18: GET /booking?checkout= filter uses the wrong direction or a strict comparison
- Expected wrong behaviour: the checkout filter returns bookings with checkout < the date, or leaves out equal dates, instead of checkout >= the date.
- Why: from the docs and prior knowledge.
- Confidence: medium

### F19: Name filters are case-sensitive
- Expected wrong behaviour: the docs example `?firstname=sally&lastname=brown` returns an empty list when the stored name is "Sally Brown".
- Why: from the docs (lowercase example compared with capitalised data).
- Confidence: medium

### F20: Invalid date format in query filter is not rejected
- Expected wrong behaviour: `GET /booking?checkin=notadate` returns 200 (all results, none, or 500) rather than 400.
- Why: from prior knowledge.
- Confidence: medium

### F21: Unsupported Accept header returns 418 I'm a teapot
- Expected wrong behaviour: GET/POST/PUT with `Accept: text/plain` (or similar) returns 418 instead of 406.
- Why: from prior knowledge (Restful-Booker).
- Confidence: high

### F22: Unsupported Content-Type or malformed body returns 500 or 400 with an HTML error page
- Expected wrong behaviour: POST /booking with malformed JSON or `Content-Type: text/plain` gives 500 or an HTML stack trace, not a clean 400 or 415.
- Why: from prior knowledge (Express defaults).
- Confidence: medium

### F23: PATCH with a partial bookingdates drops the other date
- Expected wrong behaviour: PATCH with only `{"bookingdates":{"checkin":"2020-01-01"}}` replaces the whole bookingdates object, so checkout is lost or becomes null or invalid.
- Why: from prior knowledge (a shallow merge).
- Confidence: medium

### F24: PATCH does not validate types
- Expected wrong behaviour: `{"totalprice":"abc"}` or `{"depositpaid":"maybe"}` is accepted and stored.
- Why: from prior knowledge.
- Confidence: medium

### F25: PUT with an incomplete body returns 400 or 500 without a useful message, or partially updates
- Expected wrong behaviour: PUT without required fields gives 400 "Bad Request" with no details, or 500.
- Why: from prior knowledge.
- Confidence: medium

### F26: GET /booking/:id with a non-numeric id returns 404 or 500 rather than 400
- Expected wrong behaviour: `GET /booking/abc` returns 404 "Not Found" (or 500).
- Why: from the docs (id is typed String in GET but Number elsewhere).
- Confidence: low

### F27: Tokens never expire and are not invalidated
- Expected wrong behaviour: a token from /auth works indefinitely, and many tokens can be created with no limit or rate limiting.
- Why: from prior knowledge.
- Confidence: medium

### F28: Hard-coded default credentials admin/password123 work
- Expected wrong behaviour: the publicly documented credentials grant full write and delete access, including through Basic auth.
- Why: from the docs.
- Confidence: high

### F29: Unknown or extra fields are accepted silently
- Expected wrong behaviour: POST /booking with `"bookingid":5` or `"foo":"bar"` is accepted, and extra fields may be stored or echoed back.
- Why: from prior knowledge.
- Confidence: low

### F30: Duplicate bookings are allowed
- Expected wrong behaviour: posting the same payload twice creates two bookings.
- Why: from prior knowledge.
- Confidence: low

### F31: The docs' URL-encoded request examples are not supported, or the response format is wrong
- Expected wrong behaviour: the docs say Content-Type "Can be application/json or text/xml" but show form-urlencoded examples. Sending `Accept: application/x-www-form-urlencoded` may return 418, or form bodies may be parsed wrongly (depositpaid "true" stored as a string, totalprice as a string).
- Why: from the docs (inconsistency) and prior knowledge.
- Confidence: medium

### F32: XML input parsing coerces types wrongly
- Expected wrong behaviour: POST with text/xml stores totalprice and depositpaid as strings ("111", "true"), or the XML response root element is inconsistent.
- Why: from prior knowledge.
- Confidence: low

### F33: Missing Accept header causes an error or the wrong format
- Expected wrong behaviour: the docs mark Accept as required; leaving it out may return 418 or default oddly, and `Accept: */*` may not be handled.
- Why: from the docs.
- Confidence: low

### F34: PATCH and PUT accept a Cookie token with extra whitespace or tokens from any user / any token value
- Expected wrong behaviour: auth checks may be weak (for example, any non-empty Basic header passes, or the Basic header is checked case-sensitively).
- Why: from prior knowledge (generic).
- Confidence: low

## Questions

## Coverage
All endpoints in api.md: POST /auth, GET /booking/:id, POST /booking, PUT /booking/:id, PATCH /booking/:id, DELETE /booking/:id, GET /booking (filters), and GET /ping. I also used the header tables (Accept, Content-Type, Cookie, Authorization), the request and response field tables, and the status code examples. The API is recognisable as Restful-Booker, so prior knowledge of its known defects was applied.
