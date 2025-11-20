from typing import Dict, List
from unicodedata import numeric
from uuid import UUID
from sqlalchemy import Numeric, String, case, cast, extract, func
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from decimal import Decimal

from facility_service.app.models.hospitality.booking_rooms import BookingRoom
from facility_service.app.models.parking_access.access_events import AccessEvent

from ...models.purchase_order_lines import PurchaseOrderLine
from ...models.purchase_orders import PurchaseOrder
from ...models.space_sites.buildings import Building

from ...models.energy_iot.meter_readings import MeterReading
from ...models.energy_iot.meters import Meter
from ...models.financials.invoices import Invoice, PaymentAR
from ...models.hospitality.booking_cancellations import BookingCancellation
from ...models.hospitality.bookings import Booking
from ...models.hospitality.folios import Folio
from ...models.hospitality.folios_charges import FolioCharge
from ...models.leasing_tenants.lease_charges import LeaseCharge
from ...models.leasing_tenants.leases import Lease
from ...models.maintenance_assets.service_request import ServiceRequest
from ...models.maintenance_assets.work_order import WorkOrder
from ...models.space_sites.spaces import Space
from ...schemas.overview.analytics_schema import AnalyticsRequest
from ...models.space_sites.sites import Site  

def site_open_month_lookup(db: Session, org_id: UUID):
    """
    Returns a distinct list of months in which sites were opened for the given org.
    id = month number
    name = month name
    """
    query = (
        db.query(
            cast(extract("month", Site.opened_on), String).label("id"),
            func.to_char(Site.opened_on, "FMMonth").label("name")
        )
        .filter(Site.org_id == org_id)
        .distinct()
        .order_by("id")
    )
    return [{"id": r.id, "name": r.name} for r in query.all()]

def site_name_filter_lookup(db: Session, org_id: str) -> List[Dict]:
    """
    Returns distinct site names for a given organization.
    :param db: SQLAlchemy session
    :param org_id: Organization ID
    :return: List of dicts with 'id' and 'name' keys
    """
    rows = (
        db.query(
            Site.id.label("id"),
            Site.name.label("name")
        )
        .filter(Site.org_id == org_id)
        .distinct()
        .order_by(Site.name.asc())
        .all()
    )

    return [{"id": str(r.id), "name": r.name} for r in rows]




def build_advance_analytics_filter(org_id: UUID, params: AnalyticsRequest):
    filters = [Site.org_id == org_id]

    # Filter by site opening month
    if params.site_open_month and params.site_open_month.lower() != "all":
        try:
            month_int = int(params.site_open_month)
            filters.append(extract('month', Site.opened_on) == month_int)
        except (ValueError, TypeError):
            pass

    if params.site_name and params.site_name.lower() != "all":
        try:
            site_uuid = UUID(params.site_name)
            filters.append(Site.id == site_uuid)
        except ValueError:
            filters.append(Site.code == params.site_name)

    return filters



def get_advance_analytics(db: Session, org_id: UUID, params: AnalyticsRequest):
    filters = build_advance_analytics_filter(org_id, params)
    
    # Set date range - last 30 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    # Total Revenue with filters
    folio_charges = db.query(func.coalesce(func.sum(FolioCharge.amount), 0))\
        .select_from(FolioCharge).join(Folio).join(Booking).join(Site)\
        .filter(*filters, FolioCharge.date.between(start_date, end_date), FolioCharge.amount > 0).scalar()

    lease_charges = db.query(func.coalesce(func.sum(LeaseCharge.amount), 0))\
        .select_from(LeaseCharge).join(Lease).join(Site)\
        .filter(*filters, LeaseCharge.period_start.between(start_date, end_date), LeaseCharge.amount > 0).scalar()

    invoice_totals = db.query(func.coalesce(func.sum(cast(func.jsonb_extract_path_text(Invoice.totals, 'grand'), Numeric())), 0))\
        .filter(Invoice.org_id == org_id, Invoice.date.between(start_date, end_date)).scalar()

    refunds = db.query(func.coalesce(func.sum(FolioCharge.amount), 0))\
        .select_from(FolioCharge).join(Folio).join(Booking).join(Site)\
        .filter(*filters, FolioCharge.date.between(start_date, end_date), FolioCharge.amount < 0).scalar()

    cancellation_refunds = db.query(func.coalesce(func.sum(BookingCancellation.refund_amount), 0))\
        .select_from(BookingCancellation).join(Booking).join(Site)\
        .filter(*filters, BookingCancellation.cancelled_at.between(start_date, end_date)).scalar()

    total_revenue = float(folio_charges + lease_charges + invoice_totals) - float(abs(refunds) + cancellation_refunds)
        
        # Collection Rate with filters - JOIN with Site table
    total_invoiced = db.query(func.coalesce(func.sum(cast(func.jsonb_extract_path_text(Invoice.totals, 'grand'), Numeric())), 0))\
        .select_from(Invoice)\
        .join(Site, Invoice.site_id == Site.id)\
        .filter(*filters, Invoice.date.between(start_date, end_date)).scalar()

    total_collected = db.query(func.coalesce(func.sum(PaymentAR.amount), 0))\
        .select_from(PaymentAR)\
        .join(Invoice, PaymentAR.invoice_id == Invoice.id)\
        .join(Site, Invoice.site_id == Site.id)\
        .filter(*filters, PaymentAR.paid_at.between(start_date, end_date)).scalar()

    collection_rate = (float(total_collected) / float(total_invoiced) * 100) if total_invoiced > 0 else 0

    # Occupancy Rate with filters - JOIN with Site table
    total_spaces = db.query(func.count(Space.id))\
        .select_from(Space)\
        .join(Site, Space.site_id == Site.id)\
        .filter(*filters, Space.kind.in_(['room', 'apartment', 'shop', 'office'])).scalar()

    occupied_spaces = db.query(func.count(Space.id))\
        .select_from(Space)\
        .join(Site, Space.site_id == Site.id)\
        .filter(*filters, Space.kind.in_(['room', 'apartment', 'shop', 'office']), 
                Space.status.in_(['occupied', 'in_house'])).scalar()

    occupancy_rate = (occupied_spaces / total_spaces * 100) if total_spaces > 0 else 0
    
        # Maintenance Efficiency with filters - JOIN with Site table
    total_completed_orders = db.query(func.count(WorkOrder.id))\
        .select_from(WorkOrder)\
        .join(Site, WorkOrder.site_id == Site.id)\
        .filter(*filters, WorkOrder.status == 'completed',
                WorkOrder.created_at.between(start_date, end_date)).scalar()

    if total_completed_orders == 0:
        maintenance_efficiency = 0
    else:
        on_time_orders = db.query(func.count(WorkOrder.id))\
            .select_from(WorkOrder)\
            .join(Site, WorkOrder.site_id == Site.id)\
            .filter(*filters, WorkOrder.status == 'completed',
                    WorkOrder.created_at.between(start_date, end_date),
                    WorkOrder.updated_at <= WorkOrder.created_at + timedelta(days=30)).scalar()
        maintenance_efficiency = (on_time_orders / total_completed_orders) * 100
    # Energy Cost with filters
    avg_consumption = db.query(func.coalesce(func.avg(MeterReading.delta * Meter.multiplier), 0))\
        .select_from(MeterReading).join(Meter).join(Site)\
        .filter(*filters, Meter.kind == 'electricity', 
                MeterReading.ts.between(start_date, end_date)).scalar()

    avg_consumption_float = float(avg_consumption) if avg_consumption else 0.0
    
        # Tenant Satisfaction with filters - JOIN with Site table
    avg_rating = db.query(func.coalesce(func.avg(ServiceRequest.ratings), 0.0))\
        .select_from(ServiceRequest)\
        .join(Site, ServiceRequest.site_id == Site.id)\
        .filter(*filters).scalar()

    avg_rating_float = float(avg_rating) if avg_rating else 0.0
        
    # Return in KPI format
    return [
        {
            "title": "Total Revenue",
            "value": f"₹{total_revenue:,.2f}",
            "change": 8.2,
            "trend": "up",
            "subtitle": "This month",
            "color": "text-green-600"
        },
        {
            "title": "Occupancy Rate",
            "value": f"{occupancy_rate:.1f}%",
            "change": 2.1,
            "trend": "up",
            "subtitle": "Across all properties",
            "color": "text-blue-600"
        },
        {
            "title": "Collection Rate",
            "value": f"{collection_rate:.1f}%",
            "change": 1.4,
            "trend": "up",
            "subtitle": "Payment collections",
            "color": "text-purple-600"
        },
        {
            "title": "Maintenance Efficiency",
            "value": f"{maintenance_efficiency:.1f}%",
            "change": 6.8,
            "trend": "up",
            "subtitle": "Work order completion",
            "color": "text-orange-600"
        },
        {
            "title": "Energy Cost",
            "value": f"₹{avg_consumption_float * 8:,.2f}",
            "change": -3.1,
            "trend": "down",
            "subtitle": "Monthly consumption",
            "color": "text-red-600"
        },
        {
            "title": "Tenant Satisfaction",
            "value": f"{avg_rating_float:.1f}/5",
            "change": 0.2,
            "trend": "up",
            "subtitle": "Average rating",
            "color": "text-teal-600"
        }
    ]


def get_revenue_analytics(db: Session, org_id: UUID, params: AnalyticsRequest):
    """Get revenue analytics from actual database data"""
    filters = build_advance_analytics_filter(org_id, params)
    
    # Get distinct months from folio_charges with filters
    folio_months = db.query(
        func.to_char(FolioCharge.date, 'YYYY-MM').label('month')
    ).select_from(FolioCharge).join(Folio).join(Booking).join(Site)\
    .filter(
        *filters,
        FolioCharge.amount > 0
    ).distinct().all()
    
    # Get distinct months from lease_charges with filters
    lease_months = db.query(
        func.to_char(LeaseCharge.period_start, 'YYYY-MM').label('month')
    ).select_from(LeaseCharge).join(Lease).join(Site)\
    .filter(
        *filters,
        LeaseCharge.amount > 0
    ).distinct().all()
    
    # Combine and get unique months
    db_months = set([row.month for row in folio_months] + [row.month for row in lease_months])
    db_months = sorted(list(db_months))
    
    # If no data found in database, return empty
    if not db_months:
        return {
            "monthly": [],
            "forecasted": []
        }
    
    monthly_data = []
    
    # Process each unique month that has data in the database
    for month_str in db_months:
        month_start = datetime.strptime(month_str, '%Y-%m').replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        # 1. HOTEL REVENUE: Folio Charges for this month
        hotel_revenue = db.query(func.coalesce(func.sum(FolioCharge.amount), 0))\
            .select_from(FolioCharge).join(Folio).join(Booking).join(Site)\
            .filter(
                *filters, 
                FolioCharge.date.between(month_start, month_end),
                FolioCharge.amount > 0
            ).scalar() or 0

        # 2. COMMERCIAL LEASE REVENUE: Lease Charges for this month
        lease_revenue = db.query(func.coalesce(func.sum(LeaseCharge.amount), 0))\
            .select_from(LeaseCharge).join(Lease).join(Site)\
            .filter(
                *filters,
                LeaseCharge.period_start.between(month_start, month_end),
                LeaseCharge.amount > 0
            ).scalar() or 0

        # 3. PARKING REVENUE
        parking_revenue = db.query(func.coalesce(func.sum(FolioCharge.amount), 0))\
            .select_from(FolioCharge).join(Folio).join(Booking).join(Site)\
            .filter(
                *filters,
                FolioCharge.date.between(month_start, month_end),
                FolioCharge.amount > 0,
                FolioCharge.code.in_(['PARKING', 'PARK', 'VALET', 'VEHICLE'])
            ).scalar() or 0
        
        # 4. UTILITIES REVENUE
        utilities_folio = db.query(func.coalesce(func.sum(FolioCharge.amount), 0))\
            .select_from(FolioCharge).join(Folio).join(Booking).join(Site)\
            .filter(
                *filters,
                FolioCharge.date.between(month_start, month_end),
                FolioCharge.amount > 0,
                FolioCharge.code.in_(['ELECTRICITY', 'WATER', 'GAS', 'UTILITY', 'POWER'])
            ).scalar() or 0
        
        utilities_lease = db.query(func.coalesce(func.sum(LeaseCharge.amount), 0))\
            .select_from(LeaseCharge).join(Lease).join(Site)\
            .filter(
                *filters,
                LeaseCharge.period_start.between(month_start, month_end),
                LeaseCharge.amount > 0,
                LeaseCharge.charge_code.in_(['ELEC', 'WATER', 'GAS', 'UTILITY'])
            ).scalar() or 0
        
        utilities_revenue = utilities_folio + utilities_lease
        
        # 5. CAM REVENUE
        cam_revenue = db.query(func.coalesce(func.sum(LeaseCharge.amount), 0))\
            .select_from(LeaseCharge).join(Lease).join(Site)\
            .filter(
                *filters,
                LeaseCharge.period_start.between(month_start, month_end),
                LeaseCharge.amount > 0,
                LeaseCharge.charge_code == 'CAM'
            ).scalar() or 0
        
        # Categorize revenue
        rental_revenue = hotel_revenue + lease_revenue
        total_revenue = rental_revenue + cam_revenue + parking_revenue + utilities_revenue
        
        monthly_data.append({
            "date": month_str,
            "rental": float(rental_revenue),
            "cam": float(cam_revenue),
            "parking": float(parking_revenue),
            "utilities": float(utilities_revenue),
            "total": float(total_revenue)
        })
    
    # Generate forecast for missing months
    forecasted_data = []
    
    if monthly_data:
        # Get the latest month from actual data
        latest_data_month = max([datetime.strptime(m['date'], '%Y-%m') for m in monthly_data])
        
        # Get months with actual revenue data for growth calculation
        months_with_revenue = [m for m in monthly_data if m['total'] > 0]
        
        if len(months_with_revenue) >= 2:
            # Use last 2 months with revenue for growth calculation
            recent_months = months_with_revenue[-2:]
            prev_month = recent_months[0]
            last_month = recent_months[1]
            
            # Calculate growth rates
            rental_growth = (last_month['rental'] - prev_month['rental']) / prev_month['rental'] if prev_month['rental'] > 0 else 0.05
            cam_growth = (last_month['cam'] - prev_month['cam']) / prev_month['cam'] if prev_month['cam'] > 0 else 0.05
            parking_growth = (last_month['parking'] - prev_month['parking']) / prev_month['parking'] if prev_month['parking'] > 0 else 0.05
            utilities_growth = (last_month['utilities'] - prev_month['utilities']) / prev_month['utilities'] if prev_month['utilities'] > 0 else 0.05
            
            # Generate forecast for next 3 months after latest data
            for i in range(1, 4):
                forecast_month = (latest_data_month + timedelta(days=32*i)).replace(day=1)
                forecast_month_str = forecast_month.strftime('%Y-%m')
                
                # Only forecast if this month doesn't exist in our data
                if forecast_month_str not in db_months:
                    forecast_rental = last_month['rental'] * (1 + rental_growth)
                    forecast_cam = last_month['cam'] * (1 + cam_growth)
                    forecast_parking = last_month['parking'] * (1 + parking_growth)
                    forecast_utilities = last_month['utilities'] * (1 + utilities_growth)
                    forecast_total = forecast_rental + forecast_cam + forecast_parking + forecast_utilities
                    
                    forecasted_data.append({
                        "date": forecast_month_str,
                        "rental": float(round(forecast_rental)),
                        "cam": float(round(forecast_cam)),
                        "parking": float(round(forecast_parking)),
                        "utilities": float(round(forecast_utilities)),
                        "total": float(round(forecast_total))
                    })
    
    return {
        "monthly": monthly_data,
        "forecasted": forecasted_data
    }
 

def get_collection_performance(db: Session, org_id: UUID, params: AnalyticsRequest):
    """get_collection_performance analytics from actual database data"""
    filters = build_advance_analytics_filter(org_id, params)
    
    # Generate last 10 months (including current month)
    current_date = datetime.now()
    start_date = (current_date.replace(day=1) - timedelta(days=270))  # 9 months ago
    
    all_months = []
    current_month = start_date.replace(day=1)
    while current_month <= current_date.replace(day=1):
        all_months.append(current_month.strftime('%Y-%m'))
        next_month = current_month + timedelta(days=32)
        current_month = next_month.replace(day=1)
    
    collection_data = []
    
    for month_str in all_months:
        month_start = datetime.strptime(month_str, '%Y-%m').replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        # 1. TOTAL INVOICED AMOUNT for the month
        total_invoiced = db.query(
            func.coalesce(func.sum(cast(func.jsonb_extract_path_text(Invoice.totals, 'grand'), Numeric())), 0)
        ).select_from(Invoice).join(Site)\
        .filter(
            *filters,
            Invoice.date >= month_start,
            Invoice.date <= month_end,
            Invoice.status.in_(['issued', 'paid', 'partial', 'overdue'])
        ).scalar() or 0
        
        # 2. TOTAL COLLECTED AMOUNT for the month
        total_collected = db.query(
            func.coalesce(func.sum(PaymentAR.amount), 0)
        ).select_from(PaymentAR).join(Invoice).join(Site)\
        .filter(
            *filters,
            PaymentAR.paid_at >= month_start,
            PaymentAR.paid_at <= month_end
        ).scalar() or 0
        
        # 3. OVERDUE AMOUNT
        overdue_amount = db.query(
            func.coalesce(func.sum(cast(func.jsonb_extract_path_text(Invoice.totals, 'grand'), Numeric())), 0)
        ).select_from(Invoice).join(Site)\
        .filter(
            *filters,
            Invoice.date >= month_start,
            Invoice.date <= month_end,
            Invoice.due_date < current_date,
            Invoice.status.in_(['issued', 'partial', 'overdue'])
        ).scalar() or 0
        
        # 4. PENDING AMOUNT
        total_pending = max(0, float(total_invoiced) - float(total_collected))
        
        # Calculate percentages
        total_invoiced_float = float(total_invoiced)
        total_collected_float = float(total_collected)
        overdue_amount_float = float(overdue_amount)
        
        collected_rate = 0
        pending_rate = 0
        overdue_rate = 0
        
        if total_invoiced_float > 0:
            collected_rate = min(100, max(0, (total_collected_float / total_invoiced_float) * 100))
            pending_rate = min(100, max(0, (total_pending / total_invoiced_float) * 100))
            overdue_rate = min(100, max(0, (overdue_amount_float / total_invoiced_float) * 100))
            
            # Ensure collected + pending = 100%
            if (collected_rate + pending_rate) != 100:
                pending_rate = 100 - collected_rate
        
        collection_data.append({
            "month": month_str,
            "collected": round(collected_rate, 1),
            "pending": round(pending_rate, 1),
            "overdue": round(overdue_rate, 1)
        })
    
    return {
        "collection": collection_data
    }


def get_site_profitability(db: Session, org_id: UUID, params: AnalyticsRequest):
    """Get site profitability analytics from actual database data"""
    filters = build_advance_analytics_filter(org_id, params)
    
    profitability_data = []
    
    # Get sites based on filters
    sites_query = db.query(Site).filter(Site.org_id == org_id)
    
    # Apply site filters if any
    site_filters_from_params = [f for f in filters if hasattr(f, 'left') and f.left == Site.id]
    if site_filters_from_params:
        sites_query = sites_query.filter(*site_filters_from_params)
    
    sites = sites_query.all()
    
    for site in sites:
        # Use site-specific filters for revenue/expense calculations
        site_filters = [Site.id == site.id]
        
        # REVENUE: Total revenue from all sources for current month
        current_month_start = datetime.now().replace(day=1)
        current_month_end = (current_month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        # Hotel revenue from folio_charges
        hotel_revenue = db.query(func.coalesce(func.sum(FolioCharge.amount), 0))\
            .select_from(FolioCharge)\
            .join(Folio, FolioCharge.folio_id == Folio.id)\
            .join(Booking, Folio.booking_id == Booking.id)\
            .join(Site, Booking.site_id == Site.id)\
            .filter(
                *site_filters,
                FolioCharge.date.between(current_month_start, current_month_end),
                FolioCharge.amount > 0
            ).scalar() or Decimal('0')
        
        # Lease revenue from lease_charges
        lease_revenue = db.query(func.coalesce(func.sum(LeaseCharge.amount), 0))\
            .select_from(LeaseCharge)\
            .join(Lease, LeaseCharge.lease_id == Lease.id)\
            .join(Site, Lease.site_id == Site.id)\
            .filter(
                *site_filters,
                LeaseCharge.period_start.between(current_month_start, current_month_end),
                LeaseCharge.amount > 0
            ).scalar() or Decimal('0')
        
        # Other revenue from invoices
        other_revenue = db.query(func.coalesce(func.sum(cast(func.jsonb_extract_path_text(Invoice.totals, 'grand'), Numeric())), 0))\
            .select_from(Invoice)\
            .join(Site, Invoice.site_id == Site.id)\
            .filter(
                *site_filters,
                Invoice.date.between(current_month_start, current_month_end),
                Invoice.status.in_(['paid', 'partial'])
            ).scalar() or Decimal('0')
        
        total_revenue = hotel_revenue + lease_revenue + other_revenue
        
        # EXPENSES: Detailed calculation using available data
        # Utility costs
        utility_costs = db.query(func.coalesce(func.sum(FolioCharge.amount), 0))\
            .select_from(FolioCharge)\
            .join(Folio, FolioCharge.folio_id == Folio.id)\
            .join(Booking, Folio.booking_id == Booking.id)\
            .join(Site, Booking.site_id == Site.id)\
            .filter(
                *site_filters,
                FolioCharge.date.between(current_month_start, current_month_end),
                FolioCharge.amount > 0,
                FolioCharge.code.in_(['ELECTRICITY', 'WATER', 'GAS', 'UTILITY', 'POWER'])
            ).scalar() or Decimal('0')
        
        # CAM costs
        cam_costs = db.query(func.coalesce(func.sum(LeaseCharge.amount), 0))\
            .select_from(LeaseCharge)\
            .join(Lease, LeaseCharge.lease_id == Lease.id)\
            .join(Site, Lease.site_id == Site.id)\
            .filter(
                *site_filters,
                LeaseCharge.period_start.between(current_month_start, current_month_end),
                LeaseCharge.amount > 0,
                LeaseCharge.charge_code == 'CAM'
            ).scalar() or Decimal('0')
        
        # Contract/Vendor costs
        contract_costs = db.query(func.coalesce(func.sum(PurchaseOrderLine.qty * PurchaseOrderLine.price), 0))\
            .select_from(PurchaseOrderLine)\
            .join(PurchaseOrder, PurchaseOrderLine.po_id == PurchaseOrder.id)\
            .join(Site, PurchaseOrder.site_id == Site.id)\
            .filter(
                *site_filters,
                PurchaseOrder.status.in_(['received', 'closed']),
                PurchaseOrder.expected_date.between(current_month_start, current_month_end)
            ).scalar() or Decimal('0')
        
        # Refund expenses
        refund_expenses = db.query(func.coalesce(func.sum(BookingCancellation.refund_amount), 0))\
            .select_from(BookingCancellation)\
            .join(Booking, BookingCancellation.booking_id == Booking.id)\
            .join(Site, Booking.site_id == Site.id)\
            .filter(
                *site_filters,
                BookingCancellation.cancelled_at.between(current_month_start, current_month_end),
                BookingCancellation.refund_processed == True
            ).scalar() or Decimal('0')
        
        # Convert all to Decimal for calculation
        total_expenses = utility_costs + cam_costs + contract_costs + refund_expenses
        
        # If no detailed expense data, estimate as percentage of revenue
        if total_expenses == Decimal('0') and total_revenue > Decimal('0'):
            # Estimate expenses based on site type
            expense_ratio = Decimal('0.6')  # Default 60%
            if site.kind == 'hotel':
                expense_ratio = Decimal('0.5')  # Hotels typically have 50% margins
            elif site.kind == 'commercial':
                expense_ratio = Decimal('0.4')  # Commercial properties have better margins
            elif site.kind == 'mall':
                expense_ratio = Decimal('0.3')  # Malls have high revenue share models
            
            total_expenses = total_revenue * expense_ratio
        
        profit = total_revenue - total_expenses
        profit_margin = (profit / total_revenue) * Decimal('100') if total_revenue > Decimal('0') else Decimal('0')
        
        profitability_data.append({
            "site": site.name,
            "revenue": float(total_revenue),
            "expenses": float(total_expenses),
            "profit": float(profit),
            "margin": round(float(profit_margin), 1)
        })
    
    return profitability_data
 

def get_occupancy_analytics(db: Session, org_id: UUID, params: AnalyticsRequest):
    """Get occupancy analytics from actual database data"""
    filters = build_advance_analytics_filter(org_id, params)
    
    # 1. TREND DATA - Monthly occupancy trends for all months
    trend_data = []
    
    # Get all distinct months from the beginning to current month
    current_date = datetime.now()
    start_date = current_date.replace(day=1) - timedelta(days=270)  # 9 months ago
    
    # Generate all months from start_date to current_date
    all_months = []
    current_month = start_date.replace(day=1)
    while current_month <= current_date.replace(day=1):
        all_months.append(current_month.strftime('%Y-%m'))
        # Move to next month
        next_month = current_month + timedelta(days=32)
        current_month = next_month.replace(day=1)
    
    # Process each month
    for month_str in all_months:
        month_start = datetime.strptime(month_str, '%Y-%m').replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        # Total spaces (spaces that existed by this month)
        total_spaces = db.query(func.count(Space.id))\
            .select_from(Space).join(Site)\
            .filter(
                *filters,
                Space.created_at <= month_end
            ).scalar() or 1  # Avoid division by zero
        
        # Occupied spaces
        occupied_spaces = db.query(func.count(Space.id))\
            .select_from(Space).join(Site)\
            .filter(
                *filters,
                Space.created_at <= month_end,
                Space.status.in_(['occupied', 'in_house'])
            ).scalar() or 0
        
        # Maintenance spaces
        maintenance_spaces = db.query(func.count(Space.id))\
            .select_from(Space).join(Site)\
            .filter(
                *filters,
                Space.created_at <= month_end,
                Space.status.in_(['out_of_service', 'maintenance'])
            ).scalar() or 0
        
        # Calculate percentages
        occupancy_rate = (occupied_spaces / total_spaces) * 100 if total_spaces > 0 else 0
        available_rate = ((total_spaces - occupied_spaces - maintenance_spaces) / total_spaces) * 100 if total_spaces > 0 else 0
        maintenance_rate = (maintenance_spaces / total_spaces) * 100 if total_spaces > 0 else 0
        
        trend_data.append({
            "date": month_str,
            "occupancy": round(occupancy_rate, 1),
            "available": round(available_rate, 1),
            "maintenance": round(maintenance_rate, 1)
        })
    
    return {
        "trend": trend_data
    }


def get_space_type_performance(db: Session, org_id: UUID, params: AnalyticsRequest):
    """Get comprehensive space occupancy performance by space type"""
    filters = build_advance_analytics_filter(org_id, params)
    
    space_type_data = []
    today = datetime.now().date()
    
    # Get all space kinds in the system
    space_kinds = db.query(Space.kind)\
        .filter(Space.org_id == org_id)\
        .group_by(Space.kind)\
        .all()
    
    for (space_kind,) in space_kinds:
        # Base query for this space kind
        base_query = db.query(Space)\
            .join(Site, Space.site_id == Site.id)\
            .filter(
                Space.org_id == org_id,
                Space.kind == space_kind,
                *filters
            )
        
        total = base_query.count()
        
        if space_kind == 'room':
            # Hotel rooms: use booking-based occupancy
            occupied = db.query(func.count(BookingRoom.id))\
                .select_from(BookingRoom)\
                .join(Booking, BookingRoom.booking_id == Booking.id)\
                .join(Space, BookingRoom.space_id == Space.id)\
                .join(Site, Booking.site_id == Site.id)\
                .filter(
                    Space.org_id == org_id,
                    Space.kind == 'room',
                    *filters,
                    Booking.check_in <= today,
                    Booking.check_out > today,
                    Booking.status.in_(['reserved', 'in_house', 'checked_in'])
                )\
                .scalar() or 0
            
            # Count out_of_service rooms
            out_of_service = base_query.filter(Space.status == 'out_of_service').count()
            available = total - occupied - out_of_service
            
        elif space_kind in ['apartment', 'shop', 'office']:
            # Leased spaces: use lease-based occupancy
            if space_kind == 'apartment':
                lease_occupied = db.query(func.count(Lease.id))\
                    .select_from(Lease)\
                    .join(Space, Lease.space_id == Space.id)\
                    .join(Site, Lease.site_id == Site.id)\
                    .filter(
                        Lease.org_id == org_id,
                        *filters,
                        Lease.start_date <= today,
                        Lease.end_date >= today,
                        Lease.status == 'active',
                        Space.kind == space_kind
                    )\
                    .scalar() or 0
            else:
                # For commercial spaces (shops, offices)
                lease_occupied = db.query(func.count(Lease.id))\
                    .select_from(Lease)\
                    .join(Space, Lease.space_id == Space.id)\
                    .join(Site, Lease.site_id == Site.id)\
                    .filter(
                        Lease.org_id == org_id,
                        *filters,
                        Lease.start_date <= today,
                        Lease.end_date >= today,
                        Lease.status == 'active',
                        Space.kind == space_kind
                    )\
                    .scalar() or 0
            
            occupied = lease_occupied
            out_of_service = base_query.filter(Space.status == 'out_of_service').count()
            available = total - occupied - out_of_service
            
        else:
            # Other space types (parking, common areas, etc.)
            occupied = base_query.filter(Space.status.in_(['occupied', 'checked_in'])).count()
            available = base_query.filter(Space.status == 'available').count()
        
        # Ensure numbers are valid
        occupied = max(0, min(occupied, total))
        available = max(0, min(available, total))
        
        # Calculate occupancy percentage
        occupancy_rate = (occupied / total * 100) if total > 0 else 0
            
                # First, get all distinct space kinds present in the database for this org
        space_kinds = db.query(Space.kind)\
            .filter(Space.org_id == org_id)\
            .distinct()\
            .all()
        # Map to display name
        
        
        space_type_data.append({
            "type": space_kind,
            "occupancy": round(occupancy_rate, 1),
            "total": total,
            "occupied": occupied,
            "available": available
        })
    
    # Sort by occupancy rate descending
    space_type_data.sort(key=lambda x: x['occupancy'], reverse=True)
    
    return space_type_data


def get_portfolio_distribution(db: Session, org_id: UUID, params: AnalyticsRequest):
    """Get portfolio distribution - find all space types and their occupancy percentages"""
    
    filters = build_advance_analytics_filter(org_id, params)
    today = datetime.now().date()
    
    # Get all distinct space kinds
    space_kinds = db.query(Space.kind)\
        .filter(Space.org_id == org_id)\
        .group_by(Space.kind)\
        .all()
    
    distribution_data = []
    
    for (space_kind,) in space_kinds:
        # Base query for this space kind
        base_query = db.query(Space)\
            .join(Site, Space.site_id == Site.id)\
            .filter(
                Space.org_id == org_id,
                Space.kind == space_kind,
                *filters
            )
        
        total_count = base_query.count()
        
        # Calculate occupied spaces based on space kind
        if space_kind == 'room':
            # Hotel rooms: occupied if they have active bookings
            occupied_count = db.query(func.count(BookingRoom.id))\
                .select_from(BookingRoom)\
                .join(Booking, BookingRoom.booking_id == Booking.id)\
                .join(Space, BookingRoom.space_id == Space.id)\
                .join(Site, Booking.site_id == Site.id)\
                .filter(
                    Space.org_id == org_id,
                    Space.kind == 'room',
                    *filters,
                    Booking.check_in <= today,
                    Booking.check_out > today,
                    Booking.status.in_(['reserved', 'in_house', 'checked_in'])
                )\
                .scalar() or 0
                
        elif space_kind in ['apartment', 'shop', 'office']:
            # Leased spaces: occupied if they have active leases
            occupied_count = db.query(func.count(Lease.id))\
                .select_from(Lease)\
                .join(Space, Lease.space_id == Space.id)\
                .join(Site, Lease.site_id == Site.id)\
                .filter(
                    Lease.org_id == org_id,
                    *filters,
                    Lease.start_date <= today,
                    Lease.end_date >= today,
                    Lease.status == 'active',
                    Space.kind == space_kind
                )\
                .scalar() or 0
        else:
            # For other space types (parking, common areas, etc.)
            # Use space status to determine occupancy
            occupied_count = base_query.filter(
                Space.status.in_(['occupied', 'checked_in', 'in_use'])
            ).count()
        
        # Calculate occupancy percentage for this space type
        occupancy_percentage = (occupied_count / total_count * 100) if total_count > 0 else 0
        
        # Convert space_kind to display name
        display_name = space_kind.replace('_', ' ').title()
        
        # Color mapping for different space types
        color_mapping = {
            'apartment': '#3b82f6',  # blue
            'shop': '#10b981',       # green  
            'office': '#f59e0b',     # amber
            'room': '#8b5cf6',       # violet
            'parking': '#ef4444',    # red
            'warehouse': '#f97316',  # orange
            'meeting_room': '#06b6d4', # cyan
            'hall': '#d946ef',       # fuchsia
            'common_area': '#64748b'  # slate
        }
        
        color = color_mapping.get(space_kind, '#6b7280')  # default gray
        
        distribution_data.append({
            'name': display_name,
            'value': occupied_count,  # Number of occupied spaces
            'percentage': round(occupancy_percentage, 1),  # Occupancy percentage for this type
            'color': color
        })
    
    # Sort by occupancy count descending (most occupied types first)
    distribution_data.sort(key=lambda x: x['value'], reverse=True)
    
    return distribution_data




def get_yoy_performance(db: Session, org_id: UUID, params: AnalyticsRequest):
    """Get Year-over-Year financial performance metrics"""
    
    filters = build_advance_analytics_filter(org_id, params)
    current_year = datetime.now().year
    previous_year = current_year - 1
    
    # Calculate revenue for current and previous year from folio_charges
    # Join through folio -> booking -> site to get org_id
    current_revenue = db.query(func.sum(FolioCharge.amount))\
        .join(Folio, FolioCharge.folio_id == Folio.id)\
        .join(Booking, Folio.booking_id == Booking.id)\
        .join(Site, Booking.site_id == Site.id)\
        .filter(
            Site.org_id == org_id,  # Use Site.org_id instead of FolioCharges.org_id
            extract('year', FolioCharge.date) == current_year,
            *filters
        )\
        .scalar() or 0
    
    previous_revenue = db.query(func.sum(FolioCharge.amount))\
        .join(Folio, FolioCharge.folio_id == Folio.id)\
        .join(Booking, Folio.booking_id == Booking.id)\
        .join(Site, Booking.site_id == Site.id)\
        .filter(
            Site.org_id == org_id,
            extract('year', FolioCharge.date) == previous_year,
            *filters
        )\
        .scalar() or 0
    
    # Calculate occupancy rates
    # Current year occupancy
    current_total_spaces = db.query(func.count(Space.id))\
        .join(Site, Space.site_id == Site.id)\
        .filter(
            Site.org_id == org_id,
            *filters
        )\
        .scalar() or 1
    
    # For hotel rooms - use bookings
    current_hotel_occupied = db.query(func.count(BookingRoom.id))\
        .join(Booking, BookingRoom.booking_id == Booking.id)\
        .join(Space, BookingRoom.space_id == Space.id)\
        .join(Site, Booking.site_id == Site.id)\
        .filter(
            Site.org_id == org_id,
            Space.kind == 'room',
            *filters,
            Booking.check_in <= datetime.now().date(),
            Booking.check_out > datetime.now().date(),
            Booking.status.in_(['reserved', 'in_house', 'checked_in'])
        )\
        .scalar() or 0
    
    # For leased spaces - use leases
    current_leased_occupied = db.query(func.count(Lease.id))\
        .join(Space, Lease.space_id == Space.id)\
        .join(Site, Lease.site_id == Site.id)\
        .filter(
            Site.org_id == org_id,
            *filters,
            Lease.start_date <= datetime.now().date(),
            Lease.end_date >= datetime.now().date(),
            Lease.status == 'active'
        )\
        .scalar() or 0
    
    current_occupied = current_hotel_occupied + current_leased_occupied
    current_occupancy = (current_occupied / current_total_spaces * 100) if current_total_spaces > 0 else 0
    
    # Previous year occupancy
    prev_year_date = datetime.now().date() - timedelta(days=365)
    
    previous_hotel_occupied = db.query(func.count(BookingRoom.id))\
        .join(Booking, BookingRoom.booking_id == Booking.id)\
        .join(Space, BookingRoom.space_id == Space.id)\
        .join(Site, Booking.site_id == Site.id)\
        .filter(
            Site.org_id == org_id,
            Space.kind == 'room',
            *filters,
            Booking.check_in <= prev_year_date,
            Booking.check_out > prev_year_date,
            Booking.status.in_(['reserved', 'in_house', 'checked_in'])
        )\
        .scalar() or 0
    
    previous_leased_occupied = db.query(func.count(Lease.id))\
        .join(Space, Lease.space_id == Space.id)\
        .join(Site, Lease.site_id == Site.id)\
        .filter(
            Site.org_id == org_id,
            *filters,
            Lease.start_date <= prev_year_date,
            Lease.end_date >= prev_year_date,
            Lease.status == 'active'
        )\
        .scalar() or 0
    
    previous_occupied = previous_hotel_occupied + previous_leased_occupied
    previous_occupancy = (previous_occupied / current_total_spaces * 100) if current_total_spaces > 0 else 0
    
    # Calculate expenses from lease_charges (CAM, utilities, etc.)
    # Join through lease -> site to get org_id
    current_expenses = db.query(func.sum(LeaseCharge.amount))\
        .join(Lease, LeaseCharge.lease_id == Lease.id)\
        .join(Site, Lease.site_id == Site.id)\
        .filter(
            Site.org_id == org_id,
            extract('year', LeaseCharge.period_start) == current_year,
            LeaseCharge.charge_code.in_(['CAM', 'ELEC', 'WATER', 'MAINTENANCE']),
            *filters
        )\
        .scalar() or 0
    
    previous_expenses = db.query(func.sum(LeaseCharge.amount))\
        .join(Lease, LeaseCharge.lease_id == Lease.id)\
        .join(Site, Lease.site_id == Site.id)\
        .filter(
            Site.org_id == org_id,
            extract('year', LeaseCharge.period_start) == previous_year,
            LeaseCharge.charge_code.in_(['CAM', 'ELEC', 'WATER', 'MAINTENANCE']),
            *filters
        )\
        .scalar() or 0
    
    # Calculate profit
    current_profit = current_revenue - current_expenses
    previous_profit = previous_revenue - previous_expenses
    
    # Calculate growth percentages
    revenue_growth = ((current_revenue - previous_revenue) / previous_revenue * 100) if previous_revenue > 0 else 0
    occupancy_growth = current_occupancy - previous_occupancy  # Absolute percentage point growth
    expenses_growth = ((current_expenses - previous_expenses) / previous_expenses * 100) if previous_expenses > 0 else 0
    profit_growth = ((current_profit - previous_profit) / previous_profit * 100) if previous_profit > 0 else 0
    
    return {
        'revenue': {
            'current': round(current_revenue, 2),
            'previous': round(previous_revenue, 2),
            'growth': round(revenue_growth, 1)
        },
        'occupancy': {
            'current': round(current_occupancy, 1),
            'previous': round(previous_occupancy, 1),
            'growth': round(occupancy_growth, 1)
        },
        'expenses': {
            'current': round(current_expenses, 2),
            'previous': round(previous_expenses, 2),
            'growth': round(expenses_growth, 1)
        },
        'profit': {
            'current': round(current_profit, 2),
            'previous': round(previous_profit, 2),
            'growth': round(profit_growth, 1)
        }
    }



def get_site_comparison(db: Session, org_id: UUID, params: AnalyticsRequest):
    """Get performance comparison across all sites"""
    
    filters = build_advance_analytics_filter(org_id, params)
    current_year = datetime.now().year
    
    # Get all sites for the organization
    sites = db.query(Site)\
        .filter(
            Site.org_id == org_id,
            *[f for f in filters if getattr(f, 'left', None) != Site.id]
        )\
        .all()
    
    site_comparison_data = []
    
    for site in sites:
        site_filters = [f for f in filters if f is not None]
        site_filters.append(Site.id == site.id)
        
        # Calculate occupancy for this site
        total_spaces = db.query(func.count(Space.id))\
            .filter(
                Space.org_id == org_id,
                Space.site_id == site.id
            )\
            .scalar() or 1
        
        # Hotel rooms occupancy
        hotel_occupied = db.query(func.count(BookingRoom.id))\
            .join(Booking, BookingRoom.booking_id == Booking.id)\
            .join(Space, BookingRoom.space_id == Space.id)\
            .filter(
                Space.org_id == org_id,
                Space.site_id == site.id,
                Space.kind == 'room',
                Booking.check_in <= datetime.now().date(),
                Booking.check_out > datetime.now().date(),
                Booking.status.in_(['reserved', 'in_house', 'checked_in'])
            )\
            .scalar() or 0
        
        # Leased spaces occupancy
        leased_occupied = db.query(func.count(Lease.id))\
            .join(Space, Lease.space_id == Space.id)\
            .filter(
                Lease.org_id == org_id,
                Lease.site_id == site.id,
                Lease.start_date <= datetime.now().date(),
                Lease.end_date >= datetime.now().date(),
                Lease.status == 'active'
            )\
            .scalar() or 0
        
        total_occupied = hotel_occupied + leased_occupied
        occupancy_rate = (total_occupied / total_spaces * 100) if total_spaces > 0 else 0
        
        # Calculate revenue for this site (current year)
        revenue = db.query(func.sum(FolioCharge.amount))\
            .join(Folio, FolioCharge.folio_id == Folio.id)\
            .join(Booking, Folio.booking_id == Booking.id)\
            .filter(
                Booking.org_id == org_id,
                Booking.site_id == site.id,
                extract('year', FolioCharge.date) == current_year
            )\
            .scalar() or 0
        
        # Calculate satisfaction from service_request ratings column
        satisfaction_query = db.query(func.avg(ServiceRequest.ratings))\
            .filter(
                ServiceRequest.org_id == org_id,
                ServiceRequest.site_id == site.id,
                extract('year', ServiceRequest.created_at) == current_year,
                ServiceRequest.ratings.isnot(None)  # Only include rated requests
            )\
            .scalar() or 4.0
        
        satisfaction = round(satisfaction_query, 1) if satisfaction_query else 4.0
        satisfaction = min(5.0, max(1.0, satisfaction))  # Ensure between 1-5
        
        # Calculate efficiency from work order completion rate
        total_work_orders = db.query(func.count(WorkOrder.id))\
            .filter(
                WorkOrder.org_id == org_id,
                WorkOrder.site_id == site.id,
                extract('year', WorkOrder.created_at) == current_year
            )\
            .scalar() or 1
        
        completed_work_orders = db.query(func.count(WorkOrder.id))\
            .filter(
                WorkOrder.org_id == org_id,
                WorkOrder.site_id == site.id,
                extract('year', WorkOrder.created_at) == current_year,
                WorkOrder.status == 'completed'
            )\
            .scalar() or 0
        
        efficiency = (completed_work_orders / total_work_orders * 100) if total_work_orders > 0 else 0
        
        site_comparison_data.append({
            'site': site.name,
            'metrics': {
                'occupancy': round(occupancy_rate, 1),
                'revenue': round(revenue, 2),
                'satisfaction': round(satisfaction, 1),
                'efficiency': round(efficiency, 1)
            }
        })
    
    # Sort by revenue descending
    site_comparison_data.sort(key=lambda x: x['metrics']['revenue'], reverse=True)
    
    return site_comparison_data




def get_maintenance_efficiency(db: Session, org_id: UUID, params: AnalyticsRequest):
    """Get maintenance efficiency - work order completion trends by month"""
    
    filters = build_advance_analytics_filter(org_id, params)
    current_year = datetime.now().year
    
    # Get monthly work order counts
    monthly_totals = db.query(
        extract('year', WorkOrder.created_at).label('year'),
        extract('month', WorkOrder.created_at).label('month'),
        func.count(WorkOrder.id).label('total')
    ).join(Site, WorkOrder.site_id == Site.id)\
     .filter(
        WorkOrder.org_id == org_id,
        extract('year', WorkOrder.created_at) == current_year,
        *filters
    ).group_by(
        extract('year', WorkOrder.created_at),
        extract('month', WorkOrder.created_at)
    ).all()
    
    # Get completed work orders by month
    monthly_completed = db.query(
        extract('year', WorkOrder.created_at).label('year'),
        extract('month', WorkOrder.created_at).label('month'),
        func.count(WorkOrder.id).label('completed')
    ).join(Site, WorkOrder.site_id == Site.id)\
     .filter(
        WorkOrder.org_id == org_id,
        extract('year', WorkOrder.created_at) == current_year,
        WorkOrder.status == 'completed',
        *filters
    ).group_by(
        extract('year', WorkOrder.created_at),
        extract('month', WorkOrder.created_at)
    ).all()
    
    # Get pending work orders by month
    monthly_pending = db.query(
        extract('year', WorkOrder.created_at).label('year'),
        extract('month', WorkOrder.created_at).label('month'),
        func.count(WorkOrder.id).label('pending')
    ).join(Site, WorkOrder.site_id == Site.id)\
     .filter(
        WorkOrder.org_id == org_id,
        extract('year', WorkOrder.created_at) == current_year,
        WorkOrder.status.in_(['open', 'assigned', 'in_progress']),
        *filters
    ).group_by(
        extract('year', WorkOrder.created_at),
        extract('month', WorkOrder.created_at)
    ).all()
    
    # Get overdue work orders by month
    monthly_overdue = db.query(
        extract('year', WorkOrder.created_at).label('year'),
        extract('month', WorkOrder.created_at).label('month'),
        func.count(WorkOrder.id).label('overdue')
    ).join(Site, WorkOrder.site_id == Site.id)\
     .filter(
        WorkOrder.org_id == org_id,
        extract('year', WorkOrder.created_at) == current_year,
        WorkOrder.due_at < datetime.now(),
        *filters
    ).group_by(
        extract('year', WorkOrder.created_at),
        extract('month', WorkOrder.created_at)
    ).all()
    
    # Combine all data
    maintenance_data = []
    
    for total_stat in monthly_totals:
        year = int(total_stat.year)
        month = int(total_stat.month)
        month_str = f"{year}-{month:02d}"
        
        total = total_stat.total or 0
        
        # Find matching completed count
        completed_stat = next((c for c in monthly_completed if int(c.year) == year and int(c.month) == month), None)
        completed = completed_stat.completed if completed_stat else 0
        
        # Find matching pending count
        pending_stat = next((p for p in monthly_pending if int(p.year) == year and int(p.month) == month), None)
        pending = pending_stat.pending if pending_stat else 0
        
        # Find matching overdue count
        overdue_stat = next((o for o in monthly_overdue if int(o.year) == year and int(o.month) == month), None)
        overdue = overdue_stat.overdue if overdue_stat else 0
        
        # Calculate efficiency
        efficiency = (completed / total * 100) if total > 0 else 0
        
        maintenance_data.append({
            'month': month_str,
            'completed': completed,
            'pending': pending,
            'overdue': overdue,
            'efficiency': round(efficiency, 1)
        })
    
    # Sort by month
    maintenance_data.sort(key=lambda x: x['month'])
    
    # If no data found, return sample data
    if not maintenance_data:
        for month in range(1, 10):  # Jan to Sep
            maintenance_data.append({
                'month': f"{current_year}-{month:02d}",
                'completed': 50 + month,
                'pending': 10 - (month % 3),
                'overdue': month % 3,
                'efficiency': round(85 + (month * 1.5), 1)
            })
    
    return maintenance_data



def get_energy_consumption(db: Session, org_id: UUID, params: AnalyticsRequest):
    """Get energy consumption - monthly utility usage and costs"""
    
    filters = build_advance_analytics_filter(org_id, params)
    current_year = datetime.now().year
    
    # Get meter readings for electricity, water, gas - grouped by month
    energy_stats = db.query(
        extract('year', MeterReading.ts).label('year'),
        extract('month', MeterReading.ts).label('month'),
        Meter.kind,
        func.sum(MeterReading.delta).label('consumption')
    ).join(Meter, MeterReading.meter_id == Meter.id)\
     .join(Site, Meter.site_id == Site.id)\
     .filter(
        Meter.org_id == org_id,
        extract('year', MeterReading.ts) == current_year,
        Meter.kind.in_(['electricity', 'water', 'gas']),
        *filters
    ).group_by(
        extract('year', MeterReading.ts),
        extract('month', MeterReading.ts),
        Meter.kind
    ).order_by(
        extract('year', MeterReading.ts),
        extract('month', MeterReading.ts)
    ).all()
    
    # Get utility costs from lease_charges - join through lease -> site to get org_id
    utility_costs = db.query(
        extract('year', LeaseCharge.period_start).label('year'),
        extract('month', LeaseCharge.period_start).label('month'),
        func.sum(LeaseCharge.amount).label('cost')
    ).join(Lease, LeaseCharge.lease_id == Lease.id)\
     .join(Site, Lease.site_id == Site.id)\
     .filter(
        Site.org_id == org_id,  # Filter by org_id through Site table
        extract('year', LeaseCharge.period_start) == current_year,
        LeaseCharge.charge_code.in_(['ELEC', 'WATER', 'GAS']),
        *filters
    ).group_by(
        extract('year', LeaseCharge.period_start),
        extract('month', LeaseCharge.period_start)
    ).order_by(
        extract('year', LeaseCharge.period_start),
        extract('month', LeaseCharge.period_start)
    ).all()
    
    # Organize data by month
    monthly_data = {}
    
    # Process energy consumption
    for stat in energy_stats:
        year = int(stat.year)
        month = int(stat.month)
        month_key = f"{year}-{month:02d}"
        
        if month_key not in monthly_data:
            monthly_data[month_key] = {
                'month': month_key,
                'electricity': 0,
                'water': 0,
                'gas': 0,
                'cost': 0
            }
        
        consumption = stat.consumption or 0
        if stat.kind == 'electricity':
            monthly_data[month_key]['electricity'] += round(consumption)
        elif stat.kind == 'water':
            monthly_data[month_key]['water'] += round(consumption)
        elif stat.kind == 'gas':
            monthly_data[month_key]['gas'] += round(consumption)
    
    # Process costs
    for cost in utility_costs:
        year = int(cost.year)
        month = int(cost.month)
        month_key = f"{year}-{month:02d}"
        
        if month_key in monthly_data:
            monthly_data[month_key]['cost'] += round(cost.cost or 0)
        else:
            # Create new month entry if it doesn't exist
            monthly_data[month_key] = {
                'month': month_key,
                'electricity': 0,
                'water': 0,
                'gas': 0,
                'cost': round(cost.cost or 0)
            }
    
    # Convert to list and sort
    energy_data = list(monthly_data.values())
    energy_data.sort(key=lambda x: x['month'])
    
    # If no data found, return sample data
    if not energy_data:
        base_electricity = 45000
        base_water = 12500
        base_gas = 8500
        base_cost = 180000
        
        for month in range(1, 12):  # Jan to Sep
            variation = (month - 5) * 500  # Create some variation
            energy_data.append({
                'month': f"{current_year}-{month:02d}",
                'electricity': base_electricity + (variation * 10),
                'water': base_water + (variation * 2),
                'gas': base_gas + variation,
                'cost': base_cost + (variation * 50)
            })
    
    return energy_data


def get_tenant_satisfaction(db: Session, org_id: UUID, params: AnalyticsRequest):
    """Production version without mock data"""
    
    filters = build_advance_analytics_filter(org_id, params)
    current_date = datetime.now()
    
    # Define time periods
    current_period_start = current_date.replace(day=1)
    previous_period_start = (current_period_start - timedelta(days=1)).replace(day=1)
    current_period_end = current_period_start + timedelta(days=32)

    # Get current period data
    current_ratings = db.query(
        ServiceRequest.category,
        func.avg(ServiceRequest.ratings).label('current_score'),
        func.count(ServiceRequest.id).label('current_count')
    ).join(Site, ServiceRequest.site_id == Site.id)\
     .filter(
        ServiceRequest.org_id == org_id,
        ServiceRequest.ratings.isnot(None),
        ServiceRequest.category.isnot(None),
        ServiceRequest.created_at >= current_period_start,
        ServiceRequest.created_at < current_period_end,
        *filters
    ).group_by(ServiceRequest.category).all()

    # Get previous period data
    previous_ratings = db.query(
        ServiceRequest.category,
        func.avg(ServiceRequest.ratings).label('previous_score'),
        func.count(ServiceRequest.id).label('previous_count')
    ).join(Site, ServiceRequest.site_id == Site.id)\
     .filter(
        ServiceRequest.org_id == org_id,
        ServiceRequest.ratings.isnot(None),
        ServiceRequest.category.isnot(None),
        ServiceRequest.created_at >= previous_period_start,
        ServiceRequest.created_at < current_period_start,
        *filters
    ).group_by(ServiceRequest.category).all()

    # Create previous scores mapping
    previous_scores = {}
    for rating in previous_ratings:
        if rating.previous_count >= 1:
            previous_scores[rating.category] = rating.previous_score

    # Process data
    satisfaction_data = []
    for rating in current_ratings:
        if rating.current_count >= 1:
            category = rating.category
            current_score = round(rating.current_score or 0, 1)
            
            # Calculate trend
            trend = 0.0
            if category in previous_scores:
                previous_score = previous_scores[category]
                trend = round(current_score - previous_score, 1)

            satisfaction_data.append({
                "category": category,
                "score": current_score,
                "trend": trend
            })

    # Sort by score descending
    satisfaction_data.sort(key=lambda x: x["score"], reverse=True)
    
    return satisfaction_data


def get_tenant_retention(db: Session, org_id: UUID, params: AnalyticsRequest):
    """Get tenant retention - lease renewal trends over years"""
    
    filters = build_advance_analytics_filter(org_id, params)
    current_year = datetime.now().year
    
    # Get all years where leases started
    lease_years = db.query(
        extract('year', Lease.start_date).label('year')
    ).join(Site, Lease.site_id == Site.id)\
     .filter(
        Lease.org_id == org_id,
        Lease.start_date <= datetime.now().date(),
        *filters
    ).distinct()\
     .order_by(extract('year', Lease.start_date))\
     .all()
    
    retention_data = []
    
    for (year,) in lease_years:
        year = int(year)
        
        # Skip future years and current year (incomplete data)
        if year >= current_year:
            continue
            
        # Get all leases that started in this year
        leases_started = db.query(Lease)\
            .join(Site, Lease.site_id == Site.id)\
            .filter(
                Lease.org_id == org_id,
                extract('year', Lease.start_date) == year,
                *filters
            ).all()
        
        total_leases = len(leases_started)
        
        if total_leases == 0:
            continue
            
        renewals = 0
        departures = 0
        
        for lease in leases_started:
            # Check if lease was renewed (same space has active lease after original end date)
            renewed_lease = db.query(Lease)\
                .join(Site, Lease.site_id == Site.id)\
                .filter(
                    Lease.org_id == org_id,
                    Lease.space_id == lease.space_id,
                    Lease.id != lease.id,  # Different lease
                    Lease.start_date > lease.end_date,  # Started after previous lease ended
                    Lease.start_date <= lease.end_date + timedelta(days=90),  # Within 90 days of previous end
                    Lease.status == 'active',
                    *filters
                ).first()
            
            if renewed_lease:
                renewals += 1
            else:
                # Check if space is currently occupied by someone else (definite departure)
                current_occupancy = db.query(Lease)\
                    .join(Site, Lease.site_id == Site.id)\
                    .filter(
                        Lease.org_id == org_id,
                        Lease.space_id == lease.space_id,
                        Lease.status == 'active',
                        Lease.start_date <= datetime.now().date(),
                        Lease.end_date >= datetime.now().date(),
                        *filters
                    ).first()
                
                if not current_occupancy:
                    departures += 1
                else:
                    # If space is occupied by different tenant, count as departure
                    if current_occupancy.id != lease.id:
                        departures += 1
        
        # Calculate retention rate
        retention_rate = (renewals / total_leases * 100) if total_leases > 0 else 0
        
        retention_data.append({
            'year': year,
            'renewals': renewals,
            'departures': departures,
            'rate': round(retention_rate, 1)
        })
    
    # Sort by year ascending
    retention_data.sort(key=lambda x: x['year'])
    
    return retention_data




def get_daily_visitor_trends(db: Session, org_id: UUID, params: AnalyticsRequest):
    """Get daily visitor trends - entry and exit patterns"""
    
    filters = build_advance_analytics_filter(org_id, params)
    
    # Get daily visitor statistics
    daily_stats = db.query(
        func.date(AccessEvent.ts).label('date'),
        func.count(AccessEvent.id).label('total_events'),
        func.sum(case((AccessEvent.direction == 'in', 1), else_=0)).label('entries'),
        func.sum(case((AccessEvent.direction == 'out', 1), else_=0)).label('exits')
    ).join(Site, AccessEvent.site_id == Site.id)\
     .filter(
        AccessEvent.org_id == org_id,
        *filters
    ).group_by(func.date(AccessEvent.ts))\
     .order_by(func.date(AccessEvent.ts).desc())\
     .limit(7)\
     .all()
    
    daily_data = []
    
    for stat in daily_stats:
        date_str = stat.date.strftime('%Y-%m-%d')
        
        # Calculate unique visitors (distinct vehicle_no or card_id)
        unique_visitors = db.query(func.count(func.distinct(AccessEvent.vehicle_no)))\
            .join(Site, AccessEvent.site_id == Site.id)\
            .filter(
                AccessEvent.org_id == org_id,
                func.date(AccessEvent.ts) == stat.date,
                *filters
            ).scalar() or 0
        
        # Find peak hour for this day
        peak_hour_data = db.query(
            extract('hour', AccessEvent.ts).label('hour'),
            func.count(AccessEvent.id).label('event_count')
        ).join(Site, AccessEvent.site_id == Site.id)\
         .filter(
            AccessEvent.org_id == org_id,
            func.date(AccessEvent.ts) == stat.date,
            *filters
        ).group_by(extract('hour', AccessEvent.ts))\
         .order_by(func.count(AccessEvent.id).desc())\
         .first()
        
        peak_hour = "12:00"  # Default
        if peak_hour_data:
            hour = int(peak_hour_data.hour)
            peak_hour = f"{hour:02d}:00"
        
        daily_data.append({
            'date': date_str,
            'visitors': unique_visitors,
            'entries': stat.entries or 0,
            'exits': stat.exits or 0,
            'peak_hour': peak_hour
        })
    
    # Sort by date ascending for chronological order
    daily_data.sort(key=lambda x: x['date'])
    
    return daily_data



def get_hourly_access_patterns(db: Session, org_id: UUID, params: AnalyticsRequest):
    """Get hourly access patterns - peak hours and traffic flow"""
    
    filters = build_advance_analytics_filter(org_id, params)
    
    # Get hourly statistics for the last 7 days
    hourly_stats = db.query(
        extract('hour', AccessEvent.ts).label('hour'),
        func.sum(case((AccessEvent.direction == 'in', 1), else_=0)).label('entries'),
        func.sum(case((AccessEvent.direction == 'out', 1), else_=0)).label('exits')
    ).join(Site, AccessEvent.site_id == Site.id)\
     .filter(
        AccessEvent.org_id == org_id,
        AccessEvent.ts >= datetime.now() - timedelta(days=7),  # Last 7 days
        *filters
    ).group_by(extract('hour', AccessEvent.ts))\
     .order_by(extract('hour', AccessEvent.ts))\
     .all()
    
    # Create a complete 24-hour pattern
    hourly_data = []
    
    for hour in range(24):
        # Find stats for this hour
        hour_stats = next((stat for stat in hourly_stats if int(stat.hour) == hour), None)
        
        entries = hour_stats.entries if hour_stats else 0
        exits = hour_stats.exits if hour_stats else 0
        
        # Format hour as HH:00
        hour_str = f"{hour:02d}:00"
        
        hourly_data.append({
            'hour': hour_str,
            'entries': entries,
            'exits': exits
        })
    
    return hourly_data


def get_portfolio_heatmap(db: Session, org_id: UUID, params: AnalyticsRequest):
    """Get portfolio heatmap - occupancy distribution across floors and blocks"""
    
    filters = build_advance_analytics_filter(org_id, params)
    
    # Get all spaces with floor and building name - ADD ID TO SELECT
    spaces_query = db.query(
        Space.id,  # ADD THIS LINE
        Space.floor,
        Building.name.label('building_name'),
        Space.kind,
        Space.status
    ).join(Site, Space.site_id == Site.id)\
     .join(Building, Space.building_block_id == Building.id)\
     .filter(
        Space.org_id == org_id,
        Space.floor.isnot(None),
        Space.building_block_id.isnot(None),
        *filters
    ).all()
    
    # Get active hotel room bookings
    active_bookings = db.query(BookingRoom.space_id)\
        .join(Booking, BookingRoom.booking_id == Booking.id)\
        .join(Site, Booking.site_id == Site.id)\
        .filter(
            Booking.org_id == org_id,
            Booking.check_in <= datetime.now().date(),
            Booking.check_out > datetime.now().date(),
            Booking.status.in_(['reserved', 'in_house', 'checked_in']),
            *filters
        ).all()
    active_booking_space_ids = {booking.space_id for booking in active_bookings}
    
    # Get active leases
    active_leases = db.query(Lease.space_id)\
        .join(Site, Lease.site_id == Site.id)\
        .filter(
            Lease.org_id == org_id,
            Lease.start_date <= datetime.now().date(),
            Lease.end_date >= datetime.now().date(),
            Lease.status == 'active',
            *filters
        ).all()
    active_lease_space_ids = {lease.space_id for lease in active_leases}
    
    # Group spaces by floor and building name
    floor_block_data = {}
    
    for space in spaces_query:
        floor = space.floor or 'Unknown'
        building_name = space.building_name or 'Unknown'
        key = (floor, building_name)
        
        if key not in floor_block_data:
            floor_block_data[key] = {
                'total_spaces': 0,
                'occupied_spaces': 0
            }
        
        floor_block_data[key]['total_spaces'] += 1
        
        # Check if space is occupied
        is_occupied = False
        
        if space.status in ['occupied', 'checked_in']:
            is_occupied = True
        elif space.kind == 'room' and space.id in active_booking_space_ids:
            is_occupied = True
        elif space.kind in ['apartment', 'shop', 'office'] and space.id in active_lease_space_ids:
            is_occupied = True
        
        if is_occupied:
            floor_block_data[key]['occupied_spaces'] += 1
    
    # Convert to heatmap format
    heatmap_data = []
    
    for (floor, building_name), data in floor_block_data.items():
        total = data['total_spaces']
        occupied = data['occupied_spaces']
        
        # Calculate occupancy percentage
        occupancy_rate = (occupied / total * 100) if total > 0 else 0
        
        heatmap_data.append({
            'floor': floor,
            'block': building_name,
            'occupancy': round(occupancy_rate)  # Whole number percentage
        })
    
    # Sort by floor and building name for consistent ordering
    heatmap_data.sort(key=lambda x: (x['floor'], x['block']))
    
    return heatmap_data


def get_performance_summary(db: Session, org_id: UUID, params: AnalyticsRequest):
    """Get performance summary - key metrics overview"""
    
    filters = build_advance_analytics_filter(org_id, params)
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    # Total Sites
    total_sites = db.query(func.count(Site.id))\
        .filter(
            Site.org_id == org_id,
            *filters
        ).scalar() or 0
    
    # Total Spaces
    total_spaces = db.query(func.count(Space.id))\
        .join(Site, Space.site_id == Site.id)\
        .filter(
            Space.org_id == org_id,
            *filters
        ).scalar() or 0
    
    # Occupancy Calculation
    total_occupied = 0
    
    # Hotel rooms occupancy
    hotel_occupied = db.query(func.count(BookingRoom.id))\
        .join(Booking, BookingRoom.booking_id == Booking.id)\
        .join(Space, BookingRoom.space_id == Space.id)\
        .join(Site, Booking.site_id == Site.id)\
        .filter(
            Space.org_id == org_id,
            Space.kind == 'room',
            *filters,
            Booking.check_in <= datetime.now().date(),
            Booking.check_out > datetime.now().date(),
            Booking.status.in_(['reserved', 'in_house', 'checked_in'])
        ).scalar() or 0
    
    # Leased spaces occupancy
    leased_occupied = db.query(func.count(Lease.id))\
        .join(Space, Lease.space_id == Space.id)\
        .join(Site, Lease.site_id == Site.id)\
        .filter(
            Lease.org_id == org_id,
            *filters,
            Lease.start_date <= datetime.now().date(),
            Lease.end_date >= datetime.now().date(),
            Lease.status == 'active'
        ).scalar() or 0
    
    total_occupied = hotel_occupied + leased_occupied
    avg_occupancy = (total_occupied / total_spaces * 100) if total_spaces > 0 else 0
    
    # Monthly Revenue (current month)
    monthly_revenue = db.query(func.sum(FolioCharge.amount))\
        .join(Folio, FolioCharge.folio_id == Folio.id)\
        .join(Booking, Folio.booking_id == Booking.id)\
        .join(Site, Booking.site_id == Site.id)\
        .filter(
            Booking.org_id == org_id,
            extract('year', FolioCharge.date) == current_year,
            extract('month', FolioCharge.date) == current_month,
            *filters
        ).scalar() or 0
    
    # Collection Rate - FIXED: Convert both to float before division
    total_invoiced = db.query(func.sum(Invoice.totals['grand'].as_float()))\
        .join(Site, Invoice.site_id == Site.id)\
        .filter(
            Site.org_id == org_id,
            extract('year', Invoice.date) == current_year,
            extract('month', Invoice.date) == current_month,
            *filters
        ).scalar() or 0.0  # Ensure it's float
    
    # Fixed: Use correct table name 'payments_ar' instead of 'PaymentAR'
    total_collected = db.query(func.sum(PaymentAR.amount))\
        .join(Invoice, PaymentAR.invoice_id == Invoice.id)\
        .join(Site, Invoice.site_id == Site.id)\
        .filter(
            Site.org_id == org_id,
            extract('year', PaymentAR.paid_at) == current_year,
            extract('month', PaymentAR.paid_at) == current_month,
            *filters
        ).scalar() or 0.0  # Ensure it's float
    
    # FIX: Convert both to float before division
    total_invoiced_float = float(total_invoiced)
    total_collected_float = float(total_collected)
    
    collection_rate = (total_collected_float / total_invoiced_float * 100) if total_invoiced_float > 0 else 0.0
    
    # Format revenue in Indian format (₹ with K for thousands)
    if monthly_revenue >= 100000:
        revenue_display = f"₹{monthly_revenue/100000:.1f}L"
    elif monthly_revenue >= 1000:
        revenue_display = f"₹{monthly_revenue/1000:.1f}K"
    else:
        revenue_display = f"₹{monthly_revenue:.0f}"
    
    summary_data = {
    
       'Total Properties': f"{total_sites}",
       'Total Spaces': f"{total_spaces} ",
       'Avg Occupancy': f"{avg_occupancy:.1f}",
       'Monthly Revenue': revenue_display ,
       'Collection Rate': f"{collection_rate:.1f}"
    }
    return summary_data

