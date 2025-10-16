


from sqlalchemy.orm import Session
from sqlalchemy import func, literal, or_, select
from datetime import datetime

from ...enum.revenue_enum import RevenueMonth





from shared.schemas import Lookup, UserToken

from ...models.space_sites.sites import Site
from uuid import UUID
from typing import List, Optional

from fastapi import HTTPException




def revenue_reports_filter_site_lookup(db: Session, org_id: str):
    rows = (
        db.query(
            func.lower(Site.name).label("id"),
            func.initcap(Site.name).label("name")
        )
        .filter(Site.org_id == org_id)
        .distinct()
        .order_by(func.lower(Site.name))
        .all()
    )
    return [{"id": r.id, "name": r.name} for r in rows]

def revenue_reports_site_month_lookup(db: Session, org_id: str, status: Optional[str] = None):
    return [
        {"id": month.value, "name": month.name.replace('_', ' ').title()}
        for month in RevenueMonth
    ]



def overview_revenue_reports():
    return {
        "TotalRevenue": "85.7",
        "RentRevenue": "62.4",
        "CamRevenue": "23.3",
        "CollectionRate": "92.5",
    }


def revenue_trend():
    return [
  {
    "month": "2024-01",
    "rent": "450000",
    "cam": "85000",
    "utilities": "65000",
    "penalties": "5000",
    "total": "605000",
    "collected": "580000",
    "outstanding": "25000"
  },
  {
    "month": "2024-02",
    "rent": "475000",
    "cam": "90000",
    "utilities": "70000",
    "penalties": "8000",
    "total": "643000",
    "collected": "615000",
    "outstanding": "28000"
  },
  {
    "month": "2024-03",
    "rent": "485000",
    "cam": "92000",
    "utilities": "72000",
    "penalties": "3000",
    "total": "652000",
    "collected": "640000",
    "outstanding": "12000"
  },
  {
    "month": "2024-04",
    "rent": "495000",
    "cam": "95000",
    "utilities": "75000",
    "penalties": "6000",
    "total": "671000",
    "collected": "658000",
    "outstanding": "13000"
  },
  {
    "month": "2024-05",
    "rent": "510000",
    "cam": "98000",
    "utilities": "78000",
    "penalties": "4000",
    "total": "690000",
    "collected": "675000",
    "outstanding": "15000"
  },
  {
    "month": "2024-06",
    "rent": "525000",
    "cam": "100000",
    "utilities": "80000",
    "penalties": "7000",
    "total": "712000",
    "collected": "695000",
    "outstanding": "17000"
  }
]



def revenue_by_source():
    return [
        {"name": "Rent", "value": 60 }, 
        {"name": "CAM", "value": 25 },
        {"name": "Utilities", "value": 10 },
        {"name": "Parking", "value": 5 }
    ]
    
def outstanding_receivables():
    return [
        {"period": "0-30 days", "amount": 125000},
        {"period": "31-60 days", "amount": 85000},
        {"period": "61-90 days", "amount": 45000},
        {"period": "90+ days", "amount": 25000}
    ]
