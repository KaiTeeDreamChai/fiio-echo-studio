#!/usr/bin/env python3
"""
Cover Art Normalizer Module
Aligned with FiiO Echo Hardware Specification:
1. Standard resolution: 500x500 pixels (aspect ratio maintained, padded with black if necessary).
2. Encoding: Baseline JPEG (progressive JPEG and non-standard PNGs prohibited).
3. Chroma Subsampling: Strictly YUV 4:2:0 (yuvj420p). YUV 4:4:4 prohibited to prevent display freezing.
4. Embedded FLAC Picture Block: Type 3 (Cover Front) only. All other picture blocks purged.
"""

import os
import shutil
import struct
import subprocess
from typing import Optional, Tuple
from mutagen.flac import FLAC, Picture
from engine.core.bin_resolver import get_ffmpeg_path


class CoverNormalizer:
    """Inspects and converts album art to FiiO Echo compliant Baseline JPEG (YUV 4:2:0)."""

    TARGET_WIDTH = 500
    TARGET_HEIGHT = 500
    MAX_ALLOWABLE_DIM = 600

    def __init__(self, ffmpeg_bin: Optional[str] = None):
        self.ffmpeg_bin = ffmpeg_bin or get_ffmpeg_path()

    @staticmethod
    def inspect_jpeg_chroma_420(data: bytes) -> bool:
        """
        Parses JPEG SOF marker to check if chroma subsampling is 4:2:0.
        For 4:2:0: Y component sampling factor is 0x22 (H=2, V=2), Cb=0x11, Cr=0x11.
        For 4:4:4: Y component is 0x11.
        """
        if not data.startswith(b"\xff\xd8"):
            return False  # Not JPEG

        try:
            i = 2
            data_len = len(data)
            while i < data_len - 4:
                if data[i] != 0xff:
                    i += 1
                    continue
                marker = data[i + 1]
                # SOF0 (Baseline), SOF1 (Extended), SOF2 (Progressive)
                if marker in (0xc0, 0xc1, 0xc2):
                    if marker == 0xc2:
                        return False  # Progressive JPEG is prohibited
                    num_components = data[i + 9]
                    if num_components == 3:
                        y_sampling = data[i + 11]
                        return (y_sampling == 0x22)
                    break
                elif marker in (0xd9, 0xda):
                    break
                elif marker in (0xd0, 0xd1, 0xd2, 0xd3, 0xd4, 0xd5, 0xd6, 0xd7):
                    i += 2
                else:
                    seg_len = int.from_bytes(data[i + 2:i + 4], "big")
                    i += 2 + seg_len
        except Exception:
            return False
        return False

    def is_flac_cover_compliant(self, flac_path: str) -> Tuple[bool, str]:
        """
        Checks whether the embedded FLAC cover complies with hardware specs.
        Returns (is_compliant, reason).
        """
        try:
            audio = FLAC(flac_path)
            if not audio.pictures:
                return True, "NO_COVER"  # No picture to normalize

            if len(audio.pictures) > 1:
                return False, f"MULTIPLE_PICTURES ({len(audio.pictures)})"

            pic = audio.pictures[0]
            if pic.type != 3:
                return False, f"INVALID_TYPE ({pic.type} != 3)"

            if pic.width == 0 or pic.height == 0:
                return False, "UNKNOWN_DIMENSIONS"

            if pic.width > self.MAX_ALLOWABLE_DIM or pic.height > self.MAX_ALLOWABLE_DIM:
                return False, f"DIMENSION_OVERFLOW ({pic.width}x{pic.height} > {self.MAX_ALLOWABLE_DIM})"

            if not self.inspect_jpeg_chroma_420(pic.data):
                return False, "NOT_YUV420P_OR_PROGRESSIVE"

            return True, "COMPLIANT"
        except Exception as e:
            return False, f"READ_ERROR: {e}"

    def normalize_image_bytes(self, raw_bytes: bytes, staging_dir: str) -> bytes:
        """
        Scales and transcodes any raw image bytes into 500x500 Baseline JPEG with YUV 4:2:0 subsampling.
        """
        os.makedirs(staging_dir, exist_ok=True)
        raw_in = os.path.join(staging_dir, "__temp_raw_cover.bin")
        jpg_out = os.path.join(staging_dir, "__temp_norm_cover.jpg")

        with open(raw_in, "wb") as f:
            f.write(raw_bytes)

        # Scale with black pad to preserve aspect ratio, force yuvj420p baseline
        cmd = [
            self.ffmpeg_bin, "-y",
            "-i", raw_in,
            "-vf", "scale=500:500:force_original_aspect_ratio=decrease,pad=500:500:(ow-iw)/2:(oh-ih)/2:black",
            "-pix_fmt", "yuvj420p",
            "-q:v", "2",
            jpg_out
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        with open(jpg_out, "rb") as f:
            norm_bytes = f.read()

        for tmp in (raw_in, jpg_out):
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass

        return norm_bytes

    def embed_normalized_cover(self, flac_path: str, norm_cover_bytes: bytes) -> bool:
        """
        Embeds the compliant cover bytes as Type 3 (Cover Front) and clears any other pictures.
        """
        try:
            audio = FLAC(flac_path)
            audio.clear_pictures()

            pic = Picture()
            pic.type = 3  # Cover (front)
            pic.mime = "image/jpeg"
            pic.desc = "Front Cover"
            pic.width = self.TARGET_WIDTH
            pic.height = self.TARGET_HEIGHT
            pic.depth = 24
            pic.data = norm_cover_bytes

            audio.add_picture(pic)
            audio.save()
            return True
        except Exception:
            return False
