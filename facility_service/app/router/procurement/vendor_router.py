# app/routers/vendors.py
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.database import get_facility_db as get_db
from shared.schemas import Lookup, UserToken
from ...schemas.procurement.vendors_schemas import VendorListResponse, VendorOut, VendorCreate, VendorOverviewResponse, VendorRequest, VendorUpdate
from ...crud.procurement import vendors_crud as crud
from shared.auth import validate_current_token

router = APIRouter(prefix="/api/vendors", tags=["vendors"],dependencies=[Depends(validate_current_token)])


# ---------------- List all vendors ----------------
@router.get("/all", response_model=VendorListResponse)
def get_vendors(
    params: VendorRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_vendors(db, current_user.org_id, params)

#-----overview----
@router.get("/overview", response_model=VendorOverviewResponse)
def overview(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_vendors_overview(db, current_user.org_id)

#-----Update------------------------
@router.put("/", response_model=None)
def update_vendor_endpoint(
    vendor: VendorUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    db_vendor = crud.update_vendor(db, vendor)
    if not db_vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return {"message": "Vendor updated successfully"}

#-------create-------------------------------
@router.post("/", response_model=VendorOut)
def create_vendor(
    vendor: VendorCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    vendor.org_id = current_user.org_id 
    return crud.create_vendor(db, vendor)

# ---------------- Delete ----------------
@router.delete("/{vendor_id}")
def delete_vendor_route(
    vendor_id: UUID,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    success = crud.delete_vendor(db, vendor_id)
    if not success:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return {"message": "Vendor deleted successfully"}

#----------status_lookup-------------
@router.get("/status-lookup", response_model=List[Lookup])
def vendors_status_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.vendors_status_lookup(db, current_user.org_id)

#----------categories lookup---------
@router.get("/categories-lookup", response_model=List[Lookup])
def vendors_categories_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.Vendor_Categories_lookup(db, current_user.org_id)

#----------filter_status_lookup-------------
@router.get("/filter-status-lookup", response_model=List[Lookup])
def vendors_filter_status_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.vendors_filter_status_lookup(db, current_user.org_id)

#----------filter_categories lookup---------
@router.get("/filter-categories-lookup", response_model=List[Lookup])
def Vendor_filter_Categories_lookup_endpoint(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.vendors_filter_categories_lookup(db, current_user.org_id)