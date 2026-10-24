#!/usr/bin/env python3
"""
Cover Art Normalizer Module
Aligned with FiiO Echo Hardware Specification:
1. Standard resolution: exactly 500x500 pixels (aspect ratio preserved, black padded).
2. Encoding: Baseline JPEG (progressive JPEG and PNG/GIF/WEBP prohibited).
3. Chroma Subsampling: strictly YUV 4:2:0 (yuvj420p). 4:4:4 freezes the player UI.
4. Embedded picture block: Type 3 (Cover Front) only, every other block purged.

Compliance decisions are delegated to :mod:`engine.core.inspector`, which parses
the real picture bytes instead of trusting (often 0x0) FLAC picture metadata.
"""

from __future__ import annotations

import os
import subprocess
import urllib.error
import urllib.request
from typing import Dict, Optional, Tuple

from mutagen.flac import FLAC, Picture

from engine.core.bin_resolver import get_ffmpeg_path
from engine.core.inspector import AudioInspector, image_info, TARGET_COVER


class CoverNormalizer:
    """Inspects and converts album art to FiiO Echo compliant Baseline JPEG (YUV 4:2:0)."""

    TARGET_WIDTH = TARGET_COVER
    TARGET_HEIGHT = TARGET_COVER
    MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024

    def __init__(self, ffmpeg_bin: Optional[str] = None):
        self.ffmpeg_bin = ffmpeg_bin or get_ffmpeg_path()
        self.inspector = AudioInspector()

    # ------------------------------------------------------------------ inspect
    @staticmethod
    def inspect_jpeg_chroma_420(data: bytes) -> bool:
        """True when `data` is a baseline JPEG with 4:2:0 chroma subsampling."""
        info = image_info(data)
        return bool(
            info.get("format") == "jpeg"
            and not info.get("progressive")
            and info.get("subsampling") == "4:2:0"
        )

    def assess_flac_cover(self, flac_path: str) -> Tuple[bool, Dict, Optional[bytes]]:
        """
        Return `(is_compliant, cover_info, picture_bytes)` for an embedded FLAC cover.

        `picture_bytes` is `None` when the file carries no picture at all, and
        `cover_info["compliant"]` is always `False` in that case.
        """
        audio = FLAC(flac_path)
        pictures = audio.pictures or []
        if not pictures:
            return False, {"present": False, "compliant": False, "reasons": ["NO_COVER"]}, None

        info = self.inspector.inspect(flac_path)["cover"]
        return bool(info.get("compliant")), info, pictures[0].data

    def is_flac_cover_compliant(self, flac_path: str) -> Tuple[bool, str]:
        """Backwards-compatible helper: `(compliant, reason)`."""
        audio = FLAC(flac_path)
        if not audio.pictures:
            return True, "NO_COVER"  # nothing embedded, nothing to normalize
        info = self.inspector.inspect(flac_path)["cover"]
        if info.get("compliant"):
            return True, "COMPLIANT"
        return False, ",".join(info.get("reasons") or ["NOT_COMPLIANT"])

    # ----------------------------------------------------------------- convert
    def normalize_image_bytes(self, raw_bytes: bytes, staging_dir: str) -> bytes:
        """Scale + transcode any image bytes into a 500x500 baseline JPEG (yuvj420p)."""
        os.makedirs(staging_dir, exist_ok=True)
        raw_in = os.path.join(staging_dir, "__temp_raw_cover.bin")
        jpg_out = os.path.join(staging_dir, "__temp_norm_cover.jpg")

        with open(raw_in, "wb") as handle:
            handle.write(raw_bytes)

        command = [
            self.ffmpeg_bin, "-y",
            "-i", raw_in,
            "-frames:v", "1",
            "-vf",
            "scale=500:500:force_original_aspect_ratio=decrease,"
            "pad=500:500:(ow-iw)/2:(oh-ih)/2:black",
            "-pix_fmt", "yuvj420p",
            "-q:v", "2",
            jpg_out,
        ]
        try:
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            with open(jpg_out, "rb") as handle:
                normalized = handle.read()
        finally:
            for temporary in (raw_in, jpg_out):
                if os.path.exists(temporary):
                    try:
                        os.remove(temporary)
                    except OSError:
                        pass

        if not self.inspect_jpeg_chroma_420(normalized):
            raise ValueError("normalized cover failed the 4:2:0 baseline check")
        return normalized

    def fetch_image_bytes(self, url: str, timeout: int = 20) -> Optional[bytes]:
        """
        Download cover art referenced by the NetEase database (`picUrl`).

        Network failures must never fail a build, so callers treat `None` as
        "no cover available" and continue.
        """
        if not url or not url.lower().startswith(("http://", "https://")):
            return None

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
                ),
                "Referer": "https://music.163.com/",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read(self.MAX_DOWNLOAD_BYTES + 1)
        except (urllib.error.URLError, OSError, ValueError):
            return None

        if not payload or len(payload) > self.MAX_DOWNLOAD_BYTES:
            return None
        return payload

    def embed_normalized_cover(self, flac_path: str, norm_cover_bytes: bytes) -> bool:
        """Embed bytes as the single Type 3 (Cover Front) picture block."""
        audio = FLAC(flac_path)
        audio.clear_pictures()

        picture = Picture()
        picture.type = 3
        picture.mime = "image/jpeg"
        picture.desc = "Front Cover"
        picture.width = self.TARGET_WIDTH
        picture.height = self.TARGET_HEIGHT
        picture.depth = 24
        picture.data = norm_cover_bytes

        audio.add_picture(picture)
        audio.save()
        return True
