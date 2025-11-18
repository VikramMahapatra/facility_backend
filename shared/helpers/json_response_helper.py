# app/utils/response_helper.py
from fastapi import HTTPException
from typing import Any

from shared.utils.app_status_code import AppStatusCode
from shared.core.schemas import JsonOutResult


def success_response(data: Any, message: str = "Success", status_code: str = AppStatusCode.DATA_RETRIEVED_SUCCESSFULLY):
    return JsonOutResult(
        data=data,
        status="Success",
        status_code=status_code,
        message=message
    )


def error_response(message: str, status_code: str = AppStatusCode.OPERATION_FAILED, http_status: int = 400):
    raise HTTPException(
        status_code=http_status,
        detail=JsonOutResult(
            data=None,
            status="Failure",
            status_code=status_code,
            message=message
        ).dict()
    )
