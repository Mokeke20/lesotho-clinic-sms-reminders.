"""Sending SMS. Console mode prints messages; smsgate mode sends through the
open-source "SMS Gateway for Android" app running on a spare phone (local server mode)."""
import base64
import json
import urllib.request
import config


def norm_phone(p):
    p = "".join(c for c in p if c.isdigit() or c == "+")
    return "+266" + p if len(p) == 8 else p


def send_sms(phone, text):
    """True means the gateway accepted the message, not that the phone received it."""
    if config.SMS_GATEWAY == "console":
        print(f"[SMS to {phone}] {text}")
        return True
    body = json.dumps({"textMessage": {"text": text}, "phoneNumbers": [phone]}).encode()
    auth = base64.b64encode(f"{config.GATEWAY_USER}:{config.GATEWAY_PASS}".encode()).decode()
    try:
        req = urllib.request.Request(config.GATEWAY_URL, body,
                                     {"Content-Type": "application/json", "Authorization": "Basic " + auth})
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status < 300
    except Exception as e:
        print("send failed:", e)
        return False
