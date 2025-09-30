from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.auth import validate_current_token
from shared.database import get_facility_db as get_db
from ...schemas.maintenance_assets.asset_category_schemas import AssetCategoryOut, AssetCategoryCreate, AssetCategoryUpdate
from ...crud.maintenance_assets import asset_category_crud as crud

router = APIRouter(
    prefix="/api/asset-categories",
    tags=["asset_categories"],
    dependencies=[Depends(validate_current_token)]
)


@router.get("/", response_model=List[AssetCategoryOut])
def read_categories(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_asset_categories(db, skip=skip, limit=limit)


@router.get("/{category_id}", response_model=AssetCategoryOut)
def read_category(category_id: str, db: Session = Depends(get_db)):
    db_category = crud.get_asset_category_by_id(db, category_id)
    if not db_category:
        raise HTTPException(status_code=404, detail="AssetCategory not found")
    return db_category


@router.post("/", response_model=AssetCategoryOut)
def create_category(category: AssetCategoryCreate, db: Session = Depends(get_db)):
    return crud.create_asset_category(db, category)


@router.put("/{category_id}", response_model=AssetCategoryOut)
def update_category(category_id: str, category: AssetCategoryUpdate, db: Session = Depends(get_db)):
    db_category = crud.update_asset_category(db, category_id, category)
    if not db_category:
        raise HTTPException(status_code=404, detail="AssetCategory not found")
    return db_category


@router.delete("/{category_id}", response_model=AssetCategoryOut)
def delete_category(category_id: str, db: Session = Depends(get_db)):
    db_category = crud.delete_asset_category(db, category_id)
    if not db_category:
        raise HTTPException(status_code=404, detail="AssetCategory not found")
    return db_category
