#!/usr/bin/env python3
"""
FLAC Hardware Frame Reframer Module
Aligned with FiiO Echo Hardware Specification:
1. Detects FLAC STREAMINFO block: if max_blocksize > 4096 (e.g. NetEase 8192), hardware DAC/decoder
   fails with "File format not supported".
2. Reframes audio stream to standard frame_size 4096 using ffmpeg.
3. 100% preserves original bit depth (16/24-bit) and sample rate (44.1k ~ 192kHz) with zero PCM loss.
"""

import os
import shutil
import subprocess
from typing import Tuple, Optional
from mutagen.flac import FLAC
from engine.core.bin_resolver import get_ffmpeg_path


class FlacReframer:
    """Inspects and reframes FLAC streams to frame_size <= 4096."""

    SAFE_MAX_BLOCKSIZE = 4096

    def __init__(self, ffmpeg_bin: Optional[str] = None):
        self.ffmpeg_bin = ffmpeg_bin or get_ffmpeg_path()

    def inspect_flac(self, flac_path: str) -> Tuple[bool, int, int, int]:
        """
        Inspects FLAC metadata.
        Returns: (needs_reframe: bool, max_blocksize: int, sample_rate: int, bits_per_sample: int)
        """
        audio = FLAC(flac_path)
        blocksize = audio.info.max_blocksize
        sample_rate = audio.info.sample_rate
        bits_per_sample = audio.info.bits_per_sample
        needs_reframe = (blocksize > self.SAFE_MAX_BLOCKSIZE)
        return needs_reframe, blocksize, sample_rate, bits_per_sample

    def reframe_audio_stream(self, src_path: str, dest_path: str) -> Tuple[bool, str]:
        """
        Reframes FLAC audio stream to frame_size 4096.
        Keeps 100% exact PCM fidelity.
        """
        if not os.path.exists(src_path):
            return False, f"Source file does not exist: {src_path}"

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        # ffmpeg: -c:a flac -frame_size 4096, strip video/pictures (-vn) so picture blocks can be managed cleanly
        cmd = [
            self.ffmpeg_bin, "-y",
            "-i", src_path,
            "-vn",
            "-c:a", "flac",
            "-frame_size", str(self.SAFE_MAX_BLOCKSIZE),
            dest_path
        ]

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Verify new file
            verified = FLAC(dest_path)
            if verified.info.max_blocksize > self.SAFE_MAX_BLOCKSIZE:
                return False, f"Verification failed: blocksize still {verified.info.max_blocksize}"
            return True, f"Reframed blocksize to {verified.info.max_blocksize}"
        except subprocess.CalledProcessError as e:
            return False, f"ffmpeg reframing error: exit code {e.returncode}"
        except Exception as e:
            return False, f"Reframing exception: {e}"
