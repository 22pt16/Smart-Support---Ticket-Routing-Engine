"""MVR REST API: ticket submission (202 Accepted) and queue access."""

import asyncio
import time
from typing import List

from fastapi import FastAPI, HTTPException

from broker import (
    acquire_submit_lock_async,
    add_to_all_ids_async,
    enqueue_async,
    generate_ticket_id,
    get_next_ready_ticket_sync,
    get_status_async,
    list_queue_from_redis_async,
    release_submit_lock_async,
    set_status_async,
)
from models import (
    TicketAcceptedResponse,
    TicketCreate,
    TicketItem,
    TicketStatusResponse,
)

app = FastAPI(title="MVR Ticket Router", version="2.0.0")


@app.post("/tickets", response_model=TicketAcceptedResponse, status_code=202)
async def create_ticket(payload: TicketCreate) -> TicketAcceptedResponse:
    """Accept a ticket, enqueue to broker, return 202 Accepted immediately."""
    max_retries = 10
    for attempt in range(max_retries):
        acquired = await acquire_submit_lock_async()
        if not acquired:
            await asyncio.sleep(0.05 * (attempt + 1))
            continue
        try:
            ticket_id = payload.ticket_id or generate_ticket_id()
            text = payload.combined_text()
            created_at = time.time()
            message = {
                "ticket_id": ticket_id,
                "subject": payload.subject,
                "body": payload.body,
                "description": payload.description,
                "combined_text": text,
                "created_at": created_at,
            }
            await set_status_async(
                ticket_id,
                {
                    "ticket_id": ticket_id,
                    "status": "pending",
                    "subject": payload.subject,
                    "body": payload.body,
                    "description": payload.description,
                    "created_at": created_at,
                },
            )
            await add_to_all_ids_async(ticket_id)
            await enqueue_async(message)
            status_url = f"/tickets/{ticket_id}/status"
            return TicketAcceptedResponse(
                ticket_id=ticket_id,
                status="accepted",
                status_url=status_url,
            )
        finally:
            await release_submit_lock_async()
    raise HTTPException(status_code=503, detail="Could not acquire submit lock")


@app.get("/tickets/{ticket_id}/status", response_model=TicketStatusResponse)
async def get_ticket_status(ticket_id: str) -> TicketStatusResponse:
    """Return current status: pending | processing | completed."""
    data = await get_status_async(ticket_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return TicketStatusResponse(**data)


@app.get("/queue", response_model=List[TicketItem])
async def list_queue() -> List[TicketItem]:
    """Return all tickets from Redis, sorted by urgency (completed) then pending/processing."""
    items = await list_queue_from_redis_async()
    out = []
    for d in items:
        u = d.get("urgency_label") or ("high" if (d.get("urgency_score") or 0) >= 0.5 else "low")
        out.append(
            TicketItem(
                ticket_id=d["ticket_id"],
                category=d.get("category") or "Technical",
                urgency=u,
                urgency_score=d.get("urgency_score"),
                subject=d.get("subject"),
                body=d.get("body"),
                description=d.get("description"),
                created_at=d.get("created_at") or 0,
            )
        )
    return out


@app.get("/tickets/next", response_model=TicketItem)
async def get_next_ticket() -> TicketItem:
    """Dequeue and return the highest-urgency completed ticket. 404 if none ready."""
    ticket = await asyncio.to_thread(get_next_ready_ticket_sync)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Queue is empty")
    u = ticket.get("urgency_label") or ("high" if (ticket.get("urgency_score") or 0) >= 0.5 else "low")
    return TicketItem(
        ticket_id=ticket["ticket_id"],
        category=ticket.get("category") or "Technical",
        urgency=u,
        urgency_score=ticket.get("urgency_score"),
        subject=ticket.get("subject"),
        body=ticket.get("body"),
        description=ticket.get("description"),
        created_at=ticket.get("created_at") or 0,
    )


@app.get("/health")
def health() -> dict:
    """Health check."""
    return {"status": "ok"}
