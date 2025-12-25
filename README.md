# Statly Observe SDK for Python

[![PyPI version](https://img.shields.io/pypi/v/statly-observe.svg)](https://pypi.org/project/statly-observe/)
[![Python versions](https://img.shields.io/pypi/pyversions/statly-observe.svg)](https://pypi.org/project/statly-observe/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Error tracking and monitoring for Python applications. Capture exceptions, track releases, and debug issues faster.

## Features

- Automatic exception capturing with full stack traces
- Breadcrumbs for debugging context
- User context tracking
- Release tracking
- Framework integrations (Flask, Django, FastAPI)
- Async support
- Minimal overhead

## Installation

```bash
pip install statly-observe
```

With framework integrations:

```bash
pip install statly-observe[flask]     # Flask support
pip install statly-observe[django]    # Django support
pip install statly-observe[fastapi]   # FastAPI/Starlette support
pip install statly-observe[all]       # All integrations
```

## Getting Your DSN

1. Go to [statly.live/dashboard/observe/setup](https://statly.live/dashboard/observe/setup)
2. Create an API key for Observe
3. Copy your DSN (format: `https://<api-key>@statly.live/<org-slug>`)

## Quick Start

```python
from statly_observe import Statly

# Initialize the SDK
Statly.init(
    dsn="https://sk_live_xxx@statly.live/your-org",
    environment="production",
    release="1.0.0",
)

# Errors are captured automatically via sys.excepthook

# Manual capture
try:
    risky_operation()
except Exception as e:
    Statly.capture_exception(e)

# Capture a message
Statly.capture_message("User completed checkout", level="info")

# Set user context
Statly.set_user(
    id="user-123",
    email="user@example.com",
)

# Add breadcrumb for debugging
Statly.add_breadcrumb(
    message="User logged in",
    category="auth",
    level="info",
)

# Always close before exit
Statly.close()
```

## Framework Integrations

### Flask

```python
from flask import Flask
from statly_observe import Statly
from statly_observe.integrations.flask import init_flask

app = Flask(__name__)

# Initialize Statly
Statly.init(
    dsn="https://sk_live_xxx@statly.live/your-org",
    environment="production",
)

# Attach to Flask app
init_flask(app)

@app.route("/")
def index():
    return "Hello World"

@app.route("/error")
def error():
    raise ValueError("Test error")  # Automatically captured
```

### Django

**settings.py:**

```python
INSTALLED_APPS = [
    # ...
    'statly_observe.integrations.django',
]

MIDDLEWARE = [
    'statly_observe.integrations.django.StatlyMiddleware',
    # ... other middleware (Statly should be first)
]

# Statly configuration
STATLY_DSN = "https://sk_live_xxx@statly.live/your-org"
STATLY_ENVIRONMENT = "production"
STATLY_RELEASE = "1.0.0"
```

**wsgi.py or manage.py:**

```python
from statly_observe import Statly
from django.conf import settings

Statly.init(
    dsn=settings.STATLY_DSN,
    environment=settings.STATLY_ENVIRONMENT,
    release=settings.STATLY_RELEASE,
)
```

### FastAPI

```python
from fastapi import FastAPI
from statly_observe import Statly
from statly_observe.integrations.fastapi import init_fastapi

app = FastAPI()

# Initialize Statly
Statly.init(
    dsn="https://sk_live_xxx@statly.live/your-org",
    environment="production",
)

# Attach to FastAPI app
init_fastapi(app)

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/error")
async def error():
    raise ValueError("Test error")  # Automatically captured
```

### Generic WSGI/ASGI

```python
from statly_observe import Statly
from statly_observe.integrations.wsgi import StatlyWSGIMiddleware
from statly_observe.integrations.asgi import StatlyASGIMiddleware

Statly.init(dsn="https://sk_live_xxx@statly.live/your-org")

# WSGI
app = StatlyWSGIMiddleware(your_wsgi_app)

# ASGI
app = StatlyASGIMiddleware(your_asgi_app)
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `dsn` | `str` | **Required** | Your project's Data Source Name |
| `environment` | `str` | `None` | Environment name (production, staging, development) |
| `release` | `str` | `None` | Release/version identifier for tracking |
| `debug` | `bool` | `False` | Enable debug logging to stderr |
| `sample_rate` | `float` | `1.0` | Sample rate for events (0.0 to 1.0) |
| `max_breadcrumbs` | `int` | `100` | Maximum breadcrumbs to store |
| `before_send` | `callable` | `None` | Callback to modify/filter events before sending |

### before_send Example

```python
def before_send(event):
    # Filter out specific errors
    if "KeyboardInterrupt" in event.get("message", ""):
        return None  # Drop the event

    # Scrub sensitive data
    if "extra" in event and "password" in event["extra"]:
        del event["extra"]["password"]

    return event

Statly.init(
    dsn="...",
    before_send=before_send,
)
```

## API Reference

### Statly.capture_exception(exception, **context)

Capture an exception with optional additional context:

```python
try:
    process_payment(order)
except PaymentError as e:
    Statly.capture_exception(
        e,
        extra={
            "order_id": order.id,
            "amount": order.total,
        },
        tags={
            "payment_provider": "stripe",
        },
    )
```

### Statly.capture_message(message, level="info")

Capture a message event:

```python
Statly.capture_message("User signed up", level="info")
Statly.capture_message("Payment failed after 3 retries", level="warning")
Statly.capture_message("Database connection lost", level="error")
```

Levels: `"debug"` | `"info"` | `"warning"` | `"error"` | `"fatal"`

### Statly.set_user(**kwargs)

Set user context for all subsequent events:

```python
Statly.set_user(
    id="user-123",
    email="user@example.com",
    username="johndoe",
    # Custom fields
    subscription="premium",
)

# Clear user on logout
Statly.set_user(None)
```

### Statly.set_tag(key, value) / Statly.set_tags(tags)

Set tags for filtering and searching:

```python
Statly.set_tag("version", "1.0.0")

Statly.set_tags({
    "environment": "production",
    "server": "web-1",
    "region": "us-east-1",
})
```

### Statly.add_breadcrumb(**kwargs)

Add a breadcrumb for debugging context:

```python
Statly.add_breadcrumb(
    message="User clicked checkout button",
    category="ui.click",
    level="info",
    data={
        "button_id": "checkout-btn",
        "cart_items": 3,
    },
)
```

### Statly.flush() / Statly.close()

```python
# Flush pending events (keeps SDK running)
Statly.flush()

# Flush and close (use before process exit)
Statly.close()
```

## Context Manager

Use context manager for automatic cleanup:

```python
from statly_observe import Statly

with Statly.init(dsn="...") as client:
    # Your code here
    pass
# Automatically flushed and closed
```

## Async Support

The SDK automatically detects async contexts:

```python
import asyncio
from statly_observe import Statly

async def main():
    Statly.init(dsn="...")

    try:
        await risky_async_operation()
    except Exception as e:
        Statly.capture_exception(e)

    await Statly.flush_async()

asyncio.run(main())
```

## Logging Integration

Capture Python logging as breadcrumbs or events:

```python
import logging
from statly_observe import Statly
from statly_observe.integrations.logging import StatlyHandler

Statly.init(dsn="...")

# Add handler to capture logs as breadcrumbs
handler = StatlyHandler(level=logging.INFO)
logging.getLogger().addHandler(handler)

# Now logs are captured
logging.info("User logged in")  # Becomes a breadcrumb
logging.error("Database error")  # Captured as error event
```

## Requirements

- Python 3.8+
- Works with sync and async code

## License

MIT
