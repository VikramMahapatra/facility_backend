# app/crud/contracts.py
from sqlite3 import IntegrityError
from sqlalchemy.dialects.postgresql import UUID
from typing import List, Optional
import uuid
from sqlalchemy.orm import Session

from ...models.space_sites.sites import Site
from shared.utils.app_status_code import AppStatusCode
from shared.helpers.json_response_helper import error_response

from ...enum.procurement_enum import ContractStatus, ContractType
from shared.core.schemas import Lookup
from ...schemas.procurement.contracts_schemas import ContractCreate, ContractListResponse, ContractOut, ContractRequest, ContractUpdate
from sqlalchemy import func, or_, String
from datetime import date, timedelta
from ...models.procurement.contracts import Contract
from ...models.procurement.vendors import Vendor
from sqlalchemy import and_, func
from fastapi import HTTPException, status


# ----------------- Build Filters for Contracts -----------------
def build_contract_filters(org_id: UUID, params: ContractRequest):
    # Always filter out deleted contracts
    filters = [Contract.org_id == org_id,
               Contract.is_deleted == False]  # Updated filter

    if params.type and params.type.lower() != "all":
        filters.append(func.lower(Contract.type) == params.type.lower())

    if params.status and params.status.lower() != "all":
        filters.append(func.lower(Contract.status) == params.status.lower())

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


def get_contracts_overview(db: Session, org_id: UUID, params: ContractRequest):
    filters = build_contract_filters(org_id, params)
    today = date.today()
    next_month = today + timedelta(days=30)

    # Total contracts with filters
    total_contracts = db.query(func.count(
        Contract.id)).filter(*filters).scalar()

    # Active contracts - status = 'active' AND end_date is either null or in future
    active_contracts = (
        db.query(func.count(Contract.id))
        .filter(
            *filters,
            func.lower(Contract.status) == "active",
            or_(
                Contract.end_date == None,
                Contract.end_date >= today
            )
        )
        .scalar()
    )

    # Expiring soon - Use the SAME filters but add date constraint
    expiring_filters = build_contract_filters(
        org_id, params)  # Same base filters
    expiring_soon = (
        db.query(func.count(Contract.id))
        .filter(
            # Use the same filters (including status if provided)
            *expiring_filters,
            Contract.end_date != None,
            Contract.end_date.between(today, next_month)
        )
        .scalar()
    )

    # Total value with filters
    total_value = db.query(func.coalesce(
        func.sum(Contract.value), 0)).filter(*filters).scalar()
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
        # Updated filter
        .filter(Contract.org_id == org_id,  Contract.is_deleted == False)
        .distinct()
        .order_by(Contract.status.asc())
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
        # Updated filter
        .filter(Contract.org_id == org_id, Contract.is_deleted == False)
        .distinct()
        .order_by(Contract.type.asc())
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
# ----------------- Get All Contracts -----------------
def get_contracts(db: Session, org_id: UUID, params: ContractRequest) -> ContractListResponse:
    # Join with Vendor and Site tables to get the names
    base_query = (
        db.query(Contract)
        .outerjoin(Vendor, Contract.vendor_id == Vendor.id)
        .outerjoin(Site, Contract.site_id == Site.id)
        .filter(*build_contract_filters(org_id, params))
    )

    # Total count for pagination
    total = base_query.with_entities(func.count(Contract.id)).scalar()

    # Fetch contracts with offset & limit
    contracts = (
        base_query
        .order_by(Contract.updated_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    # Convert ORM objects to Pydantic models with vendor_name and site_name
    results = []
    for contract in contracts:
        # Create a dictionary with the contract data
        contract_data = contract.__dict__.copy()

        # Safely get vendor_name - check if vendor relationship is loaded and exists
        vendor_name = None
        if hasattr(contract, 'vendor') and contract.vendor:
            vendor_name = contract.vendor.name
        contract_data["vendor_name"] = vendor_name

        # Safely get site_name - check if site relationship is loaded and exists
        site_name = None
        if hasattr(contract, 'site') and contract.site:
            site_name = contract.site.name
        contract_data["site_name"] = site_name

        results.append(ContractOut.model_validate(contract_data))

    return ContractListResponse(contracts=results, total=total)


def get_contract_by_id(db: Session, contract_id: str) -> Optional[Contract]:
    # Join with Vendor and Site tables to get the names
    return (
        db.query(Contract)
        .outerjoin(Vendor, Contract.vendor_id == Vendor.id)
        .outerjoin(Site, Contract.site_id == Site.id)
        .filter(Contract.id == contract_id, Contract.is_deleted == False)
        .first()
    )


# -------- Create Contract --------
def create_contract(db: Session, contract: ContractCreate) -> ContractOut:
    # Case-INSENSITIVE validation: Check for duplicate contract title in same org
    existing_contract = db.query(Contract).filter(
        and_(
            Contract.org_id == contract.org_id,
            func.lower(Contract.title) == func.lower(
                contract.title),  # Case-insensitive comparison
            Contract.is_deleted == False
        )
    ).first()

    if existing_contract:
        return error_response(
            message=f"Contract with title '{contract.title}' already exists in this organization",
            status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
            http_status=400
        )

    db_contract = Contract(id=uuid.uuid4(), **contract.model_dump())
    db.add(db_contract)
    db.commit()

    # Fetch the created contract with joins to get vendor and site names
    result = (
        db.query(
            Contract,
            Vendor.name.label('vendor_name'),
            Site.name.label('site_name')
        )
        .outerjoin(Vendor, Contract.vendor_id == Vendor.id)
        .outerjoin(Site, Contract.site_id == Site.id)
        .filter(Contract.id == db_contract.id)
        .first()
    )

    if result:
        contract, vendor_name, site_name = result
        contract_data = contract.__dict__.copy()
        contract_data["vendor_name"] = vendor_name
        contract_data["site_name"] = site_name
        return ContractOut.model_validate(contract_data)

    # Fallback: return without names if join fails
    contract_data = db_contract.__dict__.copy()
    contract_data["vendor_name"] = None
    contract_data["site_name"] = None
    return ContractOut.model_validate(contract_data)


# -------- Update Contract --------
def update_contract(db: Session, contract: ContractUpdate) -> Optional[ContractOut]:
    db_contract = (
        db.query(Contract)
        .filter(Contract.id == contract.id, Contract.is_deleted == False)
        .first()
    )
    if not db_contract:
        return error_response(
        message="Contract not found",
        status_code=str(AppStatusCode.OPERATION_ERROR),
        http_status=404
    )

    update_data = contract.model_dump(exclude_unset=True)

    # Check for duplicate title only if title is being updated
    if 'title' in update_data:
        existing_contract = db.query(Contract).filter(
        Contract.org_id == db_contract.org_id,
        Contract.id != contract.id,
        Contract.is_deleted == False,
        func.lower(Contract.title) == func.lower(update_data['title'])
    ).first()

    if existing_contract:
        return error_response(
            message=f"Contract with title '{update_data['title']}' already exists",
            status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
            http_status=400
        )
    
    for key, value in update_data.items():
        setattr(db_contract, key, value)
    
    try:
        db.commit()
        db.refresh(db_contract)
        return get_contract_by_id(db, contract.id)

    except IntegrityError as e:
        db.rollback()
        return error_response(
            message="Error updating contract",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )

# -------- Delete Contract (Soft Delete) --------
def delete_contract(db: Session, contract_id: UUID, org_id: UUID) -> bool:
    # Verify contract exists and belongs to org
    db_contract = (
        db.query(Contract)
        .filter(Contract.id == contract_id, Contract.org_id == org_id, Contract.is_deleted == False)
        .first()
    )
    if not db_contract:
        return False

    # Soft delete
    db_contract.is_deleted = True
    db_contract.updated_at = func.now()
    db.commit()

    return True
