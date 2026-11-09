"""Replay every answer-key item against a fresh target and check that the problem is still there.

Use it to see the bugs for yourself, or to confirm the answer key still matches the pinned target.

Usage: python3 -I scripts/verify-answer-key.py [port]      (default 3019)
       python3 -I scripts/verify-answer-key.py 3019 --markdown > scoring/answer-key-verification.md

Exit code 0 when every item reproduces, 1 otherwise. Needs only the Python standard library.
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 3019
MARKDOWN = "--markdown" in sys.argv
BASE = f"http://localhost:{PORT}"
AUTH = {"Authorization": "Basic YWRtaW46cGFzc3dvcmQxMjM="}
API_MD = open(os.path.join(ROOT, "target", "api.md")).read()


class NoProxy(urllib.request.ProxyHandler):
    def __init__(self):
        super().__init__({})


OPENER = urllib.request.build_opener(NoProxy)


def req(method, path, body=None, headers=None, form=False, raw=None):
    headers = dict(headers or {})
    data = None
    if raw is not None:
        data = raw.encode()
    elif body is not None and form:
        data = urllib.parse.urlencode(body).encode()
        headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
    elif body is not None:
        data = json.dumps(body).encode()
        headers.setdefault("Content-Type", "application/json")
    headers.setdefault("Accept", "application/json")
    r = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with OPENER.open(r) as resp:
            return resp.status, dict(resp.headers), resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode()


def js(text):
    try:
        return json.loads(text)
    except ValueError:
        return None


def booking(**over):
    b = {"firstname": "Kim", "lastname": "Lee", "totalprice": 111, "depositpaid": True,
         "bookingdates": {"checkin": "2018-01-01", "checkout": "2019-01-01"}, "additionalneeds": "Breakfast"}
    b.update(over)
    return b


def create(**over):
    s, _, t = req("POST", "/booking", booking(**over))
    return s, js(t) or {}


def ids(query=""):
    return [x["bookingid"] for x in js(req("GET", "/booking" + query)[2]) or []]


def get(i):
    return js(req("GET", f"/booking/{i}")[2]) or {}


# Each check returns (reproduced: bool, observed: str).
def k01():
    s, _, _ = req("GET", "/ping")
    return s == 201, f"GET /ping -> {s}"

def k02():
    s, _ = create()
    return s == 200, f"POST /booking -> {s}"

def k03():
    b = booking(); del b["lastname"]
    s, _, _ = req("POST", "/booking", b)
    return s == 500, f"POST without lastname -> {s}"

def k04():
    s, _ = create(firstname=123)
    return s == 500, f"POST firstname=123 -> {s}"

def k05():
    _, b = create()
    s, _, _ = req("DELETE", f"/booking/{b['bookingid']}", headers=AUTH)
    return s == 201, f"DELETE existing -> {s}"

def k06():
    codes = [req(m, "/booking/999999", booking() if m != "DELETE" else None, AUTH)[0] for m in ("DELETE", "PUT", "PATCH")]
    return codes == [405, 405, 405], f"DELETE/PUT/PATCH unknown id -> {codes}"

def k07():
    s, _, t = req("POST", "/auth", {"username": "admin", "password": "wrong"})
    return s == 200 and "Bad credentials" in t, f"bad credentials -> {s} {t}"

def k08():
    a = create(totalprice=111.99)[1]["booking"]["totalprice"]
    b = create(totalprice=1e21)[1]["booking"]["totalprice"]
    return a == 111 and b == 1, f"111.99 -> {a}; 1e21 -> {b}"

def k09():
    s, b = create(totalprice="abc")
    return s == 200 and b["booking"]["totalprice"] is None, f"totalprice 'abc' -> {s}, {b['booking']['totalprice']}"

def k10():
    s, b = create(firstname="   ", lastname="")
    return s == 200 and b["booking"]["firstname"] == "", f"blank names -> {s}, {b['booking']['firstname']!r}"

def k11():
    s, b = create(totalprice=-500)
    return s == 200 and b["booking"]["totalprice"] == -500, f"totalprice -500 -> {s}"

def k12():
    s, b = create(bookingdates={"checkin": "not-a-date", "checkout": "2019-01-01"})
    c = b["booking"]["bookingdates"]["checkin"]
    return s == 200 and "NaN" in c, f"checkin 'not-a-date' -> {s}, {c}"

def k13():
    s, b = create(bookingdates={"checkin": "2019-01-01", "checkout": "2018-01-01"})
    return s == 200, f"checkout before checkin -> {s}"

def k14():
    body = {"firstname": "Url", "lastname": "Enc", "totalprice": 10, "depositpaid": "false",
            "bookingdates[checkin]": "2018-01-01", "bookingdates[checkout]": "2018-01-02"}
    s, _, t = req("POST", "/booking", body, form=True)
    dp = (js(t) or {}).get("booking", {}).get("depositpaid")
    return s == 200 and dp is True, f"urlencoded depositpaid=false -> {dp}"

def k15():
    _, b = create(lastname="KeyCheckin", bookingdates={"checkin": "2030-01-10", "checkout": "2030-01-20"})
    i = b["bookingid"]
    on = i in ids("?checkin=2030-01-10&lastname=KeyCheckin")
    before = i in ids("?checkin=2030-01-09&lastname=KeyCheckin")
    return (not on) and before, f"same-day checkin included: {on}; day before: {before}"

def k16():
    a = create(lastname="KeyCheckout", bookingdates={"checkin": "2030-01-10", "checkout": "2030-01-20"})[1]["bookingid"]
    b = create(lastname="KeyCheckout", bookingdates={"checkin": "2030-02-10", "checkout": "2030-02-20"})[1]["bookingid"]
    got = ids("?checkout=2030-02-01&lastname=KeyCheckout")
    return got == [a], f"?checkout=2030-02-01 -> {got} (01-20 checkout is {a}, 02-20 checkout is {b})"

def k17():
    s, _, _ = req("GET", "/booking?checkin=garbage")
    return s == 500, f"?checkin=garbage -> {s}"

def k18():
    i = create(firstname="Casey", lastname="Sens")[1]["bookingid"]
    lower, exact = ids("?firstname=casey&lastname=sens"), ids("?firstname=Casey&lastname=Sens")
    return i not in lower and i in exact, f"lowercase -> {lower}; exact -> {exact}"

def k19():
    s, _, _ = req("GET", "/booking/1", headers={"Accept": "application/json, text/plain, */*"})
    return s == 418, f"compound Accept -> {s}"

def k20():
    s1, _, _ = req("POST", "/booking", booking(firstname="GhostWrite"), {"Accept": "text/html"})
    created = bool(ids("?firstname=GhostWrite"))
    i = create()[1]["bookingid"]
    s2, _, _ = req("PATCH", f"/booking/{i}", {"firstname": "PatchedAnyway"}, {**AUTH, "Accept": "text/html"})
    applied = get(i).get("firstname") == "PatchedAnyway"
    return s1 == 418 and created and s2 == 500 and applied, f"POST -> {s1}, created={created}; PATCH -> {s2}, applied={applied}"

def k21():
    i = create()[1]["bookingid"]
    s, _, t = req("PATCH", f"/booking/{i}", {"firstname": "", "totalprice": "lots"}, AUTH)
    b = js(t) or {}
    return s == 200 and b.get("firstname") == "" and b.get("totalprice") is None, f"PATCH bad values -> {s}, {b.get('firstname')!r}, {b.get('totalprice')}"

def k22():
    i = create()[1]["bookingid"]
    _, _, t = req("PATCH", f"/booking/{i}", {"bookingdates": {"checkin": "2031-01-01"}}, AUTH)
    co = (js(t) or {}).get("bookingdates", {}).get("checkout", "")
    return "NaN" in co, f"PATCH checkin only -> checkout {co}"

def k23():
    i = create()[1]["bookingid"]
    req("PATCH", f"/booking/{i}", {"bookingdates": None}, AUTH)
    s, _, t = req("GET", f"/booking/{i}")
    return s == 200 and "Cannot read properties of null" in t, f"GET after -> {s} {t[:60]}"

def k24():
    n = create()[1]["bookingid"]
    m = create()[1]["bookingid"]
    s, _, _ = req("PATCH", f"/booking/{n}", {"bookingid": m}, AUTH)
    all_ids = ids()
    return s == 405 and n not in all_ids and all_ids.count(m) == 2, f"PATCH bookingid -> {s}; id {n} present: {n in all_ids}; id {m} count: {all_ids.count(m)}"

def k25():
    xml = ("<booking><firstname>X</firstname><lastname>M</lastname><totalprice>10</totalprice><depositpaid>true</depositpaid>"
           "<bookingdates><checkin>2018-01-01</checkin><checkout>2018-01-02</checkout></bookingdates></booking>")
    s1, _, _ = req("POST", "/booking", raw=xml, headers={"Content-Type": "text/xml; charset=utf-8"})
    s2, _, _ = req("POST", "/booking", raw=json.dumps(booking()), headers={"Content-Type": "text/plain"})
    return s1 == 500 and s2 == 500, f"text/xml;charset -> {s1}; text/plain -> {s2}"

def k26():
    a, b = req("GET", "/booking/1abc")[2], req("GET", "/booking/1")[2]
    return a == b and js(a) is not None, "/booking/1abc returns booking 1" if a == b else "differs"

def k27():
    i = create()[1]["bookingid"]
    s, _, _ = req("DELETE", f"/booking/{i}", headers={"Authorization": "basic YWRtaW46cGFzc3dvcmQxMjM="})
    return s == 403, f"lowercase 'basic' -> {s}"

def k28():
    return "DELETE /booking/1" in API_MD, "api.md heading: DeleteBooking: DELETE /booking/1"

def k29():
    patch = API_MD.split("PartialUpdateBooking", 1)[1].split("## ", 1)[0]
    return "-X PUT" in patch, "PATCH section examples use curl -X PUT"

def k30():
    i = create()[1]["bookingid"]
    b = booking(firstname="Replaced"); del b["additionalneeds"]
    req("PUT", f"/booking/{i}", b, AUTH)
    kept = get(i).get("additionalneeds")
    return kept == "Breakfast", f"after PUT without additionalneeds -> {kept!r}"

def k31():
    s, _, t = req("GET", "/booking/1", headers={"Accept": "application/x-www-form-urlencoded"})
    return s == 200 and "formurlencoded is not a function" in t, f"Accept urlencoded -> {s} {t[:40]}"

def k32():
    _, h, _ = req("GET", "/booking/1", headers={"Accept": "application/xml"})
    ct = {k.lower(): v for k, v in h.items()}.get("content-type", "")
    return ct.startswith("text/html"), f"Accept xml -> Content-Type {ct}"

def k33():
    c = create(bookingdates={"checkin": "2026-02-30", "checkout": "2026-03-05"})[1]["booking"]["bookingdates"]["checkin"]
    return c == "2026-03-02", f"2026-02-30 -> {c}"

def k34():
    i = create(lastname="KeyNaN", bookingdates={"checkin": "not-a-date", "checkout": "2019-01-01"})[1]["bookingid"]
    got = ids("?checkin=2099-01-01&lastname=KeyNaN")
    return i in got, f"?checkin=2099-01-01 -> {got}"

def k35():
    b = booking(); del b["additionalneeds"]
    s, _, _ = req("POST", "/booking", b)
    documented = "| additionalneeds | String | no |" in API_MD
    return s == 200 and documented, f"documented required: {documented}; POST without it -> {s}"

def k36():
    return "YWRtaW46cGFzc3dvcmQxMjM=]" in API_MD, "Authorization row contains 'YWRtaW46cGFzc3dvcmQxMjM=]'"

def k37():
    return "| id | String |" in API_MD and "| id | Number |" in API_MD, "id typed String and Number"

def k38():
    return "Can be application/json or text/xml" in API_MD and "application/x-www-form-urlencoded" in API_MD, "Content-Type rows omit urlencoded; examples use it"


CHECKS = [(f"K{i:02d}", globals()[f"k{i:02d}"]) for i in range(1, 39)]


def main():
    start = os.path.join(ROOT, "scripts", "start-target.sh")
    subprocess.run([start, str(PORT)], check=True, stdout=subprocess.DEVNULL)
    failed = 0
    try:
        rows = []
        for key, check in CHECKS:
            try:
                ok, observed = check()
            except Exception as e:  # a check that crashes counts as not reproduced
                ok, observed = False, f"check error: {e!r}"
            failed += not ok
            rows.append((key, "yes" if ok else "NO", observed.replace("|", "\\|")))
        if MARKDOWN:
            print("# Answer-key verification\n")
            print("Output of `python3 -I scripts/verify-answer-key.py --markdown` against a fresh target (TZ=UTC).\n")
            print("| Item | Reproduced | Observed |\n| --- | --- | --- |")
            for r in rows:
                print(f"| {r[0]} | {r[1]} | {r[2]} |")
            print(f"\n{len(rows) - failed} of {len(rows)} reproduced.")
        else:
            for r in rows:
                print(f"{r[0]}  {r[1]:<3}  {r[2]}")
            print(f"\n{len(rows) - failed} of {len(rows)} items reproduced.")
    finally:
        subprocess.run([start, "stop", str(PORT)], stdout=subprocess.DEVNULL)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
