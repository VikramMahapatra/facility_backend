# app/crud/purchase_orders.py
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.purchase_orders import PurchaseOrder
from app.schemas.purchase_orders_schemas import PurchaseOrderCreate, PurchaseOrderUpdate

def get_purchase_orders(db: Session, skip: int = 0, limit: int = 100) -> List[PurchaseOrder]:
    return db.query(PurchaseOrder).offset(skip).limit(limit).all()

def get_purchase_order_by_id(db: Session, po_id: str) -> Optional[PurchaseOrder]:
    return db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()

def create_purchase_order(db: Session, po: PurchaseOrderCreate) -> PurchaseOrder:
    db_po = PurchaseOrder(id=str(uuid.uuid4()), **po.dict())
    db.add(db_po)
    db.commit()
    db.refresh(db_po)
    return db_po

def update_purchase_order(db: Session, po_id: str, po: PurchaseOrderUpdate) -> Optional[PurchaseOrder]:
    db_po = get_purchase_order_by_id(db, po_id)
    if not db_po:
        return None
    for k, v in po.dict(exclude_unset=True).items():
        setattr(db_po, k, v)
    db.commit()
    db.refresh(db_po)
    return db_po

def delete_purchase_order(db: Session, po_id: str) -> Optional[PurchaseOrder]:
    db_po = get_purchase_order_by_id(db, po_id)
    if not db_po:
        return None
    db.delete(db_po)
    db.commit()
    return db_po
