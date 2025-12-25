"""
FastAPI integration for Statly Observe SDK.

Captures errors from FastAPI applications.

Example:
    >>> from fastapi import FastAPI
    >>> from statly_observe import Statly
    >>> from statly_observe.integrations import init_fastapi
    >>>
    >>> app = FastAPI()
    >>> Statly.init(dsn="...")
    >>> init_fastapi(app)
    >>>
    >>> @app.get("/")
    >>> async def root():
    ...     return {"message": "Hello World"}
"""

from typing import Any, Callable, Awaitable
import sys
import time

from statly_observe import Statly


class StatlyFastAPI:
    """
    FastAPI integration for Statly error tracking.
    """

    def __init__(self, app=None):
        """
        Initialize the FastAPI integration.

        Args:
            app: Optional FastAPI application to initialize with.
        """
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app) -> None:
        """
        Initialize the integration with a FastAPI application.

        Args:
            app: FastAPI application instance.
        """
        # Add middleware
        app.middleware("http")(self._middleware)

        # Add exception handler
        app.add_exception_handler(Exception, self._exception_handler)

    async def _middleware(
        self,
        request,
        call_next: Callable[[Any], Awaitable[Any]],
    ):
        """
        Middleware to track requests and capture errors.

        Args:
            request: FastAPI/Starlette Request object.
            call_next: Next middleware/handler in the chain.

        Returns:
            Response object.
        """
        start_time = time.time()

        # Add breadcrumb for request
        Statly.add_breadcrumb(
            message=f"{request.method} {request.url.path}",
            category="http",
            level="info",
            data={
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
            },
        )

        try:
            response = await call_next(request)

            # Add breadcrumb for response
            duration = (time.time() - start_time) * 1000
            Statly.add_breadcrumb(
                message=f"Response {response.status_code}",
                category="http",
                level="error" if response.status_code >= 400 else "info",
                data={
                    "status_code": response.status_code,
                    "duration_ms": duration,
                },
            )

            return response

        except Exception as e:
            # Capture exception with request context
            request_info = await self._extract_request_info(request)
            Statly.capture_exception(e, context={"request": request_info})
            raise

    async def _exception_handler(self, request, exc: Exception):
        """
        Exception handler for unhandled exceptions.

        Args:
            request: FastAPI/Starlette Request object.
            exc: The exception that was raised.
        """
        request_info = await self._extract_request_info(request)

        # Set tags
        Statly.set_tag("http.method", request.method)
        Statly.set_tag("http.url", request.url.path)

        # Capture exception
        Statly.capture_exception(exc, context={"request": request_info})

        # Re-raise for FastAPI's default error handling
        raise exc

    async def _extract_request_info(self, request) -> dict[str, Any]:
        """
        Extract request information from FastAPI request.

        Args:
            request: FastAPI/Starlette Request object.

        Returns:
            Request info dictionary.
        """
        info: dict[str, Any] = {
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_string": request.url.query,
            "headers": self._sanitize_headers(dict(request.headers)),
        }

        # Get client info
        if request.client:
            info["remote_addr"] = request.client.host

        # Get path parameters
        if hasattr(request, "path_params") and request.path_params:
            info["path_params"] = dict(request.path_params)

        # Get query parameters
        if request.query_params:
            info["query_params"] = dict(request.query_params)

        # Try to get JSON body
        if request.headers.get("content-type", "").startswith("application/json"):
            try:
                body = await request.json()
                info["json"] = self._sanitize_body(body)
            except Exception:
                pass

        return info

    def _sanitize_headers(self, headers: dict[str, str]) -> dict[str, str]:
        """Sanitize headers to remove sensitive information."""
        sensitive_headers = {"authorization", "cookie", "x-api-key", "x-auth-token"}
        sanitized = {}

        for key, value in headers.items():
            if key.lower() in sensitive_headers:
                sanitized[key] = "[Filtered]"
            else:
                sanitized[key] = value

        return sanitized

    def _sanitize_body(self, body: Any) -> Any:
        """Sanitize request body to remove sensitive information."""
        if not isinstance(body, dict):
            return body

        sensitive_fields = {
            "password",
            "secret",
            "token",
            "api_key",
            "apikey",
            "credit_card",
            "creditcard",
            "ssn",
        }
        sanitized = {}

        for key, value in body.items():
            if any(field in key.lower() for field in sensitive_fields):
                sanitized[key] = "[Filtered]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_body(value)
            else:
                sanitized[key] = value

        return sanitized


def init_fastapi(app) -> StatlyFastAPI:
    """
    Initialize Statly integration with a FastAPI application.

    Args:
        app: FastAPI application instance.

    Returns:
        StatlyFastAPI integration instance.
    """
    integration = StatlyFastAPI(app)
    return integration


def statly_dependency():
    """
    FastAPI dependency that provides Statly context.

    Example:
        >>> from fastapi import Depends
        >>> from statly_observe.integrations.fastapi import statly_dependency
        >>>
        >>> @app.get("/")
        >>> async def root(statly=Depends(statly_dependency)):
        ...     statly.add_breadcrumb(message="Processing request")
        ...     return {"message": "Hello World"}
    """

    class StatlyDep:
        """Dependency class for Statly context."""

        @staticmethod
        def capture_exception(exception: Exception, context: dict | None = None) -> str:
            """Capture an exception."""
            return Statly.capture_exception(exception, context)

        @staticmethod
        def capture_message(message: str, level: str = "info", context: dict | None = None) -> str:
            """Capture a message."""
            return Statly.capture_message(message, level, context)

        @staticmethod
        def add_breadcrumb(
            message: str,
            category: str | None = None,
            level: str = "info",
            data: dict | None = None,
        ) -> None:
            """Add a breadcrumb."""
            Statly.add_breadcrumb(message=message, category=category, level=level, data=data)

        @staticmethod
        def set_user(id: str | None = None, email: str | None = None, **kwargs) -> None:
            """Set user context."""
            Statly.set_user(id=id, email=email, **kwargs)

        @staticmethod
        def set_tag(key: str, value: str) -> None:
            """Set a tag."""
            Statly.set_tag(key, value)

    return StatlyDep()
