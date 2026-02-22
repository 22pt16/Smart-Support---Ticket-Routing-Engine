"""Configuration from environment."""

import os

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
QUEUE_NAME = "mvr:ticket_queue"
STATUS_PREFIX = "mvr:status:"
ALL_IDS_KEY = "mvr:all_ids"
READY_QUEUE_KEY = "mvr:ready"  # sorted set: score = urgency_score (higher first), member = ticket_id
SUBMIT_LOCK_KEY = "mvr:lock:submit"
SUBMIT_LOCK_TTL = 5
PROCESSING_LOCK_PREFIX = "mvr:lock:processing:"
PROCESSING_LOCK_TTL = 300

# Slack webhook; if unset, high-urgency notifications (S > 0.8) are only logged
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
URGENCY_WEBHOOK_THRESHOLD = 0.8


def get_slack_webhook_url() -> str:
    return (os.environ.get("SLACK_WEBHOOK_URL") or "").strip()
