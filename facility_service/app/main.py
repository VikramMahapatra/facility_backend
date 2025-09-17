from fastapi import FastAPI
from app.core.databases import engine, Base
from app.router import (
    orgs_router,
    site_router,
    spaces_router,
    space_groups_router,
    space_group_members_router,
    vendor_router,
    contracts_router,
    inventory_items_router,
    inventory_stocks_router,
    purchase_orders_router,
    purchase_order_lines_router,
    commercial_partners_router,
    leases_router,
    lease_charges_router,
)

app = FastAPI(title="Property / Inventory SaaS API")

# Create DB tables
Base.metadata.create_all(bind=engine)

# Include routers
app.include_router(orgs_router.router)
app.include_router(site_router.router)
app.include_router(spaces_router.router)
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
