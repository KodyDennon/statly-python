"""
Tests for Statly Observe Python SDK client.
"""

import pytest
from unittest.mock import Mock, patch

from statly_observe import Statly, StatlyClient
from statly_observe.event import Event, EventLevel, extract_exception_info
from statly_observe.scope import Scope
from statly_observe.transport import Transport


class MockTransport(Transport):
    """Mock transport for testing."""

    def __init__(self):
        self.events = []
        self.flushed = False
        self.closed = False

    def send(self, event):
        self.events.append(event)
        return True

    def flush(self, timeout=None):
        self.flushed = True

    def close(self, timeout=None):
        self.closed = True


class TestStatlyClient:
    """Tests for StatlyClient."""

    def test_init_creates_client(self):
        """Test client initialization."""
        transport = MockTransport()
        client = StatlyClient(
            dsn="https://sk_test_xxx@statly.live/test",
            environment="test",
            release="1.0.0",
            transport=transport,
        )

        assert client.dsn == "https://sk_test_xxx@statly.live/test"
        assert client.environment == "test"
        assert client.release == "1.0.0"

    def test_capture_exception(self):
        """Test capturing an exception."""
        transport = MockTransport()
        client = StatlyClient(
            dsn="https://sk_test_xxx@statly.live/test",
            transport=transport,
        )

        try:
            raise ValueError("Test error")
        except ValueError as e:
            event_id = client.capture_exception(e)

        assert event_id != ""
        assert len(transport.events) == 1
        assert transport.events[0]["level"] == "error"
        assert len(transport.events[0]["exception"]["values"]) == 1

    def test_capture_message(self):
        """Test capturing a message."""
        transport = MockTransport()
        client = StatlyClient(
            dsn="https://sk_test_xxx@statly.live/test",
            transport=transport,
        )

        event_id = client.capture_message("Test message", level="warning")

        assert event_id != ""
        assert len(transport.events) == 1
        assert transport.events[0]["message"] == "Test message"
        assert transport.events[0]["level"] == "warning"

    def test_set_user(self):
        """Test setting user context."""
        transport = MockTransport()
        client = StatlyClient(
            dsn="https://sk_test_xxx@statly.live/test",
            transport=transport,
        )

        client.set_user(id="user-123", email="test@example.com")
        client.capture_message("Test")

        assert len(transport.events) == 1
        assert transport.events[0]["user"]["id"] == "user-123"
        assert transport.events[0]["user"]["email"] == "test@example.com"

    def test_set_tags(self):
        """Test setting tags."""
        transport = MockTransport()
        client = StatlyClient(
            dsn="https://sk_test_xxx@statly.live/test",
            transport=transport,
        )

        client.set_tag("key", "value")
        client.set_tags({"foo": "bar", "baz": "qux"})
        client.capture_message("Test")

        assert len(transport.events) == 1
        assert transport.events[0]["tags"]["key"] == "value"
        assert transport.events[0]["tags"]["foo"] == "bar"
        assert transport.events[0]["tags"]["baz"] == "qux"

    def test_add_breadcrumb(self):
        """Test adding breadcrumbs."""
        transport = MockTransport()
        client = StatlyClient(
            dsn="https://sk_test_xxx@statly.live/test",
            transport=transport,
        )

        client.add_breadcrumb(
            message="Test breadcrumb",
            category="test",
            level="info",
            data={"key": "value"},
        )
        client.capture_message("Test")

        assert len(transport.events) == 1
        breadcrumbs = transport.events[0]["breadcrumbs"]["values"]
        assert len(breadcrumbs) == 1
        assert breadcrumbs[0]["message"] == "Test breadcrumb"
        assert breadcrumbs[0]["category"] == "test"

    def test_sample_rate(self):
        """Test sample rate filtering."""
        transport = MockTransport()
        client = StatlyClient(
            dsn="https://sk_test_xxx@statly.live/test",
            sample_rate=0.0,  # Drop all events
            transport=transport,
        )

        client.capture_message("Test")

        assert len(transport.events) == 0

    def test_before_send_callback(self):
        """Test before_send callback."""
        transport = MockTransport()

        def before_send(event):
            event["tags"]["custom"] = "added"
            return event

        client = StatlyClient(
            dsn="https://sk_test_xxx@statly.live/test",
            before_send=before_send,
            transport=transport,
        )

        client.capture_message("Test")

        assert len(transport.events) == 1
        assert transport.events[0]["tags"]["custom"] == "added"

    def test_before_send_drop_event(self):
        """Test dropping events with before_send."""
        transport = MockTransport()

        def before_send(event):
            return None  # Drop all events

        client = StatlyClient(
            dsn="https://sk_test_xxx@statly.live/test",
            before_send=before_send,
            transport=transport,
        )

        client.capture_message("Test")

        assert len(transport.events) == 0

    def test_flush(self):
        """Test flushing events."""
        transport = MockTransport()
        client = StatlyClient(
            dsn="https://sk_test_xxx@statly.live/test",
            transport=transport,
        )

        client.flush()

        assert transport.flushed

    def test_close(self):
        """Test closing client."""
        transport = MockTransport()
        client = StatlyClient(
            dsn="https://sk_test_xxx@statly.live/test",
            transport=transport,
        )

        client.close()

        assert transport.closed


class TestEvent:
    """Tests for Event class."""

    def test_event_creation(self):
        """Test event creation."""
        event = Event(
            level=EventLevel.ERROR,
            message="Test error",
            environment="production",
        )

        assert event.event_id is not None
        assert event.level == EventLevel.ERROR
        assert event.message == "Test error"
        assert event.environment == "production"

    def test_event_to_dict(self):
        """Test event serialization."""
        event = Event(
            level=EventLevel.WARNING,
            message="Test warning",
            tags={"key": "value"},
        )

        data = event.to_dict()

        assert data["event_id"] == event.event_id
        assert data["level"] == "warning"
        assert data["message"] == "Test warning"
        assert data["tags"]["key"] == "value"


class TestExceptionExtraction:
    """Tests for exception extraction."""

    def test_extract_exception_info(self):
        """Test extracting exception information."""
        try:
            raise ValueError("Test error")
        except ValueError as e:
            info = extract_exception_info(e)

        assert info.type == "ValueError"
        assert info.value == "Test error"
        assert info.module == "builtins"
        assert len(info.stacktrace) > 0

    def test_exception_to_dict(self):
        """Test exception serialization."""
        try:
            raise RuntimeError("Runtime error")
        except RuntimeError as e:
            info = extract_exception_info(e)

        data = info.to_dict()

        assert data["type"] == "RuntimeError"
        assert data["value"] == "Runtime error"
        assert "stacktrace" in data
        assert "frames" in data["stacktrace"]


class TestScope:
    """Tests for Scope class."""

    def test_scope_creation(self):
        """Test scope creation."""
        scope = Scope()

        assert scope.user is None
        assert scope.tags == {}
        assert scope.breadcrumbs == []

    def test_scope_set_user(self):
        """Test setting user on scope."""
        scope = Scope()
        scope.set_user(id="123", email="test@example.com")

        assert scope.user["id"] == "123"
        assert scope.user["email"] == "test@example.com"

    def test_scope_set_tags(self):
        """Test setting tags on scope."""
        scope = Scope()
        scope.set_tag("key", "value")
        scope.set_tags({"foo": "bar"})

        assert scope.tags["key"] == "value"
        assert scope.tags["foo"] == "bar"

    def test_scope_add_breadcrumb(self):
        """Test adding breadcrumbs to scope."""
        scope = Scope()
        scope.add_breadcrumb(message="Test", category="test")

        assert len(scope.breadcrumbs) == 1
        assert scope.breadcrumbs[0]["message"] == "Test"
        assert scope.breadcrumbs[0]["category"] == "test"

    def test_scope_max_breadcrumbs(self):
        """Test breadcrumb limit."""
        scope = Scope(max_breadcrumbs=5)

        for i in range(10):
            scope.add_breadcrumb(message=f"Breadcrumb {i}")

        assert len(scope.breadcrumbs) == 5
        assert scope.breadcrumbs[0]["message"] == "Breadcrumb 5"

    def test_scope_clone(self):
        """Test scope cloning."""
        scope = Scope()
        scope.set_user(id="123")
        scope.set_tag("key", "value")

        cloned = scope.clone()

        assert cloned.user["id"] == "123"
        assert cloned.tags["key"] == "value"
        assert cloned is not scope

    def test_scope_clear(self):
        """Test clearing scope."""
        scope = Scope()
        scope.set_user(id="123")
        scope.set_tag("key", "value")
        scope.add_breadcrumb(message="Test")

        scope.clear()

        assert scope.user is None
        assert scope.tags == {}
        assert scope.breadcrumbs == []
