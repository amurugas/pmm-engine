"""Dependency-free local web server for the PMM engineering workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
import threading
from time import perf_counter
from collections import OrderedDict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .excel_bridge import calculate_payload

WEB_ROOT = Path(__file__).with_name("web")
ENGINE_VERSION = "0.1.0"
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
}


class AnalysisCache:
    """Small process-local LRU cache for repeated workbook/browser runs."""

    def __init__(self, maximum_entries: int = 16) -> None:
        self.maximum_entries = maximum_entries
        self._items: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def calculate(
        self, payload: dict[str, Any]
    ) -> tuple[dict[str, Any], bool, str]:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        key = hashlib.sha256(encoded).hexdigest()
        with self._lock:
            if key in self._items:
                result = self._items.pop(key)
                self._items[key] = result
                return result, True, key
        result = calculate_payload(payload)
        with self._lock:
            self._items[key] = result
            while len(self._items) > self.maximum_entries:
                self._items.popitem(last=False)
        return result, False, key


class PMMRequestHandler(BaseHTTPRequestHandler):
    server_version = "PMMEngine/0.1"
    cache = AnalysisCache()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/health":
            self._send_json({"ok": True, "status": "healthy"})
            return
        if self.path == "/api/version":
            self._send_json({"ok": True, "engine_version": ENGINE_VERSION, "api_version": "v1"})
            return
        asset = ASSETS.get(self.path.split("?", 1)[0])
        if asset is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        filename, content_type = asset
        content = (WEB_ROOT / filename).read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_HEAD(self) -> None:  # noqa: N802
        asset = ASSETS.get(self.path.split("?", 1)[0])
        if asset is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        filename, content_type = asset
        content = (WEB_ROOT / filename).read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in {"/api/analyze", "/api/v1/analyze"}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 2_000_000:
                raise ValueError("Request body must be between 1 byte and 2 MB")
            payload = json.loads(self.rfile.read(length))
            started = perf_counter()
            result, cached, input_hash = self.cache.calculate(payload)
            elapsed_ms = 1000.0 * (perf_counter() - started)
            self._send_json(
                {
                    "ok": True,
                    "cached": cached,
                    "meta": {
                        "api_version": "v1",
                        "engine_version": ENGINE_VERSION,
                        "input_sha256": input_hash,
                        "cached": cached,
                        "server_ms": elapsed_ms,
                    },
                    "result": result,
                }
            )
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self._send_json(
                {"ok": False, "error": str(error)}, status=HTTPStatus.BAD_REQUEST
            )
        except Exception as error:  # pragma: no cover - defensive HTTP boundary
            self._send_json(
                {"ok": False, "error": f"Analysis failed: {error}"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _send_json(self, value: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        content = json.dumps(value, allow_nan=False, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local PMM workspace")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3000)
    arguments = parser.parse_args(argv)
    server = ThreadingHTTPServer((arguments.host, arguments.port), PMMRequestHandler)
    print(f"PMM Engine available at http://{arguments.host}:{arguments.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
