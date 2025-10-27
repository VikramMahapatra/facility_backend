import uuid
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from ...models.maintenance_assets.asset_category import AssetCategory
from ...models.maintenance_assets.assets import Asset
from ...schemas.maintenance_assets.asset_category_schemas import AssetCategoryCreate, AssetCategoryUpdate
from uuid import UUID

def get_asset_categories(db: Session, skip: int = 0, limit: int = 100) -> List[AssetCategory]:
    # Updated filter to exclude deleted categories
    return db.query(AssetCategory).filter(AssetCategory.is_deleted == False).offset(skip).limit(limit).all()

def get_asset_category_by_id(db: Session, category_id: str) -> Optional[AssetCategory]:
    #  Updated filter to exclude deleted categories
    return db.query(AssetCategory).filter(AssetCategory.id == category_id, AssetCategory.is_deleted == False).first()

def create_asset_category(db: Session, category: AssetCategoryCreate) -> AssetCategory:
    db_category = AssetCategory(id=str(uuid.uuid4()), **category.dict())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category

def update_asset_category(db: Session, category_id: str, category: AssetCategoryUpdate) -> Optional[AssetCategory]:
    db_category = get_asset_category_by_id(db, category_id)
    if not db_category:
        return None
    
    # Check if code is being updated and if it already exists for another category
    if category.code and category.code != db_category.code:
        existing_category = db.query(AssetCategory).filter(
            AssetCategory.code == category.code,
            AssetCategory.id != category_id,
            AssetCategory.is_deleted == False
        ).first()
        if existing_category:
            raise HTTPException(
                status_code=400, 
                detail=f"Category code '{category.code}' already exists"
            )
    
    # Update fields
    for k, v in category.dict(exclude_unset=True).items():
        setattr(db_category, k, v)
    
    db.commit()
    db.refresh(db_category)
    return db_category



def delete_asset_category(db: Session, category_id: str, org_id: UUID) -> bool:
    db_category = (
        db.query(AssetCategory)
        .filter(AssetCategory.id == category_id, AssetCategory.org_id == org_id, AssetCategory.is_deleted == False)
        .first()
    )
    if not db_category:
        return False
    
    #  Check if category has any active assets

    active_assets_count = db.query(Asset).filter(
        Asset.category_id == category_id,
        Asset.is_deleted == False
    ).count()
    
    if active_assets_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete category. It has {active_assets_count} active assets. Please reassign or delete assets first."
        )
    
    # Soft delete the category
    db_category.is_deleted = True
    db.commit()
    return True


def get_asset_category_lookup(db: Session, org_id: str):
    categories = db.query(AssetCategory.id, AssetCategory.name).filter(
        AssetCategory.org_id == org_id, AssetCategory.is_deleted == False).all()  #  Updated filter
    return categories