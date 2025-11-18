"""Validation middleware for request payload size and structure."""
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import structlog
import orjson
from ..config import get_settings

log = structlog.get_logger()
settings = get_settings()


class ValidationMiddleware(BaseHTTPMiddleware):
    """Validates incoming requests for payload size and JSON structure."""

    async def dispatch(self, request: Request, call_next):
        # Only validate POST/PUT/PATCH requests
        if request.method in ["POST", "PUT", "PATCH"]:
            # Check content-length header first
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > settings.MAX_EVENT_SIZE:
                log.warning(
                    "payload.too_large",
                    size=int(content_length),
                    max_size=settings.MAX_EVENT_SIZE,
                    path=request.url.path
                )
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": "PayloadTooLarge",
                        "message": f"Request payload exceeds maximum size of {settings.MAX_EVENT_SIZE} bytes",
                        "max_size": settings.MAX_EVENT_SIZE,
                        "received_size": int(content_length)
                    }
                )

            # Validate JSON structure if content-type is application/json
            if request.headers.get("content-type", "").startswith("application/json"):
                try:
                    body = await request.body()
                    if len(body) > settings.MAX_EVENT_SIZE:
                        log.warning(
                            "payload.too_large",
                            size=len(body),
                            max_size=settings.MAX_EVENT_SIZE,
                            path=request.url.path
                        )
                        return JSONResponse(
                            status_code=413,
                            content={
                                "error": "PayloadTooLarge",
                                "message": f"Request payload exceeds maximum size of {settings.MAX_EVENT_SIZE} bytes",
                                "max_size": settings.MAX_EVENT_SIZE,
                                "received_size": len(body)
                            }
                        )

                    # Validate JSON structure
                    if body:
                        try:
                            orjson.loads(body)
                        except orjson.JSONDecodeError as e:
                            log.warning("invalid.json", error=str(e), path=request.url.path)
                            return JSONResponse(
                                status_code=400,
                                content={
                                    "error": "InvalidJSON",
                                    "message": "Request body is not valid JSON",
                                    "detail": str(e)
                                }
                            )

                    # Re-create request with consumed body
                    async def receive():
                        return {"type": "http.request", "body": body}

                    request._receive = receive

                except Exception as e:
                    log.error("validation.error", error=str(e), path=request.url.path)
                    return JSONResponse(
                        status_code=500,
                        content={
                            "error": "ValidationError",
                            "message": "Error validating request",
                            "detail": str(e)
                        }
                    )

        response = await call_next(request)
        return response
