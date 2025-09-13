# app/routers/inventory_items.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.databases import get_db
from app.schemas.inventory_items_schemas import InventoryItemOut, InventoryItemCreate, InventoryItemUpdate
from app.crud import inventory_items_crud as crud
from app.core.auth import get_current_token

router = APIRouter(prefix="/api/inventory-items", tags=["inventory_items"],dependencies=[Depends(get_current_token)])

@router.get("/", response_model=List[InventoryItemOut])
def read_items(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_inventory_items(db, skip=skip, limit=limit)

@router.get("/{item_id}", response_model=InventoryItemOut)
def read_item(item_id: str, db: Session = Depends(get_db)):
    db_item = crud.get_inventory_item_by_id(db, item_id)
    if not db_item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return db_item

@router.post("/", response_model=InventoryItemOut)
def create_item(item: InventoryItemCreate, db: Session = Depends(get_db)):
    return crud.create_inventory_item(db, item)

@router.put("/{item_id}", response_model=InventoryItemOut)
def update_item(item_id: str, item: InventoryItemUpdate, db: Session = Depends(get_db)):
    db_item = crud.update_inventory_item(db, item_id, item)
    if not db_item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return db_item

@router.delete("/{item_id}", response_model=InventoryItemOut)
def delete_item(item_id: str, db: Session = Depends(get_db)):
    db_item = crud.delete_inventory_item(db, item_id)
    if not db_item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return db_item
