# app/routers/inventory_items.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.core.database import get_facility_db as get_db
from shared.helpers.json_response_helper import success_response
from shared.core.schemas import UserToken
from ...schemas.maintenance_assets.inventory_items_schemas import InventoryItemOut, InventoryItemCreate, InventoryItemUpdate
from ...crud.maintenance_assets import inventory_items_crud as crud
from shared.core.auth import validate_current_token

router = APIRouter(prefix="/api/inventory-items",
                   tags=["inventory_items"], dependencies=[Depends(validate_current_token)])


@router.get("/", response_model=List[InventoryItemOut])
def read_items(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_inventory_items(db, current_user.org_id, skip=skip, limit=limit)


@router.get("/{item_id}", response_model=InventoryItemOut)
def read_item(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    db_item = crud.get_inventory_item_by_id(db, item_id, current_user.org_id)
    if not db_item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return db_item


@router.post("/", response_model=None)
def create_item(
    item: InventoryItemCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.create_inventory_item(db, item, current_user.org_id)


@router.put("/", response_model=None)
def update_item(
    item: InventoryItemUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.update_inventory_item(db, item, current_user.org_id)

# ---------------- Delete Inventory Item (Soft Delete) ----------------


@router.delete("/{item_id}")
def delete_item(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
): return crud.delete_inventory_item_soft(db, item_id, current_user.org_id)
