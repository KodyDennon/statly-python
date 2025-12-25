"""
Framework integrations for Statly Observe SDK.

Provides middleware and integrations for popular Python web frameworks.
"""

from .wsgi import StatlyWSGIMiddleware
from .asgi import StatlyASGIMiddleware
from .flask import StatlyFlask, init_flask
from .django import StatlyDjangoMiddleware, init_django
from .fastapi import StatlyFastAPI, init_fastapi

__all__ = [
    "StatlyWSGIMiddleware",
    "StatlyASGIMiddleware",
    "StatlyFlask",
    "init_flask",
    "StatlyDjangoMiddleware",
    "init_django",
    "StatlyFastAPI",
    "init_fastapi",
]
