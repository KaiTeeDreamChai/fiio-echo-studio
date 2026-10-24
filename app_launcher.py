#!/usr/bin/env python3
"""
FiiO Echo Studio - Native Desktop App Launcher
Powers the standalone macOS Application using WKWebView (pywebview)
and background HTTP Engine.
"""
import os
import sys
import socket
import threading
import time
from http.server import HTTPServer

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
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, StudioAPIHandler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


def main():
    import webview

    port = find_free_port()
    print(f"Starting FiiO Echo Studio Engine on port {port}...")
    httpd = start_server_in_thread(port)
    time.sleep(0.2)

    target_url = f"http://127.0.0.1:{port}"

    window = webview.create_window(
        title="FiiO Echo Studio",
        url=target_url,
        width=1340,
        height=840,
        min_size=(980, 640),
        text_select=True
    )

    webview.start(debug=False)
    print("Application window closed.")


if __name__ == "__main__":
    main()
