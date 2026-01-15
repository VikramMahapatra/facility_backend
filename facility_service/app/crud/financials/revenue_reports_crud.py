
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import Numeric, cast, func

from facility_service.app.models.leasing_tenants.lease_charge_code import LeaseChargeCode
from facility_service.app.models.leasing_tenants.lease_charge_code import LeaseChargeCode
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
    charge_codes_query = (
        db.query(LeaseChargeCode.code)
        .join(LeaseCharge, LeaseCharge.charge_code_id == LeaseChargeCode.id)
        .join(Lease, LeaseCharge.lease_id == Lease.id)
        .join(
            Invoice,
            and_(
                Invoice.billable_item_type == "lease charge",
                Invoice.billable_item_id == LeaseCharge.id
            )
        )
        .filter(
            *filters,
            Lease.org_id == org_id,
            LeaseCharge.is_deleted.is_(False),
            LeaseChargeCode.is_deleted.is_(False),
            LeaseChargeCode.code.isnot(None)
        )
        .distinct()
        .all()
    )

    
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
        base_query = (
            db.query(
                LeaseChargeCode.code.label("charge_code"),
                func.coalesce(
                    func.sum(
                        cast(
                            func.jsonb_extract_path_text(Invoice.totals, 'grand'),
                            Numeric
                        )
                    ), 0
                ).label("revenue")
            )
            .select_from(LeaseCharge)
            .join(LeaseChargeCode, LeaseCharge.charge_code_id == LeaseChargeCode.id)
            .join(Lease, LeaseCharge.lease_id == Lease.id)
            .join(
                Invoice,
                and_(
                    Invoice.billable_item_type == "lease charge",
                    Invoice.billable_item_id == LeaseCharge.id
                )
            )
            .filter(
                *filters,
                LeaseCharge.is_deleted.is_(False),
                LeaseChargeCode.is_deleted.is_(False),
                LeaseChargeCode.code.in_(charge_codes),
                Lease.org_id == org_id
            )
            .group_by(LeaseChargeCode.code)
        )

        results = base_query.all()

        charge_code_revenues = {
            row.charge_code: float(row.revenue) for row in results
        }
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

    # Get all unique charge codes
    charge_codes = [
        row[0] for row in db.query(
            func.upper(LeaseChargeCode.code)
        )
        .join(LeaseCharge, LeaseCharge.charge_code_id == LeaseChargeCode.id)
        .join(Invoice,
              and_(
                  Invoice.billable_item_type == "lease charge",
                  Invoice.billable_item_id == LeaseCharge.id
              ))
        .filter(
            *filters,
            LeaseCharge.is_deleted.is_(False),
            LeaseChargeCode.is_deleted.is_(False),
            LeaseChargeCode.code.isnot(None),
            Invoice.org_id == org_id
        )
        .distinct()
        .all()
    ]

    trend = {}

    rows = db.query(
        func.to_char(Invoice.date, "YYYY-MM").label("month"),
        LeaseChargeCode.code.label("code"),
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
    )\
    .join(LeaseCharge, Invoice.billable_item_id == LeaseCharge.id)\
    .join(LeaseChargeCode, LeaseCharge.charge_code_id == LeaseChargeCode.id)\
    .filter(
        *filters,
        Invoice.billable_item_type == "lease charge",
        Invoice.org_id == org_id,
        LeaseCharge.is_deleted.is_(False)
    )\
    .all()

    for r in rows:
        month = r.month
        code = r.code.lower()

        if month not in trend:
            trend[month] = {
                "total": 0,
                "collected": 0,
                "penalties": 0,
                **{c.lower(): 0 for c in charge_codes}
            }

        trend[month]["total"] += float(r.total)
        trend[month]["collected"] += float(r.collected)
        trend[month]["penalties"] += float(r.penalties)
        trend[month][code] += float(r.total)

    result = []
    for month in sorted(trend.keys()):
        data = trend[month]
        outstanding = data["total"] - data["collected"]

        row = {
            "month": month,
            "total": f"{data['total']:.0f}",
            "collected": f"{data['collected']:.0f}",
            "outstanding": f"{outstanding:.0f}",
            "penalties": f"{data['penalties']:.0f}",
        }

        for code in charge_codes:
            row[code.lower()] = f"{data[code.lower()]:.0f}"

        result.append(row)

    return result


def get_revenue_by_source(db: Session, org_id: UUID, params: RevenueReportsRequest):
    filters = build_revenue_filters(org_id, params)

    rows = db.query(
        LeaseChargeCode.code.label("code"),
        func.coalesce(
            func.sum(
                cast(func.jsonb_extract_path_text(Invoice.totals, "grand"), Numeric)
            ), 0
        ).label("revenue")
    )\
    .join(LeaseCharge, LeaseCharge.charge_code_id == LeaseChargeCode.id)\
    .join(
        Invoice,
        and_(
            Invoice.billable_item_type == "lease charge",
            Invoice.billable_item_id == LeaseCharge.id
        )
    )\
    .filter(
        *filters,
        Invoice.org_id == org_id,
        LeaseCharge.is_deleted.is_(False),
        LeaseChargeCode.is_deleted.is_(False),
        LeaseChargeCode.code.isnot(None)
    )\
    .group_by(LeaseChargeCode.code)\
    .all()

    totals = {row.code: float(row.revenue) for row in rows}

    grand_total = sum(totals.values())

    result = []
    for code, value in totals.items():
        if value <= 0:
            continue

        percentage = (value / grand_total * 100) if grand_total > 0 else 0
        result.append({
            "name": code,
            "value": round(percentage, 1)
        })

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


