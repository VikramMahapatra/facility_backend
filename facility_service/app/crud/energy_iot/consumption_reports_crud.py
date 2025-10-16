from datetime import timedelta
import datetime

from uuid import UUID

from requests import Session
from sqlalchemy import Numeric, cast, func

from shared.schemas import Lookup, UserToken
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
from datetime import datetime, timedelta


def overview_consumption_reports():
    return {
        "Totalcost": "1,40,682",
        "Electricity": "12500.8",
        "Water": "420.8",
        "DailyAverage": "4,538",
    }
    
def weekly_consumption_trends():
    return [
  { "name": "Week 1", "electricity": 850, "water": 120, "gas": 180 },
  { "name": "Week 2", "electricity": 920, "water": 110, "gas": 165 },
  { "name": "Week 3", "electricity": 780, "water": 105, "gas": 190 },
  { "name": "Week 4", "electricity": 1030, "water": 125, "gas": 175 }
]
    
def monthly_cost_analysis():
    return[
  { "name": "Jan", "cost": 45000 },
  { "name": "Feb", "cost": 38000 },
  { "name": "Mar", "cost": 52000 },
  { "name": "Apr", "cost": 41000 },
  { "name": "May", "cost": 49000 },
  { "name": "Jun", "cost": 43000 }
]

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