import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from ..models.asset_category_models import AssetCategory
from ..schemas.asset_category_schemas import AssetCategoryCreate, AssetCategoryUpdate

def get_asset_categories(db: Session, skip: int = 0, limit: int = 100) -> List[AssetCategory]:
    return db.query(AssetCategory).offset(skip).limit(limit).all()

def get_asset_category_by_id(db: Session, category_id: str) -> Optional[AssetCategory]:
    return db.query(AssetCategory).filter(AssetCategory.id == category_id).first()

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
    for k, v in category.dict(exclude_unset=True).items():
        setattr(db_category, k, v)
    db.commit()
    db.refresh(db_category)
    return db_category

def delete_asset_category(db: Session, category_id: str) -> Optional[AssetCategory]:
    db_category = get_asset_category_by_id(db, category_id)
    if not db_category:
        return None
    db.delete(db_category)
    db.commit()
    return db_category
