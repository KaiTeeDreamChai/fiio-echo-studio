#!/usr/bin/env python3
"""
FAT32 / exFAT Safe Naming Helpers
Aligned with FiiO Echo Hardware Specification:

Portable players mount microSD cards formatted as FAT32/exFAT. Those filesystems
forbid  \\ / : * ? " < > |  and silently truncate long names. macOS happily
creates such names, so every path written to the player card must be sanitized
before it reaches the filesystem.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Set

#: Characters FAT32/exFAT rejects, mapped to visually identical full-width forms.
FORBIDDEN_MAP = {
    "/": "／",
    "\\": "＼",
    ":": "：",
    "*": "＊",
    "?": "？",
    '"': "＂",
    "<": "＜",
    ">": "＞",
    "|": "｜",
}

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_WHITESPACE_RE = re.compile(r"\s+")

_DOS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *{f"COM{i}" for i in range(1, 10)},
    *{f"LPT{i}" for i in range(1, 10)},
}


def _truncate_bytes(text: str, max_bytes: int) -> str:
    """Truncate a string without splitting a multi-byte UTF-8 sequence."""
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text
    truncated = raw[:max_bytes]
    while truncated:
        try:
            return truncated.decode("utf-8")
        except UnicodeDecodeError:
            truncated = truncated[:-1]
    return ""


def sanitize_filename(name: str, *, max_bytes: int = 200, fallback: str = "Untitled") -> str:
    """
    Return a FAT32-safe single path component.

    - normalizes to Unicode NFC
    - replaces forbidden characters with full-width equivalents
    - strips control characters, collapses whitespace
    - strips leading/trailing dots and spaces (invalid on FAT32)
    - guards against DOS device names and over-long names
    """
    text = unicodedata.normalize("NFC", str(name or ""))
    text = _CONTROL_RE.sub("", text)
    for bad, good in FORBIDDEN_MAP.items():
        text = text.replace(bad, good)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    text = text.strip(" .")

    if not text:
        text = fallback
    if text.split(".")[0].upper() in _DOS_RESERVED:
        text = f"_{text}"

    text = _truncate_bytes(text, max_bytes).strip(" .")
    return text or fallback


def sanitize_relative_dir(relative: str, *, default: str = "Albums/Unknown") -> str:
    """
    Normalize a user-supplied relative folder (`Albums/Blonde`) into safe segments.

    Absolute paths, `.` and `..` segments are dropped so a malformed request can
    never escape the configured library root.
    """
    raw = str(relative or "").replace("\\", "/")
    parts = []
    for segment in raw.split("/"):
        segment = segment.strip()
        if not segment or segment in (".", ".."):
            continue
        parts.append(sanitize_filename(segment, max_bytes=80))
    return "/".join(parts) or default


def build_dest_stem(seq: str, artist: str, title: str) -> str:
    """Canonical `NN Artist - Title` stem (FAT32-safe, extension excluded)."""
    seq_text = str(seq or "").strip() or "01"
    if seq_text.isdigit():
        seq_text = seq_text.zfill(2)
    raw = f"{seq_text} {artist or 'Unknown'} - {title or 'Unknown'}"
    return sanitize_filename(raw, max_bytes=180, fallback=f"{seq_text} Unknown - Unknown")


def make_unique(stem: str, used: Set[str]) -> str:
    """Append ` (2)`, ` (3)` … when two different tracks would collide on disk."""
    candidate = stem
    index = 2
    while candidate.lower() in used:
        candidate = f"{stem} ({index})"
        index += 1
    used.add(candidate.lower())
    return candidate
