"""
Breadcrumb module for Statly Observe SDK.

Breadcrumbs are trail of events that led up to an error.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class BreadcrumbType(str, Enum):
    """Types of breadcrumbs."""

    DEFAULT = "default"
    DEBUG = "debug"
    ERROR = "error"
    NAVIGATION = "navigation"
    HTTP = "http"
    INFO = "info"
    QUERY = "query"
    TRANSACTION = "transaction"
    UI = "ui"
    USER = "user"


@dataclass
class Breadcrumb:
    """
    Represents a breadcrumb - a trail event leading up to an error.
    """

    message: str
    category: str | None = None
    level: str = "info"
    type: str = "default"
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert breadcrumb to dictionary for serialization."""
        result: dict[str, Any] = {
            "message": self.message,
            "level": self.level,
            "type": self.type,
            "timestamp": self.timestamp.isoformat(),
        }

        if self.category:
            result["category"] = self.category

        if self.data:
            result["data"] = self.data

        return result


def create_http_breadcrumb(
    url: str,
    method: str = "GET",
    status_code: int | None = None,
    reason: str | None = None,
) -> Breadcrumb:
    """
    Create an HTTP request breadcrumb.

    Args:
        url: The request URL.
        method: HTTP method.
        status_code: Response status code.
        reason: Response reason phrase.

    Returns:
        HTTP breadcrumb.
    """
    data: dict[str, Any] = {
        "url": url,
        "method": method,
    }

    if status_code is not None:
        data["status_code"] = status_code
    if reason is not None:
        data["reason"] = reason

    level = "info"
    if status_code and status_code >= 400:
        level = "error" if status_code >= 500 else "warning"

    return Breadcrumb(
        message=f"{method} {url}",
        category="http",
        level=level,
        type=BreadcrumbType.HTTP.value,
        data=data,
    )


def create_query_breadcrumb(
    query: str,
    duration_ms: float | None = None,
    params: dict | None = None,
) -> Breadcrumb:
    """
    Create a database query breadcrumb.

    Args:
        query: The SQL query (sanitized).
        duration_ms: Query duration in milliseconds.
        params: Query parameters (sanitized).

    Returns:
        Query breadcrumb.
    """
    data: dict[str, Any] = {"query": query}

    if duration_ms is not None:
        data["duration_ms"] = duration_ms
    if params is not None:
        data["params"] = params

    return Breadcrumb(
        message=query[:100] + "..." if len(query) > 100 else query,
        category="query",
        level="info",
        type=BreadcrumbType.QUERY.value,
        data=data,
    )


def create_navigation_breadcrumb(
    from_url: str,
    to_url: str,
) -> Breadcrumb:
    """
    Create a navigation breadcrumb.

    Args:
        from_url: Previous URL.
        to_url: New URL.

    Returns:
        Navigation breadcrumb.
    """
    return Breadcrumb(
        message=f"Navigate to {to_url}",
        category="navigation",
        level="info",
        type=BreadcrumbType.NAVIGATION.value,
        data={
            "from": from_url,
            "to": to_url,
        },
    )


def create_ui_breadcrumb(
    action: str,
    element: str | None = None,
    category: str = "ui",
) -> Breadcrumb:
    """
    Create a UI interaction breadcrumb.

    Args:
        action: The UI action (e.g., "click", "input").
        element: The element interacted with.
        category: Breadcrumb category.

    Returns:
        UI breadcrumb.
    """
    data: dict[str, Any] = {"action": action}
    if element:
        data["element"] = element

    return Breadcrumb(
        message=f"{action} on {element}" if element else action,
        category=category,
        level="info",
        type=BreadcrumbType.UI.value,
        data=data,
    )
