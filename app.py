"""MVR REST API: ticket submission and queue access."""

from typing import List

from fastapi import FastAPI, HTTPException

from classifier import classify_category, get_urgency, get_urgency_label
from models import TicketCreate, TicketItem, TicketQueuedResponse
from queue_store import add_ticket, get_next, peek_queue

app = FastAPI(title="MVR Ticket Router", version="1.0.0")


@app.post("/tickets", response_model=TicketQueuedResponse, status_code=201)
def create_ticket(payload: TicketCreate) -> TicketQueuedResponse:
    """Accept a ticket JSON, classify it, set urgency, and enqueue."""
    text = payload.combined_text()
    category = classify_category(text)
    urgency_score = get_urgency(text)
    urgency_label = get_urgency_label(text)

    ticket_payload = {
        "category": category,
        "urgency": urgency_label,
        "subject": payload.subject,
        "body": payload.body,
        "description": payload.description,
    }
    ticket_id = add_ticket(payload.ticket_id, ticket_payload, urgency_score)

    return TicketQueuedResponse(
        ticket_id=ticket_id,
        category=category,
        urgency=urgency_label,
        message="queued",
    )


@app.get("/queue", response_model=List[TicketItem])
def list_queue() -> List[TicketItem]:
    """Return current queue in priority order (no dequeue)."""
    items = peek_queue()
    return [TicketItem(**item) for item in items]


@app.get("/tickets/next", response_model=TicketItem)
def get_next_ticket() -> TicketItem:
    """Dequeue and return the highest-priority ticket. 404 if queue empty."""
    ticket = get_next()
    if ticket is None:
        raise HTTPException(status_code=404, detail="Queue is empty")
    return TicketItem(**ticket)


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health check."""
    return {"status": "ok"}
