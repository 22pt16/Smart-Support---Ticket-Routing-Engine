"""
Milestone 3 Worker:
- Background processing
- Deduplication
- Status tracking
"""

import threading
import time
from queue_store import get_next

# -------------------------
# GLOBAL STORES
# -------------------------

TICKET_STATUS = {}        # ticket_id -> status
MASTER_INCIDENTS = {}     # issue_key -> master_ticket_id

_worker_running = False


# -------------------------
# DEDUP KEY GENERATOR
# -------------------------

def generate_issue_key(ticket: dict) -> str:
    description = ticket.get("description", "").lower().strip()
    return description[:50]


# -------------------------
# WORKER LOOP
# -------------------------

def worker_loop():
    global _worker_running
    _worker_running = True

    print("Worker started...")

    while _worker_running:
        ticket = get_next()

        if ticket:
            ticket_id = ticket["ticket_id"]
            issue_key = generate_issue_key(ticket)

            # ----- DEDUP CHECK -----
            if issue_key in MASTER_INCIDENTS:
                master_id = MASTER_INCIDENTS[issue_key]
                TICKET_STATUS[ticket_id] = f"duplicate_of_{master_id}"
                print(f"{ticket_id} is duplicate of {master_id}")
                continue
            else:
                MASTER_INCIDENTS[issue_key] = ticket_id

            # ----- PROCESS -----
            TICKET_STATUS[ticket_id] = "processing"
            print(f"Processing {ticket_id}")

            time.sleep(2)

            TICKET_STATUS[ticket_id] = "completed"
            print(f"Completed {ticket_id}")

        else:
            time.sleep(8)


# -------------------------
# START WORKER
# -------------------------

def start_worker():
    thread = threading.Thread(target=worker_loop, daemon=True)
    thread.start()