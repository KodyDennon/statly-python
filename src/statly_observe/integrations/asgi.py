"""
ASGI middleware for Statly Observe SDK.

Captures errors from ASGI applications (Starlette, FastAPI, etc.).

Example:
    >>> from statly_observe import Statly
    >>> from statly_observe.integrations import StatlyASGIMiddleware
    >>>
    >>> Statly.init(dsn="...")
    >>>
    >>> app = StatlyASGIMiddleware(your_asgi_app)
"""

from typing import Any, Callable, Awaitable
import sys

from statly_observe import Statly


class StatlyASGIMiddleware:
    """
    ASGI middleware that captures errors and adds request context.
    """

    def __init__(self, app: Callable):
        """
        Initialize the middleware.

        Args:
            app: The ASGI application to wrap.
        """
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """
        Handle an ASGI request.

        Args:
            scope: ASGI scope dictionary.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Extract request info
        request_info = self._extract_request_info(scope)

        # Add breadcrumb for request
        Statly.add_breadcrumb(
            message=f"{request_info['method']} {request_info['url']}",
            category="http",
            level="info",
            data={
                "method": request_info["method"],
                "url": request_info["url"],
            },
        )

        try:
            await self.app(scope, receive, send)
        except Exception:
            # Capture exception with request context
            exc_info = sys.exc_info()
            Statly.capture_exception(
                exc_info[1],
                context={
                    "request": request_info,
                },
            )
            raise

    def _extract_request_info(self, scope: dict[str, Any]) -> dict[str, Any]:
        """
        Extract request information from ASGI scope.

        Args:
            scope: ASGI scope dictionary.

        Returns:
            Request info dictionary.
        """
        # Build URL
        scheme = scope.get("scheme", "http")
        server = scope.get("server")
        if server:
            host = f"{server[0]}:{server[1]}" if server[1] not in (80, 443) else server[0]
        else:
            host = "localhost"

        path = scope.get("path", "/")
        query_string = scope.get("query_string", b"").decode("utf-8", errors="replace")

        url = f"{scheme}://{host}{path}"
        if query_string:
            url = f"{url}?{query_string}"

        # Extract headers (skip sensitive ones)
        headers = {}
        sensitive_headers = {b"authorization", b"cookie", b"x-api-key", b"x-auth-token"}

        for key, value in scope.get("headers", []):
            if key in sensitive_headers:
                headers[key.decode("utf-8")] = "[Filtered]"
            else:
                headers[key.decode("utf-8")] = value.decode("utf-8", errors="replace")

        # Get client info
        client = scope.get("client")
        client_addr = client[0] if client else None

        return {
            "method": scope.get("method", "GET"),
            "url": url,
            "path": path,
            "query_string": query_string,
            "headers": headers,
            "remote_addr": client_addr,
            "type": scope.get("type"),
            "asgi_version": scope.get("asgi", {}).get("version"),
        }
