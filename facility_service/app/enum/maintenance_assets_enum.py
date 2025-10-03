
from enum import Enum


class WorkOrderStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    completed = "completed"


class WorkOrderPriority(str, Enum):

    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"
