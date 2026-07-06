from typing import Optional
from pydantic import BaseModel
from shared.core.schemas import CommonQueryParams


class OrgApprovalRequest(CommonQueryParams):
    status: Optional[str] = None

class OrgRejectRequest(BaseModel):
    rejection_reason: str