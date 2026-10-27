"""Who is due a reminder today? Sends 2 days before (d2) and on the morning (d0)."""
from datetime import date, timedelta
import messages
import sms_gateway


def send_due(d, today=None):
    today = today or date.today()
    sent = 0
    for kind, target in (("d2", today + timedelta(days=2)), ("d0", today)):
        rows = d.execute(
            """SELECT a.id, a.day, c.code, c.phone, c.lang FROM appts a JOIN clients c ON c.id=a.client_id
            WHERE a.day=? AND a.status IN ('scheduled','confirmed') AND c.opted_out=0
            AND NOT EXISTS (SELECT 1 FROM reminders r WHERE r.appt_id=a.id AND r.kind=?)""",
            (target.isoformat(), kind),
        ).fetchall()
        for r in rows:
            ok = sms_gateway.send_sms(r["phone"], messages.reminder_text(r["lang"], r["code"], r["day"]))
            d.execute("INSERT INTO reminders(appt_id,kind,sent_on,ok) VALUES(?,?,?,?)",
                      (r["id"], kind, today.isoformat(), int(ok)))
            sent += 1
    d.commit()
    return sent
