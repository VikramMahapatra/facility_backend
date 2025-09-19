from fastapi import FastAPI
from shared.database import facility_engine, Base
from .router import (
    orgs_router,
    space_groups_router,
    space_group_members_router,
    vendor_router,
    contracts_router,
    inventory_items_router,
    inventory_stocks_router,
    purchase_orders_router,
    purchase_order_lines_router,
    commercial_partners_router,
    asset_category_router,
    assets_router,
)
from .router.space_sites.sites_router import router as sites_router
from .router.leasing_tenants import lease_charges_router, leases_router
from .router.space_sites import (spaces_router)
from .router.overview import (dashboard_router,analytics_router)

app = FastAPI(title="Facility Service API")

# Create all tables
Base.metadata.create_all(bind=facility_engine)

# Include routers
app.include_router(orgs_router.router)
app.include_router(spaces_router.router) #----------------added space overview
app.include_router(space_groups_router.router)
app.include_router(space_group_members_router.router)
app.include_router(vendor_router.router)
app.include_router(contracts_router.router)
app.include_router(inventory_items_router.router)
app.include_router(inventory_stocks_router.router)
app.include_router(purchase_orders_router.router)
app.include_router(purchase_order_lines_router.router)
app.include_router(commercial_partners_router.router)
app.include_router(leases_router.router)
app.include_router(lease_charges_router.router)
app.include_router(asset_category_router.router)
app.include_router(assets_router.router)
app.include_router(sites_router)
app.include_router(dashboard_router.router)
app.include_router(analytics_router.router)
