#!/usr/bin/env python3
"""
Unit tests for FiiO Echo Studio core modules.

Run: python3 -m unittest discover -s engine/tests -v
"""

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from engine.core.builder import LibraryBuilder
from engine.core.inspector import AudioInspector
from engine.core.lrc_sanitizer import LrcSanitizer
from engine.core.naming import (
    build_dest_stem,
    make_unique,
    sanitize_filename,
    sanitize_relative_dir,
)
from engine.core.pipeline import PipelineOrchestrator
from engine.providers.netease_db import NetEaseDBProvider

FFMPEG = shutil.which("ffmpeg")


def _run_ffmpeg(args) -> None:
    subprocess.run(
        [FFMPEG, "-v", "error", "-y", *args],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


class NamingTests(unittest.TestCase):
    def test_forbidden_characters_are_replaced(self):
        name = sanitize_filename('Do You Like Me? / a:b *c* "d" <e> |f|')
        for illegal in '/\\:*?"<>|':
            self.assertNotIn(illegal, name)
        self.assertIn("Do You Like Me", name)

    def test_path_traversal_is_stripped(self):
        self.assertEqual(sanitize_relative_dir("../../etc/passwd"), "etc/passwd")
        self.assertEqual(sanitize_relative_dir("/Albums/../Blonde"), "Albums/Blonde")
        self.assertEqual(sanitize_relative_dir("  "), "Albums/Unknown")

    def test_long_names_are_truncated_on_utf8_boundary(self):
        name = sanitize_filename("深" * 200, max_bytes=60)
        self.assertLessEqual(len(name.encode("utf-8")), 60)
        self.assertTrue(name.startswith("深"))

    def test_dos_reserved_names(self):
        self.assertEqual(sanitize_filename("CON"), "_CON")

    def test_dest_stem_is_padded_and_unique(self):
        self.assertEqual(build_dest_stem("1", "A", "B"), "01 A - B")
        used = set()
        self.assertEqual(make_unique("01 A - B", used), "01 A - B")
        self.assertEqual(make_unique("01 A - B", used), "01 A - B (2)")


class SourceDetectionTests(unittest.TestCase):
    """Import paths must come from the machine, never from hardcoded values."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.download_dir = os.path.join(self.temp_dir, "网易云音乐")
        os.makedirs(os.path.join(self.download_dir, "meta"))
        for name in ("Artist A - Song One.ncm", "Artist B - Song Two.flac"):
            with open(os.path.join(self.download_dir, name), "wb") as handle:
                handle.write(b"x")

        self.db_path = os.path.join(self.temp_dir, "sqlite_storage.sqlite3")
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "CREATE TABLE offlineTrack (id TEXT, trackName TEXT, artistName TEXT,"
            " albumName TEXT, newRelativePath TEXT, size INTEGER, jsonStr TEXT);"
        )
        cursor.execute(
            "INSERT INTO offlineTrack VALUES ('1','Song One','Artist A','Album',"
            "'Artist A - Song One.ncm',1,NULL);"
        )
        cursor.execute(
            "INSERT INTO offlineTrack VALUES ('2','Song Two','Artist B','Album',"
            "'Artist B - Song Two.flac',1,NULL);"
        )
        cursor.execute("CREATE TABLE requestCache (id TEXT, jsonStr TEXT);")
        connection.commit()
        connection.close()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_database_and_download_dir_are_discovered(self):
        with patch.dict(
            os.environ,
            {"NETEASE_DB_PATH": self.db_path, "NETEASE_DOWNLOAD_DIR": self.download_dir},
        ):
            provider = NetEaseDBProvider()

        self.assertEqual(provider.db_path, self.db_path)
        self.assertEqual(provider.detection["db_source"], "env")
        self.assertEqual(provider.download_dir, self.download_dir)
        self.assertGreaterEqual(provider.detection["download_matched"], 1)
        self.assertEqual(provider.detection["download_sample_size"], 2)

        with patch.dict(
            os.environ,
            {"NETEASE_DB_PATH": self.db_path, "NETEASE_DOWNLOAD_DIR": self.download_dir},
        ):
            report = provider.refresh_detection()
        self.assertEqual(report["db_path"], self.db_path)
        self.assertEqual(report["download_dir"], self.download_dir)

    def test_missing_env_paths_fall_back_without_crashing(self):
        with patch.dict(
            os.environ,
            {"NETEASE_DB_PATH": "/nonexistent/db.sqlite3", "NETEASE_DOWNLOAD_DIR": "/nonexistent/dir"},
            clear=False,
        ):
            provider = NetEaseDBProvider()
        # Falls back to scanning; the key contract is that it never raises.
        self.assertIsInstance(provider.detection, dict)
        self.assertIn("db_path", provider.detection)

class LrcSanitizerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_json_lines_and_timestamps(self):
        raw = (
            '{"t":0,"c":[{"tx":"作词 : Frank Ocean"}]}\n'
            "[00:14.128]These bitches want Nikes\n"
            "[00:17.8]They looking for a check\n"
            "[01:02]No fraction\n"
        )
        cleaned = LrcSanitizer.sanitize_text(raw)
        self.assertIn("[00:00.00]作词 : Frank Ocean", cleaned)
        self.assertIn("[00:14.12]These bitches want Nikes", cleaned)
        self.assertIn("[00:17.80]They looking for a check", cleaned)
        self.assertIn("[01:02.00]No fraction", cleaned)
        self.assertTrue(cleaned.endswith("\r\n"))

    def test_writes_utf8_without_bom_by_default(self):
        source = os.path.join(self.temp_dir, "raw.lrc")
        destination = os.path.join(self.temp_dir, "dest.lrc")
        with open(source, "w", encoding="utf-8") as handle:
            handle.write("[01:05.123]Hello World\n")

        ok, _ = LrcSanitizer.sanitize_file(source, destination)
        self.assertTrue(ok)
        with open(destination, "rb") as handle:
            payload = handle.read()
        self.assertFalse(payload.startswith(b"\xef\xbb\xbf"))
        self.assertIn(b"[01:05.12]Hello World\r\n", payload)

    def test_bom_can_be_requested(self):
        source = os.path.join(self.temp_dir, "raw.lrc")
        destination = os.path.join(self.temp_dir, "bom.lrc")
        with open(source, "w", encoding="utf-8") as handle:
            handle.write("[00:01.00]Hi\n")

        ok, _ = LrcSanitizer.sanitize_file(source, destination, bom=True)
        self.assertTrue(ok)
        with open(destination, "rb") as handle:
            self.assertTrue(handle.read().startswith(b"\xef\xbb\xbf"))

    def test_gbk_lyrics_are_decoded(self):
        source = os.path.join(self.temp_dir, "gbk.lrc")
        with open(source, "wb") as handle:
            handle.write("[00:01.00]中文歌词\r\n".encode("gb18030"))

        destination = os.path.join(self.temp_dir, "out.lrc")
        ok, _ = LrcSanitizer.sanitize_file(source, destination)
        self.assertTrue(ok)
        with open(destination, "r", encoding="utf-8") as handle:
            self.assertIn("中文歌词", handle.read())


class ManifestTests(unittest.TestCase):
    def test_echo_library_json_writer(self):
        temp_dir = tempfile.mkdtemp()
        try:
            manifest = PipelineOrchestrator.write_echo_library_json(
                temp_dir,
                collections=[{
                    "id": "alb_blonde",
                    "type": "album",
                    "name": "Blonde",
                    "directory": "Albums/Blonde",
                    "tracks": [{
                        "seq": "01",
                        "filename": "01 Frank Ocean - Nikes.flac",
                        "title": "Nikes",
                    }],
                }],
            )
            with open(manifest, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            self.assertEqual(data["target_profile"], "SNOWSKY_FIIO_ECHO")
            self.assertEqual(data["total_tracks"], 1)
            self.assertEqual(data["schema_version"], "1.1.0")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class NetEaseProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "mock_netease.sqlite3")
        connection = sqlite3.connect(self.db_path)
        cursor = connection.cursor()
        cursor.execute(
            "CREATE TABLE offlineTrack (id TEXT, trackName TEXT, artistName TEXT,"
            " albumName TEXT, newRelativePath TEXT, size INTEGER, jsonStr TEXT);"
        )
        cursor.execute(
            "INSERT INTO offlineTrack VALUES ('1','Nikes','Frank Ocean','Blonde',"
            "'Frank Ocean - Nikes.ncm',108048499,"
            "'{\"detail\": {\"album\": {\"picUrl\": \"https://example.com/cover.jpg\"}}}');"
        )
        cursor.execute(
            "INSERT INTO offlineTrack VALUES ('2','Ivy','Frank Ocean','Blonde',"
            "'Frank Ocean - Ivy.flac',86409724,NULL);"
        )
        connection.commit()
        connection.close()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_local_meta_cover_resolution(self):
        """NetEase keeps full-size covers in <download_dir>/meta/track-<id>.jpg."""
        download_dir = os.path.join(self.temp_dir, "downloads")
        meta_dir = os.path.join(download_dir, "meta")
        os.makedirs(meta_dir)
        base_cover = os.path.join(meta_dir, "track-1.jpg")
        duplicate = os.path.join(meta_dir, "track-1 (1).jpg")
        for path in (base_cover, duplicate):
            with open(path, "wb") as handle:
                handle.write(b"jpeg-bytes")

        provider = NetEaseDBProvider(db_path=self.db_path, download_dir=download_dir)
        self.assertEqual(provider.resolve_local_cover("1"), base_cover)
        self.assertEqual(provider.resolve_local_cover("track-1"), base_cover)
        self.assertEqual(provider.resolve_local_cover("999"), "")

        tracks = provider.get_tracks_by_album("Blonde")
        self.assertEqual(tracks[0]["cover_local_path"], base_cover)

    def test_album_grouping_and_track_metadata(self):
        provider = NetEaseDBProvider(db_path=self.db_path)
        self.assertTrue(provider.is_available())

        albums = provider.get_downloaded_albums()
        self.assertEqual(len(albums), 1)
        self.assertEqual(albums[0]["name"], "Blonde")
        self.assertEqual(albums[0]["track_count"], 2)
        self.assertEqual(
            albums[0]["id"],
            NetEaseDBProvider(db_path=self.db_path).get_downloaded_albums()[0]["id"],
        )

        tracks = provider.get_tracks_by_album("Blonde")
        self.assertEqual(len(tracks), 2)
        self.assertEqual(tracks[0]["title"], "Nikes")
        self.assertEqual(tracks[0]["seq"], "01")
        self.assertEqual(tracks[0]["pic_url"], "https://example.com/cover.jpg")


@unittest.skipUnless(FFMPEG, "ffmpeg is required for media fixtures")
class InspectorAndPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.cover_path = os.path.join(self.temp_dir, "cover.png")
        _run_ffmpeg(["-f", "lavfi", "-i", "color=c=red:s=1400x1400:d=1",
                     "-frames:v", "1", self.cover_path])

        self.flac_path = os.path.join(self.temp_dir, "big.flac")
        _run_ffmpeg([
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-i", self.cover_path, "-map", "0:a", "-map", "1:v",
            "-c:a", "flac", "-frame_size", "8192",
            "-c:v", "mjpeg", "-frames:v", "1", "-disposition:v", "attached_pic",
            self.flac_path,
        ])

        self.mp3_path = os.path.join(self.temp_dir, "sample.mp3")
        _run_ffmpeg([
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-i", self.cover_path, "-map", "0:a", "-map", "1:v",
            "-c:a", "libmp3lame", "-b:a", "128k",
            "-c:v", "mjpeg", "-frames:v", "1", "-disposition:v", "attached_pic",
            self.mp3_path,
        ])

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_inspector_reports_real_values(self):
        info = AudioInspector().inspect(self.flac_path)
        self.assertEqual(info["container"], "flac")
        self.assertEqual(info["block_size"], 8192)
        self.assertTrue(info["needs_reframe"])
        self.assertEqual(info["cover"]["width"], 1400)
        self.assertFalse(info["cover"]["compliant"])
        self.assertIn("SIZE", info["cover"]["reasons"])

    def test_inspector_reports_encrypted_ncm(self):
        info = AudioInspector().inspect("/tmp/whatever.ncm")
        self.assertEqual(info["container"], "ncm")
        self.assertTrue(info["encrypted"])
        self.assertIsNone(info["block_size"])

    def test_flac_is_reframed_and_cover_normalized(self):
        orchestrator = PipelineOrchestrator(
            staging_dir=os.path.join(self.temp_dir, "staging")
        )
        ok, report = orchestrator.process_track(
            self.flac_path,
            os.path.join(self.temp_dir, "out", "01 Artist - Title"),
            meta_override={"title": "Title", "artist": "Artist", "album": "Album",
                           "tracknumber": "01"},
        )
        self.assertTrue(ok, report.get("error"))
        self.assertEqual(report["container"], "flac")
        self.assertTrue(report["dest_audio"].endswith(".flac"))
        self.assertLessEqual(report["block_size"], 4096)
        self.assertTrue(report["cover"]["compliant"])
        self.assertEqual(report["cover"]["width"], 500)
        self.assertEqual(report["cover"]["subsampling"], "4:2:0")

        from mutagen.flac import FLAC
        tags = FLAC(report["dest_audio"]).tags
        self.assertEqual(tags["artist"], ["Artist"])
        self.assertEqual(tags["title"], ["Title"])

    def test_local_meta_cover_is_embedded_without_network(self):
        plain_flac = os.path.join(self.temp_dir, "plain.flac")
        _run_ffmpeg(["-f", "lavfi", "-i", "sine=frequency=330:duration=1",
                     "-c:a", "flac", plain_flac])

        orchestrator = PipelineOrchestrator(
            staging_dir=os.path.join(self.temp_dir, "staging")
        )
        ok, report = orchestrator.process_track(
            plain_flac,
            os.path.join(self.temp_dir, "out", "03 Artist - Local"),
            cover_local_path=self.cover_path,
        )
        self.assertTrue(ok, report.get("error"))
        self.assertEqual(report["cover_source"], "local_meta")
        self.assertTrue(report["cover"]["compliant"])
        self.assertEqual(report["cover"]["width"], 500)

    def test_mp3_keeps_mp3_extension_and_gets_compliant_cover(self):
        orchestrator = PipelineOrchestrator(
            staging_dir=os.path.join(self.temp_dir, "staging")
        )
        ok, report = orchestrator.process_track(
            self.mp3_path,
            os.path.join(self.temp_dir, "out", "02 Artist - Title"),
            meta_override={"title": "Title", "artist": "Artist", "album": "Album",
                           "tracknumber": "02"},
        )
        self.assertTrue(ok, report.get("error"))
        self.assertEqual(report["container"], "mp3")
        self.assertTrue(report["dest_audio"].endswith(".mp3"))
        self.assertFalse(report["dest_audio"].endswith(".flac"))
        self.assertTrue(report["cover"]["compliant"])

        from mutagen.mp3 import EasyMP3
        self.assertEqual(EasyMP3(report["dest_audio"])["artist"], ["Artist"])

    def test_builder_skips_missing_sources_and_writes_manifest(self):
        library = os.path.join(self.temp_dir, "library")
        tracks = [
            {
                "src_path": self.flac_path,
                "target_folder": "Albums/Test?Album",
                "seq": "01",
                "title": "Title",
                "artist": "Artist",
                "album": "Album",
            },
            {
                "src_path": os.path.join(self.temp_dir, "missing.ncm"),
                "target_folder": "Albums/Test?Album",
                "seq": "02",
                "title": "Ghost",
                "artist": "Artist",
                "album": "Album",
            },
        ]
        outcome = LibraryBuilder(
            PipelineOrchestrator(staging_dir=os.path.join(self.temp_dir, "staging"))
        ).build(library, tracks)

        self.assertEqual(outcome["success_count"], 1)
        self.assertEqual(outcome["skipped_count"], 1)
        self.assertTrue(os.path.exists(outcome["manifest_path"]))

        for root, _dirs, files in os.walk(library):
            for name in files:
                for illegal in ':*?"<>|':
                    self.assertNotIn(illegal, name)

    def test_fat_sort_and_dot_clean(self):
        target = os.path.join(self.temp_dir, "card")
        os.makedirs(target, exist_ok=True)
        for name in ["03 c.flac", "01 a.flac", "02 b.flac"]:
            with open(os.path.join(target, name), "w", encoding="utf-8") as handle:
                handle.write("x")
        with open(os.path.join(target, "._01 a.flac"), "w", encoding="utf-8") as handle:
            handle.write("ghost")
        with open(os.path.join(target, ".DS_Store"), "w", encoding="utf-8") as handle:
            handle.write("ghost")

        sort_result = PipelineOrchestrator.fat_sort_directory(target)
        self.assertEqual(sort_result["files_reordered"], 3)

        clean_result = PipelineOrchestrator.dot_clean_directory(target)
        self.assertEqual(clean_result["removed_files"], 2)
        self.assertEqual(sorted(os.listdir(target)), ["01 a.flac", "02 b.flac", "03 c.flac"])


if __name__ == "__main__":
    unittest.main()
