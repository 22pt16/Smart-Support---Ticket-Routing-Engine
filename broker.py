"""Redis broker: queue, locks, and ticket status."""

import json
import uuid
from typing import Any, Dict, Optional

from config import (
    ALL_IDS_KEY,
    PROCESSING_LOCK_PREFIX,
    PROCESSING_LOCK_TTL,
    QUEUE_NAME,
    READY_QUEUE_KEY,
    STATUS_PREFIX,
    SUBMIT_LOCK_KEY,
    SUBMIT_LOCK_TTL,
)

# Sync Redis (for worker and for lock/enqueue from API when run in executor)
try:
    import redis
    _sync_client: Optional[redis.Redis] = None

    def get_sync_redis() -> redis.Redis:
        global _sync_client
        if _sync_client is None:
            from config import REDIS_URL
            _sync_client = redis.from_url(REDIS_URL, decode_responses=True)
        return _sync_client
except ImportError:
    def get_sync_redis():  # type: ignore
        raise RuntimeError("redis package required: pip install redis")

# Async Redis (for FastAPI)
try:
    from redis.asyncio import Redis
    _async_client: Optional[Redis] = None

    def get_async_redis() -> Redis:
        global _async_client
        if _async_client is None:
            from config import REDIS_URL
            _async_client = Redis.from_url(REDIS_URL, decode_responses=True)
        return _async_client
except ImportError:
    def get_async_redis():  # type: ignore
        raise RuntimeError("redis package required: pip install redis")


def generate_ticket_id() -> str:
    return f"ticket-{uuid.uuid4().hex[:16]}"


# --- Sync API (used by worker and by app via run_in_executor) ---

def acquire_submit_lock() -> bool:
    """Acquire global submit lock. Returns True if acquired."""
    r = get_sync_redis()
    return bool(r.set(SUBMIT_LOCK_KEY, "1", nx=True, ex=SUBMIT_LOCK_TTL))


def release_submit_lock() -> None:
    get_sync_redis().delete(SUBMIT_LOCK_KEY)


def enqueue_sync(payload: Dict[str, Any]) -> None:
    """Push ticket payload to the queue (sync)."""
    get_sync_redis().lpush(QUEUE_NAME, json.dumps(payload))


def dequeue_sync(timeout: int = 5) -> Optional[Dict[str, Any]]:
    """Blocking pop from queue. Returns None if timeout with no message."""
    r = get_sync_redis()
    result = r.brpop(QUEUE_NAME, timeout=timeout)
    if result is None:
        return None
    _, raw = result
    return json.loads(raw)


def set_status_sync(ticket_id: str, data: Dict[str, Any]) -> None:
    key = f"{STATUS_PREFIX}{ticket_id}"
    get_sync_redis().set(key, json.dumps(data), ex=86400 * 7)  # 7 days TTL


def get_status_sync(ticket_id: str) -> Optional[Dict[str, Any]]:
    key = f"{STATUS_PREFIX}{ticket_id}"
    raw = get_sync_redis().get(key)
    if raw is None:
        return None
    return json.loads(raw)


def acquire_processing_lock(ticket_id: str) -> bool:
    """Acquire per-ticket processing lock. Returns True if acquired."""
    r = get_sync_redis()
    return bool(r.set(f"{PROCESSING_LOCK_PREFIX}{ticket_id}", "1", nx=True, ex=PROCESSING_LOCK_TTL))


def release_processing_lock(ticket_id: str) -> None:
    get_sync_redis().delete(f"{PROCESSING_LOCK_PREFIX}{ticket_id}")


def add_to_all_ids_sync(ticket_id: str) -> None:
    get_sync_redis().sadd(ALL_IDS_KEY, ticket_id)


def add_to_ready_queue_sync(ticket_id: str, urgency_score: float) -> None:
    """Add completed ticket to ready queue (for GET /tickets/next). Score = S, higher first."""
    get_sync_redis().zadd(READY_QUEUE_KEY, {ticket_id: urgency_score})


def pop_next_ready_sync() -> Optional[str]:
    """Pop and return ticket_id with highest urgency_score, or None if empty."""
    r = get_sync_redis()
    results = r.zrevrange(READY_QUEUE_KEY, 0, 0)
    if not results:
        return None
    ticket_id = results[0]
    r.zrem(READY_QUEUE_KEY, ticket_id)
    return ticket_id


def list_all_ticket_ids_sync() -> list:
    return list(get_sync_redis().smembers(ALL_IDS_KEY))


# --- Async API (for FastAPI) ---

async def acquire_submit_lock_async() -> bool:
    r = get_async_redis()
    return bool(await r.set(SUBMIT_LOCK_KEY, "1", nx=True, ex=SUBMIT_LOCK_TTL))


async def release_submit_lock_async() -> None:
    await get_async_redis().delete(SUBMIT_LOCK_KEY)


async def enqueue_async(payload: Dict[str, Any]) -> None:
    r = get_async_redis()
    await r.lpush(QUEUE_NAME, json.dumps(payload))


async def set_status_async(ticket_id: str, data: Dict[str, Any]) -> None:
    r = get_async_redis()
    key = f"{STATUS_PREFIX}{ticket_id}"
    await r.set(key, json.dumps(data), ex=86400 * 7)


async def get_status_async(ticket_id: str) -> Optional[Dict[str, Any]]:
    r = get_async_redis()
    key = f"{STATUS_PREFIX}{ticket_id}"
    raw = await r.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def add_to_all_ids_async(ticket_id: str) -> None:
    await get_async_redis().sadd(ALL_IDS_KEY, ticket_id)


async def list_queue_from_redis_async() -> list:
    """List all tickets with status, sorted by completed (by -S, created_at) then pending/processing."""
    r = get_async_redis()
    ids = list(await r.smembers(ALL_IDS_KEY))
    out = []
    for tid in ids:
        raw = await r.get(f"{STATUS_PREFIX}{tid}")
        if raw:
            out.append(json.loads(raw))
    # Sort: completed first by -urgency_score, then created_at; then pending/processing by created_at
    def sort_key(x):
        s = x.get("status")
        score = x.get("urgency_score") is not None and float(x.get("urgency_score", 0)) or 0
        created = x.get("created_at") or 0
        if s == "completed":
            return (0, -score, created)
        return (1, 0, created)
    out.sort(key=sort_key)
    return out


def get_next_ready_ticket_sync() -> Optional[Dict[str, Any]]:
    """Pop highest-urgency ready ticket and return its status payload, or None."""
    ticket_id = pop_next_ready_sync()
    if ticket_id is None:
        return None
    return get_status_sync(ticket_id)
