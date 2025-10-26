from operator import or_
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, and_, distinct, case
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from typing import Dict, Optional

from ...models.leasing_tenants.leases import Lease
from shared.schemas import UserToken

from ...models.leasing_tenants.tenants import Tenant
from ...models.space_sites.spaces import Space
from sqlalchemy.orm import joinedload


def get_home_spaces(db: Session, user: UserToken):
    tenant = (
        db.query(Tenant)
        .options(
            joinedload(Tenant.space)
            .joinedload(Space.site),
            joinedload(Tenant.space)
            .joinedload(Space.building),
            joinedload(Tenant.leases)
            .joinedload(Lease.space)
            .joinedload(Space.site),
            joinedload(Tenant.leases)
            .joinedload(Lease.space)
            .joinedload(Space.building),
        )
        .filter(Tenant.user_id == user.user_id)
        .first()
    )

    if not tenant:
        return []

    results = {}

    # ✅ 1. Registered space (always included)
    if tenant.space:
        results[tenant.space.id] = {
            "tenant_id": tenant.id,
            "space_id": tenant.space.id,
            "is_primary": True,
            "space_name": tenant.space.name,
            "site_name": tenant.space.site.name if tenant.space.site else None,
            "building_name": tenant.space.building.name if tenant.space.building else None,
            "account_type": user.account_type,
            "status": user.status,
        }

    # ✅ 2. Leased spaces
    for lease in tenant.leases:
        space = lease.space
        if not space:
            continue
        # Avoid duplicates (registered space may also be leased)
        if space.id not in results:
            results[space.id] = {
                "tenant_id": tenant.id,
                "space_id": space.id,
                "is_primary": False,
                "space_name": space.name,
                "site_name": space.site.name if space.site else None,
                "building_name": space.building.name if space.building else None,
                "account_type": user.account_type,
                "status": user.status,
            }

    return list(results.values())
