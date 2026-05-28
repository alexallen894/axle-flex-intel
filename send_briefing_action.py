#!/usr/bin/env python3
"""Called by GitHub Actions to send email_body.html via Resend."""
import json
import os
import subprocess
import sys
import tempfile

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
})

with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
    f.write(payload)
    tmp_path = f.name

result = subprocess.run(
    [
        "curl", "-s", "-w", "\nHTTP_STATUS:%{http_code}",
        "-X", "POST",
        "-H", f"Authorization: Bearer {api_key}",
        "-H", "Content-Type: application/json",
        "--data-binary", f"@{tmp_path}",
        "https://api.resend.com/emails",
    ],
    capture_output=True,
    text=True,
)

os.unlink(tmp_path)

output = result.stdout
if "HTTP_STATUS:" in output:
    body, status_line = output.rsplit("\nHTTP_STATUS:", 1)
    http_status = int(status_line.strip())
else:
    body = output
    http_status = 0

print(f"HTTP {http_status}: {body}")

if http_status not in (200, 201):
    print(f"::error::Resend failed HTTP {http_status}: {body}", file=sys.stderr)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    sys.exit(1)
