from fastapi import APIRouter, Depends
from app.crud.overview import analytics_crud
from app.core.auth import get_current_token
router = APIRouter(prefix="/analytics", tags=["Analytics"],dependencies=[Depends(get_current_token)])

