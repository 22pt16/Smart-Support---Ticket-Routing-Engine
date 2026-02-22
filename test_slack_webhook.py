#!/usr/bin/env python3
"""
Test Slack webhook without running the worker.
Usage: ./venv/bin/python test_slack_webhook.py
Loads .env from project root and POSTs a test message to SLACK_WEBHOOK_URL.
"""

import os
import sys

# Load .env from project root
try:
    from dotenv import load_dotenv
    script_dir = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(script_dir, ".env"))
except ImportError:
    pass

url = (os.environ.get("SLACK_WEBHOOK_URL") or "").strip()
if not url:
    print("ERROR: SLACK_WEBHOOK_URL not set. Add it to .env in the project root.")
    sys.exit(1)

if not url.startswith("https://hooks.slack.com/"):
    print("WARNING: URL does not look like a Slack webhook (expected https://hooks.slack.com/...)")

import httpx

payload = {"text": ":white_check_mark: Test from MVR Ticket Router – if you see this, Slack webhook is working."}
try:
    r = httpx.post(url, json=payload, timeout=10.0)
    r.raise_for_status()
    print("OK: Message sent to Slack. Check your channel.")
except Exception as e:
    print("FAIL:", e)
    if hasattr(e, "response") and getattr(e, "response", None) is not None:
        print("Response:", getattr(e.response, "text", "")[:300])
    sys.exit(1)
