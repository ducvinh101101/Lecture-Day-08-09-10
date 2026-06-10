#!/usr/bin/env python3
"""Small web server for the Day 10 multi-agent RAG interface."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

from multi_agent_rag import ask

load_dotenv()
ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"


def _public_result(result: dict) -> dict:
    """Return useful UI data without secrets or full hidden context."""
    return {
        key: result.get(key)
        for key in (
            "run_id",
            "question",
            "intent",
            "answer",
            "synthesis_provider",
            "synthesis_model",
            "citations",
            "confidence",
            "needs_human_review",
            "route_reason",
            "domain_filters",
            "guard_passed",
            "workers_called",
            "events",
            "errors",
            "latency_ms",
            "timestamp",
            "trace_path",
        )
    }


class RagHandler(BaseHTTPRequestHandler):
    server_version = "Day10RAG/1.0"

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            self._json(
                {
                    "status": "ok",
                    "collection": os.environ.get("CHROMA_COLLECTION", "day10_kb"),
                    "gemini_configured": bool(os.environ.get("GEMINI_API_KEY", "").strip()),
                    "model": os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
                }
            )
            return

        if path in {"/report", "/project_summary.html"}:
            target = ROOT / "project_summary.html"
            allowed_root = ROOT
        else:
            relative = "index.html" if path == "/" else path.lstrip("/")
            target = (WEB_ROOT / relative).resolve()
            allowed_root = WEB_ROOT
        if allowed_root.resolve() not in target.resolve().parents and target.resolve() != allowed_root.resolve():
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content = target.read_bytes()
        mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{mime}; charset=utf-8" if mime.startswith("text/") else mime)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/ask":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size > 20_000:
                self._json({"error": "Request quá lớn."}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                return
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
            question = str(payload.get("question", "")).strip()
            if not question:
                self._json({"error": "Vui lòng nhập câu hỏi."}, HTTPStatus.BAD_REQUEST)
                return
            top_k = max(1, min(10, int(payload.get("top_k", 5))))
            self._json(_public_result(ask(question, top_k=top_k)))
        except Exception as exc:
            self.log_error("POST /api/ask failed: %s: %s", type(exc).__name__, exc)
            self._json(
                {"error": "Không thể xử lý câu hỏi lúc này. Vui lòng thử lại."},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"[rag-web] {self.address_string()} {fmt % args}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Web UI for the Day 10 multi-agent RAG")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), RagHandler)
    print(f"RAG web UI: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
