# app/crud/inventory_stocks.py
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.inventory_stocks import InventoryStock
from app.schemas.inventory_stocks_schemas import InventoryStockCreate, InventoryStockUpdate

def get_inventory_stocks(db: Session, skip: int = 0, limit: int = 100) -> List[InventoryStock]:
    return db.query(InventoryStock).offset(skip).limit(limit).all()

def get_inventory_stock_by_id(db: Session, stock_id: str) -> Optional[InventoryStock]:
    return db.query(InventoryStock).filter(InventoryStock.id == stock_id).first()

def create_inventory_stock(db: Session, stock: InventoryStockCreate) -> InventoryStock:
    db_stock = InventoryStock(id=str(uuid.uuid4()), **stock.dict())
    db.add(db_stock)
    db.commit()
    db.refresh(db_stock)
    return db_stock

def update_inventory_stock(db: Session, stock_id: str, stock: InventoryStockUpdate) -> Optional[InventoryStock]:
    db_stock = get_inventory_stock_by_id(db, stock_id)
    if not db_stock:
        return None
    for k, v in stock.dict(exclude_unset=True).items():
        setattr(db_stock, k, v)
    db.commit()
    db.refresh(db_stock)
    return db_stock

def delete_inventory_stock(db: Session, stock_id: str) -> Optional[InventoryStock]:
    db_stock = get_inventory_stock_by_id(db, stock_id)
    if not db_stock:
        return None
    db.delete(db_stock)
    db.commit()
    return db_stock
