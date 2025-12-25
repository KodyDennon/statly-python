# Statly Observe SDK for Python

Error tracking and monitoring for Python applications.

## Installation

```bash
pip install statly-observe
```

For framework-specific integrations:

```bash
pip install statly-observe[flask]     # Flask
pip install statly-observe[django]    # Django
pip install statly-observe[fastapi]   # FastAPI
```

## Quick Start

```python
from statly_observe import Statly

# Initialize the SDK
Statly.init(
    dsn="https://observe.statly.live/your-org",
    environment="production",
    release="1.0.0",
)

# Errors are captured automatically

# Manual capture
try:
    risky_operation()
except Exception as e:
    Statly.capture_exception(e)

# Capture a message
Statly.capture_message("Something happened", level="warning")

# Set user context
Statly.set_user(id="user-123", email="user@example.com")

# Add breadcrumb
Statly.add_breadcrumb(
    message="User clicked button",
    category="ui",
    level="info",
)

# Flush and close before exit
Statly.close()
```

## Flask Integration

```python
from flask import Flask
from statly_observe import Statly
from statly_observe.integrations import init_flask

app = Flask(__name__)

Statly.init(dsn="...")
init_flask(app)

@app.route("/")
def index():
    return "Hello World"
```

## Django Integration

```python
# settings.py
MIDDLEWARE = [
    'statly_observe.integrations.django.StatlyDjangoMiddleware',
    # ... other middleware
]

# wsgi.py or manage.py
from statly_observe import Statly
Statly.init(dsn="...")
```

## FastAPI Integration

```python
from fastapi import FastAPI
from statly_observe import Statly
from statly_observe.integrations import init_fastapi

app = FastAPI()

Statly.init(dsn="...")
init_fastapi(app)

@app.get("/")
async def root():
    return {"message": "Hello World"}
```

## Configuration

### Statly.init() Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `dsn` | `str` | Required | Data Source Name for your project |
| `environment` | `str` | `None` | Environment name (production, staging, etc.) |
| `release` | `str` | `None` | Release version of your application |
| `debug` | `bool` | `False` | Enable debug logging |
| `sample_rate` | `float` | `1.0` | Sample rate for events (0.0 to 1.0) |
| `max_breadcrumbs` | `int` | `100` | Maximum breadcrumbs to store |
| `before_send` | `callable` | `None` | Callback to modify/filter events |

### Before Send Callback

```python
def before_send(event):
    # Remove sensitive data
    if "password" in str(event.get("extra", {})):
        return None  # Drop the event
    return event

Statly.init(dsn="...", before_send=before_send)
```

## Breadcrumbs

Breadcrumbs are a trail of events that led up to an error:

```python
# Default breadcrumb
Statly.add_breadcrumb(message="User logged in")

# With category and data
Statly.add_breadcrumb(
    message="Database query",
    category="query",
    level="info",
    data={"query": "SELECT * FROM users", "duration_ms": 15},
)
```

## User Context

```python
Statly.set_user(
    id="user-123",
    email="user@example.com",
    username="johndoe",
    ip_address="192.168.1.1",  # Additional fields
)
```

## Tags

```python
# Single tag
Statly.set_tag("version", "1.0.0")

# Multiple tags
Statly.set_tags({
    "environment": "production",
    "server": "web-1",
})
```

## WSGI/ASGI Middleware

For generic WSGI/ASGI applications:

```python
from statly_observe import Statly
from statly_observe.integrations import StatlyWSGIMiddleware, StatlyASGIMiddleware

# WSGI
Statly.init(dsn="...")
app = StatlyWSGIMiddleware(your_wsgi_app)

# ASGI
Statly.init(dsn="...")
app = StatlyASGIMiddleware(your_asgi_app)
```

## License

MIT
