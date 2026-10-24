#!/usr/bin/env python3
"""
Pipeline Orchestrator Module
Coordinates:
1. Source Ingest / NCM Decryption
2. FLAC Stream Frame Reframing (frame_size <= 4096)
3. Cover Art Normalization (500x500 YUV 4:2:0 Baseline JPEG, Type 3)
4. Companion LRC Cleaning ([mm:ss.xx] UTF-8 CRLF)
5. Structured Local Library Placement & Registry Generation (echo_library.json)
"""

import os
import json
import time
import shutil
import unicodedata
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from mutagen.flac import FLAC
from engine.core.ncm_decryptor import NcmDecryptor
from engine.core.flac_reframer import FlacReframer
from engine.core.cover_normalizer import CoverNormalizer
from engine.core.lrc_sanitizer import LrcSanitizer


class PipelineOrchestrator:
    """End-to-end normalization and local library builder."""

    def __init__(self, staging_dir: str = "/tmp/echo_studio_staging"):
        self.staging_dir = staging_dir
        self.ncm_decryptor = NcmDecryptor()
        self.flac_reframer = FlacReframer()
        self.cover_normalizer = CoverNormalizer()
        self.lrc_sanitizer = LrcSanitizer()

    def process_track(
        self,
        src_audio_path: str,
        dest_audio_path: str,
        src_lrc_path: Optional[str] = None,
        dest_lrc_path: Optional[str] = None,
        meta_override: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Takes raw audio/ncm file and optional lrc, performs full compliance pipeline,
        and saves standardized files to dest_audio_path and dest_lrc_path.
        """
        os.makedirs(self.staging_dir, exist_ok=True)
        item_id = str(time.time_ns())
        tmp_dir = os.path.join(self.staging_dir, item_id)
        os.makedirs(tmp_dir, exist_ok=True)

        report = {
            "decrypted": False,
            "reframed_audio": False,
            "normalized_cover": False,
            "sanitized_lrc": False,
            "error": None
        }

        try:
            # Step 1: Decode/Decrypt if NCM
            cur_audio = src_audio_path
            if src_audio_path.lower().endswith(".ncm"):
                ok, dec_path, msg = self.ncm_decryptor.decrypt(src_audio_path, tmp_dir)
                if not ok:
                    report["error"] = f"NCM Decryption failed: {msg}"
                    return False, report
                cur_audio = dec_path
                report["decrypted"] = True

            # If not FLAC (e.g. MP3), just copy to destination directly
            ext = os.path.splitext(cur_audio)[1].lower()
            if ext != ".flac":
                os.makedirs(os.path.dirname(dest_audio_path), exist_ok=True)
                shutil.copyfile(cur_audio, dest_audio_path)
            else:
                # Step 2: Handle FLAC audio blocksize reframing
                audio = FLAC(cur_audio)
                needs_audio_reframe = (audio.info.max_blocksize > 4096)
                needs_cover_norm, cover_reason = self.cover_normalizer.is_flac_cover_compliant(cur_audio)
                needs_cover_norm = not needs_cover_norm

                staged_flac = os.path.join(tmp_dir, "staged_audio.flac")

                if needs_audio_reframe:
                    ok, msg = self.flac_reframer.reframe_audio_stream(cur_audio, staged_flac)
                    if not ok:
                        report["error"] = f"Audio reframing failed: {msg}"
                        return False, report
                    report["reframed_audio"] = True
                else:
                    shutil.copyfile(cur_audio, staged_flac)

                # Step 3: Handle Cover Art
                staged_audio = FLAC(staged_flac)
                if needs_cover_norm and audio.pictures:
                    raw_pic = audio.pictures[0].data
                    norm_bytes = self.cover_normalizer.normalize_image_bytes(raw_pic, tmp_dir)
                    self.cover_normalizer.embed_normalized_cover(staged_flac, norm_bytes)
                    report["normalized_cover"] = True
                elif not needs_cover_norm and audio.pictures and needs_audio_reframe:
                    # ffmpeg -vn stripped cover, re-attach original compliant cover
                    staged_audio.clear_pictures()
                    staged_audio.add_picture(audio.pictures[0])
                    staged_audio.save()

                # Apply metadata overrides if any
                if meta_override:
                    staged_audio = FLAC(staged_flac)
                    if meta_override.get("title"):
                        staged_audio["title"] = str(meta_override["title"])
                    if meta_override.get("artist"):
                        staged_audio["artist"] = str(meta_override["artist"])
                    if meta_override.get("album"):
                        staged_audio["album"] = str(meta_override["album"])
                    if meta_override.get("tracknumber"):
                        staged_audio["tracknumber"] = str(meta_override["tracknumber"])
                    staged_audio.save()

                # Step 4: Write to destination
                os.makedirs(os.path.dirname(dest_audio_path), exist_ok=True)
                shutil.copyfile(staged_flac, dest_audio_path)

            # Step 5: Handle companion LRC
            if src_lrc_path and os.path.exists(src_lrc_path) and dest_lrc_path:
                os.makedirs(os.path.dirname(dest_lrc_path), exist_ok=True)
                ok, msg = self.lrc_sanitizer.sanitize_file(src_lrc_path, dest_lrc_path)
                if ok:
                    report["sanitized_lrc"] = True

            return True, report

        except Exception as e:
            report["error"] = str(e)
            return False, report
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @staticmethod
    def write_echo_library_json(library_root: str, collections: List[Dict[str, Any]]) -> str:
        """
        Writes standardized echo_library.json manifest in library_root.
        """
        os.makedirs(library_root, exist_ok=True)
        manifest_path = os.path.join(library_root, "echo_library.json")

        total_tracks = sum(len(c.get("tracks", [])) for c in collections)
        data = {
            "schema_version": "1.0.0",
            "library_root": library_root,
            "target_profile": "SNOWSKY_FIIO_ECHO",
            "updated_at": datetime.now().isoformat(),
            "total_tracks": total_tracks,
            "collections": collections
        }

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return manifest_path
