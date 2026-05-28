#!/bin/bash
# Runs at 7:30am — reads composed email from relay Gist and sends via Resend
set -e

RESEND_API_KEY="re_3icU4ZrP_EMyrm99pQ6ZS5oH2tv3E5qNx"
GIST_RAW_URL="https://gist.githubusercontent.com/derivedobsessed/37d486f1c0d3e65a374fa1c9f7cdd6bf/raw/email_output.json"
TO="alex.allen894@gmail.com"
LOG="/tmp/axle-send.log"

echo "$(date): Checking relay Gist for email..." >> "$LOG"

python3 - <<'PYEOF'
import urllib.request, json, sys, os
from datetime import datetime, timezone, timedelta

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "re_3icU4ZrP_EMyrm99pQ6ZS5oH2tv3E5qNx")
GIST_URL = "https://gist.githubusercontent.com/derivedobsessed/37d486f1c0d3e65a374fa1c9f7cdd6bf/raw/email_output.json"
TO = "alex.allen894@gmail.com"
LOG = "/tmp/axle-send.log"

def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{datetime.now()}: {msg}\n")

# Fetch the relay Gist (cache-busted)
try:
    req = urllib.request.Request(GIST_URL + "?t=" + str(int(datetime.now().timestamp())))
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode())
except Exception as e:
    log(f"ERROR reading Gist: {e}")
    sys.exit(1)

subject = data.get("subject", "")
html = data.get("html", "")
generated_at = data.get("generated_at", "")

if not subject or not html:
    log("No email content in Gist yet — agent may not have run.")
    sys.exit(0)

# Only send if generated today (avoid resending yesterday's email)
if generated_at:
    try:
        gen_time = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - gen_time).total_seconds() / 3600
        if age_hours > 6:
            log(f"Email is {age_hours:.1f}h old — skipping (already sent or stale).")
            sys.exit(0)
    except Exception:
        pass

# Send via Resend
payload = json.dumps({
    "from": "Axle Flex Intel <onboarding@resend.dev>",
    "to": [TO],
    "subject": subject,
    "html": html,
}).encode()

req = urllib.request.Request(
    "https://api.resend.com/emails",
    data=payload,
    headers={
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=15) as r:
        result = json.loads(r.read().decode())
        log(f"Email sent OK. Resend ID: {result.get('id')}. Subject: {subject}")
        print(f"Sent: {subject}")
except Exception as e:
    log(f"ERROR sending email: {e}")
    sys.exit(1)
PYEOF
