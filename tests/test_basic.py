"""Run from the project folder: python -m unittest discover tests"""
import os, sys, tempfile, unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.update(STAFF_PASSWORD="change-me", INCOMING_TOKEN="change-me", SECRET_KEY="test", SMS_GATEWAY="console")  # tests ignore your terminal settings
import app as A  # noqa: E402
import db, reminders  # noqa: E402


def enrol(c, code, phone, days=2, consent=True):
    data = {"code": code, "phone": phone, "lang": "st", "day": (date.today() + timedelta(days=days)).isoformat()}
    if consent:
        data["consent"] = "on"
    return c.post("/enrol", data=data)


class Basic(unittest.TestCase):
    def setUp(self):
        self.c = A.app.test_client()
        self.c.post("/login", data={"pw": "change-me"})

    def test_consent_required(self):
        self.assertEqual(enrol(self.c, "NoConsent", "58000001", consent=False).status_code, 400)

    def test_reminder_reply_and_optout(self):
        enrol(self.c, "Thabo", "58111111")
        enrol(self.c, "Palesa", "58222222")
        self.c.post("/sms/incoming?token=change-me", data={"from": "58222222", "text": "0"})
        with A.app.app_context():
            sent = reminders.send_due(db.get_db())
        self.assertEqual(sent, 1)  # Palesa opted out, so only Thabo is messaged
        self.c.post("/sms/incoming?token=change-me", data={"from": "58111111", "text": "1"})
        self.assertEqual(self.c.get("/kpis").json["replied_confirm_or_reschedule"], 1)

    def test_login_required(self):
        self.assertEqual(A.app.test_client().get("/").status_code, 302)


if __name__ == "__main__":
    unittest.main()
