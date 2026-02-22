# deduplication.py

from collections import deque
from datetime import datetime, timedelta
from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer("all-MiniLM-L6-v2")

recent_tickets = deque()

def is_flash_flood(ticket_id, text):
    embedding = model.encode(text, normalize_embeddings=True)
    now = datetime.utcnow()

    # Remove tickets older than 5 minutes
    while recent_tickets and recent_tickets[0]["time"] < now - timedelta(minutes=5):
        recent_tickets.popleft()

    similar_count = 0

    for t in recent_tickets:
        similarity = np.dot(embedding, t["embedding"])
        if similarity > 0.9:
            similar_count += 1

    recent_tickets.append({
        "id": ticket_id,
        "embedding": embedding,
        "time": now
    })

    return similar_count >= 10