from datetime import datetime
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from shared.core.database import get_facility_db as get_db
from shared.core.auth import validate_current_token
from shared.core.schemas import ExportRequestParams, ExportResponse, Lookup, UserToken
from ...crud.common import export_crud as crud


router = APIRouter(
    prefix="/api/export",
    tags=["Export"],
    dependencies=[Depends(validate_current_token)]
)


# @router.get(
#     "/",
#     response_class=StreamingResponse,
#     responses={
#         200: {
#             "content": {
#                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}
#             },
#             "description": "Excel file download",
#         }
#     },
# )
@router.get("/", response_model=ExportResponse)
def get_export_data(
        type: str,
        params: ExportRequestParams = Depends(),
        db: Session = Depends(get_db),
        current_user: UserToken = Depends(validate_current_token)):
    return crud.get_export_data(db, current_user.org_id, type, params)
