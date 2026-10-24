#!/usr/bin/env python3
"""
LRC Sanitizer Module
Aligned with FiiO Echo Hardware Specification:
1. Strips NetEase Cloud Music JSON word-level metadata blocks ({"t":1234,"c":[...]}).
2. Formats all timestamps strictly into standard [mm:ss.xx] 2-digit fraction.
3. Enforces UTF-8 BOM (utf-8-sig) encoding and CRLF (\\r\\n) line endings for hardware DAP compatibility.
4. Normalizes unicode characters into Unicode NFC.
"""

import re
import json
import unicodedata
from typing import Tuple, List, Optional


class LrcSanitizer:
    """Sanitizes raw lyrics into strict hardware-compliant LRC files."""

    TS_PATTERN = re.compile(r"^\[(\d{1,2}):(\d{2})(?:\.(\d+))?\](.*)$")

    @classmethod
    def sanitize_text(cls, raw_content: str) -> str:
        """
        Takes raw LRC or NetEase lyric string and returns standardized [mm:ss.xx] CRLF text.
        """
        if not raw_content:
            return ""

        cleaned_lines: List[str] = []

        for line in raw_content.splitlines():
            line = unicodedata.normalize("NFC", line.strip())
            if not line:
                continue

            # 1. Convert NetEase JSON metadata lines
            # Example: {"t":1234,"c":[{"tx":"作词 : Frank Ocean"}]}
            if line.startswith("{") and '"t":' in line:
                try:
                    obj = json.loads(line)
                    t_ms = obj.get("t", 0)
                    m = int(t_ms // 60000)
                    s = (t_ms % 60000) / 1000.0
                    text = "".join([item.get("tx", "") for item in obj.get("c", [])])
                    cleaned_lines.append(f"[{m:02d}:{s:05.2f}]{text}")
                    continue
                except Exception:
                    pass

            # 2. Standardize timestamp lines to [mm:ss.xx]
            match = cls.TS_PATTERN.match(line)
            if match:
                m = int(match.group(1))
                s = int(match.group(2))
                ms_str = match.group(3)
                rest = match.group(4)
                if ms_str:
                    # Keep exactly 2 decimal digits for hardware player alignment
                    ms = int(ms_str[:2]) if len(ms_str) >= 2 else int(ms_str.ljust(2, "0"))
                    cleaned_lines.append(f"[{m:02d}:{s:02d}.{ms:02d}]{rest}")
                else:
                    cleaned_lines.append(f"[{m:02d}:{s:02d}.00]{rest}")
            else:
                cleaned_lines.append(line)

        if not cleaned_lines:
            return ""

        # Hardware DAP standard: CRLF with final newline
        return "\r\n".join(cleaned_lines) + "\r\n"

    @classmethod
    def sanitize_file(cls, src_path: str, dest_path: str) -> Tuple[bool, str]:
        """
        Reads raw LRC file from src_path, sanitizes it, and writes compliant UTF-8 BOM to dest_path.
        """
        try:
            with open(src_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_text = f.read()

            cleaned = cls.sanitize_text(raw_text)

            # Write with UTF-8 BOM (utf-8-sig) and CRLF
            with open(dest_path, "w", encoding="utf-8-sig", newline="") as f:
                f.write(cleaned)

            return True, f"Sanitized LRC saved to {dest_path}"
        except Exception as e:
            return False, f"Failed to sanitize LRC: {e}"
