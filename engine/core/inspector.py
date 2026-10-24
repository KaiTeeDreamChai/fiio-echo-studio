#!/usr/bin/env python3
"""
Read-only Audio Inspector
Aligned with FiiO Echo Hardware Specification:

The workbench must never invent numbers. Every BLOCK / PCM / COVER value shown
in the UI comes from this module, which reads container headers and embedded
picture bytes without decoding audio.

Encrypted `.ncm` containers cannot be inspected without decryption, so they are
reported as `encrypted: True` and every field stays `None` (the UI must render
them as "待解密" instead of guessing).
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from mutagen.flac import FLAC
from mutagen.id3 import ID3, ID3NoHeaderError
from mutagen.mp3 import MP3

TARGET_BLOCK = 4096
TARGET_COVER = 500
TARGET_SUBSAMPLING = "4:2:0"


def _classify_subsampling(h: int, v: int) -> str:
    """Translate JPEG sampling factors into the usual `4:x:y` notation."""
    if h == 1 and v == 1:
        return "4:4:4"
    if h == 2 and v == 2:
        return "4:2:0"
    if h == 2 and v == 1:
        return "4:2:2"
    if h == 4 and v == 1:
        return "4:1:1"
    if h == 1 and v == 2:
        return "4:4:0"
    return f"{h}x{v}"


_SOF_MARKERS = {
    0xC0: ("baseline", False),
    0xC1: ("extended", False),
    0xC2: ("progressive", True),
    0xC3: ("lossless", False),
    0xC5: ("differential", False),
    0xC6: ("differential-progressive", True),
    0xC7: ("differential-lossless", False),
    0xC9: ("arithmetic", False),
    0xCA: ("arithmetic-progressive", True),
    0xCB: ("arithmetic-lossless", False),
    0xCD: ("differential-arithmetic", False),
    0xCE: ("differential-arithmetic-progressive", True),
    0xCF: ("differential-arithmetic-lossless", False),
}


def _jpeg_info(data: bytes) -> Optional[Dict[str, Any]]:
    """Walk JPEG segments and read SOF dimensions / sampling without decoding."""
    if not data.startswith(b"\xff\xd8"):
        return None
    index = 2
    size = len(data)
    while index + 9 < size:
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        if marker == 0xFF:  # fill byte
            index += 1
            continue
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            index += 2
            continue
        if marker == 0xD9:  # end of image, no SOF seen
            break

        segment_length = int.from_bytes(data[index + 2:index + 4], "big")
        if segment_length < 2:
            break

        if marker in _SOF_MARKERS:
            mode, progressive = _SOF_MARKERS[marker]
            height = int.from_bytes(data[index + 5:index + 7], "big")
            width = int.from_bytes(data[index + 7:index + 9], "big")
            components = data[index + 9] if index + 9 < size else 0
            sampling = data[index + 11] if components and index + 11 < size else 0x11
            h = (sampling >> 4) & 0x0F or 1
            v = sampling & 0x0F or 1
            return {
                "format": "jpeg",
                "width": width,
                "height": height,
                "components": components,
                "mode": mode,
                "progressive": progressive,
                "subsampling": _classify_subsampling(h, v) if components == 3 else None,
            }

        index += 2 + segment_length
    return None


def image_info(data: bytes) -> Dict[str, Any]:
    """Return dimensions / encoding details for embedded cover bytes."""
    empty = {
        "format": None,
        "width": None,
        "height": None,
        "progressive": None,
        "subsampling": None,
        "mode": None,
    }
    if not data:
        return empty

    if data.startswith(b"\xff\xd8"):
        info = _jpeg_info(data)
        return info or {**empty, "format": "jpeg"}

    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) > 24:
        return {
            **empty,
            "format": "png",
            "width": int.from_bytes(data[16:20], "big"),
            "height": int.from_bytes(data[20:24], "big"),
        }

    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return {**empty, "format": "webp"}

    if data[:6] in (b"GIF87a", b"GIF89a"):
        return {
            **empty,
            "format": "gif",
            "width": int.from_bytes(data[6:8], "little"),
            "height": int.from_bytes(data[8:10], "little"),
        }

    if data.startswith(b"BM"):
        return {**empty, "format": "bmp"}

    return {**empty, "format": "unknown"}


def evaluate_cover(cover: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decide whether an embedded picture satisfies the player specification.

    A compliant picture is a single 500×500 **baseline** JPEG with 4:2:0 chroma
    subsampling, stored as Picture Type 3 (Cover Front). FLAC picture metadata
    dimensions must agree with the real bytes: some files carry 0×0 metadata,
    which makes strict players skip the artwork entirely.
    """
    reasons = []
    if not cover.get("present"):
        reasons.append("NO_COVER")
    else:
        if (cover.get("count") or 0) > 1:
            reasons.append("MULTIPLE_PICTURES")
        if cover.get("type") != 3:
            reasons.append(f"TYPE_{cover.get('type')}")
        if cover.get("format") != "jpeg":
            reasons.append(f"FORMAT_{(cover.get('format') or 'unknown').upper()}")
        if cover.get("progressive"):
            reasons.append("PROGRESSIVE_JPEG")
        if cover.get("width") != TARGET_COVER or cover.get("height") != TARGET_COVER:
            reasons.append("SIZE")
        if cover.get("components") == 3 and cover.get("subsampling") != TARGET_SUBSAMPLING:
            reasons.append("CHROMA")
        meta_w, meta_h = cover.get("meta_width"), cover.get("meta_height")
        if cover.get("meta_present") and (meta_w, meta_h) != (TARGET_COVER, TARGET_COVER):
            reasons.append("METADATA_ZERO_OR_MISMATCH")

    return {**cover, "compliant": not reasons, "reasons": reasons}


class AudioInspector:
    """Inspect local audio files without decoding audio samples."""

    def _empty(self, path: str) -> Dict[str, Any]:
        return {
            "path": path,
            "container": "unknown",
            "encrypted": False,
            "sample_rate": None,
            "bits_per_sample": None,
            "channels": None,
            "duration_sec": None,
            "block_size": None,
            "needs_reframe": None,
            "cover": evaluate_cover({
                "present": False, "count": 0, "type": None, "format": None,
                "width": None, "height": None, "meta_width": None,
                "meta_height": None, "meta_present": False,
                "progressive": None, "subsampling": None, "components": None,
            }),
            "error": None,
        }

    def inspect(self, path: str) -> Dict[str, Any]:
        result = self._empty(path)
        extension = os.path.splitext(path)[1].lower()

        if extension == ".ncm":
            result.update(container="ncm", encrypted=True)
            result["cover"] = evaluate_cover({
                "present": None, "count": None, "type": None, "format": None,
                "width": None, "height": None, "meta_width": None,
                "meta_height": None, "meta_present": False,
                "progressive": None, "subsampling": None, "components": None,
            })
            result["cover"]["reasons"] = ["ENCRYPTED"]
            return result

        if not os.path.exists(path):
            result["error"] = "FILE_NOT_FOUND"
            return result

        try:
            if extension == ".flac":
                self._inspect_flac(path, result)
            elif extension in (".mp3", ".aac", ".m4a"):
                self._inspect_mp3(path, result)
            else:
                self._inspect_unknown(path, result)
        except Exception as exc:  # corrupt headers must not break the request
            result["error"] = f"{exc.__class__.__name__}: {exc}"
        return result

    def _inspect_flac(self, path: str, result: Dict[str, Any]) -> None:
        audio = FLAC(path)
        result.update(
            container="flac",
            sample_rate=audio.info.sample_rate,
            bits_per_sample=audio.info.bits_per_sample,
            channels=audio.info.channels,
            duration_sec=round(audio.info.length, 2) if audio.info.length else None,
            block_size=audio.info.max_blocksize,
            needs_reframe=audio.info.max_blocksize > TARGET_BLOCK,
        )

        pictures = audio.pictures or []
        if not pictures:
            result["cover"] = evaluate_cover({
                "present": False, "count": 0, "type": None, "format": None,
                "width": None, "height": None, "meta_width": None,
                "meta_height": None, "meta_present": False,
                "progressive": None, "subsampling": None, "components": None,
            })
            return

        picture = pictures[0]
        info = image_info(picture.data)
        result["cover"] = evaluate_cover({
            "present": True,
            "count": len(pictures),
            "type": picture.type,
            "format": info["format"],
            "width": info["width"] or picture.width or None,
            "height": info["height"] or picture.height or None,
            "meta_width": picture.width,
            "meta_height": picture.height,
            "meta_present": True,
            "progressive": info["progressive"],
            "subsampling": info["subsampling"],
            "components": info["components"] if "components" in info else None,
            "bytes": len(picture.data),
        })

    def _inspect_mp3(self, path: str, result: Dict[str, Any]) -> None:
        audio = MP3(path)
        result.update(
            container="mp3",
            sample_rate=audio.info.sample_rate,
            bits_per_sample=None,
            channels=audio.info.channels,
            duration_sec=round(audio.info.length, 2) if audio.info.length else None,
            block_size=None,
            needs_reframe=False,
        )

        frames = []
        try:
            frames = ID3(path).getall("APIC")
        except ID3NoHeaderError:
            frames = []

        if not frames:
            result["cover"] = evaluate_cover({
                "present": False, "count": 0, "type": None, "format": None,
                "width": None, "height": None, "meta_width": None,
                "meta_height": None, "meta_present": False,
                "progressive": None, "subsampling": None, "components": None,
            })
            return

        frame = frames[0]
        info = image_info(frame.data)
        result["cover"] = evaluate_cover({
            "present": True,
            "count": len(frames),
            "type": int(frame.type),
            "format": info["format"],
            "width": info["width"],
            "height": info["height"],
            "meta_width": None,
            "meta_height": None,
            "meta_present": False,
            "progressive": info["progressive"],
            "subsampling": info["subsampling"],
            "components": info["components"] if "components" in info else None,
            "bytes": len(frame.data),
        })

    def _inspect_unknown(self, path: str, result: Dict[str, Any]) -> None:
        try:
            from mutagen import File as MutagenFile
        except Exception:
            return
        media = MutagenFile(path)
        if media is None:
            result["error"] = "UNSUPPORTED_CONTAINER"
            return
        result.update(
            container=(media.__class__.__name__ or "unknown").lower(),
            sample_rate=getattr(media.info, "sample_rate", None),
            bits_per_sample=getattr(media.info, "bits_per_sample", None),
            channels=getattr(media.info, "channels", None),
            duration_sec=round(media.info.length, 2) if getattr(media.info, "length", None) else None,
        )
