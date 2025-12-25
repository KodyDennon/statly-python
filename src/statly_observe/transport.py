"""
Transport module for Statly Observe SDK.

Handles sending events to the Statly backend with retry and batching support.
"""

import json
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from queue import Queue, Empty
from typing import Any
import logging

import requests

logger = logging.getLogger("statly_observe")


class Transport(ABC):
    """Abstract base class for event transports."""

    @abstractmethod
    def send(self, event: dict[str, Any]) -> bool:
        """
        Send an event to Statly.

        Args:
            event: The event dictionary to send.

        Returns:
            True if the event was sent successfully.
        """
        pass

    @abstractmethod
    def flush(self, timeout: float | None = None) -> None:
        """
        Flush pending events.

        Args:
            timeout: Maximum time to wait for flush.
        """
        pass

    @abstractmethod
    def close(self, timeout: float | None = None) -> None:
        """
        Close the transport.

        Args:
            timeout: Maximum time to wait for shutdown.
        """
        pass


@dataclass
class TransportOptions:
    """Configuration options for the transport."""

    dsn: str
    timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 1.0
    batch_size: int = 10
    flush_interval: float = 5.0
    debug: bool = False


class HttpTransport(Transport):
    """
    HTTP transport with retry and batching support.
    """

    def __init__(self, options: TransportOptions):
        self.options = options
        self.endpoint = self._parse_dsn(options.dsn)
        self._queue: Queue[dict[str, Any]] = Queue()
        self._shutdown = threading.Event()
        self._worker: threading.Thread | None = None
        self._lock = threading.Lock()
        self._pending_count = 0

        # Start the background worker
        self._start_worker()

    def _parse_dsn(self, dsn: str) -> str:
        """
        Parse DSN and return the endpoint URL.

        Args:
            dsn: The Data Source Name.

        Returns:
            The API endpoint URL.
        """
        # DSN format: https://observe.statly.live/org-slug
        # or https://observe.statly.live/org-slug/project-id
        if not dsn:
            raise ValueError("DSN is required")

        # Ensure DSN has /api/v1/events suffix
        base_url = dsn.rstrip("/")
        if not base_url.endswith("/api/v1/events"):
            base_url = f"{base_url}/api/v1/events"

        return base_url

    def _start_worker(self) -> None:
        """Start the background worker thread."""
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def _worker_loop(self) -> None:
        """Background worker that sends batched events."""
        batch: list[dict[str, Any]] = []
        last_flush = time.time()

        while not self._shutdown.is_set():
            try:
                # Get events from the queue with timeout
                try:
                    event = self._queue.get(timeout=0.5)
                    batch.append(event)
                    self._queue.task_done()
                except Empty:
                    pass

                # Check if we should flush
                should_flush = (
                    len(batch) >= self.options.batch_size
                    or (batch and time.time() - last_flush >= self.options.flush_interval)
                )

                if should_flush and batch:
                    self._send_batch(batch)
                    with self._lock:
                        self._pending_count -= len(batch)
                    batch = []
                    last_flush = time.time()

            except Exception as e:
                logger.exception(f"Error in transport worker: {e}")

        # Flush remaining events on shutdown
        if batch:
            self._send_batch(batch)
            with self._lock:
                self._pending_count -= len(batch)

    def _send_batch(self, batch: list[dict[str, Any]]) -> bool:
        """
        Send a batch of events.

        Args:
            batch: List of events to send.

        Returns:
            True if all events were sent successfully.
        """
        if not batch:
            return True

        for attempt in range(self.options.max_retries):
            try:
                response = requests.post(
                    self.endpoint,
                    json={"events": batch},
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "statly-observe-python/0.1.0",
                    },
                    timeout=self.options.timeout,
                )

                if response.status_code == 200 or response.status_code == 202:
                    if self.options.debug:
                        logger.debug(f"Sent {len(batch)} events successfully")
                    return True

                # Retry on 5xx errors
                if response.status_code >= 500:
                    logger.warning(
                        f"Server error {response.status_code}, attempt {attempt + 1}/{self.options.max_retries}"
                    )
                    time.sleep(self.options.retry_delay * (2**attempt))
                    continue

                # Don't retry on 4xx errors
                logger.error(f"Client error {response.status_code}: {response.text}")
                return False

            except requests.RequestException as e:
                logger.warning(f"Request failed, attempt {attempt + 1}/{self.options.max_retries}: {e}")
                time.sleep(self.options.retry_delay * (2**attempt))

        logger.error(f"Failed to send {len(batch)} events after {self.options.max_retries} retries")
        return False

    def send(self, event: dict[str, Any]) -> bool:
        """
        Queue an event for sending.

        Args:
            event: The event dictionary to send.

        Returns:
            True if the event was queued successfully.
        """
        if self._shutdown.is_set():
            logger.warning("Transport is shutting down, event dropped")
            return False

        self._queue.put(event)
        with self._lock:
            self._pending_count += 1

        if self.options.debug:
            logger.debug(f"Event queued: {event.get('event_id')}")

        return True

    def flush(self, timeout: float | None = None) -> None:
        """
        Flush pending events.

        Args:
            timeout: Maximum time to wait for flush.
        """
        if timeout is None:
            timeout = 10.0

        start = time.time()
        while time.time() - start < timeout:
            with self._lock:
                if self._pending_count == 0:
                    return
            time.sleep(0.1)

        logger.warning(f"Flush timeout, {self._pending_count} events may be pending")

    def close(self, timeout: float | None = None) -> None:
        """
        Close the transport.

        Args:
            timeout: Maximum time to wait for shutdown.
        """
        if timeout is None:
            timeout = 5.0

        self._shutdown.set()
        if self._worker is not None:
            self._worker.join(timeout=timeout)

        if self.options.debug:
            logger.debug("Transport closed")


class SyncTransport(Transport):
    """
    Synchronous transport that sends events immediately.

    Useful for testing or when you need guaranteed delivery before continuing.
    """

    def __init__(self, options: TransportOptions):
        self.options = options
        self.endpoint = self._parse_dsn(options.dsn)

    def _parse_dsn(self, dsn: str) -> str:
        """Parse DSN and return the endpoint URL."""
        base_url = dsn.rstrip("/")
        if not base_url.endswith("/api/v1/events"):
            base_url = f"{base_url}/api/v1/events"
        return base_url

    def send(self, event: dict[str, Any]) -> bool:
        """Send an event synchronously."""
        for attempt in range(self.options.max_retries):
            try:
                response = requests.post(
                    self.endpoint,
                    json=event,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "statly-observe-python/0.1.0",
                    },
                    timeout=self.options.timeout,
                )

                if response.status_code == 200 or response.status_code == 202:
                    return True

                if response.status_code >= 500:
                    time.sleep(self.options.retry_delay * (2**attempt))
                    continue

                return False

            except requests.RequestException:
                time.sleep(self.options.retry_delay * (2**attempt))

        return False

    def flush(self, timeout: float | None = None) -> None:
        """No-op for sync transport."""
        pass

    def close(self, timeout: float | None = None) -> None:
        """No-op for sync transport."""
        pass
