import os, sys, tempfile, unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "pages.db"))
os.environ.update(STAFF_PASSWORD="change-me", INCOMING_TOKEN="change-me", SECRET_KEY="test", SMS_GATEWAY="console")  # tests ignore your terminal settings
import app as A  # noqa: E402


class Pages(unittest.TestCase):
    def test_home_groups_and_login_error(self):
        bad = A.app.test_client().post("/login", data={"pw": "nope"})
        self.assertIn(b"Wrong password", bad.data)
        c = A.app.test_client()
        c.post("/login", data={"pw": "change-me"})
        for code, phone, days in (("Soon", "58333333", 5), ("Late", "58444444", -3)):
            c.post("/enrol", data={"code": code, "phone": phone, "lang": "en", "consent": "on",
                                   "day": (date.today() + timedelta(days=days)).isoformat()})
        html = c.get("/").data.decode()
        for needle in ("Needs an outcome", "Soon", "in 5 days", "3 days ago"):
            self.assertIn(needle, html)
        self.assertEqual(c.get("/logout").status_code, 302)
        self.assertEqual(c.get("/").status_code, 302)

    def test_search_finds_attended_clients(self):
        c = A.app.test_client()
        c.post("/login", data={"pw": "change-me"})
        c.post("/enrol", data={"code": "Zodwa", "phone": "58555555", "lang": "en", "consent": "on",
                               "day": (date.today() + timedelta(days=5)).isoformat()})
        import db
        with A.app.app_context():
            i = db.get_db().execute("SELECT a.id FROM appts a JOIN clients c ON c.id=a.client_id WHERE c.code='Zodwa'").fetchone()[0]
        c.post(f"/appt/{i}/attended")
        self.assertNotIn(b"Zodwa", c.get("/").data)
        found = c.get("/?q=zod").data.decode()
        self.assertIn("Zodwa", found)
        self.assertIn("Attended", found)
        self.assertIn("No client found", c.get("/?q=nobody").data.decode())

    def test_client_page_edit_and_delete(self):
        import db
        c = A.app.test_client()
        c.post("/login", data={"pw": "change-me"})
        c.post("/enrol", data={"code": "Del1", "phone": "58666666", "lang": "st", "consent": "on",
                               "day": (date.today() + timedelta(days=5)).isoformat()})
        with A.app.app_context():
            i = db.get_db().execute("SELECT id FROM clients WHERE code='Del1'").fetchone()[0]
        page = c.get(f"/client/{i}").data.decode()
        self.assertIn("6666", page)
        self.assertNotIn("58666666", page)  # phone is masked on screen
        c.post(f"/client/{i}/edit", data={"lang": "en", "phone": ""})
        c.post(f"/client/{i}/visit", data={"day": (date.today() + timedelta(days=9)).isoformat()})
        c.post(f"/client/{i}/optout")
        self.assertIn("Stopped", c.get(f"/client/{i}").data.decode())
        self.assertEqual(c.post(f"/client/{i}/delete").status_code, 400)
        self.assertEqual(c.post(f"/client/{i}/delete", data={"sure": "on"}).status_code, 302)
        self.assertIn("No client found", c.get("/?q=Del1").data.decode())
        self.assertEqual(c.get(f"/client/{i}").status_code, 404)


if __name__ == "__main__":
    unittest.main()
