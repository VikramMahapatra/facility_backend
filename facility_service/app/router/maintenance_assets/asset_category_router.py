from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.auth import validate_current_token
from shared.database import get_facility_db as get_db
from shared.json_response_helper import success_response
from shared.schemas import Lookup, UserToken
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

#  MOVE THE LOOKUP ENDPOINT ABOVE THE PARAMETERIZED ROUTES
@router.get("/lookup", response_model=list[Lookup])
def get_asset_category_lookup(db: Session = Depends(get_db), current_user: UserToken = Depends(validate_current_token)):
    return crud.get_asset_category_lookup(db, current_user.org_id)

# Keep parameterized routes AFTER static routes
@router.get("/{category_id}", response_model=AssetCategoryOut)
def read_category(category_id: str, db: Session = Depends(get_db)):
    db_category = crud.get_asset_category_by_id(db, category_id)
    if not db_category:
        raise HTTPException(status_code=404, detail="AssetCategory not found")
    return db_category

@router.post("/", response_model=None)
def create_category(
    category: AssetCategoryCreate, 
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    # Set org_id from current user if not provided
    if not category.org_id:
        category.org_id = current_user.org_id
    
    result = crud.create_asset_category(db, category)
    
    # Check if result is an error response
    if hasattr(result, 'status_code') and result.status_code != 200:
        return result
    
    # Convert SQLAlchemy model to Pydantic model
    category_response = AssetCategoryOut.model_validate(result)
    return success_response(data=category_response, message="Asset category created successfully")

@router.put("/{category_id}", response_model=None)
def update_category(
    category_id: str, 
    category: AssetCategoryUpdate, 
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    result = crud.update_asset_category(db, category_id, category)
    
    # Check if result is an error response
    if hasattr(result, 'status_code') and result.status_code != 200:
        return result
    
    # Convert SQLAlchemy model to Pydantic model
    category_response = AssetCategoryOut.model_validate(result)
    return success_response(data=category_response, message="Asset category updated successfully")

# ---------------- Delete AssetCategory (Soft Delete) ----------------
@router.delete("/{category_id}")
def delete_category(
        category_id: str, 
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.delete_asset_category(db, category_id, current_user.org_id)
       