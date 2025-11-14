from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from fastapi import Request
from shared.core.schemas import JsonOutResult
from typing import Callable, Any
import json
import traceback


def replace_nulls_with_empty(value: Any):
    """
    Recursively replaces None based on expected structure:
    - List fields -> []
    - Object/model fields -> {}
    - Primitives -> ""
    """
    # Dict → recurse
    if isinstance(value, dict):
        cleaned = {}
        for k, v in value.items():
            # If key suggests a LIST and value is None → []
            if v is None and k.lower() in {"roles", "items", "children", "permissions"}:
                cleaned[k] = []
            else:
                cleaned[k] = replace_nulls_with_empty(v)
        return cleaned

    # List → recurse each item
    elif isinstance(value, list):
        return [replace_nulls_with_empty(v) for v in value]

    # None → choose best type
    elif value is None:
        return ""  # default

    return value


class JsonResponseMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable):
        # Skip docs/openapi endpoints
        if request.url.path.startswith(("/openapi", "/docs", "/redoc")):
            return await call_next(request)

        try:
            response = await call_next(request)
        except Exception as e:
            # 🧨 Handle uncaught exceptions gracefully
            error_message = str(e)
            traceback.print_exc()

            wrapped_error = JsonOutResult(
                data="",
                status="Failed",
                status_code="500",
                message=f"Internal Server Error: {error_message}",
            ).model_dump(exclude_none=False)

            wrapped_error = replace_nulls_with_empty(wrapped_error)

            return JSONResponse(content=wrapped_error, status_code=500)

        # Check if it's JSON
        content_type = response.headers.get("content-type", "")
        is_json = "application/json" in content_type

        # Read the full body
        body_bytes = b""
        async for chunk in response.body_iterator:
            body_bytes += chunk

        async def body_gen():
            yield body_bytes
        response.body_iterator = body_gen()

        try:
            data = json.loads(body_bytes.decode("utf-8")) if is_json else None
        except Exception:
            data = None

        # Error responses (4xx/5xx)
        if not (200 <= response.status_code < 400):
            message = ""
            internal_status_code = str(response.status_code)

            if isinstance(data, dict):
                message = data.get("detail") or data.get("message") or ""
                internal_status_code = (
                    str(data.get("detail", {}).get("status_code"))
                    if isinstance(data.get("detail"), dict)
                    else str(data.get("status_code") or response.status_code)
                )
            elif isinstance(data, str):
                message = data
            elif data is None:
                message = "An unexpected error occurred"

            wrapped_error = JsonOutResult(
                data="",
                status="Failed",
                status_code=internal_status_code,
                message=message,
            ).model_dump(exclude_none=False)

            wrapped_error = replace_nulls_with_empty(wrapped_error)

            return JSONResponse(
                content=wrapped_error,
                status_code=response.status_code,
                headers={k: v for k, v in response.headers.items(
                ) if k.lower() != "content-length"},
            )

        # 🧹 Clean success JSON
        if data is not None:
            data = replace_nulls_with_empty(data)

        # Skip wrapping if already wrapped
        if isinstance(data, dict) and {"status", "status_code", "message"}.issubset(data.keys()):
            data = replace_nulls_with_empty(data)
            return JSONResponse(
                content=data,
                status_code=response.status_code,
                headers={k: v for k, v in response.headers.items() if k.lower()
                         != "content-length"},
            )

        wrapped = JsonOutResult(
            data=data if data not in [None, {}] else "",
            status="Success",
            status_code=str(response.status_code),
            message="Data retrieved successfully"
        ).model_dump(exclude_none=False)

        wrapped = replace_nulls_with_empty(wrapped)

        return JSONResponse(
            content=wrapped,
            status_code=response.status_code,
            headers={k: v for k, v in response.headers.items() if k.lower()
                     != "content-length"},
        )
