
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


class PmtemplateFrequency(str, Enum):

    weekly = "weekly"
    monthly = "monthly"
    quaterly = "quaterly"
    annualy = "annualy"


class PmtemplateStatus(str, Enum):

    active = "active"
    inactive = "inactive"
    completed = "completed"


class ServiceRequestStatus (str, Enum):

    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    close = "close"


class ServiceRequestCategory (str, Enum):

    security = "security"
    utilities = "utilities"
    housekeeping = "housekeeping"
    maintenance = "maintenance"
    electrical = "electrical"


class ServiceRequestRequesterKind(str, Enum):

    resident = "resident"
    merchant = "merchant"



class ServiceRequestPriority(str, Enum):

    low = "low"
    medium = "medium"
    high = "high"


class ServiceRequestchannel (str, Enum):

    phone = "phone"
    portal = "portal"
    email = "email"


class AssetStatus (str, Enum):

    active = "active"
    inactive = "inactive"
