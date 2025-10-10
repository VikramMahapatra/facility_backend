# app/crud/contracts.py
from sqlalchemy.dialects.postgresql import UUID
from typing import List, Optional
import uuid
from sqlalchemy.orm import Session

from ...enum.procurement_enum import ContractStatus, ContractType
from shared.schemas import Lookup
from ...schemas.procurement.contracts_schemas import ContractCreate, ContractListResponse, ContractOut, ContractRequest, ContractUpdate
from sqlalchemy import func, or_ , String
from datetime import date, timedelta
from ...models.procurement.contracts import Contract
from ...models.procurement.vendors import Vendor


# ----------------- Build Filters for Contracts -----------------
def build_contract_filters(org_id: UUID, params: ContractRequest):
    filters = [Contract.org_id == org_id]

    if params.type and params.type.lower() != "all":
        filters.append(func.lower(Contract.type )== params.type.lower())

    if params.status and params.status.lower() != "all":
        filters.append(func.lower(Contract.status )== params.status.lower())

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(
            or_(
                Contract.title.ilike(search_term),
                func.cast(Contract.id, String).ilike(search_term),
            )
        )
    return filters

# ----------------- Contract Query -----------------


def get_contract_query(db: Session, org_id: UUID, params: ContractRequest):
    filters = build_contract_filters(org_id, params)
    return db.query(Contract).filter(*filters)


# ---------------- Overview ----------------
def get_contracts_overview(db: Session, org_id: UUID, params: ContractRequest):
    filters = build_contract_filters(org_id, params)
    today = date.today()
    next_month = today + timedelta(days=30)  # Changed to 30 days for next month

    # Total contracts with filters
    total_contracts = db.query(func.count(Contract.id)).filter(*filters).scalar()

    # Active contracts (Contract.status == 'active') with filters
    active_contracts = (
        db.query(func.count(Contract.id))
        .filter(
            *filters,
            func.lower(Contract.status) == "active"
        )
        .scalar()
    )

    # Expiring soon AND status expired (within next month)
    expiring_soon = (
        db.query(func.count(Contract.id))
        .filter(
            *filters,
            func.lower(Contract.status) == "expired",  # Status must be expired
            Contract.end_date != None,  # Ensure end_date is not null
            Contract.end_date.between(today, next_month)  # Ending within next month
        )
        .scalar()
    )

    # Total value with filters
    total_value = db.query(func.coalesce(func.sum(Contract.value), 0)).filter(*filters).scalar()
    total_value = float(total_value)

    return {
        "total_contracts": total_contracts,
        "active_contracts": active_contracts,
        "expiring_soon": expiring_soon,
        "total_value": round(total_value, 2)
    }
# -----status_lookup-----


def contracts_filter_status_lookup(db: Session, org_id: str, status: Optional[str] = None):
    query = (
        db.query(
            Contract.status.label("id"),
            Contract.status.label("name")
        )
        .filter(Contract.org_id == org_id)
        .distinct()
    )
    if status:
        query = query.filter(Contract.status == status)

    return query.all()

def contracts_status_lookup(org_id: UUID, db: Session):
    return [
        Lookup(id=status.value, name=status.name.capitalize())
        for status in ContractStatus
    ]
# -----type_lookup-----


def contracts_filter_type_lookup(db: Session, org_id: str, contract_type: Optional[str] = None):
    query = (
        db.query(
            Contract.type.label("id"),
            Contract.type.label("name")
        )
        .filter(Contract.org_id == org_id)
        .distinct()
    )
    if contract_type:
        query = query.filter(Contract.type == contract_type)

    return query.all()


def contracts_type_lookup(org_id: UUID, db: Session):
    return [
        Lookup(id=type.value, name=type.name.capitalize())
        for type in ContractType
    ]



# ----------------- Get All Contracts -----------------
def get_contracts(db: Session, org_id: UUID, params: ContractRequest) -> ContractListResponse:
    base_query = get_contract_query(db, org_id, params)

    # Total count for pagination
    total = base_query.with_entities(func.count(Contract.id)).scalar()

    # Fetch contracts with offset & limit
    contracts = (
        base_query
        .order_by(Contract.title.asc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    # Convert ORM objects to Pydantic models
    results = [ContractOut.from_orm(c) for c in contracts]

    return ContractListResponse(contracts=results, total=total)


def get_contract_by_id(db: Session, contract_id: str) -> Optional[Contract]:
    return db.query(Contract).filter(Contract.id == contract_id).first()


# -------- Create Contract --------
def create_contract(db: Session, contract: ContractCreate) -> Contract:
    db_contract = Contract(id=uuid.uuid4(), **contract.model_dump())
    db.add(db_contract)
    db.commit()
    db.refresh(db_contract)
    return db_contract


# -------- Update Contract --------
def update_contract(db: Session, contract: ContractUpdate) -> Optional[Contract]:
    db_contract = db.query(Contract).filter(Contract.id == contract.id).first()
    if not db_contract:
        return None
    # Update only fields that are set in the request
    for k, v in contract.model_dump(exclude_unset=True).items():
        setattr(db_contract, k, v)

    db.commit()
    db.refresh(db_contract)
    return db_contract


def delete_contract(db: Session, contract_id: UUID, org_id: UUID) -> bool:
    db_contract = (
        db.query(Contract)
        .filter(Contract.id == contract_id, Contract.org_id == org_id)
        .first()
    )
    if not db_contract:
        return False
    db.delete(db_contract)
    db.commit()
    return True
