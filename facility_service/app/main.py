from .models.energy_iot import meters, meter_readings
from .models.parking_access import parking_zones, parking_pass, access_events, visitors
from .models.crm import contacts, companies
from .models.financials import invoices
from .models.leasing_tenants import commercial_partners, leases, lease_charges, tenants
from .models.space_sites import buildings, orgs, sites, space_filter_models, space_group_members, space_groups
from .models import (
    purchase_order_lines, purchase_orders
)
from .router.common import export_router
from .router.procurement import contracts_router, vendor_router
from .models.procurement import contracts, vendors
from .models.maintenance_assets import asset_category, assets, inventory_items, inventory_stocks
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared.database import facility_engine, Base

from .router.access_control import user_management_router, role_management_router, role_policies_router
from .router import (
    purchase_orders_router,
    purchase_order_lines_router,
    commercial_partners_router,
)
from .router.leasing_tenants import lease_charges_router, leases_router, tenants_router
from .router.space_sites import (
    orgs_router,
    sites_router,
    space_group_members_router,
    space_groups_router,
    spaces_router,
    building_block_router,
    space_filter_router)
from .router.overview import (dashboard_router, analytics_router)
from .router.financials import (
    invoice_router, tax_codes_router, revenue_router)
from .router.crm import contact_router
from .router.maintenance_assets import (
    asset_category_router, assets_router, inventory_items_router, inventory_stocks_router, pm_template_router, service_request_router, work_order_router)
from .router.parking_access import parking_zones_router, access_events_router, visitors_router
from .router.hospitality import bookings_router, rate_plans_router, housekeeping_tasks_router
from .router.overview import analytics_router, dashboard_router
from .router.energy_iot import meter_readings_router, meters_router, consumption_report_router


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
    # or ["*"] to allow all origins (not recommended for production)
    allow_origins=origins,
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
app.include_router(sites_router.router)
app.include_router(dashboard_router.router)
app.include_router(analytics_router.router)
app.include_router(building_block_router.router)
app.include_router(space_filter_router.router)
app.include_router(tenants_router.router)
app.include_router(invoice_router.router)
app.include_router(contact_router.router)
app.include_router(tax_codes_router.router)
app.include_router(assets_router.router)
app.include_router(parking_zones_router.router)
app.include_router(service_request_router.router)
app.include_router(access_events_router.router)
app.include_router(visitors_router.router)
app.include_router(pm_template_router.router)
app.include_router(work_order_router.router)
app.include_router(bookings_router.router)
app.include_router(rate_plans_router.router)
app.include_router(housekeeping_tasks_router.router)
app.include_router(meters_router.router)
app.include_router(meter_readings_router.router)
app.include_router(dashboard_router.router)
app.include_router(revenue_router.router)
app.include_router(consumption_report_router.router)
app.include_router(user_management_router.router)
app.include_router(export_router.router)
app.include_router(role_management_router.router)
app.include_router(role_policies_router.router)
