#!/usr/bin/env python3
"""
Pipeline Orchestrator Module
Coordinates:
1. Source Ingest / NCM Decryption
2. FLAC Stream Frame Reframing (frame size <= 4096)
3. Cover Art Normalization (500x500 YUV 4:2:0 Baseline JPEG, Type 3)
4. Companion LRC Cleaning ([mm:ss.xx] UTF-8 CRLF)
5. Structured local library placement & registry generation (echo_library.json)
6. TF-card maintenance helpers: FAT32 directory slot rebuilding & ghost file purge

Every report field is measured on the **written output file**, never assumed, so
the UI can render real telemetry.
"""

from __future__ import annotations

import os
import json
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC
from mutagen.id3 import APIC, ID3, ID3NoHeaderError
from mutagen.mp3 import EasyMP3

from engine.core.cover_normalizer import CoverNormalizer
from engine.core.flac_reframer import FlacReframer
from engine.core.inspector import AudioInspector, TARGET_BLOCK
from engine.core.lrc_sanitizer import LrcSanitizer
from engine.core.ncm_decryptor import NcmDecryptor

SUPPORTED_CONTAINERS = {"flac", "mp3"}


class PipelineOrchestrator:
    """End-to-end normalization and local library builder."""

    def __init__(self, staging_dir: Optional[str] = None):
        self.staging_dir = staging_dir or os.path.join(tempfile.gettempdir(), "echo_studio_staging")
        self.ncm_decryptor = NcmDecryptor()
        self.flac_reframer = FlacReframer()
        self.cover_normalizer = CoverNormalizer()
        self.lrc_sanitizer = LrcSanitizer()
        self.inspector = AudioInspector()

    # ------------------------------------------------------------------ public
    def process_track(
        self,
        src_audio_path: str,
        dest_stem: str,
        src_lrc_path: Optional[str] = None,
        meta_override: Optional[Dict[str, Any]] = None,
        cover_url: Optional[str] = None,
        cover_local_path: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Normalize one track and write it to ``<dest_stem>.<real extension>``.

        ``dest_stem`` has **no** extension: the pipeline decides `.flac` vs `.mp3`
        from the decoded container, so an MP3 is never mislabelled as FLAC.
        """
        os.makedirs(self.staging_dir, exist_ok=True)
        work_dir = os.path.join(self.staging_dir, f"{time.time_ns()}_{uuid.uuid4().hex[:6]}")
        os.makedirs(work_dir, exist_ok=True)

        report: Dict[str, Any] = {
            "decrypted": False,
            "reframed_audio": False,
            "normalized_cover": False,
            "cover_source": None,
            "sanitized_lrc": False,
            "container": None,
            "dest_audio": None,
            "dest_lrc": None,
            "block_size": None,
            "sample_rate": None,
            "bits_per_sample": None,
            "duration_sec": None,
            "cover": None,
            "size_bytes": 0,
            "cover_error": None,
            "metadata_error": None,
            "error": None,
        }

        try:
            if not src_audio_path or not os.path.exists(src_audio_path):
                report["error"] = "SOURCE_NOT_FOUND"
                return False, report

            current_audio = src_audio_path
            if current_audio.lower().endswith(".ncm"):
                ok, decrypted_path, message = self.ncm_decryptor.decrypt(current_audio, work_dir)
                if not ok:
                    report["error"] = f"NCM_DECRYPT_FAILED: {message}"
                    return False, report
                current_audio = decrypted_path
                report["decrypted"] = True

            container = self._detect_container(current_audio)
            report["container"] = container
            if container not in SUPPORTED_CONTAINERS:
                report["error"] = f"UNSUPPORTED_CONTAINER: {os.path.splitext(current_audio)[1] or 'unknown'}"
                return False, report

            if container == "flac":
                dest_audio = self._write_flac(
                    current_audio, dest_stem, work_dir, meta_override,
                    cover_url, cover_local_path, report,
                )
            else:
                dest_audio = self._write_mp3(
                    current_audio, dest_stem, work_dir, meta_override,
                    cover_url, cover_local_path, report,
                )

            destination_lrc = None
            if src_lrc_path and os.path.exists(src_lrc_path):
                destination_lrc = f"{dest_stem}.lrc"
                os.makedirs(os.path.dirname(destination_lrc), exist_ok=True)
                lrc_ok, _ = self.lrc_sanitizer.sanitize_file(src_lrc_path, destination_lrc)
                report["sanitized_lrc"] = bool(lrc_ok)
                if not lrc_ok:
                    destination_lrc = None

            # Measure the file we actually produced.
            output = self.inspector.inspect(dest_audio)
            report.update(
                dest_audio=dest_audio,
                dest_lrc=destination_lrc,
                block_size=output["block_size"],
                sample_rate=output["sample_rate"],
                bits_per_sample=output["bits_per_sample"],
                duration_sec=output["duration_sec"],
                cover=output["cover"],
                size_bytes=os.path.getsize(dest_audio) if os.path.exists(dest_audio) else 0,
            )
            if not output["cover"]["compliant"]:
                report["cover_reasons"] = output["cover"]["reasons"]
            return True, report

        except Exception as exc:  # pragma: no cover - defensive boundary
            report["error"] = f"{exc.__class__.__name__}: {exc}"
            return False, report
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    # ------------------------------------------------------------------- flac
    def _write_flac(
        self,
        source_path: str,
        dest_stem: str,
        work_dir: str,
        meta_override: Optional[Dict[str, Any]],
        cover_url: Optional[str],
        cover_local_path: Optional[str],
        report: Dict[str, Any],
    ) -> str:
        audio = FLAC(source_path)
        needs_reframe = audio.info.max_blocksize > TARGET_BLOCK
        pictures = list(audio.pictures or [])
        picture_bytes = pictures[0].data if pictures else None
        staged = os.path.join(work_dir, "staged.flac")

        if needs_reframe:
            ok, message = self.flac_reframer.reframe_audio_stream(source_path, staged)
            if not ok:
                raise RuntimeError(f"AUDIO_REFRAME_FAILED: {message}")
            report["reframed_audio"] = True
            # ffmpeg drops every metadata block, so restore the textual tags.
            staged_audio = FLAC(staged)
            for key, value in (audio.tags or {}).items():
                try:
                    staged_audio[key] = list(value)
                except Exception:
                    continue
            staged_audio.save()
        else:
            shutil.copyfile(source_path, staged)

        cover_info = self.inspector.inspect(source_path)["cover"]
        cover_ok = bool(cover_info.get("compliant"))

        if picture_bytes and not cover_ok:
            normalized = self._normalize_cover(picture_bytes, work_dir)
            if normalized:
                self.cover_normalizer.embed_normalized_cover(staged, normalized)
                report["normalized_cover"] = True
                report["cover_source"] = "embedded"
        elif picture_bytes and cover_ok and needs_reframe:
            staged_audio = FLAC(staged)
            staged_audio.clear_pictures()
            staged_audio.add_picture(pictures[0])
            staged_audio.save()
        elif not picture_bytes:
            normalized = self._fallback_cover(cover_local_path, cover_url, work_dir, report)
            if normalized:
                self.cover_normalizer.embed_normalized_cover(staged, normalized)
                report["normalized_cover"] = True

        if meta_override:
            self._apply_flac_tags(staged, meta_override)

        destination = f"{dest_stem}.flac"
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copyfile(staged, destination)
        return destination

    def _apply_flac_tags(self, flac_path: str, meta_override: Dict[str, Any]) -> None:
        audio = FLAC(flac_path)
        mapping = {
            "title": "title",
            "artist": "artist",
            "album": "album",
            "tracknumber": "tracknumber",
        }
        for source_key, tag_key in mapping.items():
            value = meta_override.get(source_key)
            if value:
                audio[tag_key] = str(value)
        audio.save()

    # -------------------------------------------------------------------- mp3
    def _write_mp3(
        self,
        source_path: str,
        dest_stem: str,
        work_dir: str,
        meta_override: Optional[Dict[str, Any]],
        cover_url: Optional[str],
        cover_local_path: Optional[str],
        report: Dict[str, Any],
    ) -> str:
        destination = f"{dest_stem}.mp3"
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copyfile(source_path, destination)

        if meta_override:
            self._apply_mp3_tags(destination, meta_override, report)

        cover_info = self.inspector.inspect(destination)["cover"]
        cover_bytes = self._read_mp3_cover(destination)

        if cover_bytes and not cover_info.get("compliant"):
            normalized = self._normalize_cover(cover_bytes, work_dir)
            if normalized:
                self._write_mp3_cover(destination, normalized)
                report["normalized_cover"] = True
                report["cover_source"] = "embedded"
        elif not cover_bytes:
            normalized = self._fallback_cover(cover_local_path, cover_url, work_dir, report)
            if normalized:
                self._write_mp3_cover(destination, normalized)
                report["normalized_cover"] = True

        return destination

    def _apply_mp3_tags(
        self, path: str, meta_override: Dict[str, Any], report: Dict[str, Any]
    ) -> None:
        try:
            try:
                tags = EasyMP3(path)
            except ID3NoHeaderError:
                tags = EasyMP3(path)
                tags.add_tags()
            for key in ("title", "artist", "album", "tracknumber"):
                value = meta_override.get(key)
                if value:
                    tags[key] = str(value)
            tags.save()
        except Exception as exc:  # tagging must not fail the audio write
            report["metadata_error"] = f"{exc.__class__.__name__}: {exc}"

    @staticmethod
    def _read_mp3_cover(path: str) -> Optional[bytes]:
        try:
            frames = ID3(path).getall("APIC")
        except ID3NoHeaderError:
            return None
        return frames[0].data if frames else None

    @staticmethod
    def _write_mp3_cover(path: str, cover_bytes: bytes) -> None:
        try:
            tags = ID3(path)
        except ID3NoHeaderError:
            tags = ID3()
        for key in list(tags.keys()):
            if key.startswith("APIC"):
                del tags[key]
        tags.add(
            APIC(encoding=3, mime="image/jpeg", type=3, desc="Front Cover", data=cover_bytes)
        )
        tags.save(path, v2_version=3)

    # ------------------------------------------------------------------ cover
    def _normalize_cover(self, raw_bytes: bytes, work_dir: str) -> Optional[bytes]:
        try:
            return self.cover_normalizer.normalize_image_bytes(raw_bytes, work_dir)
        except Exception:
            return None

    def _fallback_cover(
        self,
        cover_local_path: Optional[str],
        cover_url: Optional[str],
        work_dir: str,
        report: Dict[str, Any],
    ) -> Optional[bytes]:
        """
        Cover source priority when the audio file itself carries no picture:
        1. NetEase's local store ``<download_dir>/meta/track-<id>.jpg`` (offline, full-res)
        2. the album ``picUrl`` from the local database (network fallback)
        """
        if cover_local_path and os.path.exists(cover_local_path):
            try:
                with open(cover_local_path, "rb") as handle:
                    payload = handle.read()
            except OSError as exc:
                report["cover_error"] = f"LOCAL_COVER_READ_FAILED: {exc}"
            else:
                normalized = self._normalize_cover(payload, work_dir)
                if normalized:
                    report["cover_source"] = "local_meta"
                    return normalized
                report["cover_error"] = "LOCAL_COVER_NORMALIZE_FAILED"

        normalized = self._normalize_remote_cover(cover_url, work_dir, report)
        if normalized:
            report["cover_source"] = "downloaded"
        return normalized

    def _normalize_remote_cover(
        self, cover_url: str, work_dir: str, report: Dict[str, Any]
    ) -> Optional[bytes]:
        if not cover_url:
            report["cover_error"] = report.get("cover_error") or "NO_COVER_SOURCE"
            return None
        try:
            payload = self.cover_normalizer.fetch_image_bytes(cover_url)
        except Exception as exc:
            report["cover_error"] = f"COVER_DOWNLOAD_FAILED: {exc}"
            return None
        if not payload:
            report["cover_error"] = "COVER_DOWNLOAD_EMPTY"
            return None
        normalized = self._normalize_cover(payload, work_dir)
        if not normalized:
            report["cover_error"] = "COVER_NORMALIZE_FAILED"
        return normalized

    # ------------------------------------------------------------- detection
    @staticmethod
    def _detect_container(path: str) -> str:
        extension = os.path.splitext(path)[1].lower()
        if extension in (".flac", ".mp3"):
            return extension.lstrip(".")
        # decrypted payloads sometimes keep a temp name; sniff the magic bytes
        try:
            with open(path, "rb") as handle:
                header = handle.read(12)
        except OSError:
            return "unknown"
        if header.startswith(b"fLaC"):
            return "flac"
        if header.startswith(b"ID3") or header[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
            return "mp3"
        return "unknown"

    # ------------------------------------------------------------ TF card ops
    @staticmethod
    def dot_clean_directory(target: str) -> Dict[str, Any]:
        """
        Purge macOS AppleDouble (`._*`) files plus `.DS_Store` / spotlight dirs,
        then run `/usr/sbin/dot_clean -m` when available.
        """
        target = os.path.abspath(os.path.expanduser(target))
        if not os.path.isdir(target):
            raise FileNotFoundError(f"目录不存在: {target}")

        removed_files = 0
        removed_dirs = 0
        ghost_dirs = {".Spotlight-V100", ".Trashes", ".fseventsd"}

        for root, dirs, files in os.walk(target, topdown=True):
            for name in list(files):
                if name.startswith("._") or name == ".DS_Store":
                    try:
                        os.remove(os.path.join(root, name))
                        removed_files += 1
                    except OSError:
                        pass
            for name in list(dirs):
                if name in ghost_dirs:
                    try:
                        shutil.rmtree(os.path.join(root, name), ignore_errors=True)
                        removed_dirs += 1
                    except OSError:
                        pass
                    dirs.remove(name)

        dot_clean_status = "skipped"
        dot_clean_binary = "/usr/sbin/dot_clean"
        if sys.platform == "darwin" and os.path.exists(dot_clean_binary):
            result = subprocess.run(
                [dot_clean_binary, "-m", target],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            dot_clean_status = "ok" if result.returncode == 0 else (result.stderr.strip() or "failed")

        return {
            "target": target,
            "removed_files": removed_files,
            "removed_dirs": removed_dirs,
            "dot_clean": dot_clean_status,
        }

    @staticmethod
    def fat_sort_directory(target: str, staging_name: str = ".echo_fat_sort_tmp") -> Dict[str, Any]:
        """
        Rebuild FAT32 directory entries in `01..N` order.

        On FAT32 a directory is an ordered table of 32-byte entries; embedded
        players that iterate it literally play tracks in slot order. This helper
        moves every file of a directory to a staging area and moves it back in
        sorted order, so the driver allocates fresh slots sequentially. It is a
        best-effort reordering: the filesystem driver still owns the final table.
        """
        target = os.path.abspath(os.path.expanduser(target))
        if not os.path.isdir(target):
            raise FileNotFoundError(f"目录不存在: {target}")

        staging_root = os.path.join(target, staging_name)
        os.makedirs(staging_root, exist_ok=True)

        processed_dirs = 0
        reordered_files = 0
        try:
            for root, dirs, files in os.walk(target, topdown=True):
                if root == staging_root or root.startswith(staging_root + os.sep):
                    dirs[:] = []
                    continue
                dirs[:] = sorted(
                    name for name in dirs
                    if not name.startswith("._") and name != os.path.basename(staging_root)
                )

                candidates = sorted(
                    name for name in files
                    if not name.startswith("._") and name != ".DS_Store"
                )
                if not candidates:
                    continue

                bucket = os.path.join(staging_root, uuid.uuid4().hex[:10])
                os.makedirs(bucket, exist_ok=True)
                for name in candidates:
                    os.replace(os.path.join(root, name), os.path.join(bucket, name))
                for name in sorted(candidates):
                    os.replace(os.path.join(bucket, name), os.path.join(root, name))
                    reordered_files += 1
                try:
                    os.rmdir(bucket)
                except OSError:
                    pass
                processed_dirs += 1
        finally:
            shutil.rmtree(staging_root, ignore_errors=True)

        return {
            "target": target,
            "directories_processed": processed_dirs,
            "files_reordered": reordered_files,
        }

    # ---------------------------------------------------------------- manifest
    @staticmethod
    def write_echo_library_json(library_root: str, collections: List[Dict[str, Any]]) -> str:
        """Write the standardized `echo_library.json` manifest into `library_root`."""
        os.makedirs(library_root, exist_ok=True)
        manifest_path = os.path.join(library_root, "echo_library.json")

        total_tracks = sum(len(item.get("tracks", [])) for item in collections)
        data = {
            "schema_version": "1.1.0",
            "library_root": library_root,
            "target_profile": "SNOWSKY_FIIO_ECHO",
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "total_tracks": total_tracks,
            "collections": collections,
        }

        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)

        return manifest_path
