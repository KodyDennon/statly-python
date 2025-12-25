"""
Client module for Statly Observe SDK.

The main client class that handles event capture and management.
"""

import sys
import socket
import random
import logging
from typing import Any, Callable

from .event import Event, EventLevel, extract_exception_info, get_runtime_context
from .scope import Scope, ScopeManager
from .transport import Transport, HttpTransport, TransportOptions

logger = logging.getLogger("statly_observe")


class StatlyClient:
    """
    Main client for capturing and sending events to Statly.
    """

    def __init__(
        self,
        dsn: str,
        environment: str | None = None,
        release: str | None = None,
        debug: bool = False,
        sample_rate: float = 1.0,
        max_breadcrumbs: int = 100,
        before_send: Callable[[dict[str, Any]], dict[str, Any] | None] | None = None,
        transport: Transport | None = None,
    ):
        """
        Initialize the Statly client.

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
        self.dsn = dsn
        self.environment = environment
        self.release = release
        self.debug = debug
        self.sample_rate = sample_rate
        self.max_breadcrumbs = max_breadcrumbs
        self.before_send = before_send

        # Set up logging
        if debug:
            logging.basicConfig(level=logging.DEBUG)
            logger.setLevel(logging.DEBUG)

        # Initialize transport
        if transport is not None:
            self.transport = transport
        else:
            self.transport = HttpTransport(
                TransportOptions(
                    dsn=dsn,
                    debug=debug,
                )
            )

        # Initialize scope manager
        self.scope_manager = ScopeManager(max_breadcrumbs=max_breadcrumbs)

        # Original excepthook
        self._original_excepthook: Callable | None = None

        # Server name
        try:
            self._server_name = socket.gethostname()
        except Exception:
            self._server_name = None

    def install_excepthook(self) -> None:
        """Install the global exception hook to capture uncaught exceptions."""
        self._original_excepthook = sys.excepthook

        def excepthook(exc_type, exc_value, exc_tb):
            self.capture_exception(exc_value)
            if self._original_excepthook is not None:
                self._original_excepthook(exc_type, exc_value, exc_tb)

        sys.excepthook = excepthook

        if self.debug:
            logger.debug("Installed global exception hook")

    def uninstall_excepthook(self) -> None:
        """Uninstall the global exception hook."""
        if self._original_excepthook is not None:
            sys.excepthook = self._original_excepthook
            self._original_excepthook = None

    def capture_exception(
        self,
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
        # Sample rate check
        if random.random() > self.sample_rate:
            return ""

        # Get exception info
        if exception is None:
            exc_info = sys.exc_info()
            if exc_info[1] is None:
                logger.warning("No exception to capture")
                return ""
            exception = exc_info[1]
            tb = exc_info[2]
        else:
            tb = exception.__traceback__

        # Build event
        event = Event(
            level=EventLevel.ERROR,
            exception=[extract_exception_info(exception, tb)],
            environment=self.environment,
            release=self.release,
            server_name=self._server_name,
            contexts=get_runtime_context(),
        )

        # Add context if provided
        if context:
            event.extra.update(context)

        # Apply scope
        scope = self.scope_manager.get_current()
        scope.apply_to_event(event)

        # Send event
        return self._send_event(event)

    def capture_message(
        self,
        message: str,
        level: str = "info",
        context: dict | None = None,
    ) -> str:
        """
        Capture a message and send it to Statly.

        Args:
            message: The message to capture.
            level: The severity level.
            context: Additional context to attach to the event.

        Returns:
            The event ID if captured, empty string otherwise.
        """
        # Sample rate check
        if random.random() > self.sample_rate:
            return ""

        # Map level string to EventLevel
        level_map = {
            "debug": EventLevel.DEBUG,
            "info": EventLevel.INFO,
            "warning": EventLevel.WARNING,
            "error": EventLevel.ERROR,
            "fatal": EventLevel.FATAL,
        }
        event_level = level_map.get(level.lower(), EventLevel.INFO)

        # Build event
        event = Event(
            level=event_level,
            message=message,
            environment=self.environment,
            release=self.release,
            server_name=self._server_name,
            contexts=get_runtime_context(),
        )

        # Add context if provided
        if context:
            event.extra.update(context)

        # Apply scope
        scope = self.scope_manager.get_current()
        scope.apply_to_event(event)

        # Send event
        return self._send_event(event)

    def _send_event(self, event: Event) -> str:
        """
        Send an event to Statly.

        Args:
            event: The event to send.

        Returns:
            The event ID if sent, empty string otherwise.
        """
        event_dict = event.to_dict()

        # Apply before_send callback
        if self.before_send is not None:
            try:
                event_dict = self.before_send(event_dict)
                if event_dict is None:
                    if self.debug:
                        logger.debug("Event dropped by before_send callback")
                    return ""
            except Exception as e:
                logger.exception(f"Error in before_send callback: {e}")

        # Send via transport
        if self.transport.send(event_dict):
            if self.debug:
                logger.debug(f"Event sent: {event.event_id}")
            return event.event_id

        return ""

    def set_user(
        self,
        id: str | None = None,
        email: str | None = None,
        username: str | None = None,
        **kwargs,
    ) -> None:
        """Set the current user context."""
        scope = self.scope_manager.get_current()
        scope.set_user(id=id, email=email, username=username, **kwargs)

    def set_tag(self, key: str, value: str) -> None:
        """Set a tag on the current scope."""
        scope = self.scope_manager.get_current()
        scope.set_tag(key, value)

    def set_tags(self, tags: dict[str, str]) -> None:
        """Set multiple tags on the current scope."""
        scope = self.scope_manager.get_current()
        scope.set_tags(tags)

    def add_breadcrumb(
        self,
        message: str,
        category: str | None = None,
        level: str = "info",
        data: dict | None = None,
        type: str = "default",
    ) -> None:
        """Add a breadcrumb to the current scope."""
        scope = self.scope_manager.get_current()
        scope.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data,
            type=type,
        )

    def push_scope(self) -> Scope:
        """Push a new scope onto the stack."""
        return self.scope_manager.push_scope()

    def pop_scope(self) -> None:
        """Pop the current scope."""
        self.scope_manager.pop_scope()

    def configure_scope(self, callback: Callable[[Scope], None]) -> None:
        """Configure the current scope."""
        self.scope_manager.configure_scope(callback)

    def flush(self, timeout: float | None = None) -> None:
        """Flush pending events."""
        self.transport.flush(timeout)

    def close(self, timeout: float | None = None) -> None:
        """Close the client and flush pending events."""
        self.uninstall_excepthook()
        self.transport.close(timeout)
