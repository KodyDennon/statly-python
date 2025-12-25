"""
Flask integration for Statly Observe SDK.

Captures errors from Flask applications.

Example:
    >>> from flask import Flask
    >>> from statly_observe import Statly
    >>> from statly_observe.integrations import init_flask
    >>>
    >>> app = Flask(__name__)
    >>> Statly.init(dsn="...")
    >>> init_flask(app)
    >>>
    >>> @app.route("/")
    >>> def index():
    ...     return "Hello World"
"""

from typing import Any
import sys

from statly_observe import Statly


class StatlyFlask:
    """
    Flask extension for Statly error tracking.
    """

    def __init__(self, app=None):
        """
        Initialize the Flask extension.

        Args:
            app: Optional Flask application to initialize with.
        """
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app) -> None:
        """
        Initialize the extension with a Flask application.

        Args:
            app: Flask application instance.
        """
        # Register error handlers
        app.register_error_handler(Exception, self._handle_exception)

        # Register before/after request hooks
        app.before_request(self._before_request)
        app.after_request(self._after_request)

        # Try to use blinker signals if available
        try:
            from flask import got_request_exception

            got_request_exception.connect(self._got_request_exception, app)
        except ImportError:
            pass

    def _before_request(self) -> None:
        """Hook called before each request."""
        try:
            from flask import request, g
            import time

            # Store request start time
            g.statly_start_time = time.time()

            # Add breadcrumb for request
            Statly.add_breadcrumb(
                message=f"{request.method} {request.path}",
                category="http",
                level="info",
                data={
                    "method": request.method,
                    "url": request.url,
                    "path": request.path,
                },
            )

            # Set user from session if available
            if hasattr(request, "user") and request.user:
                user = request.user
                if hasattr(user, "id"):
                    Statly.set_user(
                        id=str(user.id),
                        email=getattr(user, "email", None),
                        username=getattr(user, "username", None),
                    )
        except Exception:
            pass

    def _after_request(self, response):
        """
        Hook called after each request.

        Args:
            response: Flask response object.

        Returns:
            The response object.
        """
        try:
            from flask import request, g
            import time

            # Calculate duration
            start_time = getattr(g, "statly_start_time", None)
            duration = (time.time() - start_time) * 1000 if start_time else None

            # Add breadcrumb for response
            Statly.add_breadcrumb(
                message=f"Response {response.status_code}",
                category="http",
                level="error" if response.status_code >= 400 else "info",
                data={
                    "status_code": response.status_code,
                    "duration_ms": duration,
                },
            )
        except Exception:
            pass

        return response

    def _handle_exception(self, exception: Exception):
        """
        Handle exceptions raised during request processing.

        Args:
            exception: The exception that was raised.
        """
        self._capture_exception(exception)
        raise exception

    def _got_request_exception(self, sender, exception, **extra):
        """
        Signal handler for got_request_exception.

        Args:
            sender: The Flask application.
            exception: The exception that was raised.
            **extra: Extra keyword arguments.
        """
        self._capture_exception(exception)

    def _capture_exception(self, exception: Exception) -> None:
        """
        Capture an exception with Flask request context.

        Args:
            exception: The exception to capture.
        """
        try:
            from flask import request

            # Build request context
            request_info = {
                "method": request.method,
                "url": request.url,
                "path": request.path,
                "query_string": request.query_string.decode("utf-8", errors="replace"),
                "headers": self._sanitize_headers(dict(request.headers)),
                "remote_addr": request.remote_addr,
                "endpoint": request.endpoint,
            }

            # Add form data if present
            if request.form:
                request_info["form"] = self._sanitize_body(dict(request.form))

            # Add JSON data if present
            if request.is_json:
                try:
                    request_info["json"] = self._sanitize_body(request.get_json())
                except Exception:
                    pass

            # Set tags
            Statly.set_tag("http.method", request.method)
            Statly.set_tag("http.url", request.path)
            if request.endpoint:
                Statly.set_tag("transaction", request.endpoint)

            Statly.capture_exception(exception, context={"request": request_info})

        except Exception:
            # Fall back to basic capture
            Statly.capture_exception(exception)

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


def init_flask(app) -> StatlyFlask:
    """
    Initialize Statly integration with a Flask application.

    Args:
        app: Flask application instance.

    Returns:
        StatlyFlask extension instance.
    """
    extension = StatlyFlask(app)
    return extension
