from fastapi import FastAPI
from pydantic import BaseModel
from classifier import classify_category, get_urgency, get_urgency_label
from queue_store import add_ticket, peek_queue, queue_size
from worker import start_worker, TICKET_STATUS, MASTER_INCIDENTS

app = FastAPI()

# Start background worker
start_worker()


# -------------------------
# Request Model
# -------------------------

class TicketRequest(BaseModel):
    description: str


# -------------------------
# ROUTE: Submit Ticket
# -------------------------

@app.post("/tickets")
def submit_ticket(ticket: TicketRequest):

    category = classify_category(ticket.description)
    urgency_score = get_urgency(ticket.description)
    urgency_label = get_urgency_label(ticket.description)

    payload = {
        "description": ticket.description,
        "category": category,
        "urgency": urgency_label,
    }

    ticket_id = add_ticket(None, payload, urgency_score)

    TICKET_STATUS[ticket_id] = "queued"

    return {
        "ticket_id": ticket_id,
        "category": category,
        "urgency": urgency_label,
        "status": "queued"
    }


# -------------------------
# ROUTE: Get Ticket Status
# -------------------------

@app.get("/tickets/{ticket_id}")
def get_ticket_status(ticket_id: str):
    status = TICKET_STATUS.get(ticket_id, "not_found")
    return {"ticket_id": ticket_id, "status": status}


# -------------------------
# ROUTE: View Queue
# -------------------------

@app.get("/queue")
def view_queue():
    return {
        "size": queue_size(),
        "tickets": peek_queue()
    }


# -------------------------
# ROUTE: Master Incidents
# -------------------------

@app.get("/incidents")
def view_master_incidents():
    return MASTER_INCIDENTS