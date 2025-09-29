from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ...schemas.maintenance_assets.assets_schemas import AssetCreate, AssetOverview, AssetUpdate, AssetsRequest, AssetsResponse
from ...crud.maintenance_assets import assets_crud as crud
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token  # for dependicies
from shared.schemas import Lookup, UserToken
from uuid import UUID

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
def get_asset_overview(
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_asset_overview(db, current_user.org_id)


@router.post("/", response_model=None)
def create_asset(
        asset: AssetCreate,
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    asset.org_id = current_user.org_id
    return crud.create_asset(db, asset)


@router.put("/", response_model=None)
def update_asset(asset: AssetUpdate, db: Session = Depends(get_db)):
    db_asset = crud.update_asset(db, asset)
    if not db_asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return db_asset


@router.delete("/{asset_id}", response_model=None)
def delete_space(asset_id: str, db: Session = Depends(get_db)):
    db_asset = crud.delete_asset(db, asset_id)
    if not db_asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return db_asset
