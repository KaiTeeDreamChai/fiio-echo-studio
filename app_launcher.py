#!/usr/bin/env python3
"""
FiiO Echo Studio - Native Desktop App Launcher
Powers the standalone macOS Application using WKWebView (pywebview)
and a background HTTP engine.

Usage:
    FiiO Echo Studio            # normal GUI window
    FiiO Echo Studio --headless --port 58999
                                # API only (for smoke tests / CI), no window
"""
import argparse
import os
import socket
import sys
import threading
import time
from http.server import ThreadingHTTPServer

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.core.bin_resolver import get_bundle_dir
from engine.server import StudioAPIHandler


def find_free_port(preferred: int = 57123) -> int:
    """Checks if preferred port is free, otherwise finds an available ephemeral port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


def start_server_in_thread(port: int):
    """Runs the API & static asset server in background thread."""
    httpd = ThreadingHTTPServer(("127.0.0.1", port), StudioAPIHandler)
    httpd.daemon_threads = True
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def main() -> None:
    parser = argparse.ArgumentParser(description="FiiO Echo Studio desktop app")
    parser.add_argument("--headless", action="store_true", help="run the API only (no window)")
    parser.add_argument("--port", type=int, default=0, help="fixed port (default: auto)")
    args = parser.parse_args()

    port = args.port or find_free_port()
    httpd = start_server_in_thread(port)
    print(f"Starting FiiO Echo Studio Engine on http://127.0.0.1:{port} ...", flush=True)
    time.sleep(0.2)

    if args.headless:
        print("Headless mode: press Ctrl+C to stop.", flush=True)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            print("Shutting down...", flush=True)
        finally:
            httpd.shutdown()
            httpd.server_close()
        return

    import webview

    webview.create_window(
        title="FiiO Echo Studio",
        url=f"http://127.0.0.1:{port}",
        width=1340,
        height=840,
        min_size=(980, 640),
        text_select=True,
    )
    webview.start(debug=False)
    print("Application window closed.")


if __name__ == "__main__":
    main()
