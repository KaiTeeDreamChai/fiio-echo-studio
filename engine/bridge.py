#!/usr/bin/env python3
"""
Bridge Service & CLI for FiiO Echo Studio
Provides structured JSON interfaces for Frontend IPC:
1. get-playlists: returns playlists with creator filter/priority
2. get-albums: returns downloaded albums grouped from offlineTrack
3. get-playlist-tracks: returns tracks for a given playlist ID
4. get-album-tracks: returns tracks for a given album name
5. inspect-files: inspects local files for FLAC/Cover compliance
6. build-library: executes end-to-end normalization pipeline and writes echo_library.json
"""

import sys
import os
import json
import argparse
from typing import Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.providers.netease_db import NetEaseDBProvider
from engine.core.pipeline import PipelineOrchestrator
from engine.core.cover_normalizer import CoverNormalizer
from engine.core.flac_reframer import FlacReframer
from engine.core.lrc_sanitizer import LrcSanitizer


def main():
    parser = argparse.ArgumentParser(description="FiiO Echo Studio Bridge Service")
    subparsers = parser.add_subparsers(dest="action", help="Bridge action")

    # Action: get-playlists
    p_pl = subparsers.add_parser("get-playlists")
    p_pl.add_argument("--creator", type=str, default="", help="Preferred creator")
    p_pl.add_argument("--only-mine", action="store_true", help="Only show preferred creator")

    # Action: get-albums
    subparsers.add_parser("get-albums")

    # Action: get-playlist-tracks
    p_plt = subparsers.add_parser("get-playlist-tracks")
    p_plt.add_argument("--pid", type=str, required=True, help="Playlist ID")

    # Action: get-album-tracks
    p_at = subparsers.add_parser("get-album-tracks")
    p_at.add_argument("--name", type=str, required=True, help="Album Name")

    # Action: build-library
    p_bl = subparsers.add_parser("build-library")
    p_bl.add_argument("--config", type=str, required=True, help="Path to build config JSON or inline JSON string")

    args = parser.parse_args()
    provider = NetEaseDBProvider()

    if args.action == "get-playlists":
        pls = provider.get_all_playlists(
            preferred_creator=args.creator,
            only_preferred=args.only_mine
        )
        print(json.dumps({"success": True, "count": len(pls), "playlists": pls}, ensure_ascii=False))

    elif args.action == "get-albums":
        albums = provider.get_downloaded_albums()
        print(json.dumps({"success": True, "count": len(albums), "albums": albums}, ensure_ascii=False))

    elif args.action == "get-playlist-tracks":
        tracks = provider.get_playlist_tracks(args.pid)
        print(json.dumps({"success": True, "count": len(tracks), "tracks": tracks}, ensure_ascii=False))

    elif args.action == "get-album-tracks":
        tracks = provider.get_tracks_by_album(args.name)
        print(json.dumps({"success": True, "count": len(tracks), "tracks": tracks}, ensure_ascii=False))

    elif args.action == "build-library":
        try:
            if os.path.exists(args.config):
                with open(args.config, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
            else:
                cfg = json.loads(args.config)

            library_root = os.path.expanduser(cfg.get("library_root", "~/Music/FiiO_Echo_Library"))
            tracks_to_process = cfg.get("tracks", [])

            orchestrator = PipelineOrchestrator()
            results = []
            collections_map: Dict[str, Dict[str, Any]] = {}

            for item in tracks_to_process:
                src_audio = os.path.expanduser(item.get("src_path", ""))
                rel_dest = item.get("target_folder", "Albums/Unknown")
                seq = str(item.get("seq", "01")).zfill(2)
                title = item.get("title", "Unknown")
                artist = item.get("artist", "Unknown")
                album = item.get("album", "Unknown")

                # Destination file names: e.g. 01 Frank Ocean - Nikes.flac
                dest_base = f"{seq} {artist} - {title}".replace("/", "／")
                dest_audio = os.path.join(library_root, rel_dest, f"{dest_base}.flac")
                dest_lrc = os.path.join(library_root, rel_dest, f"{dest_base}.lrc")

                # Locate candidate src_lrc if not provided
                src_lrc = item.get("src_lrc")
                if not src_lrc and src_audio:
                    cand_lrc = os.path.splitext(src_audio)[0] + ".lrc"
                    if os.path.exists(cand_lrc):
                        src_lrc = cand_lrc

                meta_override = {
                    "title": title,
                    "artist": artist,
                    "album": album,
                    "tracknumber": seq
                }

                ok, report = orchestrator.process_track(
                    src_audio_path=src_audio,
                    dest_audio_path=dest_audio,
                    src_lrc_path=src_lrc,
                    dest_lrc_path=dest_lrc,
                    meta_override=meta_override
                )

                file_size = os.path.getsize(dest_audio) if os.path.exists(dest_audio) else 0

                res_entry = {
                    "seq": seq,
                    "title": title,
                    "artist": artist,
                    "success": ok,
                    "dest_audio": dest_audio,
                    "dest_lrc": dest_lrc if os.path.exists(dest_lrc) else None,
                    "size_bytes": file_size,
                    "report": report
                }
                results.append(res_entry)

                # Collect for echo_library.json
                if rel_dest not in collections_map:
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
                    "compliant": ok
                })

            # Write manifest
            manifest_path = orchestrator.write_echo_library_json(
                library_root=library_root,
                collections=list(collections_map.values())
            )

            print(json.dumps({
                "success": True,
                "library_root": library_root,
                "manifest_path": manifest_path,
                "processed_count": len(results),
                "results": results
            }, ensure_ascii=False))

        except Exception as e:
            print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
