"""All settings come from environment variables, so no secrets live in the code."""
import os

SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")
DB_PATH = os.environ.get("DB_PATH", "reminders.db")
STAFF_PASSWORD = os.environ.get("STAFF_PASSWORD", "change-me")
INCOMING_TOKEN = os.environ.get("INCOMING_TOKEN", "change-me")
SMS_GATEWAY = os.environ.get("SMS_GATEWAY", "console")  # console | smsgate
GATEWAY_URL = os.environ.get("GATEWAY_URL", "")
GATEWAY_USER = os.environ.get("GATEWAY_USER", "")
GATEWAY_PASS = os.environ.get("GATEWAY_PASS", "")
