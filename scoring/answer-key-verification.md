# Answer-key verification

Output of `python3 -I scripts/verify-answer-key.py --markdown` against a fresh target (TZ=UTC).

| Item | Reproduced | Observed |
| --- | --- | --- |
| K01 | yes | GET /ping -> 201 |
| K02 | yes | POST /booking -> 200 |
| K03 | yes | POST without lastname -> 500 |
| K04 | yes | POST firstname=123 -> 500 |
| K05 | yes | DELETE existing -> 201 |
| K06 | yes | DELETE/PUT/PATCH unknown id -> [405, 405, 405] |
| K07 | yes | bad credentials -> 200 {"reason":"Bad credentials"} |
| K08 | yes | 111.99 -> 111; 1e21 -> 1 |
| K09 | yes | totalprice 'abc' -> 200, None |
| K10 | yes | blank names -> 200, '' |
| K11 | yes | totalprice -500 -> 200 |
| K12 | yes | checkin 'not-a-date' -> 200, 0NaN-aN-aN |
| K13 | yes | checkout before checkin -> 200 |
| K14 | yes | urlencoded depositpaid=false -> True; JSON "false" -> True |
| K15 | yes | same-day checkin included: False; day before: True |
| K16 | yes | ?checkout=2030-02-01 -> [23] (01-20 checkout is 23, 02-20 checkout is 24) |
| K17 | yes | ?checkin=garbage -> 500 |
| K18 | yes | lowercase -> []; exact -> [25] |
| K19 | yes | compound Accept -> 418 |
| K20 | yes | POST -> 418, created=True; PATCH -> 500, applied=True |
| K21 | yes | PATCH bad values -> 200, '', None |
| K22 | yes | PATCH checkin only -> checkout 0NaN-aN-aN |
| K23 | yes | GET after -> 200 Cannot read properties of null (reading 'checkin') |
| K24 | yes | PATCH bookingid -> 405; id 31 present: False; id 32 count: 2 |
| K25 | yes | text/xml;charset -> 500; text/plain -> 500 |
| K26 | yes | /booking/1abc returns booking 1 |
| K27 | yes | lowercase 'basic' -> 403 |
| K28 | yes | api.md heading: DeleteBooking: DELETE /booking/1 |
| K29 | yes | PATCH section examples use curl -X PUT |
| K30 | yes | after PUT without additionalneeds -> 'Breakfast' |
| K31 | yes | Accept urlencoded -> 200 formurlencoded is not a function |
| K32 | yes | Accept xml -> Content-Type text/html; charset=utf-8 |
| K33 | yes | 2026-02-30 -> 2026-03-02 |
| K34 | yes | ?checkin=2099-01-01 -> [36] |
| K35 | yes | documented required: True; POST without it -> 200 |
| K36 | yes | Authorization row contains 'YWRtaW46cGFzc3dvcmQxMjM=]' |
| K37 | yes | id typed String and Number |
| K38 | yes | Content-Type rows omit urlencoded; examples use it |
| K39 | yes | 2024-12-31T22:00-03:00 / 2025-01-05T08:00+10:00 -> 200, 2025-01-01 / 2025-01-04 |

39 of 39 reproduced.
