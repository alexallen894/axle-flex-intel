#!/usr/bin/env python3
"""Called by GitHub Actions to send email_body.html via Resend."""
import json
import os
import sys
import urllib.error
import urllib.request

api_key = os.environ.get("RESEND_API_KEY", "")
if not api_key:
    print("ERROR: RESEND_API_KEY env var is not set", file=sys.stderr)
    sys.exit(1)

html = open("email_body.html").read()

subject = (
    "Axle Flex Intel | 28 May 2026 | "
    "Wind at 45% but 61% of periods tight-margin — flex demand is structural"
)

payload = json.dumps({
    "from": "Axle Flex Intel <onboarding@resend.dev>",
    "to": ["alex.allen894@gmail.com"],
    "subject": subject,
    "html": html,
}).encode("utf-8")

req = urllib.request.Request(
    "https://api.resend.com/emails",
    data=payload,
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=15) as r:
        result = json.loads(r.read())
        print(f"Email sent. Resend ID: {result.get('id')}")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"::error::Resend HTTP {e.code}: {body}", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"::error::{e}", file=sys.stderr)
    sys.exit(1)
