"""Flask routes for the clinic SMS reminder pilot. Run: python -m flask --app app run"""
from datetime import date
import click
from flask import Flask, request, redirect, render_template, session, abort
import config, db, reminders
from sms_gateway import norm_phone

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.teardown_appcontext(db.close_db)


@app.cli.command("send-due")
def cmd_send_due():
    """Run daily ~07:30: python -m flask --app app send-due"""
    click.echo(f"{reminders.send_due(db.get_db())} reminder(s) sent")


def staff():
    if not session.get("ok"):
        abort(redirect("/login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("pw") == config.STAFF_PASSWORD:
            session["ok"] = True
            return redirect("/")
        error = "Wrong password. Check it and try again."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


LABELS = {"scheduled": ("○", "Reminder pending"), "confirmed": ("✓", "Confirmed"),
          "reschedule": ("↻", "Wants a new day"), "missed": ("✕", "Missed"),
          "attended": ("✓", "Attended")}


def safe_next(default="/"):
    n = request.form.get("next", default)
    return n if n.startswith("/") and not n.startswith("//") else default


def stats():
    q = lambda sql: db.get_db().execute(sql).fetchone()[0]
    att, mis = q("SELECT COUNT(*) FROM appts WHERE status='attended'"), q("SELECT COUNT(*) FROM appts WHERE status='missed'")
    return {"enrolled": q("SELECT COUNT(*) FROM clients"), "sent": q("SELECT COUNT(*) FROM reminders"),
            "replies": q("SELECT COUNT(*) FROM appts WHERE status IN ('confirmed','reschedule')"),
            "rate": f"{round(100 * att / (att + mis))}%" if att + mis else "-"}


def when(day, today):
    n = (date.fromisoformat(day) - today).days
    if n == 0: return "today"
    if n == 1: return "tomorrow"
    if n == -1: return "yesterday"
    return f"in {n} days" if n > 1 else f"{-n} days ago"


@app.route("/")
def home():
    staff()
    today = date.today()
    t = today.isoformat()
    q = request.args.get("q", "").strip()
    sql = """SELECT a.id, a.day, a.status, c.id AS cid, c.code, c.opted_out FROM appts a
        JOIN clients c ON c.id=a.client_id WHERE {} ORDER BY a.day {}"""
    if q:  # search covers every visit, including ones already marked attended
        rows = db.get_db().execute(sql.format("c.code LIKE ?", "DESC"), (f"%{q}%",)).fetchall()
    else:
        rows = db.get_db().execute(sql.format("a.status != 'attended'", "")).fetchall()
    items = [dict(r, when=when(r["day"], today), mark=LABELS[r["status"]][0], label=LABELS[r["status"]][1]) for r in rows]
    if q:
        groups = [{"title": f"Results for \u201c{q}\u201d", "tone": "", "rows": items,
                   "hint": "Includes visits already marked attended.",
                   "empty": "No client found. Check the spelling, or enrol them."}]
        return render_template("home.html", groups=groups, today=t, q=q, stats=stats())
    overdue = [x for x in items if x["status"] != "missed" and x["day"] < t]
    missed = [x for x in items if x["status"] == "missed"]
    upcoming = [x for x in items if x["status"] != "missed" and x["day"] >= t]
    groups = [
        {"title": "Needs an outcome", "tone": "wait", "rows": overdue, "hint": "The visit date has passed. Mark what happened.", "empty": "Nothing waiting. Well done."},
        {"title": "Missed: follow up", "tone": "bad", "rows": missed, "hint": "Ask the village health worker to call or visit.", "empty": "No missed visits."},
        {"title": "Coming up", "tone": "", "rows": upcoming, "hint": "Reminders go out 2 days before and on the morning of the visit.", "empty": "No visits booked yet. Enrol a client to start."},
    ]
    return render_template("home.html", groups=groups, today=t, q=q, stats=stats())


@app.post("/enrol")
def enrol():
    staff()
    d, f = db.get_db(), request.form
    if not f.get("consent"):
        return "Consent must be recorded first.", 400
    code, phone = f["code"].strip(), norm_phone(f["phone"])
    c = d.execute("SELECT id FROM clients WHERE code=?", (code,)).fetchone()
    if c:
        cid = c["id"]
    else:
        cid = d.execute("INSERT INTO clients(code,phone,lang,consent_at) VALUES(?,?,?,?)",
                        (code, phone, f["lang"], date.today().isoformat())).lastrowid
    d.execute("INSERT INTO appts(client_id,day) VALUES(?,?)", (cid, f["day"]))
    d.commit()
    return redirect("/")


@app.post("/appt/<int:i>/<action>")
def mark(i, action):
    staff()
    if action not in ("attended", "missed", "scheduled"):  # "scheduled" undoes a wrong outcome
        abort(400)
    d = db.get_db()
    d.execute("UPDATE appts SET status=? WHERE id=?", (action, i))
    d.commit()
    return redirect(safe_next())


@app.post("/sms/incoming")
def incoming():
    """Reply webhook: /sms/incoming?token=... Accepts the gateway app's JSON or form fields from/text."""
    if request.args.get("token") != config.INCOMING_TOKEN:
        abort(403)
    d = db.get_db()
    if request.is_json:  # webhook from the SMS Gateway for Android app
        body = request.get_json(silent=True) or {}
        if body.get("event") != "sms:received":
            return "", 204
        p = body.get("payload") or {}
        raw_phone, t = p.get("phoneNumber", ""), p.get("message", "")
    else:  # simple form post, handy for testing
        raw_phone, t = request.values.get("from", ""), request.values.get("text", "")
    phone, t = norm_phone(raw_phone), t.strip()
    c = d.execute("SELECT id FROM clients WHERE phone=?", (phone,)).fetchone()
    if not c:
        return "", 204
    if t == "0" or t.upper() == "STOP":
        d.execute("UPDATE clients SET opted_out=1 WHERE id=?", (c["id"],))
    elif t in ("1", "2"):
        d.execute("""UPDATE appts SET status=? WHERE id=(SELECT id FROM appts WHERE client_id=? AND
            status IN ('scheduled','confirmed','reschedule') ORDER BY day LIMIT 1)""",
                  ("confirmed" if t == "1" else "reschedule", c["id"]))
    d.commit()
    return "", 204


@app.route("/kpis")
def kpis():
    """Aggregate counts only (no personal data) for the M&E report."""
    staff()
    q = lambda s: db.get_db().execute(s).fetchone()[0]
    return {"enrolled_clients": q("SELECT COUNT(*) FROM clients"),
            "opted_out": q("SELECT COUNT(*) FROM clients WHERE opted_out=1"),
            "reminders_sent": q("SELECT COUNT(*) FROM reminders"),
            "reminders_accepted_by_gateway": q("SELECT COUNT(*) FROM reminders WHERE ok=1"),
            "replied_confirm_or_reschedule": q("SELECT COUNT(*) FROM appts WHERE status IN ('confirmed','reschedule')"),
            "attended": q("SELECT COUNT(*) FROM appts WHERE status='attended'"),
            "missed": q("SELECT COUNT(*) FROM appts WHERE status='missed'")}


def get_client(i):
    return db.get_db().execute("SELECT * FROM clients WHERE id=?", (i,)).fetchone() or abort(404)


@app.route("/client/<int:i>")
def client(i):
    staff()
    c, today = get_client(i), date.today()
    rows = db.get_db().execute("SELECT id, day, status FROM appts WHERE client_id=? ORDER BY day DESC", (i,)).fetchall()
    visits = [dict(r, when=when(r["day"], today), mark=LABELS[r["status"]][0], label=LABELS[r["status"]][1]) for r in rows]
    return render_template("client.html", c=c, visits=visits, today=today.isoformat(), masked="\u2022\u2022\u2022\u2022 " + c["phone"][-4:])


@app.post("/client/<int:i>/edit")
def client_edit(i):
    staff(); get_client(i)
    f, d = request.form, db.get_db()
    if f.get("lang") in ("st", "en"):
        d.execute("UPDATE clients SET lang=? WHERE id=?", (f["lang"], i))
    if f.get("phone", "").strip():  # blank keeps the current number
        d.execute("UPDATE clients SET phone=? WHERE id=?", (norm_phone(f["phone"]), i))
    d.commit()
    return redirect(f"/client/{i}")


@app.post("/client/<int:i>/visit")
def client_visit(i):
    staff(); get_client(i)
    d = db.get_db()
    d.execute("INSERT INTO appts(client_id,day) VALUES(?,?)", (i, request.form["day"]))
    d.commit()
    return redirect(f"/client/{i}")


@app.post("/client/<int:i>/optout")
def client_optout(i):
    staff(); get_client(i)
    d = db.get_db()
    d.execute("UPDATE clients SET opted_out=1 WHERE id=?", (i,))
    d.commit()
    return redirect(f"/client/{i}")


@app.post("/client/<int:i>/delete")
def client_delete(i):
    """Removes the client, their visits and their reminder log for good (delete on request)."""
    staff(); get_client(i)
    if not request.form.get("sure"):
        return "Tick the box to confirm deletion.", 400
    d = db.get_db()
    d.execute("DELETE FROM reminders WHERE appt_id IN (SELECT id FROM appts WHERE client_id=?)", (i,))
    d.execute("DELETE FROM appts WHERE client_id=?", (i,))
    d.execute("DELETE FROM clients WHERE id=?", (i,))
    d.commit()
    return redirect("/")
