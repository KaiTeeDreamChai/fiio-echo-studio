#!/usr/bin/env python3
"""
Lightweight Local HTTP API Server for FiiO Echo Studio
Enables the React frontend to communicate directly with Python Core Engine & NetEase SQLite DB.

Design notes:
- Threaded server: long builds never block `/api/build-progress`.
- Builds run as background jobs so the workbench can show live progress and cancel.
- Every mutation endpoint is guarded by Host / Origin checks: only the desktop app
  and the Vite dev server may call this API, never an arbitrary website.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import threading
import time
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.core.bin_resolver import get_bundle_dir, get_ffmpeg_path, get_ncmdump_path
from engine.core.builder import LibraryBuilder
from engine.core.inspector import AudioInspector
from engine.core.lrc_sanitizer import LrcSanitizer
from engine.core.pipeline import PipelineOrchestrator
from engine.providers.netease_db import NetEaseDBProvider

API_VERSION = "1.1.0"
DEFAULT_PORT = 57123
DEFAULT_LIBRARY_ROOT = "~/Music/FiiO_Echo_Library"
MAX_INSPECT_FILES = 5000

ALLOWED_HOST_RE = re.compile(r"^(127\.0\.0\.1|localhost|\[::1\])(:\d+)?$", re.IGNORECASE)
ALLOWED_ORIGIN_RE = re.compile(r"^https?://(127\.0\.0\.1|localhost|\[::1\])(:\d+)?$", re.IGNORECASE)


def choose_folder_native(prompt_text: str = "选择本地乐库根目录") -> str:
    """Invoke the native macOS folder picker, ensuring the dialog is focused."""
    if platform.system() != "Darwin":
        return ""
    command = [
        "osascript", "-e",
        "try\n"
        '  tell application "System Events" to activate\n'
        f'  set f to choose folder with prompt "{prompt_text}"\n'
        "  POSIX path of f\n"
        "on error\n"
        '  ""\n'
        "end try",
    ]
    try:
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        return result.stdout.strip().rstrip("/")
    except Exception as exc:  # noqa: BLE001 - dialog failures are non-fatal
        print(f"[choose_folder_native] {exc}", file=sys.stderr)
        return ""


class BuildJobManager:
    """Runs library builds in background threads and exposes live progress."""

    def __init__(self, builder: Optional[LibraryBuilder] = None, history: int = 20):
        self.builder = builder or LibraryBuilder()
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._order: List[str] = []
        self._lock = threading.Lock()
        self._history = history

    def start(self, library_root: str, tracks: List[Dict[str, Any]]) -> str:
        job_id = uuid.uuid4().hex[:12]
        job: Dict[str, Any] = {
            "job_id": job_id,
            "status": "running",
            "done": 0,
            "total": len(tracks or []),
            "current": "",
            "results": [],
            "success_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "library_root": os.path.abspath(
                os.path.expanduser(library_root or DEFAULT_LIBRARY_ROOT)
            ),
            "manifest_path": None,
            "error": None,
            "_cancel": False,
            "started_at": time.time(),
            "finished_at": None,
        }
        with self._lock:
            self._jobs[job_id] = job
            self._order.append(job_id)
            while len(self._order) > self._history:
                self._jobs.pop(self._order.pop(0), None)

        thread = threading.Thread(target=self._run, args=(job, list(tracks or [])), daemon=True)
        thread.start()
        return job_id

    def _run(self, job: Dict[str, Any], tracks: List[Dict[str, Any]]) -> None:
        def on_progress(done: int, total: int, result: Dict[str, Any]) -> None:
            with self._lock:
                job["done"] = done
                job["total"] = total
                job["current"] = f'{result.get("seq")} {result.get("title")}'.strip()
                job["results"].append(result)
                if result.get("skipped"):
                    job["skipped_count"] += 1
                elif result.get("success"):
                    job["success_count"] += 1
                else:
                    job["failed_count"] += 1

        try:
            outcome = self.builder.build(
                job["library_root"],
                tracks,
                progress=on_progress,
                should_cancel=lambda: job["_cancel"],
            )
            with self._lock:
                job.update(
                    results=outcome["results"],
                    total=outcome["total"],
                    done=outcome["processed_count"],
                    success_count=outcome["success_count"],
                    failed_count=outcome["failed_count"],
                    skipped_count=outcome["skipped_count"],
                    manifest_path=outcome["manifest_path"],
                    library_root=outcome["library_root"],
                    status="cancelled" if outcome["cancelled"] else "done",
                    finished_at=time.time(),
                )
        except Exception as exc:  # noqa: BLE001 - surfaced through the job snapshot
            with self._lock:
                job["status"] = "error"
                job["error"] = f"{exc.__class__.__name__}: {exc}"
                job["finished_at"] = time.time()

    def snapshot(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return {key: (list(value) if isinstance(value, list) else value)
                    for key, value in job.items() if not key.startswith("_")}

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job["status"] != "running":
                return False
            job["_cancel"] = True
            return True


class StudioAPIHandler(BaseHTTPRequestHandler):
    provider = NetEaseDBProvider()
    orchestrator = PipelineOrchestrator()
    lrc_sanitizer = LrcSanitizer()
    inspector = AudioInspector()
    jobs = BuildJobManager()

    _inspect_cache: "OrderedDict[Any, Dict[str, Any]]" = OrderedDict()
    _inspect_lock = threading.Lock()
    _inspect_cache_limit = 4000

    server_version = "FiiO-Echo-Studio"
    _allowed_origin: Optional[str] = None

    # ------------------------------------------------------------------ plumbing
    def _cors_origin(self) -> Optional[str]:
        origin = self.headers.get("Origin")
        if origin and ALLOWED_ORIGIN_RE.match(origin):
            return origin
        return None

    def _set_cors_headers(self) -> None:
        origin = self._cors_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, status: int, data: Dict[str, Any]) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _guard_request(self) -> bool:
        """
        Reject drive-by requests from arbitrary web pages.

        Browsers always attach `Origin` to cross-origin calls and `Host` to every
        request, so a malicious page cannot reach these mutating endpoints.
        """
        host = (self.headers.get("Host") or "").strip()
        if host and not ALLOWED_HOST_RE.match(host):
            self._send_json(403, {"success": False, "error": "HOST_NOT_ALLOWED"})
            return False

        origin = self.headers.get("Origin")
        if origin and not ALLOWED_ORIGIN_RE.match(origin):
            self._send_json(403, {"success": False, "error": "ORIGIN_NOT_ALLOWED"})
            return False
        return True

    def _read_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if length <= 0:
            return {}
        payload = self.rfile.read(length)
        try:
            return json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}

    def _inspect_path(self, path: str) -> Dict[str, Any]:
        try:
            stat = os.stat(path)
            cache_key = (path, stat.st_mtime_ns, stat.st_size)
        except OSError:
            cache_key = (path, 0, 0)

        with self._inspect_lock:
            cached = self._inspect_cache.get(cache_key)
            if cached is not None:
                self._inspect_cache.move_to_end(cache_key)
                return cached

        info = self.inspector.inspect(path)
        with self._inspect_lock:
            self._inspect_cache[cache_key] = info
            while len(self._inspect_cache) > self._inspect_cache_limit:
                self._inspect_cache.popitem(last=False)
        return info

    def log_message(self, fmt: str, *args: Any) -> None:  # quieter console
        if os.environ.get("ECHO_STUDIO_VERBOSE"):
            super().log_message(fmt, *args)

    # ---------------------------------------------------------------------- GET
    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if not self._guard_request():
            return
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        path = parsed.path

        try:
            if path == "/api/status":
                ffmpeg_path = get_ffmpeg_path()
                ncmdump_path = get_ncmdump_path()
                self._send_json(200, {
                    "success": True,
                    "version": API_VERSION,
                    "db_available": self.provider.is_available(),
                    "db_path": self.provider.db_path,
                    "download_dir": self.provider.download_dir,
                    "ffmpeg_available": bool(ffmpeg_path and os.path.exists(ffmpeg_path)),
                    "ncmdump_available": bool(ncmdump_path and os.path.exists(ncmdump_path)),
                })
                return

            if path == "/api/pick-folder":
                chosen = choose_folder_native("请选择飞傲 Echo 本地乐库根目录:")
                if chosen:
                    self._send_json(200, {"success": True, "path": chosen})
                else:
                    self._send_json(200, {"success": False, "cancelled": True})
                return

            if path == "/api/playlists":
                creator = (params.get("creator", [""])[0] or "").strip() or None
                only_mine = params.get("only_mine", ["false"])[0].lower() == "true"
                playlists = self.provider.get_all_playlists(
                    preferred_creator=creator, only_preferred=only_mine
                )
                self._send_json(200, {"success": True, "count": len(playlists), "playlists": playlists})
                return

            if path == "/api/albums":
                albums = self.provider.get_downloaded_albums()
                self._send_json(200, {"success": True, "count": len(albums), "albums": albums})
                return

            if path == "/api/playlist-tracks":
                playlist_id = params.get("pid", [""])[0]
                if not playlist_id:
                    self._send_json(400, {"success": False, "error": "Missing pid parameter"})
                    return
                tracks = self.provider.get_playlist_tracks(playlist_id)
                self._attach_lrc(tracks)
                self._send_json(200, {"success": True, "count": len(tracks), "tracks": tracks})
                return

            if path == "/api/album-tracks":
                album_name = params.get("name", [""])[0]
                if not album_name:
                    self._send_json(400, {"success": False, "error": "Missing name parameter"})
                    return
                tracks = self.provider.get_tracks_by_album(album_name)
                self._attach_lrc(tracks)
                self._send_json(200, {"success": True, "count": len(tracks), "tracks": tracks})
                return

            if path == "/api/inspect":
                target = params.get("file", [""])[0]
                if not target:
                    self._send_json(400, {"success": False, "error": "Missing file parameter"})
                    return
                self._send_json(200, {"success": True, "item": self._inspect_path(target)})
                return

            if path == "/api/build-progress":
                job_id = params.get("job_id", [""])[0]
                snapshot = self.jobs.snapshot(job_id)
                if snapshot is None:
                    self._send_json(404, {"success": False, "error": "JOB_NOT_FOUND"})
                    return
                self._send_json(200, {"success": True, **snapshot})
                return

            if not path.startswith("/api/"):
                self._serve_static(path)
                return

            self._send_json(404, {"success": False, "error": "Route not found"})
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"success": False, "error": f"{exc.__class__.__name__}: {exc}"})

    def _attach_lrc(self, tracks: List[Dict[str, Any]]) -> None:
        for track in tracks:
            audio_path = track.get("local_file_path") or ""
            raw_lrc, clean_lrc = self._read_companion_lrc(audio_path)
            track["raw_lrc"] = raw_lrc
            track["clean_lrc"] = clean_lrc

    def _read_companion_lrc(self, audio_path: str) -> tuple[str, str]:
        if not audio_path:
            return "", ""
        lrc_path = os.path.splitext(audio_path)[0] + ".lrc"
        if not os.path.exists(lrc_path):
            return "", ""
        try:
            raw_text = self.lrc_sanitizer.read_text(lrc_path)
            return raw_text, self.lrc_sanitizer.sanitize_text(raw_text)
        except Exception:  # noqa: BLE001
            return "", ""

    def _serve_static(self, path: str) -> None:
        dist_dir = os.path.join(get_bundle_dir(), "dist")
        requested = path.lstrip("/") or "index.html"
        file_path = os.path.normpath(os.path.join(dist_dir, requested))

        # never serve outside dist/
        if not os.path.abspath(file_path).startswith(os.path.abspath(dist_dir) + os.sep):
            file_path = os.path.join(dist_dir, "index.html")
        if not os.path.exists(file_path) or os.path.isdir(file_path):
            file_path = os.path.join(dist_dir, "index.html")

        if not os.path.exists(file_path):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Static assets not built. Run `npm run build` first.")
            return

        content_type = "text/html; charset=utf-8"
        if file_path.endswith((".js", ".mjs")):
            content_type = "application/javascript; charset=utf-8"
        elif file_path.endswith(".css"):
            content_type = "text/css; charset=utf-8"
        elif file_path.endswith(".json"):
            content_type = "application/json; charset=utf-8"
        elif file_path.endswith(".svg"):
            content_type = "image/svg+xml"
        elif file_path.endswith(".png"):
            content_type = "image/png"
        elif file_path.endswith(".ico"):
            content_type = "image/x-icon"
        elif file_path.endswith(".woff2"):
            content_type = "font/woff2"

        with open(file_path, "rb") as handle:
            content = handle.read()

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    # --------------------------------------------------------------------- POST
    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if not self._guard_request():
            return
        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path == "/api/build-library":
                body = self._read_body()
                library_root = os.path.expanduser(
                    str(body.get("library_root") or DEFAULT_LIBRARY_ROOT)
                )
                tracks = [item for item in (body.get("tracks") or []) if isinstance(item, dict)]
                job_id = self.jobs.start(library_root, tracks)
                self._send_json(200, {
                    "success": True,
                    "job_id": job_id,
                    "total": len(tracks),
                    "library_root": os.path.abspath(library_root),
                })
                return

            if path == "/api/build-cancel":
                body = self._read_body()
                job_id = str(body.get("job_id") or "")
                cancelled = self.jobs.cancel(job_id)
                self._send_json(200, {"success": cancelled, "job_id": job_id})
                return

            if path == "/api/inspect":
                body = self._read_body()
                files = [name for name in (body.get("files") or []) if isinstance(name, str)]
                files = files[:MAX_INSPECT_FILES]
                items: Dict[str, Any] = {}
                if files:
                    with ThreadPoolExecutor(max_workers=8) as pool:
                        for file_path, info in zip(files, pool.map(self._inspect_path, files)):
                            items[file_path] = info
                self._send_json(200, {"success": True, "count": len(items), "items": items})
                return

            if path == "/api/dot-clean":
                body = self._read_body()
                target = os.path.expanduser(str(body.get("target_dir") or DEFAULT_LIBRARY_ROOT))
                outcome = self.orchestrator.dot_clean_directory(target)
                self._send_json(200, {
                    "success": True,
                    "message": (
                        f"已清除 {outcome['removed_files']} 个幽灵文件、"
                        f"{outcome['removed_dirs']} 个系统目录（dot_clean: {outcome['dot_clean']}）"
                    ),
                    **outcome,
                })
                return

            if path == "/api/fat-sort":
                body = self._read_body()
                target = os.path.expanduser(str(body.get("target_dir") or DEFAULT_LIBRARY_ROOT))
                outcome = self.orchestrator.fat_sort_directory(target)
                self._send_json(200, {
                    "success": True,
                    "message": (
                        f"已重建 {outcome['directories_processed']} 个目录、"
                        f"{outcome['files_reordered']} 个文件的 FAT32 目录项顺序"
                    ),
                    **outcome,
                })
                return

            self._send_json(404, {"success": False, "error": "Route not found"})
        except FileNotFoundError as exc:
            self._send_json(400, {"success": False, "error": str(exc)})
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"success": False, "error": f"{exc.__class__.__name__}: {exc}"})

    # ------------------------------------------------------------------ OPTIONS
    def do_OPTIONS(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if not self._guard_request():
            return
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()


def run_server(port: int = DEFAULT_PORT) -> None:
    address = ("127.0.0.1", port)
    httpd = ThreadingHTTPServer(address, StudioAPIHandler)
    httpd.daemon_threads = True
    print(f"FiiO Echo Studio API Server v{API_VERSION} listening on http://127.0.0.1:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down API server...")
    finally:
        httpd.server_close()


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="FiiO Echo Studio local API server")
    parser.add_argument("--port", type=int, default=None, help="HTTP port (default 57123)")
    parser.add_argument("legacy_port", nargs="?", type=int, default=None,
                        help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    port = args.port or args.legacy_port or DEFAULT_PORT
    run_server(port)


if __name__ == "__main__":
    main()
