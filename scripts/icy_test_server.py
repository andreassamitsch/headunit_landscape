#!/usr/bin/env python3
"""Deterministic local ICY web-radio server for the Dudu7 UI smoke test."""

from __future__ import annotations

import argparse
import base64
import itertools
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

METAINT = 8192
LOGO_1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAATElEQVR4nO3PQQ0AIBDAsAP/nuGNAvZoFSzZOjNnyNi1dwfgUQCeBeBZAJ4F4FkAngXgWQCeBeBZAJ4F4FkAngXgWQCeBeBZAJ4F4FkA3gAznQF/9VwFJAAAAABJRU5ErkJggg=="
)
LOGO_2 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAATElEQVR4nO3PQQ0AIBDAsAP/nuGNAvZoFSzZujNnyNi1dwfgUQCeBeBZAJ4F4FkAngXgWQCeBeBZAJ4F4FkAngXgWQCeBeBZAJ4F4FkA3gAznQF/9VwFJAAAAABJRU5ErkJggg=="
)


class Handler(BaseHTTPRequestHandler):
    server_version = "MetrolistRadioTest/2.0"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}", flush=True)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._bytes(200, b"ok", "text/plain")
            return
        if self.path == "/logo1.png":
            self._bytes(200, LOGO_1, "image/png")
            return
        if self.path == "/logo2.png":
            self._bytes(200, LOGO_2, "image/png")
            return
        if self.path == "/logo3.png":
            self._bytes(200, self.server.logo3, "image/png")
            return
        if self.path == "/station3-home":
            self._bytes(
                200,
                b'<html><head><link rel="apple-touch-icon" sizes="512x512" href="/logo3.png"></head><body>Test Radio Three</body></html>',
                "text/html; charset=utf-8",
            )
            return
        if self.path == "/kronehit.svg":
            self._bytes(
                200,
                b'<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"><rect width="256" height="256" fill="#111"/><text x="20" y="140" fill="white">KRONEHIT</text></svg>',
                "image/svg+xml",
            )
            return
        if self.path == "/kronehit-home":
            count = getattr(self.server, "kronehit_home_requests", 0) + 1
            self.server.kronehit_home_requests = count
            logos = ("/logo1.png", "/logo2.png") if count % 2 else ("/logo2.png", "/logo1.png")
            body = (
                '<html><body><img class="station-logo" alt="kronehit logo" src="%s">'
                '<img class="station-logo" alt="kronehit logo" src="%s"></body></html>'
            ) % logos
            self._bytes(200, body.encode(), "text/html; charset=utf-8")
            return
        if self.path == "/playlist.m3u":
            host = self.headers.get("Host", "10.0.2.2:8000")
            self._bytes(200, f"#EXTM3U\nhttp://{host}/station1\n".encode(), "audio/x-mpegurl")
            return
        if self.path == "/station1":
            self._stream("Test Radio One", "Rick Astley - Never Gonna Give You Up", self.server.audio1)
            return
        if self.path == "/station2":
            self._stream("Test Radio Two", "Test Artist Two - Test Track Two", self.server.audio2)
            return
        if self.path == "/station3":
            self._stream("Test Radio Three", "Station identification", self.server.audio3)
            return
        if self.path == "/station4":
            self._stream("kronehit", "Kronehit Artist - Kronehit Track", self.server.audio2)
            return
        self.send_error(404)

    def _bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _stream(self, station: str, title: str, audio: bytes) -> None:
        wants_metadata = self.headers.get("Icy-MetaData") == "1"
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("icy-name", station)
        self.send_header("icy-genre", "Test")
        self.send_header("icy-br", "96")
        if wants_metadata:
            self.send_header("icy-metaint", str(METAINT))
        self.end_headers()

        source = itertools.cycle(audio)
        metadata = f"StreamTitle='{title}';".encode("utf-8")
        blocks = (len(metadata) + 15) // 16
        padded = metadata.ljust(blocks * 16, b"\0")
        try:
            while True:
                chunk = bytes(next(source) for _ in range(METAINT))
                self.wfile.write(chunk)
                if wants_metadata:
                    self.wfile.write(bytes([blocks]))
                    self.wfile.write(padded)
                self.wfile.flush()
                time.sleep(0.01)
        except (BrokenPipeError, ConnectionResetError):
            return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--audio1", type=Path, required=True)
    parser.add_argument("--audio2", type=Path, required=True)
    parser.add_argument("--audio3", type=Path, required=True)
    parser.add_argument("--logo3", type=Path, required=True)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    server.audio1 = args.audio1.read_bytes()
    server.audio2 = args.audio2.read_bytes()
    server.audio3 = args.audio3.read_bytes()
    server.logo3 = args.logo3.read_bytes()
    print(f"ICY test server listening on {args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
