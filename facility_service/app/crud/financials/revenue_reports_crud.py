
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import Numeric, cast, func

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
    # TOTAL & PAID REVENUE (Invoice)
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
    ).filter(*filters).one()
    
    cam_revenue = db.query(
        func.coalesce(func.sum(LeaseCharge.amount), 0)
    ).select_from(LeaseCharge)\
     .join(
         Invoice,
         and_(
             Invoice.billable_item_type == "lease charge",
             Invoice.billable_item_id == LeaseCharge.id
         )
     ).filter(
         *filters,
         LeaseCharge.is_deleted.is_(False),
         LeaseCharge.charge_code == "CAM"
     ).scalar()

    rent_revenue =db.query(
        func.coalesce(func.sum(LeaseCharge.amount), 0)
    ).select_from(LeaseCharge)\
     .join(
         Invoice,
         and_(
             Invoice.billable_item_type == "lease charge",
             Invoice.billable_item_id == LeaseCharge.id
         )
     ).filter(
         *filters,
         LeaseCharge.is_deleted.is_(False),
         LeaseCharge.charge_code == "RENT"
     ).scalar()


    # COLLECTION RATE
    total_revenue = float(invoice_totals.total_revenue or 0)

    paid_revenue = float(
        db.query(
            func.coalesce(
                func.sum(
                    case(
                        (Invoice.is_paid.is_(True),
                        cast(func.jsonb_extract_path_text(Invoice.totals, "grand"), Numeric)),
                        else_=0
                    )
                ), 0
            )
        ).filter(*filters).scalar() or 0
    )

    collection_rate = (paid_revenue / total_revenue * 100) if total_revenue > 0 else 0

    return {
        "TotalRevenue": f"{total_revenue:.1f}",
        "RentRevenue": f"{float(rent_revenue):.1f}",
        "CamRevenue": f"{float(cam_revenue or 0):.1f}",
        "CollectionRate": f"{collection_rate:.1f}"
    }




def get_revenue_trend(db: Session, org_id: UUID, params: RevenueReportsRequest):
    filters = build_revenue_filters(org_id, params)

    trend = {}

    #Invoice totals + penalties
    
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

    for r in invoice_rows:
        if r.month not in trend:
            trend[r.month] = {
                "rent": 0,
                "cam": 0,
                "utilities": 0,
                "penalties": 0,
                "total": 0,
                "collected": 0
            }

        trend[r.month]["total"] += float(r.total)
        trend[r.month]["collected"] += float(r.collected or 0)
        trend[r.month]["penalties"] += float(r.penalties)


    lease_rows = db.query(
        func.to_char(Invoice.date, "YYYY-MM").label("month"),
        LeaseCharge.charge_code,
        func.coalesce(LeaseCharge.amount, 0).label("amount")
    ).select_from(LeaseCharge)\
     .join(
         Invoice,
         and_(
             Invoice.billable_item_type == "lease charge",
             Invoice.billable_item_id == LeaseCharge.id
         )
     ).filter(
         *filters,
         LeaseCharge.is_deleted.is_(False)
     ).all()

    for r in lease_rows:
        if r.month not in trend:
            trend[r.month] = {
                "rent": 0,
                "cam": 0,
                "utilities": 0,
                "penalties": 0,
                "total": 0,
                "collected": 0
            }

        code = (r.charge_code or "").upper()

        if code == "RENT":
            trend[r.month]["rent"] += float(r.amount)
        elif code == "CAM":
            trend[r.month]["cam"] += float(r.amount)
        else:
            trend[r.month]["utilities"] += float(r.amount)

    #Final response

    result = []

    for month in sorted(trend.keys()):
        data = trend[month]
        outstanding = data["total"] - data["collected"]

        result.append({
            "month": month,
            "rent": f"{data['rent']:.0f}",
            "cam": f"{data['cam']:.0f}",
            "utilities": f"{data['utilities']:.0f}",
            "penalties": f"{data['penalties']:.0f}",
            "total": f"{data['total']:.0f}",
            "collected": f"{data['collected']:.0f}",
            "outstanding": f"{outstanding:.0f}",
        })

    return result



def get_revenue_by_source(db: Session, org_id: UUID, params: RevenueReportsRequest):
    filters = build_revenue_filters(org_id, params)

    totals = {
        "Rent": 0,
        "CAM": 0,
        "Utilities": 0,
        "Parking": 0
    }

    rows = db.query(
        LeaseCharge.charge_code,
        func.coalesce(LeaseCharge.amount, 0).label("amount")
    ).select_from(LeaseCharge)\
     .join(
         Invoice,
         and_(
             Invoice.billable_item_type == "lease charge",
             Invoice.billable_item_id == LeaseCharge.id
         )
     ).filter(
         *filters,
         LeaseCharge.is_deleted.is_(False)
     ).all()

    for r in rows:
        code = (r.charge_code or "").upper()
        amount = float(r.amount)

        if code == "RENT":
            totals["Rent"] += amount
        elif code == "CAM":
            totals["CAM"] += amount
        elif code == "PARKING":
            totals["Parking"] += amount
        else:
            totals["Utilities"] += amount

    grand_total = sum(totals.values()) or 1  

    result = []
    for name, value in totals.items():
        percentage = (value / grand_total) * 100

        result.append({
            "name": name,
            "value": round(percentage)
        })

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


