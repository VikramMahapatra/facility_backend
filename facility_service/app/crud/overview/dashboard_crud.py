from typing import Any, Dict
from sqlalchemy.orm import Session
from sqlalchemy import extract, func, case , literal_column, or_
from datetime import date, timedelta

from ...models.parking_access.access_events import AccessEvent

from ...models.hospitality.booking_cancellations import BookingCancellation
from ...models.hospitality.folios_charges import FolioCharge
from ...models.hospitality.housekeeping_tasks import HousekeepingTask

from ...models.hospitality.bookings import Booking
from ...models.parking_access.parking_pass import ParkingPass
from ...models.parking_access.parking_zones import ParkingZone
from ...models.parking_access.visitors import Visitor
from ...models.space_sites.spaces import Space
from ...models.leasing_tenants.leases import Lease  
from ...models.leasing_tenants.lease_charges import LeaseCharge
from ...models.maintenance_assets.pm_template import PMTemplate
from ...models.maintenance_assets.service_request import ServiceRequest
from ...models.maintenance_assets.work_order import WorkOrder
from ...models.maintenance_assets.assets import Asset
from ...models.space_sites.sites import Site
from ...models.hospitality.folios import Folio 
from ...models.hospitality.folios_payments import FolioPayment
from ...models.energy_iot.meter_readings import MeterReading
from ...models.energy_iot.meters import Meter
from ...models.financials.invoices import Invoice, PaymentAR
from sqlalchemy.dialects.postgresql import UUID
from dateutil.relativedelta import relativedelta
from datetime import timedelta

def get_overview_data(db: Session, org_id: UUID) -> Dict[str, Any]:
    today = date.today()

    # ------------------- Total Properties -------------------
    total_properties = db.query(func.count(Site.id))\
        .filter(Site.org_id == org_id, Site.status == "active")\
        .scalar() or 0

    # ------------------- Occupancy Rate -------------------
    occupied_count = db.query(func.count(Space.id))\
        .filter(Space.org_id == org_id, Space.status == "occupied")\
        .scalar() or 0
    total_spaces = db.query(func.count(Space.id))\
        .filter(Space.org_id == org_id)\
        .scalar() or 1
    occupancy_rate = round((occupied_count / total_spaces) * 100, 2)

    # ------------------- Monthly Revenue -------------------
    total_charges = (
        db.query(func.coalesce(func.sum(FolioCharge.amount + (FolioCharge.amount * FolioCharge.tax_pct / 100)), 0))
        .join(Folio, Folio.id == FolioCharge.folio_id)
        .join(Booking, Booking.id == Folio.booking_id)
        .filter(
            Booking.org_id == org_id,
            extract("month", FolioCharge.date) == today.month,
            extract("year", FolioCharge.date) == today.year
        )
        .scalar()
    ) or 0.0

    total_refunds = (
        db.query(func.coalesce(func.sum(BookingCancellation.refund_amount), 0))
        .join(Booking, Booking.id == BookingCancellation.booking_id)
        .filter(
            Booking.org_id == org_id,
            extract("month", BookingCancellation.cancelled_at) == today.month,
            extract("year", BookingCancellation.cancelled_at) == today.year,
            BookingCancellation.refund_processed == True
        )
        .scalar()
    ) or 0.0

    monthly_revenue = total_charges - total_refunds

    # ------------------- Work Orders -------------------
    total_work_orders = (
        db.query(func.count(WorkOrder.id))
        .filter(WorkOrder.status == "open")
        .scalar()
        or 0
    )

    # ------------------- Rent Collections -------------------
    rent_collections = (
        db.query(func.coalesce(func.sum(FolioPayment.amount), 0))
        .join(Folio, Folio.id == FolioPayment.folio_id)
        .join(Booking, Booking.id == Folio.booking_id)
        .filter(
            Booking.org_id == org_id,
            extract("month", FolioPayment.paid_at) == today.month,
            extract("year", FolioPayment.paid_at) == today.year
        )
        .scalar() or 0.0
    )

    # ------------------- Energy Usage -------------------
    energy_usage = (
        db.query(func.coalesce(func.sum(MeterReading.delta), 0))
        .join(Meter, MeterReading.meter_id == Meter.id)
        .filter(
            Meter.org_id == org_id,
            Meter.kind == "electricity",
            MeterReading.ts >= func.date_trunc("month", func.current_date()),
            MeterReading.ts < func.date_trunc("month", func.current_date()) + literal_column("INTERVAL '1 month'"),
        )
        .scalar()
        or 0.0
    )

    # Format values as strings for consistent frontend display
    stats_list = [
        {
            "title": "Total Properties",
            "value": str(int(total_properties)),
            "icon": "Building2",
            "trend": "up",
            "change": "+0%",
            "description": "Active properties",
        },
        {
            "title": "Occupancy Rate",
            "value": f"{occupancy_rate}%",
            "icon": "Users",
            "trend": "up",
            "change": "+0%",
            "description": "Current occupancy",
        },
        {
            "title": "Monthly Revenue",
            "value": f"₹{monthly_revenue:,.0f}",
            "icon": "CreditCard",
            "trend": "up",
            "change": "+0%",
            "description": "This month's income",
        },
        {
            "title": "Work Orders",
            "value": str(int(total_work_orders)),
            "icon": "Wrench",
            "trend": "up",
            "change": "+0%",
            "description": "Open tickets",
        },
        {
            "title": "Rent Collections",
            "value": f"₹{rent_collections:,.0f}",
            "icon": "BarChart3",
            "trend": "up",
            "change": "+0%",
            "description": "Collection rate",
        },
        {
            "title": "Energy Usage",
            "value": f"{energy_usage:.1f} kWh",
            "icon": "Zap",
            "trend": "up",
            "change": "+0%",
            "description": "Monthly consumption",
        },
    ]
    
    return {"stats": stats_list}



def get_leasing_overview(db: Session, org_id: UUID):
    today = date.today()

    renewals = db.query(
        func.sum(
            case(
                ((Lease.end_date >= today) &
                (Lease.end_date <= today + timedelta(days=30)) &
                (func.lower(Lease.status) == "active") &
                (Lease.org_id == org_id), 1),
                else_=0
            )
        ).label("renewals_30_days"),
        func.sum(
            case(
                ((Lease.end_date >= today) &
                (Lease.end_date <= today + timedelta(days=60)) &
                (func.lower(Lease.status) == "active") &
                (Lease.org_id == org_id), 1),
                else_=0
            )
        ).label("renewals_60_days"),
        func.sum(
            case(
                ((Lease.end_date >= today) &
                (Lease.end_date <= today + timedelta(days=90)) &
                (func.lower(Lease.status) == "active") &
                (Lease.org_id == org_id), 1),
                else_=0
            )
        ).label("renewals_90_days")
    ).first()

    # ------------------- Total Billed -------------------
    total_billed = (
        db.query(
            func.coalesce(
                func.sum(LeaseCharge.amount + (LeaseCharge.amount * LeaseCharge.tax_pct / 100)), 0
            )
        )
        .join(Lease, Lease.id == LeaseCharge.lease_id)
        .filter(
            Lease.org_id == org_id,
            Lease.status == "active"  # Optional: sum only active leases
        )
        .scalar()
    )

    # ------------------- Total Collected -------------------
    total_collected = (
        db.query(func.coalesce(func.sum(PaymentAR.amount), 0))
        .join(Invoice, Invoice.id == PaymentAR.invoice_id)
        .filter(Invoice.org_id == org_id)
        .scalar()
    )

    # ------------------- Collection Rate -------------------
    collection_rate_pct = round(
        (float(total_collected) / float(total_billed) * 100) if total_billed > 0 else 0,
        2
    )

    # ------------------- Return Overview -------------------
    return {
        "renewals_30_days": int(renewals.renewals_30_days or 0),
        "renewals_60_days": int(renewals.renewals_60_days or 0),
        "renewals_90_days": int(renewals.renewals_90_days or 0),
        "collection_rate_pct": collection_rate_pct,
    }

# ------------------------ Maintenance Status ------------------------
def get_maintenance_status(db: Session, org_id: UUID):
    today = date.today()
    
    # Open and Closed Work Orders
    open_work_orders = db.query(func.count(WorkOrder.id))\
        .filter(WorkOrder.org_id == org_id, WorkOrder.status == 'open')\
        .scalar()
    closed_work_orders = db.query(func.count(WorkOrder.id))\
        .filter(WorkOrder.org_id == org_id, WorkOrder.status == 'close')\
        .scalar()

    # Upcoming PM
    upcoming_pm = db.query(func.count(PMTemplate.id))\
        .filter(PMTemplate.org_id == org_id,
                PMTemplate.next_due >= today,
                PMTemplate.status == 'active')\
        .scalar()

    # Open Service Requests
    open_service_requests = db.query(func.count(ServiceRequest.id))\
        .filter(ServiceRequest.org_id == org_id,
                ServiceRequest.status == 'open')\
        .scalar()

    # Assets at risk
    assets_at_risk = db.query(func.count(Asset.id))\
        .filter(Asset.org_id == org_id,
                ((Asset.warranty_expiry.between(today, today + timedelta(days=30))) |
                 (Asset.status != 'active')))\
        .scalar()

    return {
        "open_work_orders": open_work_orders,
        "closed_work_orders": closed_work_orders,
        "upcoming_pm": upcoming_pm,
        "open_service_requests": open_service_requests,
        "assets_at_risk": assets_at_risk
    }

#-----------------access and parking -------------------
def get_access_and_parking(db: Session, org_id: UUID):
    today = date.today()
    
    # Today's Visitors
    today_visitors = db.query(func.count()).filter(
        Visitor.org_id == org_id,
        func.date(Visitor.entry_time) == today
    ).scalar()
        
    # Total capacity
    total_capacity = db.query(func.coalesce(func.sum(ParkingZone.capacity), 0)).filter(
        ParkingZone.org_id == org_id
    ).scalar()

    # Total occupied
    total_occupied = db.query(func.count(ParkingPass.id)).filter(
        ParkingPass.org_id == org_id,
        ParkingPass.status == 'ACTIVE',
        ParkingPass.valid_from <= today,
        ParkingPass.valid_to >= today
    ).scalar()

    # Occupancy %
    parking_occupancy_pct = round((total_occupied / total_capacity * 100) if total_capacity else 0, 2)

    
    # Spaces
    total_spaces = db.query(func.count()).filter(
        Space.org_id == org_id,
        Space.status == 'available'
    ).scalar()
    
    occupied_spaces = db.query(func.count()).filter(
        Space.org_id == org_id,
        Space.status == 'occupied'
    ).scalar()
    
    # Recent Access Events (latest 5)
    recent_access_events = (
        db.query(AccessEvent)
        .filter(AccessEvent.org_id == org_id)
        .order_by(AccessEvent.ts.desc())
        .limit(5)
        .all()
    )
    
    
    formatted_events = [
        {"time": ae.ts.strftime("%H:%M"), "event": "Entry" if ae.direction == "in" else "Exit", "location": ae.gate}
        for ae in recent_access_events
    ]
    
    return {
        "today_visitors": today_visitors,
        "parking_occupancy_pct": parking_occupancy_pct,
        "total_spaces": total_spaces,
        "occupied_spaces": occupied_spaces,
        "recent_access_events": formatted_events
    }



# ------------------------ Financial Summary ------------------------
def get_financial_summary(db: Session, org_id: UUID):
    today = date.today()

     # ------------------- Monthly Income -------------------
    monthly_income = (
        db.query(
            func.coalesce(
                func.sum(LeaseCharge.amount + LeaseCharge.amount * LeaseCharge.tax_pct / 100),
                0
            )
        )
        .join(Lease, Lease.id == LeaseCharge.lease_id)
        .filter(
            Lease.org_id == org_id,
            or_(
                LeaseCharge.period_start <= (
                    func.date_trunc("month", func.current_date()) + literal_column("INTERVAL '1 month - 1 day'")
                ),
                LeaseCharge.period_end >= func.date_trunc("month", func.current_date())
            )
        )
        .scalar()
        or 0.0
    )

    # ------------------- Overdue -------------------
    overdue = (
        db.query(
            func.coalesce(
                func.sum(LeaseCharge.amount + LeaseCharge.amount * LeaseCharge.tax_pct / 100), 0
            )
        )
        .join(Lease, Lease.id == LeaseCharge.lease_id)
        .filter(
            Lease.org_id == org_id,
            LeaseCharge.period_end < today
        )
        .scalar()
        or 0.0
    )

    # ------------------- Pending Invoices -------------------
    pending_invoices_count = (
        db.query(func.count(Invoice.id))
        .filter(
            Invoice.org_id == org_id,
            func.lower(Invoice.status).in_(
                ["draft", "pending", "unpaid", "partially"]
            )
        )
        .scalar()
        or 0
    )

    # ------------------- Recent Payments -------------------
    recent_payments_amount = (
        db.query(func.coalesce(func.sum(PaymentAR.amount), 0))
        .outerjoin(Invoice, Invoice.id == PaymentAR.invoice_id)
        .filter(
            Invoice.org_id == org_id,
            PaymentAR.paid_at != None,
            PaymentAR.paid_at >= func.date_trunc("month", func.current_date())
        )
        .scalar()
        or 0.0
    )

    # ------------------- Outstanding CAM -------------------
    outstanding_cam = (
        db.query(func.coalesce(func.sum(LeaseCharge.amount), 0))
        .join(Lease, Lease.id == LeaseCharge.lease_id)
        .filter(
            Lease.org_id == org_id,
            func.lower(LeaseCharge.charge_code).like("cam%"),
            LeaseCharge.period_end < today,
        )
        .scalar()
        or 0.0
    )

    return {
        "monthly_income": float(monthly_income),
        "overdue": float(overdue),
        "pending_invoices": int(pending_invoices_count),
        "recent_payments_total": float(recent_payments_amount),
        "outstanding_cam": float(outstanding_cam),
    }


#-------------------------------monthly revenue-----------------------
def monthly_revenue_trend(db: Session, org_id: UUID):
    # Get the current date and calculate the last 4 months
    today = date.today()
    current_month_start = today.replace(day=1)
    
    # Generate the last 4 months including current month
    months = []
    for i in range(3, -1, -1):  # Last 3 months + current month
        month_date = current_month_start - relativedelta(months=i)
        months.append({
            "date": month_date,
            "label": month_date.strftime("%b")
        })
    
    monthly_data = []
    
    for month_info in months:
        month_start = month_info["date"]
        month_end = (month_start + relativedelta(months=1)) - timedelta(days=1)
        
        # Calculate rental revenue for the month
        rental_revenue = float((
            db.query(
                func.coalesce(
                    func.sum(LeaseCharge.amount + LeaseCharge.amount * LeaseCharge.tax_pct / 100),
                    0
                )
            )
            .join(Lease, Lease.id == LeaseCharge.lease_id)
            .filter(
                Lease.org_id == org_id,
                LeaseCharge.period_start <= month_end,
                LeaseCharge.period_end >= month_start,
                ~func.lower(LeaseCharge.charge_code).like("cam%")
            )
            .scalar() or 0.0
        ))
        
        # Calculate CAM revenue for the month
        cam_revenue = float((
            db.query(
                func.coalesce(
                    func.sum(LeaseCharge.amount + LeaseCharge.amount * LeaseCharge.tax_pct / 100),
                    0
                )
            )
            .join(Lease, Lease.id == LeaseCharge.lease_id)
            .filter(
                Lease.org_id == org_id,
                LeaseCharge.period_start <= month_end,
                LeaseCharge.period_end >= month_start,
                func.lower(LeaseCharge.charge_code).like("cam%")
            )
            .scalar() or 0.0
        ))
        
        # Round all values to 2 decimal places
        rental_revenue = round(rental_revenue, 2)
        cam_revenue = round(cam_revenue, 2)
        total_revenue = round(rental_revenue + cam_revenue, 2)
        
        monthly_data.append({
            "month": month_info["label"],
            "rental": rental_revenue,
            "cam": cam_revenue,
            "total": total_revenue
        })
    
    return monthly_data



def space_occupancy(db: Session, org_id: UUID):
    # Count total spaces (excluding deleted ones)
    total_spaces = (
        db.query(func.count(Space.id))
        .filter(
            Space.org_id == org_id,
            Space.is_deleted == False
        )
        .scalar() or 0
    )
    
    # Count occupied spaces
    occupied_spaces = (
        db.query(func.count(Space.id))
        .filter(
            Space.org_id == org_id,
            Space.is_deleted == False,
            func.lower(Space.status) == "occupied"
        )
        .scalar() or 0
    )
    
    # Count available spaces
    available_spaces = (
        db.query(func.count(Space.id))
        .filter(
            Space.org_id == org_id,
            Space.is_deleted == False,
            func.lower(Space.status) == "available"
        )
        .scalar() or 0
    )
    
    # Count out of service spaces
    out_of_service_spaces = (
        db.query(func.count(Space.id))
        .filter(
            Space.org_id == org_id,
            Space.is_deleted == False,
            func.lower(Space.status) == "out_of_service"
        )
        .scalar() or 0
    )
    
    # Calculate occupancy rate (percentage)
    occupancy_rate = 0.0
    if total_spaces > 0:
        occupancy_rate = round((occupied_spaces / total_spaces) * 100, 1)
    
    return {
        "total": total_spaces,
        "occupied": occupied_spaces,
        "available": available_spaces,
        "outOfService": out_of_service_spaces,
        "occupancyRate": occupancy_rate,
    }



def work_orders_priority():
    return [ 
    { "priority": "Critical", "count": 3 },
    { "priority": "High",     "count": 8 },
    { "priority": "Medium",   "count": 12 },
    { "priority": "Low",      "count": 5 }
    ]



def get_energy_consumption_trend():
    return [
       { "month": "Sep", "electricity": 42500, "water": 1250, "gas": 890 },
    { "month": "Oct", "electricity": 44200, "water": 1180, "gas": 920 },
    { "month": "Nov", "electricity": 46800, "water": 1320, "gas": 850 },
    { "month": "Dec", "electricity": 45680, "water": 1280, "gas": 880 },
    ]


def get_occupancy_by_floor():
    return [
     
    { "floor": "Ground", "total": 65, "occupied": 52, "available": 10, "outOfService": 3 },
    { "floor": "1st Floor", "total": 58, "occupied": 43, "available": 12, "outOfService": 3 },
    { "floor": "2nd Floor", "total": 55, "occupied": 42, "available": 11, "outOfService": 2 },
    { "floor": "3rd Floor", "total": 52, "occupied": 38, "available": 9, "outOfService": 5 },
    { "floor": "Basement", "total": 18, "occupied": 12, "available": 3, "outOfService": 3 }
    ]

def get_energy_status():
    return {
        "totalConsumption": 45680,
        "alerts": [
            {"type": "High Usage", "message": "Building A electricity usage 15% above normal"},
            {"type": "Meter Issue", "message": "Water meter B-3 needs maintenance"}
        ]
    }
