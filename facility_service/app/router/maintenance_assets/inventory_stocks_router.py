# app/routers/inventory_stocks.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from shared.core.database import get_facility_db as get_db
from shared.core.schemas import UserToken
from ...schemas.maintenance_assets.inventory_stocks_schemas import InventoryStockOut, InventoryStockCreate, InventoryStockUpdate
from ...crud.maintenance_assets import inventory_stocks_crud as crud
from shared.core.auth import validate_current_token

router = APIRouter(prefix="/api/inventory-stocks",
                   tags=["inventory_stocks"], dependencies=[Depends(validate_current_token)])


@router.get("/", response_model=List[InventoryStockOut])
def read_stocks(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.get_inventory_stocks(db, current_user.org_id, skip=skip, limit=limit)


@router.get("/{stock_id}", response_model=InventoryStockOut)
def read_stock(
    stock_id: str,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    db_stock = crud.get_inventory_stock_by_id(
        db, stock_id, current_user.org_id)
    if not db_stock:
        raise HTTPException(
            status_code=404, detail="Inventory stock not found")
    return db_stock


@router.post("/", response_model=InventoryStockOut)
def create_stock(
    stock: InventoryStockCreate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    return crud.create_inventory_stock(db, stock, current_user.org_id)


@router.put("/", response_model=InventoryStockOut)
def update_stock(
    stock: InventoryStockUpdate,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
):
    db_stock = crud.update_inventory_stock(db, stock, current_user.org_id)
    if not db_stock:
        raise HTTPException(
            status_code=404, detail="Inventory stock not found")
    return db_stock

# ---------------- Delete Inventory Stock (Soft Delete) ----------------


@router.delete("/{stock_id}")
def delete_stock(
    stock_id: str,
    db: Session = Depends(get_db),
    current_user: UserToken = Depends(validate_current_token)
): return crud.delete_inventory_stock_soft(db, stock_id, current_user.org_id)
