"""Pydantic models for ticket API request and response."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

Category = Literal["Billing", "Technical", "Legal"]
UrgencyLabel = Literal["low", "high"]


class TicketCreate(BaseModel):
    """Incoming ticket payload for POST /tickets."""

    subject: Optional[str] = None
    body: Optional[str] = None
    description: Optional[str] = None
    ticket_id: Optional[str] = None

    @model_validator(mode="after")
    def at_least_one_text_field(self) -> "TicketCreate":
        if not (self.subject or self.body or self.description):
            raise ValueError("At least one of subject, body, or description is required")
        return self

    def combined_text(self) -> str:
        """Single text used for classification and urgency."""
        parts = [self.subject or "", self.body or "", self.description or ""]
        return " ".join(p for p in parts if p).strip()


class TicketQueuedResponse(BaseModel):
    """Response after submitting a ticket."""

    ticket_id: str
    category: Category
    urgency: UrgencyLabel
    message: str = "queued"


class TicketItem(BaseModel):
    """A ticket as returned from the queue (e.g. GET /queue or GET /tickets/next)."""

    ticket_id: str
    category: Category
    urgency: UrgencyLabel
    subject: Optional[str] = None
    body: Optional[str] = None
    description: Optional[str] = None
    created_at: float = Field(description="Unix timestamp")
