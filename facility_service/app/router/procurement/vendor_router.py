# app/routers/vendors.py
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.core.database import get_facility_db as get_db
from shared.core.schemas import Lookup, UserToken
from ...schemas.procurement.vendors_schemas import VendorListResponse, VendorOut, VendorCreate, VendorOverviewResponse, VendorRequest, VendorUpdate
from ...crud.procurement import vendors_crud as crud
from shared.core.auth import validate_current_token

router = APIRouter(prefix="/api/vendors",
                   tags=["vendors"], dependencies=[Depends(validate_current_token)])

# ---------------- List all vendors ----------------


@router.get("/all", response_model=VendorListResponse)
def get_vendors(
    params: VendorRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_vendors(db, current_user.org_id, params)

# -----overview----


@router.get("/overview", response_model=VendorOverviewResponse)
def overview(
    params: VendorRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_vendors_overview(db, current_user.org_id, params)

# -----Update------------------------


# ---------------- Update Vendor ----------------
@router.put("/", response_model=VendorOut)
def update_vendor(
    vendor: VendorUpdate,
    db: Session = Depends(get_db)
):
    return crud.update_vendor(db, vendor)

# -------create-------------------------------

@router.post("/", response_model=VendorOut)
def create_vendor(
    vendor: VendorCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.create_vendor(db, vendor, org_id=current_user.org_id)

# ---------------- Delete (Soft Delete) ----------------


# ✅ Updated response model
@router.delete("/{vendor_id}", response_model=VendorOut)
def delete_vendor_route(
    vendor_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
    # ✅ Return the soft-deleted vendor
): return crud.delete_vendor(db, vendor_id, current_user.org_id)


@router.get("/vendor-lookup", response_model=List[Lookup])
def vendor_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.vendor_lookup(db, current_user.org_id)

# ----------status_lookup-------------


@router.get("/status-lookup", response_model=List[Lookup])
def vendors_status_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.vendors_status_lookup(db, current_user.org_id)

# ----------categories lookup---------


@router.get("/categories-lookup", response_model=List[Lookup])
def vendors_categories_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.Vendor_Categories_lookup(db, current_user.org_id)

# ----------filter_status_lookup-------------


@router.get("/filter-status-lookup", response_model=List[Lookup])
def vendors_filter_status_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.vendors_filter_status_lookup(db, current_user.org_id)

# ----------filter_categories lookup---------


@router.get("/filter-categories-lookup", response_model=List[Lookup])
def Vendor_filter_Categories_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.vendors_filter_categories_lookup(db, current_user.org_id)
