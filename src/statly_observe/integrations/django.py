"""
Django integration for Statly Observe SDK.

Captures errors from Django applications.

Example:
    # settings.py
    >>> MIDDLEWARE = [
    ...     'statly_observe.integrations.django.StatlyDjangoMiddleware',
    ...     # ... other middleware
    ... ]

    # wsgi.py or manage.py
    >>> from statly_observe import Statly
    >>> Statly.init(dsn="...")
"""

from typing import Any, Callable
import sys

from statly_observe import Statly


class StatlyDjangoMiddleware:
    """
    Django middleware for error tracking with Statly.
    """

    def __init__(self, get_response: Callable):
        """
        Initialize the middleware.

        Args:
            get_response: Django's get_response callable.
        """
        self.get_response = get_response

    def __call__(self, request):
        """
        Handle a Django request.

        Args:
            request: Django HttpRequest object.

        Returns:
            Django HttpResponse object.
        """
        import time

        # Store start time
        request._statly_start_time = time.time()

        # Add breadcrumb for request
        Statly.add_breadcrumb(
            message=f"{request.method} {request.path}",
            category="http",
            level="info",
            data={
                "method": request.method,
                "url": request.build_absolute_uri(),
                "path": request.path,
            },
        )

        # Set user context if available
        if hasattr(request, "user") and request.user.is_authenticated:
            user = request.user
            Statly.set_user(
                id=str(user.pk),
                email=getattr(user, "email", None),
                username=getattr(user, "username", None),
            )

        response = self.get_response(request)

        # Add breadcrumb for response
        duration = (time.time() - request._statly_start_time) * 1000
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

    def process_exception(self, request, exception: Exception) -> None:
        """
        Process exceptions raised during request handling.

        Args:
            request: Django HttpRequest object.
            exception: The exception that was raised.
        """
        # Build request context
        request_info = self._extract_request_info(request)

        # Set tags
        Statly.set_tag("http.method", request.method)
        Statly.set_tag("http.url", request.path)

        # Get resolver match for transaction name
        if hasattr(request, "resolver_match") and request.resolver_match:
            Statly.set_tag("transaction", request.resolver_match.view_name)

        # Capture exception
        Statly.capture_exception(exception, context={"request": request_info})

        # Return None to allow Django's default error handling
        return None

    def _extract_request_info(self, request) -> dict[str, Any]:
        """
        Extract request information from Django request.

        Args:
            request: Django HttpRequest object.

        Returns:
            Request info dictionary.
        """
        info: dict[str, Any] = {
            "method": request.method,
            "url": request.build_absolute_uri(),
            "path": request.path,
            "query_string": request.META.get("QUERY_STRING", ""),
            "headers": self._sanitize_headers(dict(request.headers)),
            "remote_addr": self._get_client_ip(request),
        }

        # Add resolver match info
        if hasattr(request, "resolver_match") and request.resolver_match:
            info["view_name"] = request.resolver_match.view_name
            info["url_name"] = request.resolver_match.url_name
            info["kwargs"] = dict(request.resolver_match.kwargs)

        # Add POST data if present
        if request.POST:
            info["post"] = self._sanitize_body(dict(request.POST))

        # Add JSON data if present
        if hasattr(request, "content_type") and "application/json" in request.content_type:
            try:
                import json

                info["json"] = self._sanitize_body(json.loads(request.body))
            except Exception:
                pass

        return info

    def _get_client_ip(self, request) -> str | None:
        """Get the client IP address from Django request."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

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
            "csrfmiddlewaretoken",
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


def init_django() -> None:
    """
    Initialize Statly integration for Django.

    This should be called after Statly.init() in your settings or wsgi.py.

    Note: Also add 'statly_observe.integrations.django.StatlyDjangoMiddleware'
    to your MIDDLEWARE setting.
    """
    # Install excepthook for uncaught exceptions
    client = Statly.get_client()
    if client:
        client.install_excepthook()


class StatlyDjangoHandler:
    """
    Django logging handler that sends log records to Statly.

    Example:
        # settings.py
        >>> LOGGING = {
        ...     'handlers': {
        ...         'statly': {
        ...             'class': 'statly_observe.integrations.django.StatlyDjangoHandler',
        ...             'level': 'ERROR',
        ...         },
        ...     },
        ...     'root': {
        ...         'handlers': ['statly'],
        ...         'level': 'ERROR',
        ...     },
        ... }
    """

    def __init__(self, level: str = "ERROR"):
        """
        Initialize the logging handler.

        Args:
            level: Minimum log level to capture.
        """
        import logging

        self.level = getattr(logging, level.upper(), logging.ERROR)

    def emit(self, record) -> None:
        """
        Emit a log record to Statly.

        Args:
            record: Python logging record.
        """
        import logging

        # Skip if below threshold
        if record.levelno < self.level:
            return

        # Map log level to Statly level
        level_map = {
            logging.DEBUG: "debug",
            logging.INFO: "info",
            logging.WARNING: "warning",
            logging.ERROR: "error",
            logging.CRITICAL: "fatal",
        }
        level = level_map.get(record.levelno, "error")

        # Check for exception info
        if record.exc_info and record.exc_info[1]:
            Statly.capture_exception(
                record.exc_info[1],
                context={
                    "logger": record.name,
                    "message": record.getMessage(),
                },
            )
        else:
            Statly.capture_message(
                record.getMessage(),
                level=level,
                context={
                    "logger": record.name,
                },
            )
