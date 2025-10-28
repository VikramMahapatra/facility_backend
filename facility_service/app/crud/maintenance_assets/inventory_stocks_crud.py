# app/crud/inventory_stocks.py
from uuid import UUID
from typing import List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
from ...models.maintenance_assets.inventory_stocks import InventoryStock
from ...schemas.maintenance_assets.inventory_stocks_schemas import InventoryStockCreate, InventoryStockUpdate


def get_inventory_stocks(db: Session, org_id: UUID, skip: int = 0, limit: int = 100) -> List[InventoryStock]:
    # ✅ Filter by org_id and exclude deleted stocks
    return db.query(InventoryStock).filter(
        InventoryStock.org_id == org_id,
        InventoryStock.is_deleted == False
    ).offset(skip).limit(limit).all()


def get_inventory_stock_by_id(db: Session, stock_id: str, org_id: UUID) -> Optional[InventoryStock]:
    # ✅ Filter by org_id and exclude deleted stocks
    return db.query(InventoryStock).filter(
        InventoryStock.id == stock_id,
        InventoryStock.org_id == org_id,
        InventoryStock.is_deleted == False
    ).first()


def create_inventory_stock(db: Session, stock: InventoryStockCreate, org_id: UUID) -> InventoryStock:
    # ✅ Use org_id from token instead of request body
    stock_data = stock.dict()
    stock_data['org_id'] = org_id  # Override with token org_id
    db_stock = InventoryStock(**stock_data)
    db.add(db_stock)
    db.commit()
    db.refresh(db_stock)
    return db_stock


def update_inventory_stock(db: Session, stock: InventoryStockUpdate, org_id: UUID) -> Optional[InventoryStock]:
    # ✅ Get the stock and verify it belongs to the organization
    db_stock = db.query(InventoryStock).filter(
        InventoryStock.id == stock.id,
        InventoryStock.org_id == org_id,  # ✅ Security check
        InventoryStock.is_deleted == False
    ).first()

    if not db_stock:
        return None

    # Update only the fields that are provided
    for k, v in stock.dict(exclude_unset=True, exclude={'id'}).items():
        setattr(db_stock, k, v)

    db.commit()
    db.refresh(db_stock)
    return db_stock

# ----------------- Soft Delete Inventory Stock -----------------


def delete_inventory_stock_soft(db: Session, stock_id: str, org_id: UUID) -> bool:
    """
    Soft delete inventory stock
    Returns: True if deleted, False if not found
    """
    db_stock = db.query(InventoryStock).filter(
        InventoryStock.id == stock_id,
        InventoryStock.org_id == org_id,  # ✅ Security check
        InventoryStock.is_deleted == False
    ).first()

    if not db_stock:
        return False

    # ✅ Business rule: Cannot delete stock with quantity > 0
    if db_stock.qty_on_hand > 0:
        raise ValueError(
            f"Cannot delete stock. It has {db_stock.qty_on_hand} quantity. Please adjust quantity to zero first.")

    # ✅ Soft delete the stock
    db_stock.is_deleted = True
    db_stock.deleted_at = func.now()
    db.commit()
    return True
