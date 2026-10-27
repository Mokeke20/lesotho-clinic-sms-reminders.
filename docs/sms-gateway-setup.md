# Connecting the spare Android phone as the SMS gateway

Uses the open-source **SMS Gateway for Android** app (Apache-2.0): https://github.com/capcom6/android-sms-gateway
Check its README for the current steps if anything below has changed.

## What you need
- A spare Android phone (Android 5.0 or newer) with a **dedicated local SIM** and airtime. Do not use anyone's personal number.
- The phone and the laptop running the app on the **same Wi-Fi**.
- Keep the phone **plugged in**, with a **screen PIN**. It stores clients' phone numbers and replies.

## 1. Install and start the gateway app
1. On the phone, download the latest APK from the project's Releases page (link above) and install it (allow unknown sources when asked).
2. Grant the SMS permissions it asks for. Sending needs SEND_SMS; receiving replies needs RECEIVE_SMS.
3. Turn on **Local Server** (not Cloud Server, so messages never pass through a third party), then tap **Start Service**.
4. Note the phone's local IP address, the username and the password shown in the Local Server section.
5. In the app's settings, switch on a **send rate limit** so the SIM is not throttled by the operator.

## 2. Test sending from PowerShell (replace the capitals)
```
$auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("USER:PASSWORD"))
Invoke-RestMethod -Method Post -Uri "http://PHONE_IP:8080/message" -Headers @{Authorization="Basic $auth"} -ContentType "application/json" -Body '{"textMessage":{"text":"Test from the clinic project"},"phoneNumbers":["+266YOURNUMBER"]}'
```
Your phone should receive the text within a minute.

## 3. Point the reminder app at the gateway
```
$env:SMS_GATEWAY="smsgate"
$env:GATEWAY_URL="http://PHONE_IP:8080/message"
$env:GATEWAY_USER="USER"
$env:GATEWAY_PASS="PASSWORD"
$env:STAFF_PASSWORD="your-password"
$env:SECRET_KEY="long-random-text"
$env:INCOMING_TOKEN="another-random-text"
python -m flask --app app send-due
```
Enrol your own number first (with a visit date of today) and check the SMS arrives.

## 4. Receive replies (do this after sending works)
The gateway app sends each incoming SMS to a web address you register (a webhook). The phone must be able to reach that address, and the phone needs an internet connection to send it.
Start the app so the phone can reach it: `python -m flask --app app run --host 0.0.0.0` (allow it through Windows Firewall).
Register the webhook:
```
Invoke-RestMethod -Method Post -Uri "http://PHONE_IP:8080/webhooks" -Headers @{Authorization="Basic $auth"} -ContentType "application/json" -Body '{"id":"clinic-replies","url":"http://LAPTOP_IP:5000/sms/incoming?token=YOUR_INCOMING_TOKEN","event":"sms:received"}'
```
The app's README says the standard build expects an HTTPS webhook address, and a separate "insecure" build allows plain http for testing only. If the standard build will not deliver to your laptop, use the insecure build for testing on your own Wi-Fi, or an HTTPS tunnel. Never use the insecure build with real client data in a public setting.
Then text `1` from your own phone to the gateway SIM and check the visit turns Confirmed.

## Limits to write into your report
- The gateway accepting a message is not proof it was delivered. Count "accepted by gateway" and ask clients if they received it.
- The phone must stay on, charged, with airtime and signal. Name who checks it daily.
- The project says not to use this for large batches, which is fine for a small clinic pilot but not for scale-up.
