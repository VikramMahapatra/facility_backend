# app/routers/inventory_stocks.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.databases import get_db
from app.schemas.inventory_stocks_schemas import InventoryStockOut, InventoryStockCreate, InventoryStockUpdate
from app.crud import inventory_stocks_crud as crud
from app.core.auth import get_current_token

router = APIRouter(prefix="/api/inventory-stocks", tags=["inventory_stocks"],dependencies=[Depends(get_current_token)])

@router.get("/", response_model=List[InventoryStockOut])
def read_stocks(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_inventory_stocks(db, skip=skip, limit=limit)

@router.get("/{stock_id}", response_model=InventoryStockOut)
def read_stock(stock_id: str, db: Session = Depends(get_db)):
    db_stock = crud.get_inventory_stock_by_id(db, stock_id)
    if not db_stock:
        raise HTTPException(status_code=404, detail="Inventory stock not found")
    return db_stock

@router.post("/", response_model=InventoryStockOut)
def create_stock(stock: InventoryStockCreate, db: Session = Depends(get_db)):
    return crud.create_inventory_stock(db, stock)

@router.put("/{stock_id}", response_model=InventoryStockOut)
def update_stock(stock_id: str, stock: InventoryStockUpdate, db: Session = Depends(get_db)):
    db_stock = crud.update_inventory_stock(db, stock_id, stock)
    if not db_stock:
        raise HTTPException(status_code=404, detail="Inventory stock not found")
    return db_stock

@router.delete("/{stock_id}", response_model=InventoryStockOut)
def delete_stock(stock_id: str, db: Session = Depends(get_db)):
    db_stock = crud.delete_inventory_stock(db, stock_id)
    if not db_stock:
        raise HTTPException(status_code=404, detail="Inventory stock not found")
    return db_stock
