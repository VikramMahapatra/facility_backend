import uuid
from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session

from shared.utils.app_status_code import AppStatusCode
from shared.helpers.json_response_helper import error_response
from ...models.maintenance_assets.asset_category import AssetCategory
from ...models.maintenance_assets.assets import Asset
from ...schemas.maintenance_assets.asset_category_schemas import AssetCategoryCreate, AssetCategoryUpdate
from uuid import UUID
from sqlalchemy import func, or_, and_
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError


def get_asset_categories(db: Session, skip: int = 0, limit: int = 100) -> List[AssetCategory]:
    # Updated filter to exclude deleted categories
    return db.query(AssetCategory).filter(AssetCategory.is_deleted == False).offset(skip).limit(limit).all()


def get_asset_category_by_id(db: Session, category_id: str) -> Optional[AssetCategory]:
    #  Updated filter to exclude deleted categories
    return db.query(AssetCategory).filter(AssetCategory.id == category_id, AssetCategory.is_deleted == False).first()


def create_asset_category(db: Session, category: AssetCategoryCreate) -> AssetCategory:
    # Check for duplicate name (case-insensitive) within the same organization
    existing_category = db.query(AssetCategory).filter(
        AssetCategory.org_id == category.org_id,
        AssetCategory.is_deleted == False,
        func.lower(AssetCategory.name) == func.lower(
            category.name)  # Case-insensitive
    ).first()

    if existing_category:
        return error_response(
            message=f"Category with name '{category.name}' already exists in this organization",
            status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
            http_status=400
        )

    # Check for duplicate code (case-insensitive) if provided
    if category.code:
        existing_code = db.query(AssetCategory).filter(
            AssetCategory.org_id == category.org_id,
            AssetCategory.is_deleted == False,
            func.lower(AssetCategory.code) == func.lower(
                category.code)  # Case-insensitive
        ).first()

        if existing_code:
            return error_response(
                message=f"Category with code '{category.code}' already exists",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )

    # Create the category
    db_category = AssetCategory(id=str(uuid.uuid4()), **category.model_dump())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


def update_asset_category(db: Session, category_id: str, category: AssetCategoryUpdate) -> Optional[AssetCategory]:
    db_category = get_asset_category_by_id(db, category_id)
    if not db_category:
        return error_response(
            message="Category not found",
            status_code=str(AppStatusCode.OPERATION_ERROR),
            http_status=404
        )

    # Extract update data
    update_data = category.model_dump(exclude_unset=True)

    # Only validate if name or code are being updated
    if any(field in update_data for field in ['name', 'code']):
        # Build duplicate check query (exclude current category)
        duplicate_filters = [
            AssetCategory.org_id == db_category.org_id,
            AssetCategory.id != category_id,
            AssetCategory.is_deleted == False
        ]

        duplicate_conditions = []
        if 'name' in update_data:
            duplicate_conditions.append(func.lower(
                AssetCategory.name) == func.lower(update_data['name']))
        if 'code' in update_data and update_data['code']:
            duplicate_conditions.append(func.lower(
                AssetCategory.code) == func.lower(update_data['code']))

        if duplicate_conditions:
            duplicate_filters.append(or_(*duplicate_conditions))

            # Check for existing categories with same values
            existing_category = db.query(AssetCategory).filter(
                *duplicate_filters).first()

            if existing_category:
                if 'name' in update_data and func.lower(existing_category.name) == func.lower(update_data['name']):
                    return error_response(
                        message=f"Category with name '{update_data['name']}' already exists in this organization",
                        status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                        http_status=400
                    )
                if 'code' in update_data and update_data['code'] and func.lower(existing_category.code) == func.lower(update_data['code']):
                    return error_response(
                        message=f"Category with code '{update_data['code']}' already exists",
                        status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                        http_status=400
                    )

    # Update the category
    for field, value in update_data.items():
        setattr(db_category, field, value)

    try:
        db.commit()
        db.refresh(db_category)
        return db_category
    except IntegrityError as e:
        db.rollback()
        if "asset_categories_code_key" in str(e):
            return error_response(
                message=f"Category with code '{update_data.get('code', db_category.code)}' already exists",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )
        return error_response(
            message="Duplicate category found during update",
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
        AssetCategory.org_id == org_id, AssetCategory.is_deleted == False).all()
    return categories
