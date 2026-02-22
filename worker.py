"""
Background worker: pull jobs from Redis queue, process (ML + webhook), write status.
Run: python worker.py
"""

import logging
import os
import sys

# Load .env from project root (same dir as this file) before any config imports
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    load_dotenv(_env_path)
except ImportError:
    pass

from broker import (
    acquire_processing_lock,
    add_to_ready_queue_sync,
    dequeue_sync,
    release_processing_lock,
    set_status_sync,
)
from config import QUEUE_NAME
from ml_models import predict_category, predict_urgency_score
from webhook import notify_high_urgency

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _urgency_label(s: float) -> str:
    return "high" if s >= 0.5 else "low"


def process_ticket(payload: dict) -> None:
    """Process one ticket: ML (Transformer + sentiment S), then webhook if S > 0.8."""
    ticket_id = payload.get("ticket_id")
    if not ticket_id:
        logger.warning("Missing ticket_id in payload: %s", payload)
        return
    if not acquire_processing_lock(ticket_id):
        logger.warning("Skip ticket %s: already being processed", ticket_id)
        return
    try:
        set_status_sync(
            ticket_id,
            {
                "ticket_id": ticket_id,
                "status": "processing",
                "subject": payload.get("subject"),
                "body": payload.get("body"),
                "description": payload.get("description"),
            },
        )
        text = payload.get("combined_text") or ""
        if not text and payload.get("subject"):
            text = " ".join(
                str(p) for p in [
                    payload.get("subject"),
                    payload.get("body"),
                    payload.get("description"),
                ] if p
            )
        created_at = payload.get("created_at")
        try:
            category = predict_category(text)
            s = predict_urgency_score(text)
            s = max(0.0, min(1.0, s))
        except Exception as e:
            logger.exception("ML failed for ticket %s, using baseline fallback: %s", ticket_id, e)
            from classifier import classify_category, get_urgency
            category = classify_category(text)
            s = float(get_urgency(text))  # 0 or 1
        urgency_label = _urgency_label(s)
        set_status_sync(
            ticket_id,
            {
                "ticket_id": ticket_id,
                "status": "completed",
                "category": category,
                "urgency_score": round(s, 4),
                "urgency_label": urgency_label,
                "subject": payload.get("subject"),
                "body": payload.get("body"),
                "description": payload.get("description"),
                "created_at": created_at,
            },
        )
        add_to_ready_queue_sync(ticket_id, s)
        notify_high_urgency(ticket_id, s, category, text)
        logger.info("Completed ticket %s category=%s S=%.2f", ticket_id, category, s)
    except Exception as e:
        logger.exception("Process failed for ticket %s: %s", ticket_id, e)
        created_at = payload.get("created_at")
        set_status_sync(
            ticket_id,
            {
                "ticket_id": ticket_id,
                "status": "completed",
                "category": "Technical",
                "urgency_score": 0.0,
                "urgency_label": "low",
                "subject": payload.get("subject"),
                "body": payload.get("body"),
                "description": payload.get("description"),
                "created_at": created_at,
            },
        )
    finally:
        release_processing_lock(ticket_id)


def main() -> None:
    from config import get_slack_webhook_url
    slack = get_slack_webhook_url()
    logger.info("Worker started, listening on queue %s", QUEUE_NAME)
    if slack:
        logger.info("Slack webhook: configured")
    else:
        logger.info("Slack webhook: not set (set SLACK_WEBHOOK_URL in .env)")
    while True:
        try:
            msg = dequeue_sync(timeout=5)
            if msg is not None:
                process_ticket(msg)
        except KeyboardInterrupt:
            logger.info("Shutting down")
            sys.exit(0)
        except Exception as e:
            logger.exception("Worker error: %s", e)


if __name__ == "__main__":
    main()
