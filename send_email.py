#!/usr/bin/env python3
"""
Send the Axle Flex Intel briefing email via Resend API.
Usage: python3 send_email.py --api-key re_xxx --to recipient@gmail.com --subject "..." --html "<html>..."
"""

import argparse
import json
import sys
import urllib.request
import urllib.error


def send(api_key: str, to: str, subject: str, html: str, from_name: str = "Axle Flex Intel") -> dict:
    payload = json.dumps({
        "from": f"{from_name} <onboarding@resend.dev>",
        "to": [to],
        "subject": subject,
        "html": html,
    }).encode()

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
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            print(f"Email sent successfully. ID: {result.get('id')}")
            return result
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"Failed to send email: HTTP {e.code} — {body}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--to", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--html", required=True)
    args = parser.parse_args()
    send(args.api_key, args.to, args.subject, args.html)
