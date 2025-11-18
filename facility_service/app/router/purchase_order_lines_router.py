# app/routers/purchase_order_lines.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.core.database import get_facility_db as get_db
from ..schemas.purchase_order_lines_schemas import PurchaseOrderLineOut, PurchaseOrderLineCreate, PurchaseOrderLineUpdate
from ..crud import purchase_order_lines_crud as crud
from shared.core.auth import validate_current_token

router = APIRouter(prefix="/api/purchase-order-lines",
                   tags=["purchase_order_lines"], dependencies=[Depends(validate_current_token)])


@router.get("/", response_model=List[PurchaseOrderLineOut])
def read_lines(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_purchase_order_lines(db, skip=skip, limit=limit)


@router.get("/{line_id}", response_model=PurchaseOrderLineOut)
def read_line(line_id: str, db: Session = Depends(get_db)):
    db_line = crud.get_purchase_order_line_by_id(db, line_id)
    if not db_line:
        raise HTTPException(
            status_code=404, detail="PurchaseOrderLine not found")
    return db_line


@router.post("/", response_model=PurchaseOrderLineOut)
def create_line(line: PurchaseOrderLineCreate, db: Session = Depends(get_db)):
    return crud.create_purchase_order_line(db, line)


@router.put("/{line_id}", response_model=PurchaseOrderLineOut)
def update_line(line_id: str, line: PurchaseOrderLineUpdate, db: Session = Depends(get_db)):
    db_line = crud.update_purchase_order_line(db, line_id, line)
    if not db_line:
        raise HTTPException(
            status_code=404, detail="PurchaseOrderLine not found")
    return db_line


@router.delete("/{line_id}", response_model=PurchaseOrderLineOut)
def delete_line(line_id: str, db: Session = Depends(get_db)):
    db_line = crud.delete_purchase_order_line(db, line_id)
    if not db_line:
        raise HTTPException(
            status_code=404, detail="PurchaseOrderLine not found")
    return db_line
