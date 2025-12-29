from datetime import timedelta
import datetime

from uuid import UUID

from fastapi import params
from requests import Session
from sqlalchemy import Numeric, cast, func

from facility_service.app.models.space_sites.sites import Site
from facility_service.app.schemas.energy_iot.consumption_report_schema import ConsumptionReportParams
from shared.core.schemas import Lookup, UserToken
from ...models.energy_iot.meters import Meter
from ...models.energy_iot.meter_readings import MeterReading
from ...models.financials.invoices import Invoice
from ...models.hospitality.booking_cancellations import BookingCancellation
from ...models.hospitality.bookings import Booking
from ...models.hospitality.folios import Folio
from ...models.hospitality.folios_charges import FolioCharge
from ...models.leasing_tenants.lease_charges import LeaseCharge
from ...models.leasing_tenants.leases import Lease
from ...enum.consumption_enum import ConsumptionMonth
from ...enum.consumption_enum import ConsumptionType
from typing import List, Optional
import calendar
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from datetime import date

def overview_consumption_reports(db: Session, org_id: UUID):
    today = date.today()

    # Base query
    base_query = (
        db.query(
            Meter.kind,
            func.sum(
                (MeterReading.delta * Meter.multiplier)
            ).label("total_consumption")
        )
        .join(Meter, Meter.id == MeterReading.meter_id)
        .filter(
            Meter.org_id == org_id,
            Meter.status == "active",
            Meter.is_deleted == False,
            MeterReading.is_deleted == False,
        )
        .group_by(Meter.kind)
    )

    results = base_query.all()

    electricity = 0
    water = 0

    for row in results:
        if row.kind == "electricity":
            electricity = float(row.total_consumption or 0)
        elif row.kind == "water":
            water = float(row.total_consumption or 0)

    # ---- Daily average (last 30 days) ----
    days = 30

    daily_avg = (electricity + water) / days if days else 0

    return {
        "Totalcost": round(electricity + water, 2),  # replace with tariff logic later
        "Electricity": round(electricity, 2),
        "Water": round(water, 2),
        "DailyAverage": round(daily_avg, 2),
    }


def weekly_consumption_trends(db: Session, org_id: UUID):
    now = datetime.utcnow()

    # Define week ranges
    weeks = [
        ("Week 1", now - timedelta(days=28), now - timedelta(days=21)),
        ("Week 2", now - timedelta(days=21), now - timedelta(days=14)),
        ("Week 3", now - timedelta(days=14), now - timedelta(days=7)),
        ("Week 4", now - timedelta(days=7), now),
    ]

    result = []

    for label, start, end in weeks:
        rows = (
            db.query(
                Meter.kind,
                func.sum(MeterReading.delta * Meter.multiplier).label("consumption")
            )
            .join(Meter, Meter.id == MeterReading.meter_id)
            .filter(
                Meter.org_id == org_id,
                Meter.status == "active",
                Meter.is_deleted == False,
                MeterReading.is_deleted == False,
                MeterReading.ts >= start,
                MeterReading.ts < end,
            )
            .group_by(Meter.kind)
            .all()
        )

        week_data = {
            "name": label,
            "electricity": 0,
            "water": 0,
            "gas": 0
        }

        for row in rows:
            week_data[row.kind] = float(row.consumption or 0)

        result.append(week_data)

    return result




def monthly_cost_analysis(db: Session, org_id: UUID):
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=180)  # last 6 months

    rows = (
        db.query(
            func.date_trunc("month", MeterReading.ts).label("month"),
            func.sum(MeterReading.delta * Meter.multiplier).label("cost")
        )
        .join(Meter, Meter.id == MeterReading.meter_id)
        .filter(
            Meter.org_id == org_id,
            Meter.status == "active",
            Meter.is_deleted == False,
            MeterReading.is_deleted == False,
            MeterReading.ts >= start_date,
            MeterReading.ts <= end_date
        )
        .group_by("month")
        .order_by("month")
        .all()
    )

    # Month labels
    monthly_data = []
    for row in rows:
        monthly_data.append({
            "name": row.month.strftime("%b"),  # Jan, Feb, Mar
            "cost": round(float(row.cost or 0), 2)
        })

    return monthly_data



# -----------------------------
# BUILD FILTER FUNCTION
# -----------------------------
def build_consumption_filters(
    org_id: UUID,
    utility_type: Optional[str] = None,
    month: Optional[int] = None,
):
    filters = [
        Meter.org_id == org_id,
        Meter.status == "active",
        Meter.is_deleted == False,
        MeterReading.is_deleted == False,
    ]

    # Utility type filter
    if utility_type:
        value = utility_type.value.lower().replace(" ", "_")
        filters.append(Meter.kind == value)

        # Month filter (current year)
    if month:
            month_value = int(month.value) if hasattr(month, "value") else int(month)
            year = datetime.utcnow().year

            start_date = datetime(year, month_value, 1)
            last_day = calendar.monthrange(year, month_value)[1]
            end_date = datetime(year, month_value, last_day, 23, 59, 59)

            filters.extend([
                MeterReading.ts >= start_date,
                MeterReading.ts <= end_date,
            ])
    return filters


# -----------------------------
# MAIN CONSUMPTION REPORT
# -----------------------------
def consumption_reports(
    db: Session,
    org_id: UUID,
    params: ConsumptionReportParams,
):
    # Tariff (hardcoded as per requirement)
    TARIFF = {
        "electricity": 0.12,
        "water": 0.015,
        "gas": 0.09,
        "btuh": 0.1,
        "people_counter": 0.1,
    }

    filters = build_consumption_filters(
        org_id=org_id,
        utility_type=params.consumption_type,
        month=params.month,
    )

    rows = (
        db.query(
            Site.name.label("site"),
            Meter.kind.label("utility_type"),
            func.sum(MeterReading.delta * Meter.multiplier).label("total_consumption"),
            func.max(MeterReading.delta * Meter.multiplier).label("peak_usage"),
            func.count(func.distinct(func.date(MeterReading.ts))).label("active_days"),
        )
        .join(Meter, Meter.id == MeterReading.meter_id)
        .join(Site, Site.id == Meter.site_id)
        .filter(*filters)
        .group_by(Site.name, Meter.kind)
        .all()
    )

    end_date = datetime.utcnow()
    report = []

    for row in rows:
        total = float(row.total_consumption or 0)
        days = row.active_days or 1
        daily_avg = total / days
        tariff = TARIFF.get(row.utility_type, 0)
        cost = total * tariff

        # -----------------------------
        # TREND (last 7 vs previous 7)
        # -----------------------------
        recent = (
            db.query(func.sum(MeterReading.delta * Meter.multiplier))
            .join(Meter)
            .filter(
                Meter.org_id == org_id,
                Meter.kind == row.utility_type,
                Meter.status == "active",
                Meter.is_deleted == False,
                MeterReading.is_deleted == False,
                MeterReading.ts >= end_date - timedelta(days=7),
            )
            .scalar() or 0
        )

        previous = (
            db.query(func.sum(MeterReading.delta * Meter.multiplier))
            .join(Meter)
            .filter(
                Meter.org_id == org_id,
                Meter.kind == row.utility_type,
                Meter.status == "active",
                Meter.is_deleted == False,
                MeterReading.is_deleted == False,
                MeterReading.ts < end_date - timedelta(days=7),
                MeterReading.ts >= end_date - timedelta(days=14),
            )
            .scalar() or 0
        )

        if recent > previous:
            trend = "up"
        elif recent < previous:
            trend = "down"
        else:
            trend = "stable"

        report.append({
            "site": row.site,
            "utility_type": row.utility_type,
            "total_consumption": round(total, 2),
            "daily_average": round(daily_avg, 2),
            "peak_usage": round(float(row.peak_usage or 0), 2),
            "cost": round(cost, 2),
            "trend": trend,
        })

    return report



def consumption_reports_month_lookup(db: Session, org_id: str, status: Optional[str] = None):
    return [
        {"id": month.value, "name": month.name.replace('_', ' ').title()}
        for month in ConsumptionMonth
    ]


def consumption_types_lookup(db: Session, org_id: UUID):
    return [
        Lookup(id=order.value, name=order.name.capitalize())
        for order in ConsumptionType
    ]


