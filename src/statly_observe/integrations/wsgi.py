"""
WSGI middleware for Statly Observe SDK.

Captures errors from WSGI applications.

Example:
    >>> from statly_observe import Statly
    >>> from statly_observe.integrations import StatlyWSGIMiddleware
    >>>
    >>> Statly.init(dsn="...")
    >>>
    >>> app = StatlyWSGIMiddleware(your_wsgi_app)
"""

from typing import Any, Callable, Iterable
from datetime import datetime, timezone
import sys

from statly_observe import Statly


class StatlyWSGIMiddleware:
    """
    WSGI middleware that captures errors and adds request context.
    """

    def __init__(self, app: Callable):
        """
        Initialize the middleware.

        Args:
            app: The WSGI application to wrap.
        """
        self.app = app

    def __call__(
        self,
        environ: dict[str, Any],
        start_response: Callable,
    ) -> Iterable[bytes]:
        """
        Handle a WSGI request.

        Args:
            environ: WSGI environ dictionary.
            start_response: WSGI start_response callable.

        Returns:
            Response iterable.
        """
        # Extract request info
        request_info = self._extract_request_info(environ)

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
            return self.app(environ, start_response)
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

    def _extract_request_info(self, environ: dict[str, Any]) -> dict[str, Any]:
        """
        Extract request information from WSGI environ.

        Args:
            environ: WSGI environ dictionary.

        Returns:
            Request info dictionary.
        """
        # Build URL
        scheme = environ.get("wsgi.url_scheme", "http")
        host = environ.get("HTTP_HOST") or environ.get("SERVER_NAME", "localhost")
        path = environ.get("PATH_INFO", "/")
        query = environ.get("QUERY_STRING", "")

        url = f"{scheme}://{host}{path}"
        if query:
            url = f"{url}?{query}"

        # Extract headers (skip sensitive ones)
        headers = {}
        sensitive_headers = {"authorization", "cookie", "x-api-key", "x-auth-token"}

        for key, value in environ.items():
            if key.startswith("HTTP_"):
                header_name = key[5:].lower().replace("_", "-")
                if header_name in sensitive_headers:
                    headers[header_name] = "[Filtered]"
                else:
                    headers[header_name] = value

        return {
            "method": environ.get("REQUEST_METHOD", "GET"),
            "url": url,
            "path": path,
            "query_string": query,
            "headers": headers,
            "content_type": environ.get("CONTENT_TYPE"),
            "content_length": environ.get("CONTENT_LENGTH"),
            "remote_addr": environ.get("REMOTE_ADDR"),
            "server_name": environ.get("SERVER_NAME"),
            "server_port": environ.get("SERVER_PORT"),
        }
