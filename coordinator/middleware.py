"""FastAPI middleware for rate limiting and request tracking."""

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time
import uuid
from rate_limit import RateLimiter
from audit import log_rate_limit


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, rate_limiter: RateLimiter):
        super().__init__(app)
        self.rate_limiter = rate_limiter
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/public-key"]:
            return await call_next(request)
        
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Check rate limits based on endpoint
        if request.url.path in ["/heartbeat", "/peers", "/v1/models"]:
            # Discovery endpoints
            allowed, remaining = self.rate_limiter.check_discovery_limit(client_ip)
            if not allowed:
                log_rate_limit(client_ip, request.url.path, 100, 3600)
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Rate limit exceeded",
                        "limit": 100,
                        "window": "1 hour"
                    },
                    headers={"Retry-After": "3600"}
                )
        
        elif request.url.path in ["/authorize"]:
            # Authorization endpoint - use user ID from request body
            # For now, use IP as proxy until we parse the request
            allowed, remaining = self.rate_limiter.check_inference_limit(client_ip)
            if not allowed:
                log_rate_limit(client_ip, request.url.path, 20, 3600)
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Rate limit exceeded",
                        "limit": 20,
                        "window": "1 hour"
                    },
                    headers={"Retry-After": "3600"}
                )
        
        response = await call_next(request)
        return response


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Add request ID for distributed tracing."""
    
    async def dispatch(self, request: Request, call_next):
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Add to request state for use in endpoints
        request.state.request_id = request_id
        
        # Time the request
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Add headers
        duration_ms = int((time.time() - start_time) * 1000)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms}ms"
        
        return response
