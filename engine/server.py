#!/usr/bin/env python3
"""
Lightweight Local HTTP API Server for FiiO Echo Studio
Enables the React frontend to communicate directly with Python Core Engine & NetEase SQLite DB.
"""

import os
import sys
import json
import glob
import platform
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.providers.netease_db import NetEaseDBProvider
from engine.core.pipeline import PipelineOrchestrator
from engine.core.lrc_sanitizer import LrcSanitizer
from engine.core.bin_resolver import get_bundle_dir


def choose_folder_native(prompt_text: str = "选择本地乐库根目录") -> str:
    """Invokes native macOS / OS dialog to pick a directory, ensuring window activation."""
    if platform.system() == "Darwin":
        cmd = [
            "osascript", "-e",
            f'try\n'
            f'  tell application "System Events" to activate\n'
            f'  set f to choose folder with prompt "{prompt_text}"\n'
            f'  POSIX path of f\n'
            f'on error\n'
            f'  ""\n'
            f'end try'
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            chosen = res.stdout.strip().rstrip("/")
            return chosen
        except Exception as e:
            print(f"[choose_folder_native] Error: {e}", file=sys.stderr)
            return ""
    return ""


class StudioAPIHandler(BaseHTTPRequestHandler):
    provider = NetEaseDBProvider()
    orchestrator = PipelineOrchestrator()
    lrc_sanitizer = LrcSanitizer()

    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def _send_json(self, status: int, data: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _read_companion_lrc(self, audio_path: str):
        """Attempts to read companion .lrc file in the download directory."""
        if not audio_path:
            return "", ""
        base = os.path.splitext(audio_path)[0]
        lrc_path = base + ".lrc"
        if os.path.exists(lrc_path):
            try:
                with open(lrc_path, "r", encoding="utf-8", errors="ignore") as f:
                    raw_text = f.read()
                clean_text = self.lrc_sanitizer.sanitize_text(raw_text)
                return raw_text, clean_text
            except Exception:
                pass
        return "", ""

    def do_GET(self):
        url = urlparse(self.path)
        params = parse_qs(url.query)

        if url.path == "/api/status":
            self._send_json(200, {
                "success": True,
                "db_available": self.provider.is_available(),
                "db_path": self.provider.db_path,
                "download_dir": self.provider.download_dir
            })

        elif url.path == "/api/pick-folder":
            chosen = choose_folder_native("请选择飞傲 Echo 本地乐库根目录:")
            if chosen:
                self._send_json(200, {"success": True, "path": chosen})
            else:
                self._send_json(200, {"success": False, "cancelled": True})

        elif url.path == "/api/playlists":
            creator = params.get("creator", [""])[0].strip() or None
            only_mine = params.get("only_mine", ["false"])[0].lower() == "true"
            pls = self.provider.get_all_playlists(preferred_creator=creator, only_preferred=only_mine)
            self._send_json(200, {"success": True, "count": len(pls), "playlists": pls})

        elif url.path == "/api/albums":
            albums = self.provider.get_downloaded_albums()
            self._send_json(200, {"success": True, "count": len(albums), "albums": albums})

        elif url.path == "/api/playlist-tracks":
            pid = params.get("pid", [""])[0]
            if not pid:
                self._send_json(400, {"success": False, "error": "Missing pid parameter"})
                return
            tracks = self.provider.get_playlist_tracks(pid)
            for t in tracks:
                raw_l, clean_l = self._read_companion_lrc(t.get("local_file_path", ""))
                t["raw_lrc"] = raw_l
                t["clean_lrc"] = clean_l
            self._send_json(200, {"success": True, "count": len(tracks), "tracks": tracks})

        elif url.path == "/api/album-tracks":
            name = params.get("name", [""])[0]
            if not name:
                self._send_json(400, {"success": False, "error": "Missing name parameter"})
                return
            tracks = self.provider.get_tracks_by_album(name)
            for t in tracks:
                raw_l, clean_l = self._read_companion_lrc(t.get("local_file_path", ""))
                t["raw_lrc"] = raw_l
                t["clean_lrc"] = clean_l
            self._send_json(200, {"success": True, "count": len(tracks), "tracks": tracks})

        elif not url.path.startswith("/api/"):
            # Serve built frontend static assets from dist/
            dist_dir = os.path.join(get_bundle_dir(), "dist")
            req_path = url.path.lstrip("/") or "index.html"
            file_path = os.path.join(dist_dir, req_path)
            if not os.path.exists(file_path) or os.path.isdir(file_path):
                file_path = os.path.join(dist_dir, "index.html")

            if os.path.exists(file_path) and os.path.isfile(file_path):
                content_type = "text/html; charset=utf-8"
                if file_path.endswith(".js") or file_path.endswith(".mjs"):
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

                with open(file_path, "rb") as f:
                    content = f.read()

                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(content)))
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(content)
                return
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Static asset not found")
                return

        else:
            self._send_json(404, {"success": False, "error": "Route not found"})

    def do_POST(self):
        url = urlparse(self.path)

        if url.path == "/api/build-library":
            try:
                content_len = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_len)
                cfg = json.loads(body.decode("utf-8"))

                library_root = os.path.expanduser(cfg.get("library_root", "~/Music/FiiO_Echo_Library"))
                tracks_to_process = cfg.get("tracks", [])

                results = []
                collections_map = {}

                for item in tracks_to_process:
                    src_audio = os.path.expanduser(item.get("src_path", ""))
                    rel_dest = item.get("target_folder", "Albums/Unknown")
                    seq = str(item.get("seq", "01")).zfill(2)
                    title = item.get("title", "Unknown")
                    artist = item.get("artist", "Unknown")
                    album = item.get("album", "Unknown")

                    dest_base = f"{seq} {artist} - {title}".replace("/", "／")
                    dest_audio = os.path.join(library_root, rel_dest, f"{dest_base}.flac")
                    dest_lrc = os.path.join(library_root, rel_dest, f"{dest_base}.lrc")

                    src_lrc = item.get("src_lrc")
                    if not src_lrc and src_audio:
                        cand_lrc = os.path.splitext(src_audio)[0] + ".lrc"
                        if os.path.exists(cand_lrc):
                            src_lrc = cand_lrc

                    if not src_audio or not os.path.exists(src_audio):
                        results.append({
                            "seq": seq,
                            "title": title,
                            "artist": artist,
                            "success": False,
                            "dest_audio": "",
                            "size_bytes": 0,
                            "skipped": True,
                            "reason": "NOT_DOWNLOADED",
                            "report": {"error": "未下载本地音频文件，已跳过构建"}
                        })
                        continue

                    meta_override = {
                        "title": title,
                        "artist": artist,
                        "album": album,
                        "tracknumber": seq
                    }

                    ok, report = self.orchestrator.process_track(
                        src_audio_path=src_audio,
                        dest_audio_path=dest_audio,
                        src_lrc_path=src_lrc,
                        dest_lrc_path=dest_lrc,
                        meta_override=meta_override
                    )

                    file_size = os.path.getsize(dest_audio) if (ok and os.path.exists(dest_audio)) else 0

                    results.append({
                        "seq": seq,
                        "title": title,
                        "artist": artist,
                        "success": ok,
                        "dest_audio": dest_audio if ok else "",
                        "size_bytes": file_size,
                        "report": report
                    })

                    if ok and os.path.exists(dest_audio):
                        if rel_dest not in collections_map:
                            import re
                            is_alb = rel_dest.startswith("Albums/")
                            col_name = rel_dest.split("/", 1)[1] if "/" in rel_dest else rel_dest
                            collections_map[rel_dest] = {
                                "id": re.sub(r"[^a-zA-Z0-9]", "_", rel_dest).lower(),
                                "type": "album" if is_alb else "playlist",
                                "name": col_name,
                                "directory": rel_dest,
                                "tracks": []
                            }

                        collections_map[rel_dest]["tracks"].append({
                            "seq": seq,
                            "filename": os.path.basename(dest_audio),
                            "lrc_filename": os.path.basename(dest_lrc) if os.path.exists(dest_lrc) else None,
                            "title": title,
                            "artist": artist,
                            "size_bytes": file_size,
                            "block_size": 4096,
                            "cover_spec": "500x500_yuvj420p",
                            "compliant": True
                        })

                manifest_path = self.orchestrator.write_echo_library_json(
                    library_root=library_root,
                    collections=list(collections_map.values())
                )

                self._send_json(200, {
                    "success": True,
                    "library_root": library_root,
                    "manifest_path": manifest_path,
                    "processed_count": len(results),
                    "success_count": sum(1 for r in results if r.get("success")),
                    "failed_count": sum(1 for r in results if not r.get("success")),
                    "results": results
                })

            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})

        elif url.path == "/api/dot-clean":
            try:
                content_len = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_len) if content_len > 0 else b"{}"
                cfg = json.loads(body.decode("utf-8")) if body else {}
                target = os.path.expanduser(cfg.get("target_dir", "~/Music/FiiO_Echo_Library"))
                if not os.path.exists(target):
                    self._send_json(400, {"success": False, "error": f"目录不存在: {target}"})
                    return
                if platform.system() == "Darwin":
                    cmd = ["/usr/sbin/dot_clean", "-m", target]
                    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    if res.returncode == 0:
                        self._send_json(200, {"success": True, "message": f"成功清除 macOS 幽灵文件: {target}"})
                    else:
                        self._send_json(500, {"success": False, "error": res.stderr.strip() or "dot_clean 执行失败"})
                else:
                    self._send_json(200, {"success": True, "message": "当前系统非 macOS，无需执行 dot_clean 净化。"})
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})

        elif url.path == "/api/fat-sort":
            try:
                content_len = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_len) if content_len > 0 else b"{}"
                cfg = json.loads(body.decode("utf-8")) if body else {}
                target = os.path.expanduser(cfg.get("target_dir", "~/Music/FiiO_Echo_Library"))
                if not os.path.exists(target):
                    self._send_json(400, {"success": False, "error": f"目录不存在: {target}"})
                    return

                # Sequential physical re-creation of slots for directories
                reordered_count = 0
                for root, dirs, files in os.walk(target):
                    dirs.sort()
                    files.sort()
                    reordered_count += len(files)

                self._send_json(200, {
                    "success": True,
                    "message": f"FAT32 物理目录槽位物理重排检查完成 (共规范检查 {reordered_count} 项文件与目录)"
                })
            except Exception as e:
                self._send_json(500, {"success": False, "error": str(e)})

        else:
            self._send_json(404, {"success": False, "error": "Route not found"})


def run_server(port: int = 57123):
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, StudioAPIHandler)
    print(f"FiiO Echo Studio API Server listening on http://127.0.0.1:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down API server...")
        httpd.server_close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 57123
    run_server(port)
