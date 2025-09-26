from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from ...models.leasing_tenants.tenants import Tenant
from ...schemas.tenants_schemas import TenantCreate
from ...models.space_sites.sites import Site
# ---------- Create Tenant ----------
def get_tenant(db: Session, tenant_id: str):
    return db.query(Tenant).filter(Tenant.id == tenant_id).first()

