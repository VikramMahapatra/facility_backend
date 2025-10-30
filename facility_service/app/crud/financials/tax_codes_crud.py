from decimal import Decimal
import uuid
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, or_, case, literal, Numeric
from dateutil.relativedelta import relativedelta
from sqlalchemy.dialects.postgresql import UUID

from shared.app_status_code import AppStatusCode
from shared.json_response_helper import error_response
from ...models.financials.tax_reports import TaxReport
from ...models.financials.tax_codes import TaxCode
from ...schemas.financials.tax_codes_schemas import TaxCodeCreate, TaxCodeOut, TaxCodeUpdate, TaxCodesRequest, TaxCodesResponse, TaxReturnOut

from sqlalchemy import and_, func
from fastapi import HTTPException, status


# ----------------------------------------------------------------------
# CRUD OPERATIONS
# ----------------------------------------------------------------------

def build_tax_codes_filters(org_id: UUID, params: TaxCodesRequest):
    filters = [TaxCode.org_id == org_id]

    if params.jurisdiction and params.jurisdiction.lower() != "all":
        filters.append(TaxCode.jurisdiction == params.jurisdiction)

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(TaxCode.code.ilike(search_term))

    return filters


def get_tax_codes_query(db: Session, org_id: UUID, params: TaxCodesRequest):
    filters = build_tax_codes_filters(org_id, params)
    return db.query(TaxCode).filter(*filters)


def get_tax_overview(db: Session, org_id: UUID):
    today = datetime.utcnow()

    first_day_this_month = datetime(today.year, today.month, 1)
    last_day_last_month = first_day_this_month - timedelta(days=1)

    three_months_ago = today - relativedelta(months=3)

    # Aggregate TaxCode fields
    tax_code_agg = db.query(
        func.count(case((TaxCode.status == "active", 1))
                   ).label("active_tax_codes"),
        func.coalesce(func.avg(TaxCode.rate), 0).label("avg_tax_rate")
    ).filter(TaxCode.org_id == org_id).one()

    # Aggregate TaxReport fields separately
    total_tax_last_3_months = db.query(
        func.coalesce(func.sum(TaxReport.total_tax), 0)
    ).filter(
        TaxReport.org_id == org_id,
        (TaxReport.year > three_months_ago.year) |
        ((TaxReport.year == three_months_ago.year) &
         (TaxReport.month_no >= three_months_ago.month))
    ).scalar()

    pending_returns_all_time = db.query(
        func.count(case((TaxReport.filed == False, 1)))
    ).filter(TaxReport.org_id == org_id).scalar()

    # Query active tax codes created last month
    last_month_active_tax_codes = db.query(func.count()).filter(
        TaxCode.org_id == org_id,
        TaxCode.status == "active",
        TaxCode.created_at >= last_day_last_month,
        TaxCode.created_at <= today
    ).scalar()

    return {
        "activeTaxCodes": tax_code_agg.active_tax_codes,
        "totalTaxCollected": float(total_tax_last_3_months),
        "avgTaxRate": float(tax_code_agg.avg_tax_rate),
        "pendingReturns": pending_returns_all_time,
        "lastMonthActiveTaxCodes": last_month_active_tax_codes
    }


def get_tax_codes(db: Session, org_id: UUID, params: TaxCodesRequest) -> TaxCodesResponse:
    base_query = get_tax_codes_query(db, org_id, params)
    total = base_query.with_entities(func.count(TaxCode.id)).scalar()

    codes = (
        base_query
        .order_by(TaxCode.updated_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    return {"tax_codes": codes, "total": total}


def get_tax_returns(db: Session, org_id: str, params: TaxCodesRequest):
    total = (
        db.query(func.count(TaxReport.id))
        .filter(TaxReport.org_id == org_id)
        .scalar()
    )

    returns = (
        db.query(TaxReport)
        .filter(TaxReport.org_id == org_id)
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    tax_returns = []
    for r in returns:
        tax_returns.append(
            TaxReturnOut.model_validate({
                **r.__dict__,
                "period": f"{r.year}-{r.month_no:02d}"  # YYYY-MM format
            })
        )

    return {"tax_returns": tax_returns, "total": total}


def get_code_by_id(db: Session, tax_code_id: str):
    return db.query(TaxCode).filter(TaxCode.id == tax_code_id).first()


# ----------------- Create Tax Code -----------------
def create_tax_code(db: Session, tax_code: TaxCodeCreate):
    # Case-insensitive validation: Check for duplicate tax code in same org
    existing_tax = db.query(TaxCode).filter(
        and_(
            TaxCode.org_id == tax_code.org_id,
            func.lower(TaxCode.code) == func.lower(tax_code.code)
        )
    ).first()
    
    if existing_tax:
        return error_response(
            message=f"Tax code '{tax_code.code}' already exists in this organization",
            status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
            http_status=400
        )
    
    db_tax = TaxCode(**tax_code.model_dump())
    db.add(db_tax)
    db.commit()
    db.refresh(db_tax)
    
    # Use your Pydantic model for serialization
    return TaxCodeOut.model_validate(db_tax)


# ----------------- Update Tax Code -----------------
def update_tax_code(db: Session, tax_code: TaxCodeUpdate):
    db_tax = get_code_by_id(db, tax_code.id)
    if not db_tax:
        return None
    
    # Case-insensitive validation: Check if code is being updated and causes duplicates
    if hasattr(tax_code, 'code') and tax_code.code is not None and tax_code.code.lower() != db_tax.code.lower():
        existing_tax = db.query(TaxCode).filter(
            and_(
                TaxCode.org_id == db_tax.org_id,
                func.lower(TaxCode.code) == func.lower(tax_code.code),
                TaxCode.id != tax_code.id
            )
        ).first()
        
        if existing_tax:
            return error_response(
                message=f"Tax code '{tax_code.code}' already exists in this organization",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )
    
    # Your original update logic
    for k, v in tax_code.dict(exclude_unset=True).items():
        setattr(db_tax, k, v)
    db.commit()
    db.refresh(db_tax)
    
    # Use your Pydantic model for serialization
    return TaxCodeOut.model_validate(db_tax)


def delete_tax_code(db: Session, tax_code_id: str):
    db_tax = get_code_by_id(db, tax_code_id)
    if not db_tax:
        return None
    db.delete(db_tax)
    db.commit()
    return True
