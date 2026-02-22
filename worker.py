"""
Milestone 3 Production Worker (Redis-Based)
- Async broker (Redis)
- Circuit breaker
- Semantic deduplication
- Skill-based routing
- Slack webhook
"""

import time
import logging
from typing import Optional

from broker import (
    dequeue_sync,
    acquire_processing_lock,
    release_processing_lock,
    set_status_sync,
    add_to_ready_queue_sync,
)
from ml_models import predict_category, predict_urgency_score
from classifier import classify_category, get_urgency
from circuit_breaker import breaker
from deduplication import is_flash_flood
from agents import select_agent, agents
from webhook import notify_high_urgency

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def process_ticket(ticket: dict) -> None:
    ticket_id = ticket["ticket_id"]
    text = ticket.get("combined_text") or ticket.get("description") or ""

    # Prevent duplicate processing
    if not acquire_processing_lock(ticket_id):
        logger.info("Skipping %s (already processing)", ticket_id)
        return

    try:
        # -------------------------
        # Set status: processing
        # -------------------------
        set_status_sync(ticket_id, {
            **ticket,
            "status": "processing"
        })

        # -------------------------
        # CIRCUIT BREAKER + ML
        # -------------------------
        start = time.time()

        if breaker.allow():
            category = predict_category(text)
            urgency_score = predict_urgency_score(text)
            latency_ms = (time.time() - start) * 1000
            breaker.record(latency_ms)
            logger.info("ML latency %.2f ms (state=%s)", latency_ms, breaker.state)
        else:
            logger.warning("Circuit OPEN → using baseline model")
            category = classify_category(text)
            urgency_score = float(get_urgency(text))

        # -------------------------
        # Semantic Deduplication
        # -------------------------
        flood = is_flash_flood(ticket_id, text)

        if flood:
            logger.warning("FLASH FLOOD detected → creating master incident")
            status_payload = {
                **ticket,
                "status": "master_incident",
                "category": category,
                "urgency_score": urgency_score,
                "urgency_label": "high" if urgency_score > 0.5 else "low",
            }
            set_status_sync(ticket_id, status_payload)
            return

        # -------------------------
        # Skill-Based Routing
        # -------------------------
        agent = select_agent(category)

        if agent:
            agents[agent]["load"] += 1
            assigned_agent = agent
        else:
            assigned_agent = "unassigned"

        # -------------------------
        # Completed Status
        # -------------------------
        status_payload = {
            **ticket,
            "status": "completed",
            "category": category,
            "urgency_score": urgency_score,
            "urgency_label": "high" if urgency_score > 0.5 else "low",
            "assigned_agent": assigned_agent,
        }

        set_status_sync(ticket_id, status_payload)

        # Add to ready queue
        add_to_ready_queue_sync(ticket_id, urgency_score)

        # Slack webhook
        notify_high_urgency(ticket_id, urgency_score, category, text)

        logger.info("Completed %s → Agent: %s", ticket_id, assigned_agent)

    finally:
        release_processing_lock(ticket_id)


def worker_loop():
    logger.info("Worker started (Redis-based)...")

    while True:
        ticket = dequeue_sync(timeout=5)

        if ticket:
            process_ticket(ticket)
        else:
            time.sleep(1)


if __name__ == "__main__":
    worker_loop()