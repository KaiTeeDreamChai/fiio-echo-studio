#!/usr/bin/env python3
"""
NCM Decryptor Module
Decrypts NetEase Cloud Music private format (.ncm) to standard .flac or .mp3.
Extracts embedded metadata and cover artwork.
"""

import os
import shutil
import subprocess
from typing import Tuple, Optional
from engine.core.bin_resolver import get_ncmdump_path


class NcmDecryptor:
    """Wrapper and executor for decrypting .ncm files to standard lossless/lossy formats."""

    def __init__(self, ncmdump_bin: Optional[str] = None):
        self.ncmdump_bin = ncmdump_bin or get_ncmdump_path()

    def decrypt(self, ncm_file: str, dest_dir: str) -> Tuple[bool, str, str]:
        """
        Decrypts an .ncm file into dest_dir.
        Returns: (success: bool, output_file_path: str, message: str)
        """
        if not os.path.exists(ncm_file):
            return False, "", f"Source file does not exist: {ncm_file}"

        if not self.ncmdump_bin or not os.path.exists(self.ncmdump_bin):
            return False, "", f"ncmdump binary not found at: {self.ncmdump_bin}"

        os.makedirs(dest_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(ncm_file))[0]
        candidate_flac = os.path.join(dest_dir, f"{base_name}.flac")
        candidate_mp3 = os.path.join(dest_dir, f"{base_name}.mp3")

        # Skip if already exists and valid
        if os.path.exists(candidate_flac) and os.path.getsize(candidate_flac) > 0:
            return True, candidate_flac, f"Cached FLAC: {os.path.basename(candidate_flac)}"
        if os.path.exists(candidate_mp3) and os.path.getsize(candidate_mp3) > 0:
            return True, candidate_mp3, f"Cached MP3: {os.path.basename(candidate_mp3)}"

        cmd = [self.ncmdump_bin, "-o", dest_dir, ncm_file]
        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

            if os.path.exists(candidate_flac):
                return True, candidate_flac, "Decrypted to FLAC"
            elif os.path.exists(candidate_mp3):
                return True, candidate_mp3, "Decrypted to MP3"
            else:
                # Find any newly generated file matching base_name
                for f in os.listdir(dest_dir):
                    if f.startswith(base_name) and not f.endswith(".ncm"):
                        return True, os.path.join(dest_dir, f), f"Decrypted: {f}"
                return False, "", "Decryption succeeded but output file not found in destination"
        except subprocess.CalledProcessError as e:
            return False, "", f"ncmdump execution failed: code {e.returncode}"
        except Exception as e:
            return False, "", f"ncmdump error: {e}"
