"""Privacy-conscious structured request logs for only ``/api/kidquest/*``."""

from __future__ import annotations

import json
import logging
from time import perf_counter
import uuid


LOGGER = logging.getLogger("kidquest.requests")
LOGGER.setLevel(logging.INFO)
PREFIX = "/api/kidquest/"


class KidQuestRequestLoggingMiddleware:
    """ASGI middleware that leaves every non-KidQuest request completely untouched."""

    def __init__(self, app, *, content_version):
        self.app = app
        self.content_version = content_version

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or not (scope.get("path") or "").startswith(PREFIX):
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        started = perf_counter()
        status_code = 500
        chunks: list[bytes] = []

        async def logged_send(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message = {**message, "headers": [*message.get("headers", []), (b"x-request-id", request_id.encode())]}
            elif message["type"] == "http.response.body" and sum(map(len, chunks)) < 65_536:
                chunks.append(message.get("body", b""))
            await send(message)

        escaped = False
        try:
            await self.app(scope, receive, logged_send)
        except BaseException:
            escaped = True
            raise
        finally:
            error_code = None
            if status_code >= 400:
                try:
                    error_code = json.loads(b"".join(chunks)).get("error", {}).get("code")
                except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
                    pass
                error_code = error_code or ("INTERNAL_ERROR" if escaped else f"HTTP_{status_code}")
            route = scope.get("route")
            operation = getattr(route, "name", None) or "kidquest_not_found"
            record = {
                "operation": operation,
                "request_id": request_id,
                "content_version": self.content_version,
                "result": "success" if status_code < 400 else "error",
                "latency_ms": round((perf_counter() - started) * 1000, 3),
                "error_code": error_code,
            }
            LOGGER.info(json.dumps(record, separators=(",", ":"), sort_keys=True))
