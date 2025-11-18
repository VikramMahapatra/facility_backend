# app/crud/purchase_order_lines.py
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from ..models.purchase_order_lines import PurchaseOrderLine
from ..schemas.purchase_order_lines_schemas import PurchaseOrderLineCreate, PurchaseOrderLineUpdate

def get_purchase_order_lines(db: Session, skip: int = 0, limit: int = 100) -> List[PurchaseOrderLine]:
    return db.query(PurchaseOrderLine).offset(skip).limit(limit).all()

def get_purchase_order_line_by_id(db: Session, line_id: str) -> Optional[PurchaseOrderLine]:
    return db.query(PurchaseOrderLine).filter(PurchaseOrderLine.id == line_id).first()

def create_purchase_order_line(db: Session, line: PurchaseOrderLineCreate) -> PurchaseOrderLine:
    db_line = PurchaseOrderLine(id=str(uuid.uuid4()), **line.dict())
    db.add(db_line)
    db.commit()
    db.refresh(db_line)
    return db_line

def update_purchase_order_line(db: Session, line_id: str, line: PurchaseOrderLineUpdate) -> Optional[PurchaseOrderLine]:
    db_line = get_purchase_order_line_by_id(db, line_id)
    if not db_line:
        return None
    for k, v in line.dict(exclude_unset=True).items():
        setattr(db_line, k, v)
    db.commit()
    db.refresh(db_line)
    return db_line

def delete_purchase_order_line(db: Session, line_id: str) -> Optional[PurchaseOrderLine]:
    db_line = get_purchase_order_line_by_id(db, line_id)
    if not db_line:
        return None
    db.delete(db_line)
    db.commit()
    return db_line
