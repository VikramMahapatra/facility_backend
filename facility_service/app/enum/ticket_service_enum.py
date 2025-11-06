import enum


class TicketStatus(enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    RETURNED = "returned"
    REOPENED = "reopened"
    ESCALATED = "escalated"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
