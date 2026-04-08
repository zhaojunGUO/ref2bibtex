#!/usr/bin/env python3
"""Local web UI server for ref-to-bibtex."""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ref_to_bibtex import extract_title, resolve_bibtex

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path: Path, content_type: str) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        route = self.path.split("?", 1)[0]
        if route == "/":
            self._serve_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
            return
        if route == "/styles.css":
            self._serve_file(WEB_DIR / "styles.css", "text/css; charset=utf-8")
            return
        if route == "/app.js":
            self._serve_file(WEB_DIR / "app.js", "application/javascript; charset=utf-8")
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        route = self.path.split("?", 1)[0]
        if route != "/api/resolve":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Request body is empty."})
            return

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Invalid JSON body."})
            return

        reference = str(payload.get("reference", "")).strip()
        explicit_title = str(payload.get("title", "")).strip()
        source = str(payload.get("source", "auto")).strip() or "auto"

        try:
            timeout = float(payload.get("timeout", 15))
        except Exception:
            timeout = 15.0

        if source not in {"auto", "dblp", "crossref", "scholar"}:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "Invalid source option."})
            return

        if not explicit_title and not reference:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "reference or title is required."})
            return

        try:
            title = explicit_title or extract_title(reference)
            result = resolve_bibtex(title=title, source=source, timeout=timeout, reference_text=reference)
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            return

        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "input_title": title,
                "matched_title": result.title,
                "source": result.source,
                "bibtex": result.bibtex,
            },
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local web UI for ref-to-bibtex.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not WEB_DIR.exists():
        raise RuntimeError(f"Web directory not found: {WEB_DIR}")

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Server running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
