"""Timeout middleware for FastAPI endpoints."""

import asyncio
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time

# Timeout configuration per endpoint pattern
ENDPOINT_TIMEOUTS = {
    "/health": 5,
    "/public-key": 5,
    "/v1/models": 5,
    "/peers": 5,
    "/heartbeat": 5,
    "/authorize": 30,
    "/hardware/challenge": 30,
    "/hardware/verify": 30,
    "/transactions/submit": 30,
    "/users/": 5,  # Balance and transaction queries
    # Inference endpoints would be 300s, but we don't have those in coordinator
}

DEFAULT_TIMEOUT = 30  # Default for unmatched endpoints


class TimeoutMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce timeouts on all endpoints.
    Returns 504 Gateway Timeout if request exceeds configured limit.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Determine timeout for this endpoint
        timeout = self._get_timeout(request.url.path)
        
        # Track request start time
        start_time = time.time()
        
        try:
            # Execute request with timeout
            response = await asyncio.wait_for(
                call_next(request),
                timeout=timeout
            )
            
            # Add elapsed time header
            elapsed_ms = int((time.time() - start_time) * 1000)
            response.headers["X-Timeout-Ms"] = str(elapsed_ms)
            
            return response
            
        except asyncio.TimeoutError:
            # Request exceeded timeout
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            return JSONResponse(
                status_code=504,
                content={
                    "error": "Gateway Timeout",
                    "message": f"Request exceeded timeout of {timeout}s",
                    "timeout_seconds": timeout,
                    "elapsed_ms": elapsed_ms
                },
                headers={"X-Timeout-Ms": str(elapsed_ms)}
            )
    
    def _get_timeout(self, path: str) -> float:
        """Get timeout for specific endpoint path."""
        # Check exact matches first
        if path in ENDPOINT_TIMEOUTS:
            return ENDPOINT_TIMEOUTS[path]
        
        # Check prefix matches
        for pattern, timeout in ENDPOINT_TIMEOUTS.items():
            if path.startswith(pattern):
                return timeout
        
        # Return default
        return DEFAULT_TIMEOUT
