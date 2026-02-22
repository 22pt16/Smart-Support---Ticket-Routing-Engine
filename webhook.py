"""Slack webhook: notify when urgency score S > threshold."""

import logging
from typing import Optional

import httpx

from config import URGENCY_WEBHOOK_THRESHOLD, get_slack_webhook_url

logger = logging.getLogger(__name__)


def _build_message(ticket_id: str, urgency_score: float, category: str, text: Optional[str]) -> str:
    snippet = (text or "")[:200].replace("\n", " ") if text else "(no content)"
    return (
        f":rotating_light: *High-urgency ticket* (S={urgency_score:.2f})\n"
        f"*ID:* `{ticket_id}` | *Category:* {category}\n"
        f"*Preview:* {snippet}"
    )


def notify_high_urgency(
    ticket_id: str,
    urgency_score: float,
    category: str,
    text: Optional[str] = None,
) -> None:
    """POST to Slack webhook when S > threshold. No-op if SLACK_WEBHOOK_URL unset."""
    if urgency_score <= URGENCY_WEBHOOK_THRESHOLD:
        return
    message = _build_message(ticket_id, urgency_score, category, text)
    slack_url = get_slack_webhook_url()
    if not slack_url:
        logger.info("Mock webhook would fire for ticket %s (S=%.2f)", ticket_id, urgency_score)
        return
    try:
        resp = httpx.post(
            slack_url,
            json={"text": message},
            timeout=10.0,
        )
        resp.raise_for_status()
        logger.info("Slack webhook sent for ticket %s", ticket_id)
    except Exception as e:
        err_detail = str(e)
        if hasattr(e, "response") and e.response is not None:
            try:
                err_detail += " | response: " + (e.response.text or "")[:200]
            except Exception:
                pass
        logger.warning("Slack webhook failed for ticket %s: %s", ticket_id, err_detail)
