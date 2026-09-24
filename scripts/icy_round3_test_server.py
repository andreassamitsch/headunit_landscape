#!/usr/bin/env python3
"""Deterministic ICY + Radio Browser mock for Dudu7 round 3."""
from __future__ import annotations

import argparse
import itertools
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

METAINT = 8192


class Handler(BaseHTTPRequestHandler):
    server_version = "MetrolistRound3/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}", flush=True)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._bytes(200, b"ok", "text/plain")
            return
        if self.path == "/always-broken":
            self._bytes(410, b"stale stream URL", "text/plain")
            return
        if self.path.startswith("/json/stations/byuuid/"):
            uuid = self.path.rsplit("/", 1)[-1]
            if uuid == "slow-one":
                time.sleep(6)
                self._station_json(uuid, "Slow Refreshed Radio", "/station1", "Rock")
                return
            if uuid == "stale-one":
                self._station_json(uuid, "Test Radio One", "/station1", "Rock")
                return
            if uuid == "stale-two":
                self._station_json(uuid, "Test Radio Two", "/station2", "Pop")
                return
            self._bytes(200, b"[]", "application/json")
            return
        if self.path == "/station1":
            self._stream("Test Radio One", "Rick Astley - Never Gonna Give You Up", self.server.audio1)
            return
        if self.path == "/station2":
            self._stream("Test Radio Two", "Test Artist Two - Test Track Two", self.server.audio2)
            return
        self.send_error(404)

    def _station_json(self, uuid: str, name: str, stream_path: str, tag: str) -> None:
        host = self.headers.get("Host", "10.0.2.2:8000")
        body = json.dumps(
            [
                {
                    "stationuuid": uuid,
                    "name": name,
                    "url": f"http://{host}{stream_path}",
                    "url_resolved": f"http://{host}{stream_path}",
                    "homepage": "",
                    "favicon": "",
                    "country": "Austria",
                    "language": "German",
                    "tags": tag,
                    "codec": "MP3",
                    "bitrate": 96,
                }
            ]
        ).encode()
        self._bytes(200, body, "application/json")

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
        if wants_metadata:
            self.send_header("icy-metaint", str(METAINT))
        self.end_headers()
        source = itertools.cycle(audio)
        metadata = f"StreamTitle='{title}';".encode()
        blocks = (len(metadata) + 15) // 16
        padded = metadata.ljust(blocks * 16, b"\0")
        try:
            while True:
                self.wfile.write(bytes(next(source) for _ in range(METAINT)))
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
    args = parser.parse_args()
    server = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    server.audio1 = args.audio1.read_bytes()
    server.audio2 = args.audio2.read_bytes()
    print(f"Round 3 test server listening on {args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
