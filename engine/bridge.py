#!/usr/bin/env python3
"""
Bridge Service & CLI for FiiO Echo Studio
Provides structured JSON interfaces for headless / agent invocation:

1. get-playlists        - playlists with optional creator filter/priority
2. get-albums           - downloaded albums grouped from offlineTrack
3. get-playlist-tracks  - ordered tracks for a playlist ID
4. get-album-tracks     - tracks for an album name
5. inspect              - real container / PCM / cover telemetry for local files
6. build-library        - end-to-end normalization + echo_library.json (same code as the app)

Every command prints a single JSON document on stdout; progress goes to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.core.builder import LibraryBuilder
from engine.core.inspector import AudioInspector
from engine.providers.netease_db import NetEaseDBProvider


def _print(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def _load_config(raw: str) -> Dict[str, Any]:
    """Accept either a path to a JSON file or an inline JSON string."""
    if os.path.exists(raw):
        with open(raw, "r", encoding="utf-8") as handle:
            return json.load(handle)
    return json.loads(raw)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FiiO Echo Studio bridge service")
    subparsers = parser.add_subparsers(dest="action")

    playlists = subparsers.add_parser("get-playlists", help="list playlists")
    playlists.add_argument("--creator", type=str, default="", help="preferred creator nickname")
    playlists.add_argument("--only-mine", action="store_true", help="only the preferred creator")

    subparsers.add_parser("get-albums", help="list downloaded albums")

    playlist_tracks = subparsers.add_parser("get-playlist-tracks", help="tracks of one playlist")
    playlist_tracks.add_argument("--pid", type=str, required=True)

    album_tracks = subparsers.add_parser("get-album-tracks", help="tracks of one album")
    album_tracks.add_argument("--name", type=str, required=True)

    inspect = subparsers.add_parser("inspect", help="inspect audio files")
    inspect.add_argument("--file", dest="files", action="append", default=[], help="file to inspect")
    inspect.add_argument("paths", nargs="*", default=[], help="additional files")

    build = subparsers.add_parser("build-library", help="normalize a library")
    build.add_argument("--config", type=str, required=True, help="config JSON path or inline JSON")
    build.add_argument("--library-root", type=str, default="", help="override output root")
    build.add_argument("--quiet", action="store_true", help="no per-track progress on stderr")

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    provider = NetEaseDBProvider()

    if args.action == "get-playlists":
        playlists = provider.get_all_playlists(
            preferred_creator=args.creator or None, only_preferred=args.only_mine
        )
        _print({"success": True, "count": len(playlists), "playlists": playlists})
        return

    if args.action == "get-albums":
        albums = provider.get_downloaded_albums()
        _print({"success": True, "count": len(albums), "albums": albums})
        return

    if args.action == "get-playlist-tracks":
        tracks = provider.get_playlist_tracks(args.pid)
        _print({"success": True, "count": len(tracks), "tracks": tracks})
        return

    if args.action == "get-album-tracks":
        tracks = provider.get_tracks_by_album(args.name)
        _print({"success": True, "count": len(tracks), "tracks": tracks})
        return

    if args.action == "inspect":
        inspector = AudioInspector()
        targets = [*args.files, *args.paths]
        items = [inspector.inspect(path) for path in targets]
        _print({"success": True, "count": len(items), "items": items})
        return

    if args.action == "build-library":
        try:
            config = _load_config(args.config)
            library_root = args.library_root or config.get("library_root") or "~/Music/FiiO_Echo_Library"
            tracks = [item for item in (config.get("tracks") or []) if isinstance(item, dict)]

            def on_progress(done: int, total: int, result: Dict[str, Any]) -> None:
                if args.quiet:
                    return
                state = "SKIP" if result.get("skipped") else ("OK" if result.get("success") else "FAIL")
                print(
                    f"[{done}/{total}] {state} {result.get('seq')} {result.get('title')}",
                    file=sys.stderr,
                )

            outcome = LibraryBuilder().build(library_root, tracks, progress=on_progress)
            _print({"success": True, **outcome})
        except Exception as exc:  # noqa: BLE001 - CLI contract is JSON, never a traceback
            _print({"success": False, "error": f"{exc.__class__.__name__}: {exc}"})
        return

    build_parser().print_help()


if __name__ == "__main__":
    main()
