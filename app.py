"""
Production FastAPI App (Milestone 2 + 3)
- Async Redis broker
- 202 Accepted
- Atomic submit lock
- No in-memory queue
"""

import time
from fastapi import FastAPI, HTTPException
from models import (
    TicketCreate,
    TicketAcceptedResponse,
    TicketStatusResponse,
    TicketItem,
)
from broker import (
    generate_ticket_id,
    acquire_submit_lock_async,
    release_submit_lock_async,
    enqueue_async,
    set_status_async,
    get_status_async,
    add_to_all_ids_async,
    list_queue_from_redis_async,
    get_next_ready_ticket_sync,
)

app = FastAPI(title="Smart-Support Ticket Routing Engine")


# -------------------------
# Health Check
# -------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


# -------------------------
# Submit Ticket (Async)
# -------------------------

@app.post("/tickets", response_model=TicketAcceptedResponse, status_code=202)
async def submit_ticket(ticket: TicketCreate):
    combined_text = ticket.combined_text()

    # Acquire atomic submit lock
    locked = await acquire_submit_lock_async()
    if not locked:
        raise HTTPException(status_code=429, detail="System busy, retry")

    try:
        ticket_id = ticket.ticket_id or generate_ticket_id()
        created_at = time.time()

        # Initial status
        status_payload = {
            "ticket_id": ticket_id,
            "status": "pending",
            "subject": ticket.subject,
            "body": ticket.body,
            "description": ticket.description,
            "created_at": created_at,
        }

        await set_status_async(ticket_id, status_payload)
        await add_to_all_ids_async(ticket_id)

        # Enqueue message for worker
        await enqueue_async({
            "ticket_id": ticket_id,
            "subject": ticket.subject,
            "body": ticket.body,
            "description": ticket.description,
            "combined_text": combined_text,
            "created_at": created_at,
        })

    finally:
        await release_submit_lock_async()

    return TicketAcceptedResponse(
        ticket_id=ticket_id,
        status="accepted",
        status_url=f"/tickets/{ticket_id}/status",
    )


# -------------------------
# Ticket Status
# -------------------------

@app.get("/tickets/{ticket_id}/status", response_model=TicketStatusResponse)
async def get_ticket_status(ticket_id: str):
    status = await get_status_async(ticket_id)
    if not status:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return status


# -------------------------
# View Queue
# -------------------------

@app.get("/queue")
async def view_queue():
    return await list_queue_from_redis_async()


# -------------------------
# Get Next Highest Urgency Ticket
# -------------------------

@app.get("/tickets/next")
async def get_next_ticket():
    ticket = get_next_ready_ticket_sync()
    if not ticket:
        raise HTTPException(status_code=404, detail="No ready tickets")
    return ticket