# app/crud/inventory_items.py

from typing import List, Optional
from uuid import UUID
import uuid
from sqlalchemy import func
from sqlalchemy.orm import Session

from shared.utils.app_status_code import AppStatusCode
from shared.helpers.json_response_helper import error_response
from ...models.maintenance_assets.inventory_items import InventoryItem
from ...schemas.maintenance_assets.inventory_items_schemas import InventoryItemCreate, InventoryItemOut, InventoryItemUpdate
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError


def get_inventory_items(db: Session, org_id: UUID, skip: int = 0, limit: int = 100) -> List[InventoryItem]:
    # ✅ Filter by org_id and exclude deleted items
    return db.query(InventoryItem).filter(
        InventoryItem.org_id == org_id,
        InventoryItem.is_deleted == False
    ).offset(skip).limit(limit).all()


def get_inventory_item_by_id(db: Session, item_id: str, org_id: UUID) -> Optional[InventoryItem]:
    # ✅ Filter by org_id and exclude deleted items
    return db.query(InventoryItem).filter(
        InventoryItem.id == item_id,
        InventoryItem.org_id == org_id,
        InventoryItem.is_deleted == False
    ).first()


def create_inventory_item(db: Session, item: InventoryItemCreate, org_id: UUID) -> InventoryItem:
    # Check for duplicate name (case-insensitive) within the same organization
    existing_item = db.query(InventoryItem).filter(
        InventoryItem.org_id == org_id,
        InventoryItem.is_deleted == False,
        func.lower(InventoryItem.name) == func.lower(
            item.name)  # Case-insensitive
    ).first()

    if existing_item:
        return error_response(
            message=f"Inventory item with name '{item.name}' already exists in this organization",
            status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
            http_status=400
        )

    # ✅ Use org_id from token instead of request body
    item_data = item.model_dump()
    item_data['org_id'] = org_id  # Override with token org_id

    try:
        db_item = InventoryItem(**item_data)
        db.add(db_item)
        db.commit()
        db.refresh(db_item)

        # Convert to InventoryItemOut for proper serialization
        return InventoryItemOut.model_validate(db_item)

    except IntegrityError as e:
        db.rollback()
        return error_response(
            message="Duplicate inventory item found",
            status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
            http_status=400
        )


def update_inventory_item(db: Session, item: InventoryItemUpdate, org_id: UUID) -> Optional[InventoryItem]:
    # ✅ Get the item and verify it belongs to the organization
    db_item = db.query(InventoryItem).filter(
        InventoryItem.id == item.id,
        InventoryItem.org_id == org_id,  # ✅ Security check
        InventoryItem.is_deleted == False
    ).first()

    if not db_item:
        return error_response(
            message="Inventory item not found",
            status_code=str(AppStatusCode.REQUIRED_VALIDATION_ERROR),
            http_status=404
        )

    # Extract update data
    update_data = item.model_dump(exclude_unset=True, exclude={'id'})

    # Only validate if name is being updated
    if 'name' in update_data:
        # Check for duplicate name (case-insensitive, exclude current item)
        existing_item = db.query(InventoryItem).filter(
            InventoryItem.org_id == org_id,
            InventoryItem.id != item.id,
            InventoryItem.is_deleted == False,
            func.lower(InventoryItem.name) == func.lower(
                update_data['name'])  # Case-insensitive
        ).first()

        if existing_item:
            return error_response(
                message=f"Inventory item with name '{update_data['name']}' already exists in this organization",
                status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
                http_status=400
            )

    # Update only the fields that are provided
    for k, v in update_data.items():
        setattr(db_item, k, v)

    try:
        db.commit()
        db.refresh(db_item)

        # Convert to InventoryItemOut for proper serialization
        return InventoryItemOut.model_validate(db_item)

    except IntegrityError as e:
        db.rollback()
        return error_response(
            message="Duplicate inventory item found during update",
            status_code=str(AppStatusCode.DUPLICATE_ADD_ERROR),
            http_status=400
        )


# ----------------- Soft Delete Inventory Item -----------------


def delete_inventory_item_soft(db: Session, item_id: str, org_id: UUID) -> bool:
    """
    Soft delete inventory item and its associated stocks
    Returns: True if deleted, False if not found
    """
    db_item = db.query(InventoryItem).filter(
        InventoryItem.id == item_id,
        InventoryItem.org_id == org_id,  # ✅ Security check
        InventoryItem.is_deleted == False
    ).first()

    if not db_item:
        return False

    # ✅ Check if item has stock quantity (business rule)
    from ...models.maintenance_assets.inventory_stocks import InventoryStock
    total_stock = db.query(func.sum(InventoryStock.qty_on_hand)).filter(
        InventoryStock.item_id == item_id,
        InventoryStock.is_deleted == False
    ).scalar() or 0

    if total_stock > 0:
        # Business rule: Cannot delete items with stock
        raise ValueError(
            f"Cannot delete item. It has {total_stock} quantity in stock. Please adjust stock to zero first.")

    # ✅ Soft delete the item
    db_item.is_deleted = True
    db_item.deleted_at = func.now()

    # ✅ Also soft delete all associated stocks
    db.query(InventoryStock).filter(
        InventoryStock.item_id == item_id,
        InventoryStock.is_deleted == False
    ).update({
        "is_deleted": True,
        "deleted_at": func.now()
    })

    db.commit()
    return True
