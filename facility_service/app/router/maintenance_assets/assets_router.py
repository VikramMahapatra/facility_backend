# app/routers/maintenance_assets/assets_router.py
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from shared.json_response_helper import success_response
from ...schemas.maintenance_assets.assets_schemas import AssetCreate, AssetOverview, AssetResponse, AssetUpdate, AssetsRequest, AssetsResponse, AssetOut
from ...crud.maintenance_assets import assets_crud as crud
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token
from shared.schemas import Lookup, UserToken
from uuid import UUID
from ...schemas.maintenance_assets.asset_category_schemas import AssetCategoryOutFilter
from ...schemas.maintenance_assets.assets_schemas import AssetStatusOut

router = APIRouter(
    prefix="/api/assets",
    tags=["assets"],
    dependencies=[Depends(validate_current_token)]
)

# -----------------------------------------------------------------
@router.get("/all", response_model=AssetsResponse)
def get_assets(
        params: AssetsRequest = Depends(),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_assets(db, current_user.org_id, params)


@router.get("/overview", response_model=AssetOverview)
def get_assets_overview(
    params: AssetsRequest = Depends(),
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_asset_overview(db, current_user.org_id, params)


@router.post("/", response_model=None)
def create_asset(
        asset: AssetCreate,
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    asset.org_id = current_user.org_id
    result = crud.create_asset(db, asset)
    
    # Check if result is an error response
    if hasattr(result, 'status_code') and result.status_code != 200:
        return result
    
    # Convert SQLAlchemy model to Pydantic model
    asset_response = AssetResponse.model_validate(result)
    return success_response(data=asset_response, message="Asset created successfully")

@router.put("/{asset_id}", response_model=None)
def update_asset(
        asset_id: UUID,
        asset_update: AssetUpdate,
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    result = crud.update_asset(db, asset_id, asset_update)
    
    # Check if result is an error response
    if hasattr(result, 'status_code') and result.status_code != 200:
        return result
    
    # Convert SQLAlchemy model to Pydantic model
    asset_response = AssetResponse.model_validate(result)
    return success_response(data=asset_response, message="Asset updated successfully")



# ---------------- Delete Asset (Soft Delete) ----------------
@router.delete("/{asset_id}")  # REMOVE response_model=AssetOut
def delete_asset(
        asset_id: str, 
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
   
    return crud.delete_asset(db, asset_id, current_user.org_id)
    

@router.get("/asset-lookup", response_model=list[Lookup])
def asset_lookup(db: Session = Depends(get_db), current_user: UserToken = Depends(validate_current_token)):
    return crud.asset_lookup(db, current_user.org_id)

@router.get("/status-lookup", response_model=list[Lookup])
def status_lookup(db: Session = Depends(get_db), current_user: UserToken = Depends(validate_current_token)):
    return crud.asset_status_lookup(db, current_user.org_id)

@router.get("/category-lookup", response_model=List[Lookup])
def category_lookup(
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.assets_category_lookup(db, current_user.org_id)

@router.get("/filter-status-lookup", response_model=list[Lookup])
def asset_filter_status_lookup_endpoint(db: Session = Depends(get_db), current_user: UserToken = Depends(validate_current_token)):
    return crud.asset_filter_status_lookup(db, current_user.org_id)