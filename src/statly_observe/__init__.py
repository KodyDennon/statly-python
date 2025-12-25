"""
Statly Observe SDK

Error tracking and monitoring for Python applications.

Example:
    >>> from statly_observe import Statly
    >>>
    >>> # Get your DSN from statly.live/dashboard/observe/setup
    >>> Statly.init(dsn="https://sk_live_xxx@statly.live/your-org")
    >>>
    >>> # Errors are captured automatically
    >>>
    >>> # Manual capture
    >>> try:
    ...     risky_operation()
    ... except Exception as e:
    ...     Statly.capture_exception(e)
    >>>
    >>> # Capture a message
    >>> Statly.capture_message("Something happened", level="warning")
    >>>
    >>> # Set user context
    >>> Statly.set_user(id="user-123", email="user@example.com")
"""

from .client import StatlyClient
from .scope import Scope
from .event import Event, EventLevel
from .breadcrumb import Breadcrumb, BreadcrumbType
from .transport import Transport

__version__ = "0.1.0"
__all__ = [
    "Statly",
    "StatlyClient",
    "Scope",
    "Event",
    "EventLevel",
    "Breadcrumb",
    "BreadcrumbType",
    "Transport",
    "init",
    "capture_exception",
    "capture_message",
    "set_user",
    "set_tag",
    "set_tags",
    "add_breadcrumb",
    "flush",
    "close",
]

# Global client instance
_client: StatlyClient | None = None


class Statly:
    """Main SDK interface - provides static methods for error tracking."""

    @staticmethod
    def init(
        dsn: str,
        environment: str | None = None,
        release: str | None = None,
        debug: bool = False,
        sample_rate: float = 1.0,
        max_breadcrumbs: int = 100,
        before_send: callable | None = None,
        transport: Transport | None = None,
    ) -> None:
        """
        Initialize the Statly SDK.

        Args:
            dsn: The Data Source Name (DSN) for your project.
            environment: The environment name (e.g., "production", "staging").
            release: The release version of your application.
            debug: Enable debug mode for verbose logging.
            sample_rate: Sample rate for events (0.0 to 1.0).
            max_breadcrumbs: Maximum number of breadcrumbs to store.
            before_send: Callback to modify or drop events before sending.
            transport: Custom transport for sending events.
        """
        global _client
        if _client is not None:
            import warnings

            warnings.warn(
                "Statly SDK already initialized. Call Statly.close() first to reinitialize.",
                UserWarning,
            )
            return

        _client = StatlyClient(
            dsn=dsn,
            environment=environment,
            release=release,
            debug=debug,
            sample_rate=sample_rate,
            max_breadcrumbs=max_breadcrumbs,
            before_send=before_send,
            transport=transport,
        )
        _client.install_excepthook()

    @staticmethod
    def capture_exception(
        exception: BaseException | None = None,
        context: dict | None = None,
    ) -> str:
        """
        Capture an exception and send it to Statly.

        Args:
            exception: The exception to capture. If None, captures sys.exc_info().
            context: Additional context to attach to the event.

        Returns:
            The event ID if captured, empty string otherwise.
        """
        if _client is None:
            import warnings

            warnings.warn("Statly SDK not initialized. Call Statly.init() first.", UserWarning)
            return ""
        return _client.capture_exception(exception, context)

    @staticmethod
    def capture_message(
        message: str,
        level: str = "info",
        context: dict | None = None,
    ) -> str:
        """
        Capture a message and send it to Statly.

        Args:
            message: The message to capture.
            level: The severity level (debug, info, warning, error, fatal).
            context: Additional context to attach to the event.

        Returns:
            The event ID if captured, empty string otherwise.
        """
        if _client is None:
            import warnings

            warnings.warn("Statly SDK not initialized. Call Statly.init() first.", UserWarning)
            return ""
        return _client.capture_message(message, level, context)

    @staticmethod
    def set_user(
        id: str | None = None,
        email: str | None = None,
        username: str | None = None,
        **kwargs,
    ) -> None:
        """
        Set the current user context.

        Args:
            id: User ID.
            email: User email.
            username: Username.
            **kwargs: Additional user attributes.
        """
        if _client is None:
            import warnings

            warnings.warn("Statly SDK not initialized. Call Statly.init() first.", UserWarning)
            return
        _client.set_user(id=id, email=email, username=username, **kwargs)

    @staticmethod
    def set_tag(key: str, value: str) -> None:
        """
        Set a tag on the current scope.

        Args:
            key: Tag key.
            value: Tag value.
        """
        if _client is None:
            import warnings

            warnings.warn("Statly SDK not initialized. Call Statly.init() first.", UserWarning)
            return
        _client.set_tag(key, value)

    @staticmethod
    def set_tags(tags: dict[str, str]) -> None:
        """
        Set multiple tags on the current scope.

        Args:
            tags: Dictionary of tags to set.
        """
        if _client is None:
            import warnings

            warnings.warn("Statly SDK not initialized. Call Statly.init() first.", UserWarning)
            return
        _client.set_tags(tags)

    @staticmethod
    def add_breadcrumb(
        message: str,
        category: str | None = None,
        level: str = "info",
        data: dict | None = None,
        type: str = "default",
    ) -> None:
        """
        Add a breadcrumb to the current scope.

        Args:
            message: Breadcrumb message.
            category: Breadcrumb category.
            level: Breadcrumb level.
            data: Additional data.
            type: Breadcrumb type.
        """
        if _client is None:
            import warnings

            warnings.warn("Statly SDK not initialized. Call Statly.init() first.", UserWarning)
            return
        _client.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data,
            type=type,
        )

    @staticmethod
    def flush(timeout: float | None = None) -> None:
        """
        Flush pending events to Statly.

        Args:
            timeout: Maximum time to wait for flush (in seconds).
        """
        if _client is None:
            return
        _client.flush(timeout)

    @staticmethod
    def close(timeout: float | None = None) -> None:
        """
        Close the SDK and flush pending events.

        Args:
            timeout: Maximum time to wait for flush (in seconds).
        """
        global _client
        if _client is None:
            return
        _client.close(timeout)
        _client = None

    @staticmethod
    def get_client() -> StatlyClient | None:
        """Get the current client instance."""
        return _client


# Convenience aliases for module-level access
def init(*args, **kwargs) -> None:
    """Initialize the Statly SDK. See Statly.init() for details."""
    Statly.init(*args, **kwargs)


def capture_exception(*args, **kwargs) -> str:
    """Capture an exception. See Statly.capture_exception() for details."""
    return Statly.capture_exception(*args, **kwargs)


def capture_message(*args, **kwargs) -> str:
    """Capture a message. See Statly.capture_message() for details."""
    return Statly.capture_message(*args, **kwargs)


def set_user(*args, **kwargs) -> None:
    """Set user context. See Statly.set_user() for details."""
    Statly.set_user(*args, **kwargs)


def set_tag(*args, **kwargs) -> None:
    """Set a tag. See Statly.set_tag() for details."""
    Statly.set_tag(*args, **kwargs)


def set_tags(*args, **kwargs) -> None:
    """Set multiple tags. See Statly.set_tags() for details."""
    Statly.set_tags(*args, **kwargs)


def add_breadcrumb(*args, **kwargs) -> None:
    """Add a breadcrumb. See Statly.add_breadcrumb() for details."""
    Statly.add_breadcrumb(*args, **kwargs)


def flush(*args, **kwargs) -> None:
    """Flush pending events. See Statly.flush() for details."""
    Statly.flush(*args, **kwargs)


def close(*args, **kwargs) -> None:
    """Close the SDK. See Statly.close() for details."""
    Statly.close(*args, **kwargs)
