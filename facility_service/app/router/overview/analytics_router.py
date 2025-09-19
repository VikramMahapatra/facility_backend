from fastapi import APIRouter, Depends
from app.crud.overview import analytics_crud
from shared.auth import validate_current_token
router = APIRouter(prefix="/analytics", tags=["Analytics"],dependencies=[Depends(validate_current_token)])

