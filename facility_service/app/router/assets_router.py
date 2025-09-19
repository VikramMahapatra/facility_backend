# app/routers/assets.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List
from ..models import assets_models as models
from ..schemas import assets_schemas as schemas
from shared.database import get_facility_db as get_db
from shared.auth import validate_current_token
from ..crud import assets_crud as crud

router = APIRouter(
    prefix="/assets",
    tags=["assets"],
    dependencies=[Depends(validate_current_token)]
)

@router.post("/", response_model=schemas.AssetResponse)
def create_asset(asset: schemas.AssetCreate, db: Session = Depends(get_db)):
    return crud.create_asset(db, asset)

@router.get("/{asset_id}", response_model=schemas.AssetResponse)
def read_asset(asset_id: UUID, db: Session = Depends(get_db)):
    db_asset = crud.get_asset(db, asset_id)
    if db_asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return db_asset

@router.get("/", response_model=List[schemas.AssetResponse])
def read_assets(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_assets(db, skip=skip, limit=limit)

@router.put("/{asset_id}", response_model=schemas.AssetResponse)
def update_asset(asset_id: UUID, asset: schemas.AssetUpdate, db: Session = Depends(get_db)):
    db_asset = crud.update_asset(db, asset_id, asset)
    if db_asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return db_asset

@router.delete("/{asset_id}", response_model=schemas.AssetResponse)
def delete_asset(asset_id: UUID, db: Session = Depends(get_db)):
    db_asset = crud.delete_asset(db, asset_id)
    if db_asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return db_asset
