#!/usr/bin/env python3
"""
Unit Tests for FiiO Echo Studio Core Modules
"""

import os
import shutil
import tempfile
import unittest

from engine.core.lrc_sanitizer import LrcSanitizer
from engine.core.cover_normalizer import CoverNormalizer
from engine.core.flac_reframer import FlacReframer
from engine.core.pipeline import PipelineOrchestrator


class TestCoreModules(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_lrc_sanitizer_json_cleaning(self):
        """Test converting NetEase JSON lines into standard [mm:ss.xx] timestamps."""
        raw_lrc = (
            '{"t":0,"c":[{"tx":"作词 : Frank Ocean"}]}\n'
            '[00:14.128]These bitches want Nikes\n'
            '[00:17.8]They looking for a check\n'
        )
        cleaned = LrcSanitizer.sanitize_text(raw_lrc)
        self.assertIn("[00:00.00]作词 : Frank Ocean", cleaned)
        self.assertIn("[00:14.12]These bitches want Nikes", cleaned)
        self.assertIn("[00:17.80]They looking for a check", cleaned)
        self.assertTrue(cleaned.endswith("\r\n"))

    def test_lrc_file_utf8_sig(self):
        """Test writing LRC with UTF-8 BOM."""
        src_lrc = os.path.join(self.test_dir, "raw.lrc")
        dest_lrc = os.path.join(self.test_dir, "dest.lrc")
        with open(src_lrc, "w", encoding="utf-8") as f:
            f.write('[01:05.123]Hello World\n')

        ok, msg = LrcSanitizer.sanitize_file(src_lrc, dest_lrc)
        self.assertTrue(ok)
        with open(dest_lrc, "rb") as f:
            content = f.read()
            # UTF-8 BOM header is EF BB BF
            self.assertTrue(content.startswith(b"\xef\xbb\xbf"))
            self.assertIn(b"[01:05.12]Hello World\r\n", content)

    def test_echo_library_json_writer(self):
        """Test generating echo_library.json manifest."""
        manifest_path = PipelineOrchestrator.write_echo_library_json(
            self.test_dir,
            collections=[
                {
                    "id": "alb_blonde",
                    "type": "album",
                    "name": "Blonde",
                    "directory": "Albums/Blonde",
                    "tracks": [
                        {
                            "seq": "01",
                            "filename": "01 Frank Ocean - Nikes.flac",
                            "title": "Nikes"
                        }
                    ]
                }
            ]
        )
        self.assertTrue(os.path.exists(manifest_path))
        with open(manifest_path, "r", encoding="utf-8") as f:
            import json
            data = json.load(f)
            self.assertEqual(data["schema_version"], "1.0.0")
            self.assertEqual(data["target_profile"], "SNOWSKY_FIIO_ECHO")
            self.assertEqual(data["total_tracks"], 1)


if __name__ == "__main__":
    unittest.main()
    def test_netease_db_provider_mock(self):
        """Test NetEaseDBProvider schema queries with an in-memory SQLite database."""
        import sqlite3
        from engine.providers.netease_db import NetEaseDBProvider

        mock_db = os.path.join(self.test_dir, "mock_netease.sqlite3")
        conn = sqlite3.connect(mock_db)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE offlineTrack (
                id TEXT, trackName TEXT, artistName TEXT, albumName TEXT,
                newRelativePath TEXT, size INTEGER, jsonStr TEXT
            );
        """)
        c.execute("""
            INSERT INTO offlineTrack VALUES
            ('1', 'Nikes', 'Frank Ocean', 'Blonde', 'Frank Ocean - Nikes.ncm', 108048499, '{"detail": {"album": {"picUrl": "https://example.com/cover.jpg"}}}'),
            ('2', 'Ivy', 'Frank Ocean', 'Blonde', 'Frank Ocean - Ivy.flac', 86409724, NULL);
        """)
        conn.commit()
        conn.close()

        provider = NetEaseDBProvider(db_path=mock_db)
        self.assertTrue(provider.is_available())

        albums = provider.get_downloaded_albums()
        self.assertEqual(len(albums), 1)
        self.assertEqual(albums[0]["name"], "Blonde")
        self.assertEqual(albums[0]["track_count"], 2)

        tracks = provider.get_tracks_by_album("Blonde")
        self.assertEqual(len(tracks), 2)
        self.assertEqual(tracks[0]["title"], "Nikes")
        self.assertEqual(tracks[0]["seq"], "01")
        self.assertEqual(tracks[0]["pic_url"], "https://example.com/cover.jpg")
