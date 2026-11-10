#!/usr/bin/env python3
"""Replay the sealed Claimdesk answer key against a freshly started server.

Usage: python3 -I verify-key.py [port]      (default 3101)

Starts nothing: start the target first (targets/claimdesk/start.sh <port>) and
restart it before every run, because the checks change server state.
Prints one line per T item, then "N of N reproduced", then the happy-path checks.
"""
import datetime
import json
import sys
import urllib.error
import urllib.request

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 3101
BASE = f"http://localhost:{PORT}"
PASSWORDS = {u: f"{u}-pass" for u in ("alice", "bob", "erin", "carol", "frank", "dave")}
TODAY = datetime.datetime.now(datetime.timezone.utc).date()


def days_ago(n):
    return (TODAY - datetime.timedelta(days=n)).isoformat()


def call(method, path, token=None, body=None, raw=None):
    headers = {}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    elif raw is not None:
        data = raw.encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status, hdrs, text = resp.status, resp.headers, resp.read().decode()
    except urllib.error.HTTPError as err:
        status, hdrs, text = err.code, err.headers, err.read().decode()
    try:
        payload = json.loads(text) if text else None
    except ValueError:
        payload = text
    return status, payload, hdrs


def login(username):
    status, body, _ = call("POST", "/auth/login", body={"username": username, "password": PASSWORDS[username]})
    assert status == 200, (username, status, body)
    return body["token"]


def item(date=None, category="other", description="Item", amount=10):
    return {"date": date or days_ago(3), "category": category, "description": description, "amount": amount}


def new_claim(token, title, items=None, currency="EUR"):
    body = {"title": title, "currency": currency}
    if items is not None:
        body["items"] = items
    status, claim, _ = call("POST", "/claims", token, body)
    assert status == 201, (title, status, claim)
    return claim


T = {}


def check(fn):
    T[fn.__name__.upper()] = fn
    return fn


# --- T items ----------------------------------------------------------------

@check
def t01(tok):
    claim = new_claim(tok["alice"], "T01 zero amount")
    status, body, _ = call("POST", f"/claims/{claim['id']}/items", tok["alice"], item(amount=0, description="Nothing"))
    return status == 201 and body["amount"] == 0, f"amount 0 -> {status} {body}"


@check
def t02(tok):
    _, first, _ = call("GET", "/claims?per_page=1", tok["alice"])
    n = first["meta"]["total_count"]
    _, last, _ = call("GET", f"/claims?per_page=1&page={n}", tok["alice"])
    _, beyond, _ = call("GET", f"/claims?per_page=1&page={n + 1}", tok["alice"])
    ok = last["meta"]["next_page"] == n + 1 and beyond["data"] == []
    note = ""
    if n == 4:
        _, p2, _ = call("GET", "/claims?per_page=2&page=2", tok["alice"])
        ok = ok and p2["meta"]["next_page"] == 3
        note = f"; per_page=2&page=2 meta {p2['meta']}"
    return ok, f"last page (page {n} of {n}) meta {last['meta']}, page {n + 1} data {beyond['data']}{note}"


@check
def t03(tok):
    _, before, _ = call("GET", "/claims/5", tok["bob"])
    status, body, _ = call("POST", "/claims/5/submit", tok["bob"])
    _, after, _ = call("GET", "/claims/5", tok["bob"])
    ok = before["status"] == "rejected" and status == 409 and after["status"] == "rejected"
    return ok, f"submit rejected claim 5 -> {status} {body}"


@check
def t04(tok):
    status, body, _ = call("GET", "/claims?owner=erin", tok["alice"])
    owners = sorted({c["owner"] for c in body["data"]})
    ids = [c["id"] for c in body["data"]]
    statuses = [c["status"] for c in body["data"]]
    ok = status == 200 and "erin" in owners and 7 in ids and "draft" in statuses
    return ok, f"alice ?owner=erin -> {status}, ids {ids}, statuses {statuses}"


@check
def t05(tok):
    seen, _, _ = call("GET", "/claims/6", tok["carol"])
    status, body, _ = call("POST", "/claims/6/review", tok["carol"], {"decision": "approve"})
    ok = seen == 404 and status == 200 and body["status"] == "approved" and body["reviewed_by"] == "carol"
    return ok, f"carol GET /claims/6 -> {seen}; carol approve claim 6 (team mobile) -> {status} status={body.get('status') if isinstance(body, dict) else body}"


@check
def t06(tok):
    claim = new_claim(tok["alice"], "T06 cents")
    status, body, _ = call("POST", f"/claims/{claim['id']}/items", tok["alice"], item(amount=19.99, description="Cable"))
    _, detail, _ = call("GET", f"/claims/{claim['id']}", tok["alice"])
    ok = status == 201 and body["amount"] == 19.98 and detail["total"] == 19.98
    return ok, f"amount 19.99 -> stored {body['amount']}, claim total {detail['total']}"


@check
def t07(tok):
    day = days_ago(4)
    status, body, _ = call("POST", "/claims", tok["alice"], {
        "title": "T07 meals", "currency": "EUR",
        "items": [item(day, "meals", "Lunch", 40), item(day, "meals", "Dinner", 35)],
    })
    ok = status == 201 and body["total"] == 75
    status2, body2, _ = call("POST", f"/claims/{body['id']}/items", tok["alice"], item(day, "meals", "Snack", 50))
    ok = ok and status2 == 201
    return ok, f"two meals 40+35 on {day} -> {status}; third meal 50 same day -> {status2}"


@check
def t08(tok):
    claim = new_claim(tok["alice"], "T08 dates")
    s90, b90, _ = call("POST", f"/claims/{claim['id']}/items", tok["alice"], item(days_ago(90), description="Day 90"))
    s89, _, _ = call("POST", f"/claims/{claim['id']}/items", tok["alice"], item(days_ago(89), description="Day 89"))
    ok = s90 == 400 and s89 == 201
    return ok, f"date {days_ago(90)} (90 days ago) -> {s90} {b90.get('message') if isinstance(b90, dict) else b90}; {days_ago(89)} -> {s89}"


@check
def t09(tok):
    claim = new_claim(tok["alice"], "T09 status", [item(amount=25, description="Taxi")])
    status, body, _ = call("PATCH", f"/claims/{claim['id']}", tok["alice"], {"status": "approved"})
    pay_status, paid, _ = call("POST", f"/claims/{claim['id']}/pay", tok["dave"])
    ok = status == 200 and body["status"] == "approved" and pay_status == 200 and paid["status"] == "paid"
    return ok, f"PATCH status=approved -> {status} status={body['status']}; dave pay -> {pay_status} {paid.get('status')}"


@check
def t10(tok):
    title = "T10 stale total"
    claim = new_claim(tok["alice"], title, [item(amount=10, description="Bus"), item(amount=20, description="Taxi")])
    drop = claim["items"][1]["id"]
    s_del, _, _ = call("DELETE", f"/claims/{claim['id']}/items/{drop}", tok["alice"])
    _, detail, _ = call("GET", f"/claims/{claim['id']}", tok["alice"])
    _, listing, _ = call("GET", "/claims?q=T10%20stale", tok["alice"])
    row = next(c for c in listing["data"] if c["id"] == claim["id"])
    call("POST", f"/claims/{claim['id']}/submit", tok["alice"])
    call("POST", f"/claims/{claim['id']}/review", tok["carol"], {"decision": "approve"})
    _, paid, _ = call("POST", f"/claims/{claim['id']}/pay", tok["dave"])
    ok = s_del == 204 and detail["total"] == 10 and row["total"] == 30 and paid["amount_paid"] == 30
    return ok, (f"after deleting the 20.00 item: detail total {detail['total']}, list total {row['total']}; "
                f"paid: total {paid['total']}, amount_paid {paid['amount_paid']}")


@check
def t11(tok):
    s1, first, _ = call("POST", "/claims/1/pay", tok["dave"], {"reference": "T11-A"})
    s2, second, _ = call("POST", "/claims/1/pay", tok["dave"], {"reference": "T11-B"})
    ok = (s1 == 200 and s2 == 200 and first["amount_paid"] == first["total"]
          and second["amount_paid"] == 2 * first["total"] and second["payment_reference"] == "T11-B")
    return ok, (f"pay #1 -> {s1} amount_paid {first['amount_paid']} ref {first['payment_reference']}; "
                f"pay #2 -> {s2} amount_paid {second['amount_paid']} ref {second['payment_reference']}")


@check
def t12(tok):
    status, body, _ = call("GET", "/claims?sort=title", tok["alice"])
    return status == 500, f"sort=title -> {status} {body}"


@check
def t13(tok):
    s_del, _, _ = call("DELETE", "/claims/4/items/5", tok["alice"])
    _, bobs, _ = call("GET", "/claims/3", tok["bob"])
    _, alices, _ = call("GET", "/claims/4", tok["alice"])
    ids = [i["id"] for i in bobs["items"]]
    ok = s_del == 204 and 5 not in ids and bobs["status"] == "submitted" and len(alices["items"]) == 1
    return ok, f"alice DELETE /claims/4/items/5 -> {s_del}; bob's claim 3 ({bobs['status']}) items now {ids}"


@check
def t14(tok):
    _, body, _ = call("GET", "/claims", tok["dave"])
    return body["meta"]["per_page"] == 10, f"default meta {body['meta']}"


@check
def t15(tok):
    _, detail, _ = call("GET", "/claims/1", tok["alice"])
    has_word = any("train" in i["description"].lower() for i in detail["items"])
    _, by_item, _ = call("GET", "/claims?q=train", tok["alice"])
    _, by_title, _ = call("GET", "/claims?q=berlin", tok["alice"])
    ok = has_word and by_item["data"] == [] and [c["id"] for c in by_title["data"]] == [1]
    return ok, f"q=train -> ids {[c['id'] for c in by_item['data']]}; q=berlin -> ids {[c['id'] for c in by_title['data']]}"


# --- Happy paths ------------------------------------------------------------

def happy_paths(tok):
    results = []

    def expect(name, condition, detail=""):
        results.append((name, bool(condition), detail))

    s, b, _ = call("GET", "/ping")
    expect("ping 200", s == 200 and b == {"status": "ok"}, s)
    s, b, _ = call("POST", "/auth/login", body={"username": "alice", "password": "nope"})
    expect("wrong password 401", s == 401 and b["error"] == "invalid_credentials", s)
    s, _, _ = call("POST", "/auth/login", body={"username": "nobody", "password": "x"})
    expect("unknown user 401", s == 401, s)
    s, _, _ = call("POST", "/auth/login", body={"username": "alice"})
    expect("login without password 400", s == 400, s)
    s, _, _ = call("GET", "/claims")
    expect("no token 401", s == 401, s)
    s, _, _ = call("GET", "/claims", "bogus")
    expect("bad token 401", s == 401, s)
    s, b, _ = call("GET", "/nope", tok["alice"])
    expect("unknown route 404", s == 404, s)
    s, _, h = call("PUT", "/claims/1", tok["alice"], {})
    expect("wrong method 405 with Allow", s == 405 and "PATCH" in h.get("Allow", ""), (s, h.get("Allow")))
    s, _, _ = call("GET", "/claims/abc", tok["alice"])
    expect("non-numeric id 404", s == 404, s)

    # Create, read, update, items
    s, c, h = call("POST", "/claims", tok["alice"], {
        "title": "  Happy trip  ", "currency": "EUR", "purpose": "Customer meeting",
        "items": [item(days_ago(2), "travel", "Train", 12.5), item(days_ago(2), "lodging", "Hotel", 30)],
    })
    expect("create 201 + Location", s == 201 and h.get("Location") == f"/claims/{c['id']}", (s, h.get("Location")))
    expect("create body", c["status"] == "draft" and c["title"] == "Happy trip" and c["total"] == 42.5
           and c["owner"] == "alice" and c["team"] == "platform" and len(c["items"]) == 2, c)
    cid = c["id"]
    s, d, _ = call("GET", f"/claims/{cid}", tok["alice"])
    expect("get 200", s == 200 and d["total"] == 42.5 and d["items"][0]["claim_id"] == cid, s)
    s, d, _ = call("PATCH", f"/claims/{cid}", tok["alice"], {"title": "Happy trip to Kiel", "purpose": None})
    expect("patch 200", s == 200 and d["title"] == "Happy trip to Kiel" and d["purpose"] is None
           and d["currency"] == "EUR" and d["total"] == 42.5, d)
    s, d, _ = call("PATCH", f"/claims/{cid}", tok["alice"], {"currency": "eur"})
    expect("patch bad currency 400", s == 400 and d["field"] == "currency", s)
    s, d, _ = call("PATCH", f"/claims/{cid}", tok["alice"], {"title": ""})
    expect("patch empty title 400", s == 400, s)
    s, it, _ = call("POST", f"/claims/{cid}/items", tok["alice"], item(days_ago(1), "meals", "Lunch", 7.25))
    expect("add item 201", s == 201 and it["amount"] == 7.25 and it["claim_id"] == cid, (s, it))
    s, d, _ = call("GET", f"/claims/{cid}", tok["alice"])
    expect("total after add", d["total"] == 49.75, d["total"])
    s, lst, _ = call("GET", "/claims?q=kiel", tok["alice"])
    expect("list finds by title", s == 200 and [r["id"] for r in lst["data"]] == [cid] and lst["data"][0]["total"] == 49.75, lst)
    s, rm, _ = call("POST", "/claims", tok["alice"], {"title": "Happy remove", "currency": "EUR",
                                                      "items": [item(amount=5), item(amount=6)]})
    s, _, _ = call("DELETE", f"/claims/{rm['id']}/items/{rm['items'][0]['id']}", tok["alice"])
    s2, d, _ = call("GET", f"/claims/{rm['id']}", tok["alice"])
    expect("remove own item 204", s == 204 and d["total"] == 6 and len(d["items"]) == 1, (s, d["total"]))
    s, _, _ = call("DELETE", f"/claims/{rm['id']}/items/999999", tok["alice"])
    expect("remove unknown item 404", s == 404, s)

    # Validation
    def bad_item(name, it_body, field):
        s, b, _ = call("POST", f"/claims/{cid}/items", tok["alice"], it_body)
        expect(f"item {name} 400", s == 400 and b.get("field") == field, (s, b))

    bad_item("future date", item((TODAY + datetime.timedelta(days=1)).isoformat()), "date")
    bad_item("impossible date", item("2026-02-30"), "date")
    bad_item("bad format date", item("10/11/2026"), "date")
    bad_item("old date", item(days_ago(120)), "date")
    bad_item("negative", item(amount=-5), "amount")
    bad_item("three decimals", item(amount=12.345), "amount")
    bad_item("too large", item(amount=10000.01), "amount")
    bad_item("string amount", item(amount="12.50"), "amount")
    bad_item("bad category", {**item(), "category": "casino"}, "category")
    bad_item("empty description", {**item(), "description": "  "}, "description")
    bad_item("single meal over 60", item(category="meals", amount=60.01), "amount")
    s, _, _ = call("POST", f"/claims/{cid}/items", tok["alice"], item(days_ago(5), "meals", "Big dinner", 60))
    expect("meal of exactly 60 accepted", s == 201, s)
    s, _, _ = call("POST", f"/claims/{cid}/items", tok["alice"], item(TODAY.isoformat(), "travel", "Today", 10000))
    expect("today and 10000.00 accepted", s == 201, s)
    s, b, _ = call("POST", "/claims", tok["alice"], {"currency": "EUR"})
    expect("create without title 400", s == 400 and b["field"] == "title", (s, b))
    s, b, _ = call("POST", "/claims", tok["alice"], {"title": "x", "currency": "JPY"})
    expect("create bad currency 400", s == 400, s)
    s, b, _ = call("POST", "/claims", tok["alice"], {"title": "x" * 121, "currency": "EUR"})
    expect("title 121 chars 400", s == 400, s)
    s, b, _ = call("POST", "/claims", tok["alice"], {"title": "x", "currency": "EUR", "items": [item(), item(amount=-1)]})
    expect("create with a bad item 400 + field", s == 400 and b["field"] == "items[1].amount", b)
    s, b, _ = call("POST", "/claims", tok["alice"], raw="{not json")
    expect("invalid json 400", s == 400 and b["error"] == "invalid_json", (s, b))
    s, b, _ = call("POST", "/claims", tok["alice"], raw="[]")
    expect("array body 400", s == 400 and b["error"] == "invalid_body", (s, b))
    s, _, _ = call("POST", "/claims", tok["carol"], {"title": "x", "currency": "EUR"})
    expect("manager create 403", s == 403, s)
    s, _, _ = call("POST", "/claims", tok["dave"], {"title": "x", "currency": "EUR"})
    expect("finance create 403", s == 403, s)

    # State machine: draft -> submitted -> approved -> paid
    s, _, _ = call("POST", f"/claims/{cid}/review", tok["carol"], {"decision": "approve"})
    expect("review a draft 409", s == 409, s)
    s, d, _ = call("POST", f"/claims/{cid}/submit", tok["alice"])
    expect("submit 200", s == 200 and d["status"] == "submitted" and d["submitted_at"], (s, d.get("status")))
    total = d["total"]
    s, _, _ = call("POST", f"/claims/{cid}/submit", tok["alice"])
    expect("submit twice 409", s == 409, s)
    s, _, _ = call("PATCH", f"/claims/{cid}", tok["alice"], {"title": "late edit"})
    expect("patch submitted 409", s == 409, s)
    s, _, _ = call("POST", f"/claims/{cid}/items", tok["alice"], item())
    expect("add item to submitted 409", s == 409, s)
    s, _, _ = call("DELETE", f"/claims/{cid}", tok["alice"])
    expect("delete submitted 409", s == 409, s)
    s, _, _ = call("GET", f"/claims/{cid}", tok["carol"])
    expect("team manager sees submitted", s == 200, s)
    s, _, _ = call("GET", f"/claims/{cid}", tok["frank"])
    expect("other-team manager cannot see 404", s == 404, s)
    s, _, _ = call("GET", f"/claims/{cid}", tok["bob"])
    expect("other employee cannot see 404", s == 404, s)
    s, _, _ = call("POST", f"/claims/{cid}/review", tok["alice"], {"decision": "approve"})
    expect("owner review 403", s == 403, s)
    s, _, _ = call("POST", f"/claims/{cid}/review", tok["dave"], {"decision": "approve"})
    expect("finance review 403", s == 403, s)
    s, _, _ = call("POST", f"/claims/{cid}/review", tok["carol"], {"decision": "maybe"})
    expect("bad decision 400", s == 400, s)
    s, _, _ = call("POST", f"/claims/{cid}/pay", tok["dave"])
    expect("pay submitted 409", s == 409, s)
    s, d, _ = call("POST", f"/claims/{cid}/review", tok["carol"], {"decision": "approve", "comment": "ok"})
    expect("approve 200", s == 200 and d["status"] == "approved" and d["reviewed_by"] == "carol"
           and d["review_comment"] == "ok" and d["reviewed_at"], d)
    s, _, _ = call("POST", f"/claims/{cid}/review", tok["carol"], {"decision": "reject", "comment": "x"})
    expect("review approved 409", s == 409, s)
    s, _, _ = call("POST", f"/claims/{cid}/pay", tok["carol"])
    expect("manager pay 403", s == 403, s)
    s, d, _ = call("POST", f"/claims/{cid}/pay", tok["dave"], {"reference": "HAPPY-1"})
    expect("pay 200", s == 200 and d["status"] == "paid" and d["amount_paid"] == total
           and d["payment_reference"] == "HAPPY-1" and d["paid_at"], d)
    s, lst, _ = call("GET", "/claims?status=paid&owner=alice", tok["dave"])
    expect("finance list by status+owner", s == 200 and cid in [r["id"] for r in lst["data"]]
           and all(r["status"] == "paid" and r["owner"] == "alice" for r in lst["data"]), lst)

    # Reject path
    s, rc, _ = call("POST", "/claims", tok["bob"], {"title": "Happy reject", "currency": "GBP", "items": [item(amount=45.5)]})
    rid = rc["id"]
    call("POST", f"/claims/{rid}/submit", tok["bob"])
    s, _, _ = call("POST", f"/claims/{rid}/review", tok["carol"], {"decision": "reject"})
    expect("reject without comment 400", s == 400, s)
    s, _, _ = call("POST", f"/claims/{rid}/review", tok["carol"], {"decision": "reject", "comment": "   "})
    expect("reject with blank comment 400", s == 400, s)
    s, d, _ = call("POST", f"/claims/{rid}/review", tok["carol"], {"decision": "reject", "comment": "Missing receipt"})
    expect("reject 200", s == 200 and d["status"] == "rejected" and d["review_comment"] == "Missing receipt", d)
    s, d, _ = call("PATCH", f"/claims/{rid}", tok["bob"], {"purpose": "Receipt attached"})
    expect("patch rejected 200", s == 200 and d["purpose"] == "Receipt attached" and d["status"] == "rejected", d)
    s, _, _ = call("POST", f"/claims/{rid}/items", tok["bob"], item(amount=4.5))
    expect("add item to rejected 201", s == 201, s)
    s, _, _ = call("DELETE", f"/claims/{rid}", tok["bob"])
    expect("delete rejected 409", s == 409, s)
    s, _, _ = call("POST", f"/claims/{rid}/pay", tok["dave"])
    expect("pay rejected 409", s == 409, s)
    s, _, _ = call("PATCH", f"/claims/{rid}", tok["carol"], {"title": "x"})
    expect("manager patch 403", s == 403, s)

    # Delete a draft; drafts are private
    s, dc, _ = call("POST", "/claims", tok["alice"], {"title": "Happy delete", "currency": "USD", "items": [item()]})
    s, _, _ = call("GET", f"/claims/{dc['id']}", tok["carol"])
    expect("manager cannot see draft 404", s == 404, s)
    s, _, _ = call("GET", f"/claims/{dc['id']}", tok["dave"])
    expect("finance cannot see draft 404", s == 404, s)
    s, _, _ = call("DELETE", f"/claims/{dc['id']}", tok["bob"])
    expect("other employee delete 404", s == 404, s)
    s, _, _ = call("POST", f"/claims/{dc['id']}/submit", tok["bob"])
    expect("other employee submit 404", s == 404, s)
    s, _, _ = call("DELETE", f"/claims/{dc['id']}", tok["alice"])
    expect("delete draft 204", s == 204, s)
    s, _, _ = call("GET", f"/claims/{dc['id']}", tok["alice"])
    expect("deleted claim 404", s == 404, s)
    s, e, _ = call("POST", "/claims", tok["alice"], {"title": "Happy empty", "currency": "EUR"})
    s, b, _ = call("POST", f"/claims/{e['id']}/submit", tok["alice"])
    expect("submit empty claim 400", s == 400 and b.get("field") == "items", (s, b))

    # Lists
    s, lst, _ = call("GET", "/claims", tok["bob"])
    expect("employee list only own", s == 200 and all(r["owner"] == "bob" for r in lst["data"]), lst["meta"])
    s, lst, _ = call("GET", "/claims?per_page=50", tok["carol"])
    expect("manager list own team, no drafts", all(r["team"] == "platform" and r["status"] != "draft" for r in lst["data"]), "")
    s, lst, _ = call("GET", "/claims?per_page=50", tok["frank"])
    expect("frank list mobile only", all(r["team"] == "mobile" and r["status"] != "draft" for r in lst["data"]), "")
    s, lst, _ = call("GET", "/claims?per_page=50", tok["dave"])
    expect("finance list no drafts", all(r["status"] != "draft" for r in lst["data"]) and lst["meta"]["total_count"] >= 8, lst["meta"])
    s, lst, _ = call("GET", "/claims?status=submitted&per_page=50", tok["dave"])
    expect("status filter", all(r["status"] == "submitted" for r in lst["data"]), "")
    s, lst, _ = call("GET", "/claims?owner=bob&per_page=50", tok["carol"])
    expect("owner filter (manager)", lst["data"] and all(r["owner"] == "bob" for r in lst["data"]), "")
    s, lst, _ = call("GET", "/claims?sort=total&per_page=50", tok["dave"])
    totals = [r["total"] for r in lst["data"]]
    expect("sort=total ascending", totals == sorted(totals), totals)
    s, lst, _ = call("GET", "/claims?sort=-total&per_page=50", tok["dave"])
    totals = [r["total"] for r in lst["data"]]
    expect("sort=-total descending", totals == sorted(totals, reverse=True), totals)
    s, lst, _ = call("GET", "/claims?sort=created_at&per_page=50", tok["dave"])
    created = [r["created_at"] for r in lst["data"]]
    expect("sort=created_at ascending", created == sorted(created), "")
    s, lst, _ = call("GET", "/claims?q=BERLIN", tok["carol"])
    expect("q case-insensitive on title", [r["id"] for r in lst["data"]] == [1], lst["data"])
    s, p1, _ = call("GET", "/claims?per_page=3&page=1", tok["dave"])
    s, p2, _ = call("GET", "/claims?per_page=3&page=2", tok["dave"])
    ids1 = [r["id"] for r in p1["data"]]
    ids2 = [r["id"] for r in p2["data"]]
    expect("pagination pages disjoint", len(ids1) == 3 and len(ids2) == 3 and not set(ids1) & set(ids2)
           and p1["meta"]["next_page"] == 2, (ids1, ids2))
    s, far, _ = call("GET", "/claims?page=99", tok["dave"])
    expect("page past end empty 200", s == 200 and far["data"] == [] and far["meta"]["next_page"] is None, far["meta"])
    for q in ("per_page=51", "per_page=0", "page=0", "page=x", "status=open"):
        s, _, _ = call("GET", f"/claims?{q}", tok["alice"])
        expect(f"list {q} -> 400", s == 400, s)

    return results


def main():
    tokens = {u: login(u) for u in PASSWORDS}
    reproduced = 0
    for tid in sorted(T):
        try:
            ok, observed = T[tid](tokens)
        except Exception as exc:  # noqa: BLE001
            ok, observed = False, f"error: {exc!r}"
        reproduced += ok
        print(f"{tid} {'reproduced' if ok else 'NOT reproduced'}: {observed}")
    print(f"{reproduced} of {len(T)} reproduced")

    results = happy_paths(tokens)
    failed = [r for r in results if not r[1]]
    for name, ok, detail in failed:
        print(f"  happy path FAILED: {name}: {detail}")
    print(f"Happy paths: {len(results) - len(failed)} of {len(results)} checks passed")
    return 0 if reproduced == len(T) and not failed else 1


if __name__ == "__main__":
    sys.exit(main())
