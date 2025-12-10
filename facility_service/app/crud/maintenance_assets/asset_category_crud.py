import uuid
from typing import Dict, List, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from shared.utils.app_status_code import AppStatusCode
from shared.helpers.json_response_helper import error_response
from ...models.maintenance_assets.asset_category import AssetCategory
from ...models.maintenance_assets.assets import Asset
from ...schemas.maintenance_assets.asset_category_schemas import AssetCategoryCreate, AssetCategoryOut, AssetCategoryUpdate
from uuid import UUID
from sqlalchemy import func, or_, and_
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

def get_asset_categories(db: Session, skip: int = 0, limit: int = 100,search:Optional[str]=None):
    category_query = (
        db.query(
            AssetCategory.id,
            AssetCategory.name,
            AssetCategory.org_id,
            AssetCategory.created_at,
            AssetCategory.updated_at,
        )
        .filter(AssetCategory.is_deleted == False)
    )

    total = db.query(func.count()).select_from(category_query.subquery()).scalar()

    if search:
        search_term = f"%{search}%"
        category_query  =  category_query .filter( or_(AssetCategory.code.ilike(search_term),AssetCategory.name.ilike(search_term)))

    category_query = category_query.order_by(
        AssetCategory.updated_at.desc()
    ).offset(skip).limit(limit)

    categories = category_query.all()
    results = [
        AssetCategoryOut.model_validate(c._asdict())
        for c in categories
    ]
    
    return {"assetcategories": results, "total": total}



def get_asset_category_by_id(db: Session, category_id: str) -> Optional[AssetCategory]:
    #  Updated filter to exclude deleted categories
    return db.query(AssetCategory).filter(AssetCategory.id == category_id, AssetCategory.is_deleted == False).first()


def create_asset_category(db: Session, category: AssetCategoryCreate ,org_id:UUID) -> AssetCategory:
    # Check for duplicate name (case-insensitive) within the same organization
    existing_category = db.query(AssetCategory).filter(
        AssetCategory.org_id == org_id,
        AssetCategory.is_deleted == False,
        func.lower(AssetCategory.name) == func.lower(
            category.name)  # Case-insensitive
    ).first()

    if existing_category:
        return error_response(
            message=f"Category with name '{category.name}' already exists in this organization"
        )

    if category.code:
        existing_code = db.query(AssetCategory).filter(
            AssetCategory.org_id == org_id,
            AssetCategory.is_deleted == False,
            func.lower(AssetCategory.code) == func.lower(
                category.code)  # Case-insensitive
        ).first()

    if existing_code:
        return error_response(
            message=f"Category with code '{category.code}' already exists in this organization"
        )

    # Create the category
    category_data = category.model_dump()
    category_data["org_id"] = org_id 
    db_category = AssetCategory(id=str(uuid.uuid4()), **category_data)
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


def update_asset_category(db: Session, category_id: str, category: AssetCategoryUpdate) -> Optional['AssetCategory']:
    db_category = get_asset_category_by_id(db, category_id)
    if not db_category:
        return error_response(
            message="Category not found",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=404
        )

    # Extract update data
    update_data = category.model_dump(exclude_unset=True)
    org_id = db_category.org_id

    if 'name' in update_data:
        new_name = update_data['name']
        name_exists = db.query(AssetCategory).filter(
            AssetCategory.org_id == org_id,
            AssetCategory.id != category_id,
            AssetCategory.is_deleted == False,
            AssetCategory.name.ilike(new_name) 
        ).first()

        if name_exists:
            return error_response(
                message=f"Category with name '{new_name}' already exists in this organization",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )

    if 'code' in update_data and update_data['code']:
        new_code = update_data['code']
        code_exists = db.query(AssetCategory).filter(
            AssetCategory.org_id == org_id,
            AssetCategory.id != category_id,
            AssetCategory.is_deleted == False,
            AssetCategory.code.ilike(new_code)
        ).first()

        if code_exists:
            return error_response(
                message=f"Category with code '{new_code}' already exists",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )


    for field, value in update_data.items():
        setattr(db_category, field, value)

    try:
        db.commit()
        db.refresh(db_category)
        return db_category
    except IntegrityError as e:
        db.rollback()
        return error_response(
            message="Duplicate category found during update due to a database constraint violation",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=400
        )


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
        # Updated filter
        AssetCategory.org_id == org_id, AssetCategory.is_deleted == False).order_by(AssetCategory.name.asc()).all()
    return categories



def asset_parent_category_lookup(db: Session, org_id: str, exclude_category_id: Optional[str] = None) -> List[Dict]:
    query = (
        db.query(
            AssetCategory.id.label("id"),
            AssetCategory.name.label("name")
        )
        .filter(
            AssetCategory.org_id == org_id,
            AssetCategory.is_deleted == False
        )
    )
    if exclude_category_id:
        query = query.filter(AssetCategory.id != exclude_category_id)
    
    query = query.distinct().order_by(AssetCategory.name.asc())
    
    rows = query.all()
    
    return [{"id": str(r.id), "name": r.name} for r in rows]