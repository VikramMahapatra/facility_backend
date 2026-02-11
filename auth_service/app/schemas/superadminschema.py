from typing import Optional
from shared.core.schemas import CommonQueryParams


class OrgApprovalRequest(CommonQueryParams):
    status: Optional[str] = None
