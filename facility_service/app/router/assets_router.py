# app/routers/assets.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List
from app import crud
from app.models import assets_models as models
from app.schemas import assets_schemas as schemas
from app.core.databases import get_db
from app.core.auth import get_current_token
from app.crud.assets_crud import create_asset
router = APIRouter(
    prefix="/assets",
    tags=["assets"],
    dependencies=[Depends(get_current_token)]
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
