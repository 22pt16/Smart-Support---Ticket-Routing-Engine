"""In-memory priority queue for tickets using heapq."""

import heapq
import time
from typing import Any, Dict, List, Optional, Tuple

# Min-heap: we store (-urgency, timestamp, ticket_id, payload) so higher urgency and earlier time come first.
_heap: List[Tuple[Tuple[int, float, str], Dict[str, Any]]] = []
_counter = 0


def _next_id() -> str:
    global _counter
    _counter += 1
    return f"ticket-{int(time.time() * 1000)}-{_counter}"


def add_ticket(
    ticket_id: Optional[str],
    payload: Dict[str, Any],
    urgency_score: int,
) -> str:
    """Add a ticket to the queue. Returns the ticket_id used."""
    tid = ticket_id or _next_id()
    ts = time.time()
    # Sort key: higher urgency first (negate), then earlier time
    key = (-urgency_score, ts, tid)
    entry = (key, {**payload, "ticket_id": tid, "created_at": ts})
    heapq.heappush(_heap, entry)
    return tid


def get_next() -> Optional[Dict[str, Any]]:
    """Dequeue and return the highest-priority ticket, or None if empty."""
    if not _heap:
        return None
    _, payload = heapq.heappop(_heap)
    return payload


def peek_queue() -> List[Dict[str, Any]]:
    """Return current queue contents in priority order (no mutation)."""
    ordered = sorted(_heap, key=lambda x: x[0])
    return [payload for _, payload in ordered]


def queue_size() -> int:
    """Return number of tickets in the queue."""
    return len(_heap)
