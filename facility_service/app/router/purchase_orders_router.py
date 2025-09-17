# app/routers/purchase_orders.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.databases import get_db
from app.schemas.purchase_orders_schemas import PurchaseOrderOut, PurchaseOrderCreate, PurchaseOrderUpdate
from app.crud import purchase_orders_crud as crud
from app.core.auth import get_current_token

router = APIRouter(prefix="/api/purchase-orders", tags=["purchase_orders"],dependencies=[Depends(get_current_token)])

@router.get("/", response_model=List[PurchaseOrderOut])
def read_pos(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_purchase_orders(db, skip=skip, limit=limit)

@router.get("/{po_id}", response_model=PurchaseOrderOut)
def read_po(po_id: str, db: Session = Depends(get_db)):
    db_po = crud.get_purchase_order_by_id(db, po_id)
    if not db_po:
        raise HTTPException(status_code=404, detail="PurchaseOrder not found")
    return db_po

@router.post("/", response_model=PurchaseOrderOut)
def create_po(po: PurchaseOrderCreate, db: Session = Depends(get_db)):
    return crud.create_purchase_order(db, po)

@router.put("/{po_id}", response_model=PurchaseOrderOut)
def update_po(po_id: str, po: PurchaseOrderUpdate, db: Session = Depends(get_db)):
    db_po = crud.update_purchase_order(db, po_id, po)
    if not db_po:
        raise HTTPException(status_code=404, detail="PurchaseOrder not found")
    return db_po

@router.delete("/{po_id}", response_model=PurchaseOrderOut)
def delete_po(po_id: str, db: Session = Depends(get_db)):
    db_po = crud.delete_purchase_order(db, po_id)
    if not db_po:
        raise HTTPException(status_code=404, detail="PurchaseOrder not found")
    return db_po
