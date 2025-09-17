# app/crud/inventory_items.py
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.inventory_items import InventoryItem
from app.schemas.inventory_items_schemas import InventoryItemCreate, InventoryItemUpdate

def get_inventory_items(db: Session, skip: int = 0, limit: int = 100) -> List[InventoryItem]:
    return db.query(InventoryItem).offset(skip).limit(limit).all()

def get_inventory_item_by_id(db: Session, item_id: str) -> Optional[InventoryItem]:
    return db.query(InventoryItem).filter(InventoryItem.id == item_id).first()

def create_inventory_item(db: Session, item: InventoryItemCreate) -> InventoryItem:
    db_item = InventoryItem(id=str(uuid.uuid4()), **item.dict())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

def update_inventory_item(db: Session, item_id: str, item: InventoryItemUpdate) -> Optional[InventoryItem]:
    db_item = get_inventory_item_by_id(db, item_id)
    if not db_item:
        return None
    for k, v in item.dict(exclude_unset=True).items():
        setattr(db_item, k, v)
    db.commit()
    db.refresh(db_item)
    return db_item

def delete_inventory_item(db: Session, item_id: str) -> Optional[InventoryItem]:
    db_item = get_inventory_item_by_id(db, item_id)
    if not db_item:
        return None
    db.delete(db_item)
    db.commit()
    return db_item
