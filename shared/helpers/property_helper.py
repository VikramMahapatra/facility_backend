
from requests import Session
from sqlalchemy.orm import joinedload
from facility_service.app.models.common.staff_sites import StaffSite
from facility_service.app.models.leasing_tenants.leases import Lease
from facility_service.app.models.leasing_tenants.tenants import Tenant
from facility_service.app.models.space_sites.buildings import Building
from facility_service.app.models.space_sites.sites import Site
from facility_service.app.models.space_sites.spaces import Space
from shared.core.schemas import UserToken
from shared.utils.enums import UserAccountType

def get_allowed_sites(db: Session, user: UserToken):
    results = []
    account_type = user.account_type.lower()

    if account_type == UserAccountType.TENANT:
        tenant = (
            db.query(Tenant)
            .options(
                joinedload(Tenant.space).joinedload(Space.site),
                joinedload(Tenant.leases)
                .joinedload(Lease.space)
                .joinedload(Space.site),
            )
            .filter(Tenant.user_id == user.user_id)
            .first()
        )

        if not tenant:
            return {"sites": []}

        seen_site_ids = set()

        # Registered space site
        if tenant.space and tenant.space.site:
            site = tenant.space.site
            results.append({
                "site_id": site.id,
                "site_name": site.name,
                "is_primary": True
            })
            seen_site_ids.add(site.id)

        #  Leased space sites
        for lease in tenant.leases:
            space = lease.space
            if space and space.site and space.site.id not in seen_site_ids:
                results.append({
                    "site_id": space.site.id,
                    "site_name": space.site.name,
                    "is_primary": False
                })
                seen_site_ids.add(space.site.id)

    else:
        sites = (
            db.query(Site)
            .filter(Site.org_id == user.org_id)
            .all()
        )
        results = [
            {"site_id": s.id, "site_name": s.name, "is_primary": True}
            for s in sites
        ]

    return results


def get_allowed_spaces(db: Session, user: UserToken):
    results = []
    account_type = user.account_type.lower()

    if account_type == UserAccountType.TENANT:
        tenant = (
            db.query(Tenant)
            .options(
                joinedload(Tenant.space).joinedload(Space.site),
                joinedload(Tenant.space).joinedload(Space.building),
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
            return {"spaces": []}

        seen_space_ids = set()

        #  Registered space
        if tenant.space:
            results.append({
                "space_id": tenant.space.id,
                "space_name": tenant.space.name,
                "site_id": tenant.space.site_id,
                "building_name": tenant.space.building.name if tenant.space.building else None,
                "is_primary": True
            })
            seen_space_ids.add(tenant.space.id)

        #  Leased spaces
        for lease in tenant.leases:
            space = lease.space
            if space and space.id not in seen_space_ids:
                results.append({
                    "space_id": space.id,
                    "space_name": space.name,
                    "site_id": space.site_id,
                    "building_name": space.building.name if space.building else None,
                    "is_primary": False
                })
                seen_space_ids.add(space.id)

    else:
        # Non-tenant logic stays same (org/admin)
        spaces = db.query(Space).all()
        results = [
            {
                "space_id": s.id,
                "space_name": s.name,
                "site_id": s.site_id,
                "is_primary": True
            }
            for s in spaces
        ]

    return results


def get_allowed_buildings(db: Session, user: UserToken):
    results = []
    account_type = user.account_type.lower()

    if account_type == UserAccountType.TENANT:
        tenant = (
            db.query(Tenant)
            .options(
                joinedload(Tenant.space).joinedload(Space.building),
                joinedload(Tenant.leases)
                .joinedload(Lease.space)
                .joinedload(Space.building),
            )
            .filter(Tenant.user_id == user.user_id)
            .first()
        )

        if not tenant:
            return {"buildings": []}

        seen_building_ids = set()

        #  Registered space building
        if tenant.space and tenant.space.building:
            building = tenant.space.building
            results.append({
                "building_id": building.id,
                "building_name": building.name,
                "is_primary": True
            })
            seen_building_ids.add(building.id)

        # Leased space buildings
        for lease in tenant.leases:
            space = lease.space
            if space and space.building and space.building.id not in seen_building_ids:
                results.append({
                    "building_id": space.building.id,
                    "building_name": space.building.name,
                    "is_primary": False
                })
                seen_building_ids.add(space.building.id)

    else:
        buildings = db.query(Building).all()
        results = [
            {
                "building_id": b.id,
                "building_name": b.name,
                "is_primary": True
            }
            for b in buildings
        ]

    return results
