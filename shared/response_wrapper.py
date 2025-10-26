from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse, Response
from shared.schemas import JsonOutResult
import json
from typing import Callable


class JsonResponseMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next: Callable):
        # Skip OpenAPI/Swagger endpoints
        if request.url.path.startswith("/openapi") or request.url.path.startswith("/docs") or request.url.path.startswith("/redoc"):
            return await call_next(request)

        response = await call_next(request)

        # Only wrap successful JSON responses
        if 200 <= response.status_code < 400 and "application/json" in response.headers.get("content-type", ""):
            # Read body safely
            body_bytes = b""
            async for chunk in response.body_iterator:
                body_bytes += chunk

            # Restore body as async iterator
            async def body_gen():
                yield body_bytes

            response.body_iterator = body_gen()  # async iterator

            try:
                data = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                return response  # non-JSON, return as-is

            # Skip if already wrapped
            if isinstance(data, dict) and {"status", "status_code", "message"}.issubset(data.keys()):
                return response

            wrapped = JsonOutResult(
                data=data,
                status="Success",
                status_code="200",
                message="Data retrieved successfully"
            ).dict()

            return JSONResponse(
                content=wrapped,
                status_code=response.status_code,
                headers={k: v for k, v in response.headers.items()
                         if k.lower() != "content-length"}
            )

        return response
