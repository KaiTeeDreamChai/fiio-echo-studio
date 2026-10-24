#!/usr/bin/env python3
"""
Library Builder
Shared by the HTTP server (`engine/server.py`) and the CLI bridge
(`engine/bridge.py`) so both entry points run the exact same code path.

Responsibilities:
- skip undownloaded / missing sources instead of writing placeholder files
- FAT32-safe destination naming with collision handling
- run the normalization pipeline per track and collect truthful telemetry
- write `echo_library.json`
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional

from engine.core.naming import build_dest_stem, sanitize_relative_dir
from engine.core.pipeline import PipelineOrchestrator

ProgressCallback = Callable[[int, int, Dict[str, Any]], None]
CancelCallback = Callable[[], bool]


class LibraryBuilder:
    """Turn a list of NetEase track descriptors into a player-ready library."""

    def __init__(self, orchestrator: Optional[PipelineOrchestrator] = None):
        self.orchestrator = orchestrator or PipelineOrchestrator()

    def build(
        self,
        library_root: str,
        tracks: List[Dict[str, Any]],
        progress: Optional[ProgressCallback] = None,
        should_cancel: Optional[CancelCallback] = None,
    ) -> Dict[str, Any]:
        root = os.path.abspath(os.path.expanduser(library_root or "~/Music/FiiO_Echo_Library"))
        os.makedirs(root, exist_ok=True)

        results: List[Dict[str, Any]] = []
        collections: Dict[str, Dict[str, Any]] = {}
        used_stems: set[str] = set()
        counts = {"success": 0, "failed": 0, "skipped": 0}
        total = len(tracks or [])
        cancelled = False

        for index, item in enumerate(tracks or [], start=1):
            if should_cancel and should_cancel():
                cancelled = True
                break

            result = self._process_one(item, root, used_stems)
            results.append(result)

            if result.get("skipped"):
                counts["skipped"] += 1
            elif result.get("success"):
                counts["success"] += 1
                self._register_collection(collections, result)
            else:
                counts["failed"] += 1

            if progress:
                try:
                    progress(index, total, result)
                except Exception:
                    pass

        manifest_path = self.orchestrator.write_echo_library_json(root, list(collections.values()))

        return {
            "library_root": root,
            "manifest_path": manifest_path,
            "total": total,
            "processed_count": len(results),
            "success_count": counts["success"],
            "failed_count": counts["failed"],
            "skipped_count": counts["skipped"],
            "cancelled": cancelled,
            "results": results,
        }

    # ------------------------------------------------------------------ single
    def _process_one(self, item: Dict[str, Any], root: str, used_stems: set[str]) -> Dict[str, Any]:
        seq = str(item.get("seq") or "01")
        title = str(item.get("title") or "Unknown")
        artist = str(item.get("artist") or "Unknown")
        album = str(item.get("album") or "Unknown")
        base = {"seq": seq, "title": title, "artist": artist, "album": album}

        source_audio = os.path.expanduser(str(item.get("src_path") or ""))
        if not source_audio or not os.path.exists(source_audio):
            return {
                **base,
                "success": False,
                "skipped": True,
                "reason": "NOT_DOWNLOADED",
                "dest_audio": None,
                "size_bytes": 0,
                "report": {"error": "未下载本地音频文件，已跳过构建"},
            }

        relative_dir = sanitize_relative_dir(item.get("target_folder"))
        stem = build_dest_stem(seq, artist, title)
        unique_stem = stem
        counter = 2
        while f"{relative_dir}/{unique_stem}".lower() in used_stems:
            unique_stem = f"{stem} ({counter})"
            counter += 1
        used_stems.add(f"{relative_dir}/{unique_stem}".lower())

        dest_stem = os.path.join(root, relative_dir, unique_stem)

        source_lrc = item.get("src_lrc")
        if not source_lrc:
            candidate = os.path.splitext(source_audio)[0] + ".lrc"
            if os.path.exists(candidate):
                source_lrc = candidate

        meta_override = {
            "title": title,
            "artist": artist,
            "album": album,
            "tracknumber": seq,
        }

        ok, report = self.orchestrator.process_track(
            src_audio_path=source_audio,
            dest_stem=dest_stem,
            src_lrc_path=source_lrc,
            meta_override=meta_override,
            cover_url=item.get("cover_url") or None,
            cover_local_path=item.get("cover_local_path") or None,
        )

        cover = report.get("cover") or {}
        result = {
            **base,
            "success": bool(ok),
            "skipped": False,
            "reason": None if ok else (report.get("error") or "PIPELINE_ERROR"),
            "dest_audio": report.get("dest_audio") if ok else None,
            "dest_lrc": report.get("dest_lrc") if ok else None,
            "filename": os.path.basename(report.get("dest_audio") or "") or None,
            "size_bytes": report.get("size_bytes") or 0,
            "container": report.get("container"),
            "block_size": report.get("block_size"),
            "sample_rate": report.get("sample_rate"),
            "bits_per_sample": report.get("bits_per_sample"),
            "cover_compliant": bool(cover.get("compliant")),
            "cover_width": cover.get("width"),
            "cover_height": cover.get("height"),
            "cover_subsampling": cover.get("subsampling"),
            "cover_format": cover.get("format"),
            "cover_type": cover.get("type"),
            "cover_source": report.get("cover_source"),
            "cover_reasons": cover.get("reasons") or [],
            "target_folder": relative_dir,
            "report": report,
        }
        return result

    @staticmethod
    def _register_collection(
        collections: Dict[str, Dict[str, Any]], result: Dict[str, Any]
    ) -> None:
        relative_dir = result["target_folder"]
        is_album = relative_dir.startswith("Albums/")
        name = relative_dir.split("/", 1)[1] if "/" in relative_dir else relative_dir

        if relative_dir not in collections:
            collections[relative_dir] = {
                "id": relative_dir.replace("/", "_").lower(),
                "type": "album" if is_album else "playlist",
                "name": name,
                "directory": relative_dir,
                "tracks": [],
            }

        collections[relative_dir]["tracks"].append({
            "seq": result["seq"],
            "filename": result["filename"],
            "lrc_filename": (
                os.path.basename(result["dest_lrc"]) if result.get("dest_lrc") else None
            ),
            "title": result["title"],
            "artist": result["artist"],
            "container": result["container"],
            "size_bytes": result["size_bytes"],
            "block_size": result["block_size"],
            "sample_rate": result["sample_rate"],
            "bits_per_sample": result["bits_per_sample"],
            "cover": {
                "compliant": result["cover_compliant"],
                "width": result["cover_width"],
                "height": result["cover_height"],
                "subsampling": result["cover_subsampling"],
                "format": result["cover_format"],
                "type": result["cover_type"],
                "source": result["cover_source"],
            },
            "compliant": bool(
                result["success"]
                and result["cover_compliant"]
                and (result["container"] != "flac" or (result["block_size"] or 0) <= 4096)
            ),
        })
