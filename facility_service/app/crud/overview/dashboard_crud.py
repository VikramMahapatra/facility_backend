from typing import Any, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import Integer, and_, extract, func, case , literal_column, or_
from datetime import date, datetime, timedelta

from ...models.leasing_tenants.lease_charge_code import LeaseChargeCode

from ...models.financials.tax_codes import TaxCode

from ...models.service_ticket.tickets import Ticket
from ...models.service_ticket.tickets_work_order import TicketWorkOrder

from ...schemas.overview.dasboard_schema import OccupancyByFloorResponse

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
        db.query(func.count(TicketWorkOrder.id))
        .filter(TicketWorkOrder.ticket_id==Ticket.id,
                Ticket.status=="open")
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
            "title": "Total Sites",
            "value": str(int(total_properties)),
            "icon": "Building2",
            "trend": "up",
            "change": "+0%",
            "description": "Active Sites",
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
                func.sum(LeaseCharge.amount + (LeaseCharge.amount * TaxCode.rate / 100)), 0
            )
        )
        .join(Lease, Lease.id == LeaseCharge.lease_id)
        .join(TaxCode, TaxCode.id == LeaseCharge.tax_code_id)
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
    
    # Open Tickets
    open_tickets = db.query(func.count(Ticket.id))\
        .filter(Ticket.org_id == org_id,
                func.lower(Ticket.status)==  'open')\
        .scalar() or 0
        
    # Closed Tickets
    closed_tickets = db.query(func.count(Ticket.id))\
        .filter(Ticket.org_id == org_id,
                func.lower(Ticket.status) == 'closed')\
        .scalar() or 0

    # Upcoming PM - 
    upcoming_pm = db.query(func.count(PMTemplate.id))\
        .filter(PMTemplate.org_id==org_id,
                func.lower(PMTemplate.status) =="active")\
        .scalar()or 0

    service_requests = db.query(func.count(Ticket.id))\
        .filter(Ticket.org_id == org_id,
                func.lower(Ticket.status)==  'open')\
        .scalar() or 0
  
    asset_at_risk = db.query(
        func.sum(
            case(
                (and_(
                    Asset.warranty_expiry.isnot(None),
                    Asset.warranty_expiry < today,
                    Asset.is_deleted ==False
                ), 1),
                else_=0 
            )
        )
    ).filter(Asset.org_id == org_id,
            func.lower(Asset.status) == "active",).scalar() or 0
 
    return {
        "open": open_tickets,                 
        "closed": closed_tickets,             
        "upcoming_pm": upcoming_pm,           
        "service_requests": service_requests, 
        "asset_at_risk": asset_at_risk   
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
                func.sum(LeaseCharge.amount + LeaseCharge.amount * TaxCode.rate / 100),
                0
            )
        )
        .join(Lease, Lease.id == LeaseCharge.lease_id)
        .join(TaxCode, TaxCode.id == LeaseCharge.tax_code_id)
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
                func.sum(LeaseCharge.amount + LeaseCharge.amount * TaxCode.rate / 100), 0
            )
        )
        .join(Lease, Lease.id == LeaseCharge.lease_id)
        .join(TaxCode, TaxCode.id == LeaseCharge.tax_code_id)
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
        .join(LeaseChargeCode, LeaseChargeCode.id == LeaseCharge.charge_code_id)
        .filter(
            Lease.org_id == org_id,
            func.lower(LeaseChargeCode.code).like("cam%"),
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
                    func.sum(LeaseCharge.amount + LeaseCharge.amount * TaxCode.rate / 100),
                    0
                )
            )
            .join(Lease, Lease.id == LeaseCharge.lease_id)
            .join(TaxCode, TaxCode.id == LeaseCharge.tax_code_id)
            .join(LeaseChargeCode, LeaseChargeCode.id == LeaseCharge.charge_code_id)
            .filter(
                Lease.org_id == org_id,
                LeaseCharge.period_start <= month_end,
                LeaseCharge.period_end >= month_start,
                ~func.lower(LeaseChargeCode.code).like("cam%")
            )
            .scalar() or 0.0
        ))
        
        # Calculate CAM revenue for the month
        cam_revenue = float((
            db.query(
                func.coalesce(
                    func.sum(LeaseCharge.amount + LeaseCharge.amount * TaxCode.rate / 100),
                    0
                )
            )
            .join(Lease, Lease.id == LeaseCharge.lease_id)
            .join(TaxCode, TaxCode.id == LeaseCharge.tax_code_id)
            .join(LeaseChargeCode, LeaseChargeCode.id == LeaseCharge.charge_code_id)
            .filter(
                Lease.org_id == org_id,
                LeaseCharge.period_start <= month_end,
                LeaseCharge.period_end >= month_start,
                func.lower(LeaseChargeCode.code).like("cam%")
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



def work_orders_priority(db: Session, org_id: UUID) -> List[Dict]:
    # Base query
    query = db.query(
        Ticket.priority,
        func.count(Ticket.id).label('count')
    ).filter(
        Ticket.status=="open", 
        TicketWorkOrder.id.is_not(None)
    )

    query = query.join(
        TicketWorkOrder, 
        TicketWorkOrder.ticket_id == Ticket.id
    )
    
    if org_id:
        query = query.filter(Ticket.org_id == org_id)
    
    results = query.group_by(Ticket.priority).all()
    
    priority_order = ["high", "medium", "low"]

    priority_counts = {row.priority: row.count for row in results}
 
    response = []
    for priority in priority_order:
        response.append({
            "priority": priority,
            "count": priority_counts.get(priority, 0)
        })
    
    return response

def get_energy_consumption_trend(db: Session, org_id: UUID):
    # Get the current date and calculate the last 4 months
    today = date.today()
    
    current_month_start = today.replace(day=1)
    
    # Generate the last 4 months including current month
    months = []
    for i in range(3, -1, -1):  # Last 3 months + current month: Aug, Sep, Oct, Nov
        month_date = current_month_start - relativedelta(months=i)
        months.append({
            "date": month_date,
            "label": month_date.strftime("%b")
        })
    
    monthly_data = []
    
    for month_info in months:
        month_start = month_info["date"]
        month_end = (month_start + relativedelta(months=1)) - timedelta(days=1)
        
        # Use between() for cleaner date range filtering
        electricity_consumption = float((
            db.query(
                func.coalesce(func.sum(MeterReading.delta), 0)
            )
            .join(Meter, Meter.id == MeterReading.meter_id)
            .filter(
                Meter.org_id == org_id,
                Meter.kind == "electricity",
                func.date(MeterReading.ts).between(month_start, month_end)
            )
            .scalar() or 0.0
        ))
        
        water_consumption = float((
            db.query(
                func.coalesce(func.sum(MeterReading.delta), 0)
            )
            .join(Meter, Meter.id == MeterReading.meter_id)
            .filter(
                Meter.org_id == org_id,
                Meter.kind == "water",
                func.date(MeterReading.ts).between(month_start, month_end)
            )
            .scalar() or 0.0
        ))
        
        gas_consumption = float((
            db.query(
                func.coalesce(func.sum(MeterReading.delta), 0)
            )
            .join(Meter, Meter.id == MeterReading.meter_id)
            .filter(
                Meter.org_id == org_id,
                Meter.kind == "gas",
                func.date(MeterReading.ts).between(month_start, month_end)
            )
            .scalar() or 0.0
        ))
        
        monthly_data.append({
            "month": month_info["label"],
            "electricity": round(electricity_consumption, 2),
            "water": round(water_consumption, 2),
            "gas": round(gas_consumption, 2)
        })
    
    return monthly_data


def get_occupancy_by_floor(db: Session, org_id: UUID) -> List[OccupancyByFloorResponse]:
    """
    Calculate occupancy statistics by floor for a given organization using dynamic grouping
    Returns only: floor, total, occupied, available, outOfService
    """
    # Single query to get all occupancy stats grouped by floor
    occupancy_stats = db.query(
        Space.floor,
        func.count(Space.id).label('total'),
        func.sum(case((func.lower(Space.status) == 'occupied', 1), else_=0)).label('occupied'),
        func.sum(case((func.lower(Space.status) == 'available', 1), else_=0)).label('available'),
        func.sum(case((func.lower(Space.status) == 'out_of_service', 1), else_=0)).label('out_of_service')
    ).filter(
        Space.org_id == org_id,
        Space.is_deleted == False,
        Space.floor.isnot(None)
    ).group_by(
        Space.floor
    ).order_by(
        # Natural sorting: numeric floors first, then others
        func.cast(Space.floor, Integer).nullsfirst(),  # Fixed: Use Integer from sqlalchemy
        Space.floor
    ).all()
    
        # Convert to the exact format requested
    occupancy_data = []
    for floor, total, occupied, available, out_of_service in occupancy_stats:
        floor_str = str(floor) if floor is not None else "Unknown"
        
        # Dynamic floor name conversion - integrated directly
        floor_lower = floor_str.lower().strip()
        
        # Special cases
        if floor_lower == "0":
            floor_display = "Ground Floor"
        else:
            # Numeric floors
            try:
                floor_num = int(floor_lower)
                suffixes = {1: "st", 2: "nd", 3: "rd"}
                suffix = suffixes.get(floor_num, "th") if floor_num < 4 else "th"
                floor_display = f"{floor_num}{suffix} Floor"
            except (ValueError, TypeError):
                # If it's not a number, return the original string capitalized
                floor_display = floor_str.title()
        
        occupancy_data.append(OccupancyByFloorResponse(
            floor=floor_display,
            total=total or 0,
            occupied=occupied or 0,
            available=available or 0,
            outOfService=out_of_service or 0
        ))
    
    return occupancy_data




def get_energy_status(db: Session, org_id: UUID):
    # Calculate total consumption for ALL meter kinds
    total_consumption = db.query(func.coalesce(func.sum(MeterReading.reading), 0))\
        .join(Meter, MeterReading.meter_id == Meter.id)\
        .filter(Meter.org_id == org_id,
                Meter.is_deleted == False,
                MeterReading.is_deleted == False)\
        .scalar() or 0

    alerts = []
    recent_threshold = datetime.utcnow() - timedelta(days=7)

    # 1. Check for meters with no recent readings - USING LEFT JOIN
    subquery = db.query(MeterReading.meter_id)\
        .filter(MeterReading.ts >= recent_threshold,
                MeterReading.is_deleted == False)\
        .subquery()

    meters_without_readings = db.query(Meter.kind)\
        .outerjoin(subquery, Meter.id == subquery.c.meter_id)\
        .filter(Meter.org_id == org_id,
                Meter.is_deleted == False,
                subquery.c.meter_id == None)\
        .distinct()\
        .all()

    for (meter_kind,) in meters_without_readings:
        alerts.append({
            "type": meter_kind,
            "message": ""
        })

    # If no issues found, return system status
    if not alerts:
        alerts.append({
            "type": "System", 
            "message": ""
        })

    return {
        "totalConsumption": int(total_consumption),
        "alerts": alerts
    }