from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from shared.schemas import JsonOutResult
from shared.app_status_code import AppStatusCode
import traceback


def setup_exception_handlers(app: FastAPI):

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        wrapped = JsonOutResult(
            data=None,
            status="Failure",
            status_code=exc.status_code or AppStatusCode.OPERATION_FAILED,
            message=str(exc.detail)
        ).dict()
        return JSONResponse(content=wrapped, status_code=exc.status_code or 400)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        wrapped = JsonOutResult(
            data=None,
            status="Failure",
            status_code=AppStatusCode.INVALID_INPUT,
            message=str(exc)
        ).dict()
        return JSONResponse(content=wrapped, status_code=422)

    # Catch all unhandled exceptions
    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        # Log the traceback for debugging
        print("Unhandled Exception:", traceback.format_exc())

        wrapped = JsonOutResult(
            data=None,
            status="Failure",
            status_code=AppStatusCode.OPERATION_FAILED,
            # you can also use a generic message in production
            message=str(exc)
        ).dict()
        return JSONResponse(content=wrapped, status_code=500)
