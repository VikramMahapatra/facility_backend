import enum
from enum import Enum

class TicketStatus(enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    RETURNED = "returned"
    REOPENED = "reopened"
    ESCALATED = "escalated"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"


class AutoAssignRoleEnum(str, Enum):
    TECHNICIAN = "technician"
    ADMIN = "admin"
    MANAGER = "manager"
    AGENT = "agent"
    SUPPORT = "support"


class StatusEnum(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"