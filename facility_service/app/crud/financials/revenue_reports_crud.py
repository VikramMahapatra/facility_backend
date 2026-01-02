
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import Numeric, cast, func

from facility_service.app.models.leasing_tenants.leases import Lease

from ...models.leasing_tenants.lease_charges import LeaseCharge

from ...schemas.financials.revenue_schemas import RevenueReportsRequest
from ...models.financials.invoices import Invoice
from ...enum.revenue_enum import RevenueMonth
from ...models.space_sites.sites import Site
from uuid import UUID
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case
from datetime import date, datetime
from dateutil.relativedelta import relativedelta


def revenue_reports_filter_site_lookup(db: Session, org_id: str):
    rows = (
        db.query(
            func.lower(Site.name).label("id"),
            func.initcap(Site.name).label("name")
        )
        .filter(Site.org_id == org_id)
        .distinct()
        .order_by(func.lower(Site.name).asc())
        .all()
    )
    return [{"id": r.id, "name": r.name} for r in rows]


def revenue_reports_site_month_lookup(db: Session, org_id: str, status: Optional[str] = None):
    return [
        {"id": month.value, "name": month.name.replace('_', ' ').title()}
        for month in RevenueMonth
    ]



def build_revenue_filters(org_id: UUID, params: RevenueReportsRequest):
    filters = [
        Invoice.org_id == org_id,
        Invoice.is_deleted.is_(False)
    ]

    if params.site_id:
        filters.append(Invoice.site_id == params.site_id)

  
    if params.month:
        today = datetime.now().date()

        if params.month == RevenueMonth.LAST_MONTH:
            start_date = today - relativedelta(months=1)

        elif params.month == RevenueMonth.LAST_3_MONTHS:
            start_date = today - relativedelta(months=3)

        elif params.month == RevenueMonth.LAST_6_MONTHS:
            start_date = today - relativedelta(months=6)

        elif params.month == RevenueMonth.LAST_YEAR:
            start_date = today - relativedelta(years=1)

        filters.append(Invoice.date >= start_date)

   
    if params.status and params.status.lower() != "all":
        filters.append(Invoice.status == params.status)

    return filters


def get_revenue_overview(db: Session, org_id: UUID, params: RevenueReportsRequest):
    filters = build_revenue_filters(org_id, params)
    
    # Get all unique charge codes for the organization
    charge_codes_query= db.query(
        LeaseCharge.charge_code.distinct()
    ).join(Lease, LeaseCharge.lease_id == Lease.id)\
    .join(
        Invoice,
        and_(
            Invoice.billable_item_type == "lease charge",
            Invoice.billable_item_id == LeaseCharge.id
        )
    )\
    .filter(
        *filters, 
        Lease.org_id == org_id,
        LeaseCharge.is_deleted.is_(False),
        LeaseCharge.charge_code.isnot(None)
    ).all()
    print("Charge Codes Query Result:", charge_codes_query)
    charge_codes = [code[0] for code in charge_codes_query if code[0]]  # Extract codes from tuple
    
    # TOTAL & PAID REVENUE (Invoice) - Keep this as is
    invoice_totals = db.query(
        func.coalesce(
            func.sum(
                case(
                    (Invoice.status.in_(["draft", "issued", "partial", "paid"]),
                     cast(func.jsonb_extract_path_text(Invoice.totals, "grand"), Numeric)),
                    else_=0
                )
            ), 0
        ).label("total_revenue"),

        func.coalesce(
            func.sum(
                case(
                    (Invoice.status == "paid",
                     cast(func.jsonb_extract_path_text(Invoice.totals, "grand"), Numeric)),
                    else_=0
                )
            ), 0
        ).label("paid_revenue")
    ).filter(*filters,
            Invoice.billable_item_type == "lease charge"  ).one()
    
    # Dynamic calculation for all charge codes
    charge_code_revenues = {}
    
    if charge_codes:
        base_query = db.query(
            LeaseCharge.charge_code,
            func.coalesce(  
                func.sum(
                    case(
                        (func.jsonb_typeof(Invoice.totals) == 'object',
                         cast(func.jsonb_extract_path_text(Invoice.totals, 'grand'), Numeric)),
                        else_=cast(Invoice.totals, Numeric)
                    )
                ), 0
            ).label("revenue")
        ).select_from(LeaseCharge)\
         .join(Lease, LeaseCharge.lease_id == Lease.id)\
         .join(
             Invoice,
             and_(
                 Invoice.billable_item_type == "lease charge",
                 Invoice.billable_item_id == LeaseCharge.id
             )
         ).filter(
             *filters,
             LeaseCharge.is_deleted.is_(False),
             LeaseCharge.charge_code.in_(charge_codes),
             Lease.org_id == org_id
         ).group_by(LeaseCharge.charge_code)
        
        # Execute the query
        results = base_query.all()
        
        # Convert results to dictionary
        charge_code_revenues = {row.charge_code: float(row.revenue) for row in results}
    
    # Ensure all charge codes have an entry (even if 0)
    for code in charge_codes:
        if code not in charge_code_revenues:
            charge_code_revenues[code] = 0.0
    
    # Calculate collection rate
    total_revenue = float(invoice_totals.total_revenue or 0)
    paid_revenue = float(invoice_totals.paid_revenue or 0)
    
    collection_rate = (paid_revenue / total_revenue * 100) if total_revenue > 0 else 0
    
    # Prepare response with dynamic charge codes
    response = {
        "TotalRevenue": f"{total_revenue:.1f}",
        "CollectionRate": f"{collection_rate:.1f}"
    }
    
    # Add each charge code revenue to the response
    for code, revenue in charge_code_revenues.items():
        response[f"{code}Revenue"] = f"{revenue:.1f}"
    
    return response




def get_revenue_trend(db: Session, org_id: UUID, params: RevenueReportsRequest):
    filters = build_revenue_filters(org_id, params)

    # Get all unique charge codes for the organization
    charge_codes_query = db.query(
        func.upper(LeaseCharge.charge_code).label("charge_code")
    ).distinct()\
    .join(Lease, LeaseCharge.lease_id == Lease.id)\
    .join(
        Invoice,
        and_(
            Invoice.billable_item_type == "lease charge",
            Invoice.billable_item_id == LeaseCharge.id
        )
    )\
    .filter(
        *filters,  
        LeaseCharge.is_deleted.is_(False),
        LeaseCharge.charge_code.isnot(None),
        Lease.org_id == org_id
    ).all()
    
    # Extract and normalize charge codes
    charge_codes = []
    for code_tuple in charge_codes_query:
        if code_tuple[0]: 
            charge_codes.append(code_tuple[0].upper())

    trend = {}

    # Invoice totals + penalties
    invoice_rows = db.query(
        func.to_char(Invoice.date, "YYYY-MM").label("month"),
        func.coalesce(
            cast(func.jsonb_extract_path_text(Invoice.totals, "grand"), Numeric),
            0
        ).label("total"),
        func.coalesce(
            case(
                (Invoice.status == "paid",
                 cast(func.jsonb_extract_path_text(Invoice.totals, "grand"), Numeric)),
                else_=0
            ),
            0
        ).label("collected"),
        func.coalesce(
            cast(func.jsonb_extract_path_text(Invoice.meta, "penalties"), Numeric),
            0
        ).label("penalties")
    ).filter(*filters).all()

    # Process invoice rows
    for r in invoice_rows:
        if r.month not in trend:
            # Initialize month data with dynamic structure
            month_data = {
                "total": 0,
                "collected": 0,
                "penalties": 0,
            }
            # Initialize all charge codes to 0
            for code in charge_codes:
                month_data[code.lower()] = 0
            trend[r.month] = month_data

        trend[r.month]["total"] += float(r.total)
        trend[r.month]["collected"] += float(r.collected or 0)
        trend[r.month]["penalties"] += float(r.penalties)

    # Lease charge rows for all charge codes (YOUR ORIGINAL QUERY - CORRECTED)
    lease_rows = db.query(
        func.to_char(Invoice.date, "YYYY-MM").label("month"),
        LeaseCharge.charge_code,
        func.coalesce(LeaseCharge.amount, 0).label("amount")
    ).select_from(LeaseCharge)\
     .join(Lease, LeaseCharge.lease_id == Lease.id)\
     .join(
         Invoice,
         and_(
             Invoice.billable_item_type == "lease charge",
             Invoice.billable_item_id == LeaseCharge.id
         )
     ).filter(
         *filters,
         LeaseCharge.is_deleted.is_(False),
         Lease.org_id == org_id
     ).all()

    # Process lease rows - DYNAMICALLY
    for r in lease_rows:
        month = r.month
        code = (r.charge_code or "").upper()
        amount = float(r.amount or 0)
        
        if not month or not code or amount == 0:
            continue
            
        # Ensure month exists in trend
        if month not in trend:
            month_data = {
                "total": 0,
                "collected": 0,
                "penalties": 0,
            }
            # Initialize all known charge codes
            for charge_code in charge_codes:
                month_data[charge_code.lower()] = 0
            trend[month] = month_data
        
        # Handle the charge code
        if code not in charge_codes:
            # This is a new charge code we haven't seen before
            charge_codes.append(code)
            # Initialize this code for all existing months
            for existing_month in trend.keys():
                trend[existing_month][code.lower()] = 0
        
        # Add amount to the specific charge code
        trend[month][code.lower()] += amount

    # Final response
    result = []
    for month in sorted(trend.keys()):
        data = trend[month]
        outstanding = data["total"] - data["collected"]
        
        
        month_result = {
            "month": month,
            "penalties": f"{data['penalties']:.0f}",
            "total": f"{data['total']:.0f}",
            "collected": f"{data['collected']:.0f}",
            "outstanding": f"{outstanding:.0f}",
        }
        
        # Add all charge code fields
        for code in charge_codes:
            month_result[code.lower()] = f"{data.get(code.lower(), 0):.0f}"
        
        result.append(month_result)

    return result


def get_revenue_by_source(db: Session, org_id: UUID, params: RevenueReportsRequest):
    filters = build_revenue_filters(org_id, params)

    # Get all unique charge codes for the organization
    charge_codes_query = db.query(
        func.upper(LeaseCharge.charge_code).label("charge_code")
    ).distinct()\
     .join(Lease, LeaseCharge.lease_id == Lease.id)\
     .filter(
         Lease.org_id == org_id,
         LeaseCharge.is_deleted.is_(False),
         LeaseCharge.charge_code.isnot(None)
     ).all()
    
    # Extract charge codes
    all_charge_codes = [code.charge_code for code in charge_codes_query]
  

    # Get lease charge amounts grouped by charge code
    rows = db.query(
        func.upper(LeaseCharge.charge_code).label("charge_code"),
        func.coalesce(func.sum(LeaseCharge.amount), 0).label("amount")
    ).select_from(LeaseCharge)\
     .join(Lease, LeaseCharge.lease_id == Lease.id)\
     .join(
         Invoice,
         and_(
             Invoice.billable_item_type == "lease charge",
             Invoice.billable_item_id == LeaseCharge.id
         )
     ).filter(
         *filters,
         LeaseCharge.is_deleted.is_(False),
         Lease.org_id == org_id,
         LeaseCharge.charge_code.isnot(None)
     ).group_by(func.upper(LeaseCharge.charge_code)).all()

    # Create totals dictionary from query results
    totals = {}
    for r in rows:
        totals[r.charge_code] = float(r.amount or 0)
    
    # Ensure all charge codes are in totals (even with 0)
    for code in all_charge_codes:
        if code not in totals:
            totals[code] = 0.0


    # Calculate grand total
    grand_total = sum(totals.values())
    
    # Prepare result - include ALL charge codes
    result = []
    for code, value in totals.items():
        if value <= 0:
            continue  # skip zero-value charge codes

        percentage = (value / grand_total * 100) if grand_total > 0 else 0
        result.append({
            "name": code,
            "value": round(percentage, 1)
        })

    # Sort by value descending
    result.sort(key=lambda x: x["value"], reverse=True)
    
    return result



def get_outstanding_receivables(db: Session, org_id: UUID, params: RevenueReportsRequest):
    filters = build_revenue_filters(org_id, params)

    today = date.today()

    buckets = {
        "0-30 days": 0,
        "31-60 days": 0,
        "61-90 days": 0,
        "90+ days": 0
    }

    rows = db.query(
        Invoice.date.label("invoice_date"),

        func.coalesce(
            cast(func.jsonb_extract_path_text(Invoice.totals, "grand"), Numeric),
            0
        ).label("amount")
    ).filter(
        *filters,
        Invoice.status != "paid"
    ).all()

    for r in rows:
        if not r.invoice_date:
            continue

        days_due = (today - r.invoice_date).days
        amount = float(r.amount)

        if days_due <= 30:
            buckets["0-30 days"] += amount
        elif days_due <= 60:
            buckets["31-60 days"] += amount
        elif days_due <= 90:
            buckets["61-90 days"] += amount
        else:
            buckets["90+ days"] += amount

    result = []
    for period, amount in buckets.items():
        result.append({
            "period": period,
            "amount": round(amount)
        })

    return result


