"""
Event module for Statly Observe SDK.

Handles event creation and serialization for error tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid
import sys
import platform
import traceback


class EventLevel(str, Enum):
    """Event severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


@dataclass
class StackFrame:
    """Represents a single frame in a stack trace."""

    filename: str
    function: str
    lineno: int | None = None
    colno: int | None = None
    abs_path: str | None = None
    context_line: str | None = None
    pre_context: list[str] | None = None
    post_context: list[str] | None = None
    in_app: bool = True
    vars: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result: dict[str, Any] = {
            "filename": self.filename,
            "function": self.function,
            "in_app": self.in_app,
        }
        if self.lineno is not None:
            result["lineno"] = self.lineno
        if self.colno is not None:
            result["colno"] = self.colno
        if self.abs_path is not None:
            result["abs_path"] = self.abs_path
        if self.context_line is not None:
            result["context_line"] = self.context_line
        if self.pre_context is not None:
            result["pre_context"] = self.pre_context
        if self.post_context is not None:
            result["post_context"] = self.post_context
        if self.vars is not None:
            result["vars"] = self.vars
        return result


@dataclass
class ExceptionInfo:
    """Represents an exception with its stack trace."""

    type: str
    value: str
    module: str | None = None
    stacktrace: list[StackFrame] = field(default_factory=list)
    mechanism: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        result: dict[str, Any] = {
            "type": self.type,
            "value": self.value,
            "stacktrace": {"frames": [f.to_dict() for f in self.stacktrace]},
        }
        if self.module is not None:
            result["module"] = self.module
        if self.mechanism is not None:
            result["mechanism"] = self.mechanism
        return result


@dataclass
class Event:
    """Represents a Statly event."""

    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    level: EventLevel = EventLevel.ERROR
    platform: str = "python"

    # Message
    message: str | None = None

    # Exception
    exception: list[ExceptionInfo] = field(default_factory=list)

    # Context
    contexts: dict[str, Any] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    # User
    user: dict[str, Any] | None = None

    # Breadcrumbs
    breadcrumbs: list[dict[str, Any]] = field(default_factory=list)

    # SDK info
    sdk: dict[str, Any] = field(
        default_factory=lambda: {
            "name": "statly-observe-python",
            "version": "0.1.0",
        }
    )

    # Environment
    environment: str | None = None
    release: str | None = None
    server_name: str | None = None

    # Request context (for web frameworks)
    request: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization."""
        result: dict[str, Any] = {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value if isinstance(self.level, EventLevel) else self.level,
            "platform": self.platform,
            "sdk": self.sdk,
        }

        if self.message:
            result["message"] = self.message

        if self.exception:
            result["exception"] = {"values": [e.to_dict() for e in self.exception]}

        if self.contexts:
            result["contexts"] = self.contexts

        if self.tags:
            result["tags"] = self.tags

        if self.extra:
            result["extra"] = self.extra

        if self.user:
            result["user"] = self.user

        if self.breadcrumbs:
            result["breadcrumbs"] = {"values": self.breadcrumbs}

        if self.environment:
            result["environment"] = self.environment

        if self.release:
            result["release"] = self.release

        if self.server_name:
            result["server_name"] = self.server_name

        if self.request:
            result["request"] = self.request

        return result


def extract_exception_info(exc: BaseException, tb: Any = None) -> ExceptionInfo:
    """
    Extract exception information from an exception object.

    Args:
        exc: The exception to extract info from.
        tb: Optional traceback object.

    Returns:
        ExceptionInfo object with stack trace.
    """
    if tb is None:
        tb = exc.__traceback__

    frames: list[StackFrame] = []

    if tb is not None:
        for frame_info in traceback.extract_tb(tb):
            frames.append(
                StackFrame(
                    filename=frame_info.filename,
                    function=frame_info.name,
                    lineno=frame_info.lineno,
                    context_line=frame_info.line,
                    abs_path=frame_info.filename,
                )
            )

    return ExceptionInfo(
        type=type(exc).__name__,
        value=str(exc),
        module=type(exc).__module__,
        stacktrace=frames,
        mechanism={"type": "generic", "handled": True},
    )


def get_runtime_context() -> dict[str, Any]:
    """Get Python runtime context information."""
    return {
        "runtime": {
            "name": "Python",
            "version": platform.python_version(),
            "build": platform.python_build()[0],
        },
        "os": {
            "name": platform.system(),
            "version": platform.release(),
            "build": platform.version(),
        },
        "device": {
            "arch": platform.machine(),
            "processor": platform.processor(),
        },
    }
