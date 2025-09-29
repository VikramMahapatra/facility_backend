from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared.database import facility_engine, Base
from .router import (
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
from .router.leasing_tenants import lease_charges_router, leases_router, tenants_router
from .router.space_sites import (
    orgs_router, 
    sites_router,
    space_group_members_router, 
    space_groups_router, 
    spaces_router ,
    building_block_router,
    space_filter_router)
from .router.overview import (dashboard_router,analytics_router)
from .router.financials import (invoice_router, tax_codes_router)
from .router.crm import contact_router
from .models import (
    asset_category_models, assets_models, commercial_partners, contracts, inventory_items, inventory_stocks,
    purchase_order_lines, purchase_orders, vendors
)
from .models.space_sites import buildings, orgs, sites, space_filter_models, space_group_members, space_groups
from .models.leasing_tenants import leases, lease_charges, tenants
from .models.leasing_tenants import leases, lease_charges
from .models.financials import invoices
from .models.crm import contacts, companies
app = FastAPI(title="Facility Service API")

# Create all tables
Base.metadata.create_all(bind=facility_engine)

# Allow requests from your React app
origins = [
    "http://localhost:8080",
    "http://127.0.0.1:8002"
    # Add other origins if deploying later
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # or ["*"] to allow all origins (not recommended for production)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(orgs_router.router)
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
app.include_router(asset_category_router.router)
app.include_router(assets_router.router)
app.include_router(sites_router.router)
app.include_router(dashboard_router.router)
app.include_router(analytics_router.router)
app.include_router(building_block_router.router)
app.include_router(space_filter_router.router)
app.include_router(tenants_router.router)
app.include_router(invoice_router.router)
app.include_router(contact_router.router)
app.include_router(tax_codes_router.router)