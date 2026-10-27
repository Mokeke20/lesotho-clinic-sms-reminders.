import base64, json, os, sys, tempfile, unittest
from datetime import date, timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DB_PATH", os.path.join(tempfile.mkdtemp(), "gw.db"))
os.environ.update(STAFF_PASSWORD="change-me", INCOMING_TOKEN="change-me", SECRET_KEY="test", SMS_GATEWAY="console")  # tests ignore your terminal settings
import app as A  # noqa: E402
import config, db, sms_gateway  # noqa: E402


class Gateway(unittest.TestCase):
    def test_send_uses_gateway_api_with_basic_auth(self):
        with mock.patch.object(config, "SMS_GATEWAY", "smsgate"), \
             mock.patch.object(config, "GATEWAY_URL", "http://192.168.1.50:8080/message"), \
             mock.patch.object(config, "GATEWAY_USER", "u"), mock.patch.object(config, "GATEWAY_PASS", "p"), \
             mock.patch("urllib.request.urlopen") as op:
            op.return_value.__enter__.return_value.status = 202
            self.assertTrue(sms_gateway.send_sms("+26658123456", "Hello"))
            req = op.call_args[0][0]
        self.assertEqual(req.full_url, "http://192.168.1.50:8080/message")
        self.assertEqual(req.get_header("Authorization"), "Basic " + base64.b64encode(b"u:p").decode())
        self.assertEqual(json.loads(req.data), {"textMessage": {"text": "Hello"}, "phoneNumbers": ["+26658123456"]})

    def test_send_failure_returns_false(self):
        with mock.patch.object(config, "SMS_GATEWAY", "smsgate"), \
             mock.patch("urllib.request.urlopen", side_effect=OSError("unreachable")):
            self.assertFalse(sms_gateway.send_sms("+26658123456", "Hello"))

    def test_json_webhook_updates_visit(self):
        c = A.app.test_client()
        c.post("/login", data={"pw": "change-me"})
        c.post("/enrol", data={"code": "Hook1", "phone": "58777777", "lang": "en", "consent": "on",
                               "day": (date.today() + timedelta(days=6)).isoformat()})
        hook = lambda ev, msg: c.post("/sms/incoming?token=change-me", json={
            "event": ev, "payload": {"message": msg, "phoneNumber": "+26658777777"}})
        status = lambda: db.get_db().execute(
            "SELECT a.status FROM appts a JOIN clients c ON c.id=a.client_id WHERE c.code='Hook1'").fetchone()[0]
        self.assertEqual(c.post("/sms/incoming", json={}).status_code, 403)
        hook("sms:sent", "2")  # other events are ignored
        with A.app.app_context():
            self.assertEqual(status(), "scheduled")
        hook("sms:received", "2")
        with A.app.app_context():
            self.assertEqual(status(), "reschedule")


if __name__ == "__main__":
    unittest.main()
