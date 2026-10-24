#!/usr/bin/env python3
"""
LRC Sanitizer Module
Aligned with FiiO Echo Hardware Specification:
1. Strips NetEase Cloud Music JSON word-level metadata blocks ({"t":1234,"c":[...]}).
2. Formats all timestamps strictly into standard [mm:ss.xx] 2-digit fraction.
3. Writes UTF-8 **without BOM** by default plus CRLF (\\r\\n) line endings, because
   several embedded lyric parsers treat a BOM as part of the first timestamp.
   Set ``FIIO_LRC_BOM=1`` to prepend a BOM when a specific player needs it.
4. Normalizes unicode characters into Unicode NFC.
"""

import codecs
import json
import os
import re
import unicodedata
from typing import List, Optional, Tuple

_BOMS = (
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
)


class LrcSanitizer:
    """Sanitizes raw lyrics into strict hardware-compliant LRC files."""

    TS_PATTERN = re.compile(r"^\[(\d{1,2}):(\d{2})(?:[.:](\d+))?\](.*)$")
    JSON_LINE_MARKERS = ('"t":', '"t": ')

    @classmethod
    def bom_enabled(cls, override: Optional[bool] = None) -> bool:
        """Resolve whether to write a UTF-8 BOM (explicit arg > env var > off)."""
        if override is not None:
            return override
        return os.environ.get("FIIO_LRC_BOM", "").strip().lower() in ("1", "true", "yes", "on")

    # ------------------------------------------------------------------ text
    @classmethod
    def sanitize_text(cls, raw_content: str) -> str:
        """
        Take raw LRC or a NetEase lyric string and return standardized
        `[mm:ss.xx]` text with CRLF line endings.
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
            if line.startswith("{") and any(marker in line for marker in cls.JSON_LINE_MARKERS):
                try:
                    payload = json.loads(line)
                    milliseconds = int(payload.get("t", 0) or 0)
                    minutes = milliseconds // 60000
                    seconds = (milliseconds % 60000) / 1000.0
                    text = "".join(
                        str(item.get("tx", "")) for item in payload.get("c", []) if isinstance(item, dict)
                    )
                    cleaned_lines.append(f"[{minutes:02d}:{seconds:05.2f}]{text}")
                    continue
                except (ValueError, TypeError):
                    pass

            # 2. Standardize timestamp lines to [mm:ss.xx]
            match = cls.TS_PATTERN.match(line)
            if match:
                minutes = int(match.group(1))
                seconds = int(match.group(2))
                fraction = match.group(3)
                rest = match.group(4)
                if fraction:
                    # Hardware players expect exactly two centisecond digits.
                    centis = int(fraction[:2]) if len(fraction) >= 2 else int(fraction.ljust(2, "0"))
                else:
                    centis = 0
                cleaned_lines.append(f"[{minutes:02d}:{seconds:02d}.{centis:02d}]{rest}")
            else:
                cleaned_lines.append(line)

        if not cleaned_lines:
            return ""

        return "\r\n".join(cleaned_lines) + "\r\n"

    # ------------------------------------------------------------------ files
    @staticmethod
    def read_text(path: str) -> str:
        """Read an LRC file, tolerating BOMs and GBK/GB18030 encoded files."""
        with open(path, "rb") as handle:
            payload = handle.read()

        for bom, encoding in _BOMS:
            if payload.startswith(bom):
                return payload.decode(encoding, errors="replace")

        for encoding in ("utf-8", "gb18030", "big5"):
            try:
                return payload.decode(encoding)
            except UnicodeDecodeError:
                continue
        return payload.decode("utf-8", errors="ignore")

    @classmethod
    def sanitize_file(
        cls, src_path: str, dest_path: str, bom: Optional[bool] = None
    ) -> Tuple[bool, str]:
        """Sanitize `src_path` and write the result to `dest_path`."""
        try:
            raw_text = cls.read_text(src_path)
            cleaned = cls.sanitize_text(raw_text)
            encoding = "utf-8-sig" if cls.bom_enabled(bom) else "utf-8"

            os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
            with open(dest_path, "w", encoding=encoding, newline="") as handle:
                handle.write(cleaned)

            return True, f"Sanitized LRC saved to {dest_path}"
        except Exception as exc:
            return False, f"Failed to sanitize LRC: {exc}"
