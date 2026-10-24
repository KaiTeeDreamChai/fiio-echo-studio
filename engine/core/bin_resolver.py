#!/usr/bin/env python3
"""
Binary and Bundle Path Resolver for FiiO Echo Studio.
Seamlessly handles dev workspaces, pyinstaller bundles, and standalone binaries.
"""
import os
import sys
import shutil


def get_bundle_dir() -> str:
    """Returns the base directory of the running app (supports PyInstaller sys._MEIPASS)."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return getattr(sys, '_MEIPASS')
    # When running directly from engine or repo root:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(current_dir))


def get_ffmpeg_path() -> str:
    """Returns path to static ffmpeg binary (embedded in bundle > system path)."""
    bundle_bin = os.path.join(get_bundle_dir(), "engine", "bin", "ffmpeg")
    if os.path.exists(bundle_bin) and os.access(bundle_bin, os.X_OK):
        return bundle_bin
    sys_which = shutil.which("ffmpeg")
    if sys_which:
        return sys_which
    if os.path.exists("/opt/homebrew/bin/ffmpeg"):
        return "/opt/homebrew/bin/ffmpeg"
    return "ffmpeg"


def get_ncmdump_path() -> str:
    """Returns path to static ncmdump binary (embedded in bundle > system path)."""
    bundle_bin = os.path.join(get_bundle_dir(), "engine", "bin", "ncmdump")
    if os.path.exists(bundle_bin) and os.access(bundle_bin, os.X_OK):
        return bundle_bin
    sys_which = shutil.which("ncmdump")
    if sys_which:
        return sys_which
    if os.path.exists("/opt/homebrew/bin/ncmdump"):
        return "/opt/homebrew/bin/ncmdump"
    return "ncmdump"
