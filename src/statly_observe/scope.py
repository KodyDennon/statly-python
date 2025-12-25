"""
Scope module for Statly Observe SDK.

Manages contextual data that is attached to events.
"""

from dataclasses import dataclass, field
from typing import Any
from contextvars import ContextVar
from copy import deepcopy


@dataclass
class Scope:
    """
    Holds contextual information to be attached to events.

    Scopes can be layered to create context-specific overrides.
    """

    user: dict[str, Any] | None = None
    tags: dict[str, str] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)
    contexts: dict[str, Any] = field(default_factory=dict)
    breadcrumbs: list[dict[str, Any]] = field(default_factory=list)
    max_breadcrumbs: int = 100
    transaction_name: str | None = None
    fingerprint: list[str] | None = None

    def set_user(
        self,
        id: str | None = None,
        email: str | None = None,
        username: str | None = None,
        **kwargs,
    ) -> None:
        """
        Set the current user.

        Args:
            id: User ID.
            email: User email.
            username: Username.
            **kwargs: Additional user attributes.
        """
        user_data: dict[str, Any] = {}
        if id is not None:
            user_data["id"] = id
        if email is not None:
            user_data["email"] = email
        if username is not None:
            user_data["username"] = username
        user_data.update(kwargs)

        if user_data:
            self.user = user_data
        else:
            self.user = None

    def set_tag(self, key: str, value: str) -> None:
        """
        Set a tag.

        Args:
            key: Tag key.
            value: Tag value.
        """
        self.tags[key] = value

    def set_tags(self, tags: dict[str, str]) -> None:
        """
        Set multiple tags.

        Args:
            tags: Dictionary of tags.
        """
        self.tags.update(tags)

    def remove_tag(self, key: str) -> None:
        """
        Remove a tag.

        Args:
            key: Tag key to remove.
        """
        self.tags.pop(key, None)

    def set_extra(self, key: str, value: Any) -> None:
        """
        Set extra data.

        Args:
            key: Extra key.
            value: Extra value.
        """
        self.extra[key] = value

    def set_context(self, key: str, value: dict[str, Any]) -> None:
        """
        Set a context.

        Args:
            key: Context key.
            value: Context data.
        """
        self.contexts[key] = value

    def add_breadcrumb(
        self,
        message: str,
        category: str | None = None,
        level: str = "info",
        data: dict | None = None,
        type: str = "default",
        timestamp: str | None = None,
    ) -> None:
        """
        Add a breadcrumb.

        Args:
            message: Breadcrumb message.
            category: Breadcrumb category.
            level: Breadcrumb level.
            data: Additional data.
            type: Breadcrumb type.
            timestamp: ISO timestamp (auto-generated if not provided).
        """
        from datetime import datetime, timezone

        crumb: dict[str, Any] = {
            "message": message,
            "level": level,
            "type": type,
            "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        }

        if category is not None:
            crumb["category"] = category
        if data is not None:
            crumb["data"] = data

        self.breadcrumbs.append(crumb)

        # Trim breadcrumbs if we exceed the limit
        if len(self.breadcrumbs) > self.max_breadcrumbs:
            self.breadcrumbs = self.breadcrumbs[-self.max_breadcrumbs :]

    def clear_breadcrumbs(self) -> None:
        """Clear all breadcrumbs."""
        self.breadcrumbs.clear()

    def clear(self) -> None:
        """Clear all scope data."""
        self.user = None
        self.tags.clear()
        self.extra.clear()
        self.contexts.clear()
        self.breadcrumbs.clear()
        self.transaction_name = None
        self.fingerprint = None

    def clone(self) -> "Scope":
        """Create a deep copy of this scope."""
        return Scope(
            user=deepcopy(self.user),
            tags=deepcopy(self.tags),
            extra=deepcopy(self.extra),
            contexts=deepcopy(self.contexts),
            breadcrumbs=deepcopy(self.breadcrumbs),
            max_breadcrumbs=self.max_breadcrumbs,
            transaction_name=self.transaction_name,
            fingerprint=deepcopy(self.fingerprint),
        )

    def apply_to_event(self, event: "Event") -> "Event":
        """
        Apply this scope's data to an event.

        Args:
            event: The event to modify.

        Returns:
            The modified event.
        """
        from .event import Event

        if self.user:
            event.user = deepcopy(self.user)

        if self.tags:
            event.tags.update(self.tags)

        if self.extra:
            event.extra.update(self.extra)

        if self.contexts:
            event.contexts.update(self.contexts)

        if self.breadcrumbs:
            event.breadcrumbs.extend(deepcopy(self.breadcrumbs))

        return event


# Context variable for async context propagation
_scope_context: ContextVar[Scope | None] = ContextVar("statly_scope", default=None)


def get_current_scope() -> Scope | None:
    """Get the current scope from context."""
    return _scope_context.get()


def set_current_scope(scope: Scope) -> None:
    """Set the current scope in context."""
    _scope_context.set(scope)


class ScopeManager:
    """
    Manages scope lifecycle with context propagation support.
    """

    def __init__(self, max_breadcrumbs: int = 100):
        self.max_breadcrumbs = max_breadcrumbs
        self._global_scope = Scope(max_breadcrumbs=max_breadcrumbs)

    def get_current(self) -> Scope:
        """Get the current scope, falling back to global scope."""
        scope = get_current_scope()
        if scope is None:
            return self._global_scope
        return scope

    def get_global(self) -> Scope:
        """Get the global scope."""
        return self._global_scope

    def push_scope(self) -> Scope:
        """
        Push a new scope onto the stack.

        Returns:
            The new scope.
        """
        current = self.get_current()
        new_scope = current.clone()
        set_current_scope(new_scope)
        return new_scope

    def pop_scope(self) -> None:
        """Pop the current scope."""
        set_current_scope(None)

    def configure_scope(self, callback: callable) -> None:
        """
        Configure the current scope.

        Args:
            callback: Function that receives the scope to configure.
        """
        scope = self.get_current()
        callback(scope)
