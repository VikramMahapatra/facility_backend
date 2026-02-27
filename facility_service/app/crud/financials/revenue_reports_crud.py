
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import Numeric, cast, func

from facility_service.app.models.leasing_tenants.lease_charge_code import LeaseChargeCode
from facility_service.app.models.leasing_tenants.lease_charge_code import LeaseChargeCode
from facility_service.app.models.leasing_tenants.leases import Lease

from ...models.leasing_tenants.lease_charges import LeaseCharge

from ...schemas.financials.revenue_schemas import RevenueReportsRequest
from ...models.financials.invoices import Invoice, InvoiceLine, PaymentAR
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

    # ---------------------------------------------------------
    # Revenue by line code (rent / maintenance / parking_pass)
    # ---------------------------------------------------------
    revenue_rows = (
        db.query(
            InvoiceLine.code,
            func.coalesce(func.sum(InvoiceLine.amount), 0).label("revenue")
        )
        .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
        .filter(
            *filters,
            Invoice.org_id == org_id,
            InvoiceLine.code.in_(["rent", "maintenance", "parking_pass"])
        )
        .group_by(InvoiceLine.code)
        .all()
    )

    revenue_map = {
        row.code: float(row.revenue)
        for row in revenue_rows
    }

    rent_revenue = revenue_map.get("rent", 0.0)
    maintenance_revenue = revenue_map.get("maintenance", 0.0)
    parking_revenue = revenue_map.get("parking_pass", 0.0)

    # ---------------------------------------------------------
    # TOTAL & COLLECTION RATE (Invoice level)
    # ---------------------------------------------------------
    grand_total = cast(
        func.jsonb_extract_path_text(Invoice.totals, "grand"),
        Numeric
    )

    invoice_totals = (
        db.query(
            func.coalesce(func.sum(grand_total), 0).label("total_revenue"),
            func.coalesce(
                func.sum(
                    case(
                        (Invoice.status == "paid", grand_total),
                        else_=0
                    )
                ), 0
            ).label("paid_revenue")
        )
        .filter(
            *filters,
            Invoice.org_id == org_id
        )
        .one()
    )

    total_revenue = float(invoice_totals.total_revenue or 0)
    paid_revenue = float(invoice_totals.paid_revenue or 0)

    collection_rate = (
        (paid_revenue / total_revenue) * 100
        if total_revenue > 0 else 0
    )

    # ---------------------------------------------------------
    # RESPONSE
    # ---------------------------------------------------------
    return {
        "TotalRevenue": f"{total_revenue:.1f}",
        "CollectionRate": f"{collection_rate:.1f}",
        "RentRevenue": f"{rent_revenue:.1f}",
        "MaintenanceRevenue": f"{maintenance_revenue:.1f}",
        "ParkingPassRevenue": f"{parking_revenue:.1f}",
    }


def get_revenue_trend(db: Session, org_id: UUID, params: RevenueReportsRequest):
    filters = build_revenue_filters(org_id, params)

    REVENUE_CODES = ["rent", "maintenance", "parking_pass"]

    # ---------------------------------------------------------
    # Revenue grouped by Month + Code
    # ---------------------------------------------------------
    rows = (
        db.query(
            func.to_char(Invoice.date, "YYYY-MM").label("month"),
            InvoiceLine.code.label("code"),

            # revenue
            func.coalesce(func.sum(InvoiceLine.amount), 0).label("total"),

            # collected revenue
            func.coalesce(
                func.sum(
                    case(
                        (Invoice.status == "paid", InvoiceLine.amount),
                        else_=0
                    )
                ), 0
            ).label("collected"),

            # penalties (invoice level)
            func.coalesce(
                func.sum(
                    cast(
                        func.jsonb_extract_path_text(
                            Invoice.meta, "penalties"
                        ),
                        Numeric
                    )
                ), 0
            ).label("penalties")
        )
        .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
        .filter(
            *filters,
            Invoice.org_id == org_id,
            InvoiceLine.code.in_(REVENUE_CODES)
        )
        .group_by(
            func.to_char(Invoice.date, "YYYY-MM"),
            InvoiceLine.code
        )
        .order_by("month")
        .all()
    )

    # ---------------------------------------------------------
    # Build Trend Structure
    # ---------------------------------------------------------
    trend = {}

    for r in rows:
        month = r.month
        code = r.code.lower()

        if month not in trend:
            trend[month] = {
                "total": 0,
                "collected": 0,
                "penalties": 0,
                **{c: 0 for c in REVENUE_CODES}
            }

        trend[month]["total"] += float(r.total)
        trend[month]["collected"] += float(r.collected)
        trend[month]["penalties"] += float(r.penalties)
        trend[month][code] += float(r.total)

    # ---------------------------------------------------------
    # Final Response
    # ---------------------------------------------------------
    result = []

    for month in sorted(trend.keys()):
        data = trend[month]
        outstanding = data["total"] - data["collected"]

        result.append({
            "month": month,
            "total": f"{data['total']:.0f}",
            "collected": f"{data['collected']:.0f}",
            "outstanding": f"{outstanding:.0f}",
            "penalties": f"{data['penalties']:.0f}",
            "rent": f"{data['rent']:.0f}",
            "maintenance": f"{data['maintenance']:.0f}",
            "parking_pass": f"{data['parking_pass']:.0f}",
        })

    return result


def get_revenue_by_source(db: Session, org_id: UUID, params: RevenueReportsRequest):
    filters = build_revenue_filters(org_id, params)

    REVENUE_CODES = ["rent", "maintenance", "parking_pass"]

    # ---------------------------------------------------------
    # Revenue grouped by source (invoice lines)
    # ---------------------------------------------------------
    rows = (
        db.query(
            InvoiceLine.code.label("code"),
            func.coalesce(
                func.sum(InvoiceLine.amount),
                0
            ).label("revenue")
        )
        .join(Invoice, Invoice.id == InvoiceLine.invoice_id)
        .filter(
            *filters,
            Invoice.org_id == org_id,
            InvoiceLine.code.in_(REVENUE_CODES)
        )
        .group_by(InvoiceLine.code)
        .all()
    )

    totals = {
        row.code.lower(): float(row.revenue)
        for row in rows
    }

    grand_total = sum(totals.values())

    # ---------------------------------------------------------
    # Convert to percentage distribution
    # ---------------------------------------------------------
    result = []

    for code, value in totals.items():
        if value <= 0:
            continue

        percentage = (
            (value / grand_total) * 100
            if grand_total > 0 else 0
        )

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

    # ---------------------------------------------------------
    # Invoice Outstanding Calculation
    # ---------------------------------------------------------
    grand_total = cast(
        func.jsonb_extract_path_text(Invoice.totals, "grand"),
        Numeric
    )

    paid_amount = func.coalesce(func.sum(PaymentAR.amount), 0)

    rows = (
        db.query(
            Invoice.date.label("invoice_date"),
            (grand_total - paid_amount).label("outstanding")
        )
        .outerjoin(
            PaymentAR,
            PaymentAR.invoice_id == Invoice.id
        )
        .filter(
            *filters,
            Invoice.org_id == org_id
        )
        .group_by(
            Invoice.id,
            Invoice.date,
            grand_total
        )
        .having((grand_total - paid_amount) > 0)
        .all()
    )

    # ---------------------------------------------------------
    # Aging Bucket Logic
    # ---------------------------------------------------------
    for r in rows:
        if not r.invoice_date:
            continue

        days_due = (today - r.invoice_date).days
        amount = float(r.outstanding or 0)

        if days_due <= 30:
            buckets["0-30 days"] += amount
        elif days_due <= 60:
            buckets["31-60 days"] += amount
        elif days_due <= 90:
            buckets["61-90 days"] += amount
        else:
            buckets["90+ days"] += amount

    # ---------------------------------------------------------
    # Response
    # ---------------------------------------------------------
    return [
        {
            "period": period,
            "amount": round(amount)
        }
        for period, amount in buckets.items()
    ]
