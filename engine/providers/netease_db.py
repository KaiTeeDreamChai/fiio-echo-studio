#!/usr/bin/env python3
"""
NetEase Cloud Music Local SQLite Database Provider
Supports reading NetEase Cloud Music SQLite databases (Modern 3.x & Legacy).
Safely opens in read-only mode (mode=ro) to prevent database locking or corruption.
"""

import os
import json
import sqlite3
import unicodedata
from typing import List, Dict, Any, Optional

DEFAULT_MODERN_DB = os.path.expanduser(
    "~/Library/Application Support/com.netease.163music/Documents/storage/sqlite_storage.sqlite3"
)
DEFAULT_LEGACY_DB = os.path.expanduser(
    "~/Library/Containers/com.netease.163music/Data/Documents/storage/sqlite_storage.sqlite3"
)
DEFAULT_DOWNLOAD_DIR = os.path.expanduser("~/Music/网易云音乐")


class NetEaseDBProvider:
    """Safe, read-only reader for NetEase Cloud Music desktop database."""

    def __init__(self, db_path: Optional[str] = None, download_dir: Optional[str] = None):
        if db_path and os.path.exists(db_path):
            self.db_path = db_path
        elif os.path.exists(DEFAULT_MODERN_DB):
            self.db_path = DEFAULT_MODERN_DB
        elif os.path.exists(DEFAULT_LEGACY_DB):
            self.db_path = DEFAULT_LEGACY_DB
        else:
            self.db_path = None

        self.download_dir = download_dir or DEFAULT_DOWNLOAD_DIR

    def is_available(self) -> bool:
        return bool(self.db_path and os.path.exists(self.db_path))

    def _get_connection(self) -> sqlite3.Connection:
        if not self.db_path or not os.path.exists(self.db_path):
            raise FileNotFoundError("NetEase database not found.")
        uri = f"file:{os.path.abspath(self.db_path)}?mode=ro"
        return sqlite3.connect(uri, uri=True)

    def get_all_playlists(self, preferred_creator: Optional[str] = None, only_preferred: bool = False) -> List[Dict[str, Any]]:
        """
        Retrieve all playlists and cached playlist metadata.
        Supports filtering or prioritizing by an optional creator name.
        """
        if not self.is_available():
            return []

        conn = self._get_connection()
        cur = conn.cursor()
        playlists_dict: Dict[str, Dict[str, Any]] = {}

        # 1. From requestCache (/eapi/v6/playlist/detail)
        try:
            cur.execute("SELECT id, jsonStr FROM requestCache WHERE id LIKE '%/eapi/v6/playlist/detail%'")
            for _, jstr in cur.fetchall():
                try:
                    d = json.loads(jstr)
                    cache = d.get("cache", {})
                    if isinstance(cache, str):
                        cache = json.loads(cache)
                    pl = cache.get("playlist", {})
                    if pl and "id" in pl and "name" in pl:
                        pid = str(pl["id"])
                        playlists_dict[pid] = {
                            "id": pid,
                            "type": "playlist",
                            "name": pl.get("name", f"歌单 {pid}"),
                            "track_count": pl.get("trackCount", 0),
                            "creator": pl.get("creator", {}).get("nickname", "网易云用户"),
                            "description": pl.get("description", "") or ""
                        }
                except Exception:
                    pass
        except Exception:
            pass

        # 2. From persistentModel (User detail playlists)
        try:
            cur.execute("SELECT uniKey, jsonStr FROM persistentModel WHERE uniKey LIKE 'page:userDetail%'")
            for _, jstr in cur.fetchall():
                try:
                    data = json.loads(jstr).get("data", {})
                    for key in ["createPlaylist", "favPlaylist"]:
                        user_obj = data.get(key, {})
                        if isinstance(user_obj, dict):
                            for _, block in user_obj.items():
                                records = block.get("records", []) if isinstance(block, dict) else []
                                for pl in records:
                                    pid = str(pl.get("id"))
                                    if pid not in playlists_dict:
                                        playlists_dict[pid] = {
                                            "id": pid,
                                            "type": "playlist",
                                            "name": pl.get("name", f"歌单 {pid}"),
                                            "track_count": pl.get("trackCount", 0),
                                            "creator": pl.get("creator", {}).get("nickname", "网易云用户"),
                                            "description": pl.get("description", "") or ""
                                        }
                except Exception:
                    pass
        except Exception:
            pass

        # 3. From persistentModel page:playlist
        try:
            cur.execute("SELECT jsonStr FROM persistentModel WHERE uniKey = 'page:playlist'")
            row = cur.fetchone()
            if row:
                entities = json.loads(row[0]).get("data", {}).get("entities", {})
                for eid, evalue in entities.items():
                    if isinstance(evalue, dict) and "name" in evalue:
                        pid = str(evalue.get("id", eid))
                        if pid not in playlists_dict:
                            playlists_dict[pid] = {
                                "id": pid,
                                "type": "playlist",
                                "name": evalue.get("name", f"歌单 {pid}"),
                                "track_count": evalue.get("trackCount", 0),
                                "creator": evalue.get("creator", {}).get("nickname", "网易云用户"),
                                "description": evalue.get("description", "") or ""
                            }
        except Exception:
            pass

        conn.close()
        all_pls = list(playlists_dict.values())

        # Filtering / Priority Sorting
        if preferred_creator:
            pref = preferred_creator.lower().strip()
            if only_preferred:
                filtered = [p for p in all_pls if p.get("creator", "").lower() == pref]
                return sorted(filtered, key=lambda x: x["track_count"], reverse=True)
            else:
                # Prioritize preferred creator first, then by track count
                return sorted(
                    all_pls,
                    key=lambda x: (x.get("creator", "").lower() != pref, -x.get("track_count", 0))
                )

        return sorted(all_pls, key=lambda x: x["track_count"], reverse=True)

    def get_playlist_tracks(self, pid: str) -> List[Dict[str, Any]]:
        """
        Retrieves ordered track details for a given playlist ID (pid),
        querying dbTrack and requestCache for complete title, artist, album, and duration.
        """
        if not self.is_available():
            return []

        conn = self._get_connection()
        cur = conn.cursor()

        # Step 1: Get ordered track IDs from playlistTrackIds
        cur.execute("SELECT jsonStr FROM playlistTrackIds WHERE id = ?", (str(pid),))
        row = cur.fetchone()
        tids = []
        if row:
            try:
                data = json.loads(row[0])
                tids = [str(item.get("id")) for item in data.get("trackIds", [])]
            except Exception:
                pass

        # Step 2: Pre-index offlineTrack for fast local file matching
        cur.execute("SELECT id, newRelativePath, size, trackName, artistName FROM offlineTrack")
        offline_map = {}
        for rid, rel, size, tr_name, ar_name in cur.fetchall():
            if not rid:
                continue
            clean_id = str(rid).replace("track-", "")
            full_path = ""
            if rel:
                cand = os.path.join(self.download_dir, rel.lstrip("/"))
                if os.path.exists(cand):
                    full_path = cand
            offline_map[clean_id] = {
                "local_file_path": full_path,
                "size_bytes": size or (os.path.getsize(full_path) if full_path else 0),
                "track_name": tr_name,
                "artist_name": ar_name
            }

        # Step 3: Batch load dbTrack in blocks of 500 for optimal performance
        db_track_map = {}
        batch_size = 500
        for i in range(0, len(tids), batch_size):
            batch = tids[i:i + batch_size]
            placeholders = ','.join('?' for _ in batch)
            cur.execute(f"SELECT id, jsonStr FROM dbTrack WHERE id IN ({placeholders})", batch)
            for row_id, jstr in cur.fetchall():
                if jstr:
                    try:
                        db_track_map[str(row_id)] = json.loads(jstr)
                    except Exception:
                        pass

        tracks = []
        for idx, tid in enumerate(tids, 1):
            seq = f"{idx:02d}"
            title = f"曲目 {tid}"
            artist = "未知艺术家"
            album = "未知专辑"
            duration_ms = 0

            # 1. Query db_track_map
            if str(tid) in db_track_map:
                obj = db_track_map[str(tid)]
                title = obj.get("name") or title
                artist_list = [a.get("name") for a in obj.get("artists", []) if a.get("name")]
                if artist_list:
                    artist = " / ".join(artist_list)
                album = obj.get("album", {}).get("name") or album
                duration_ms = obj.get("duration") or 0
            else:
                # 2. Query requestCache fallback
                cur.execute("SELECT jsonStr FROM requestCache WHERE jsonStr LIKE ? LIMIT 1", (f'%\"id\":{tid}%',))
                rc_row = cur.fetchone()
                if rc_row and rc_row[0]:
                    try:
                        d = json.loads(rc_row[0])
                        cache = d.get("cache", {})
                        if isinstance(cache, str):
                            cache = json.loads(cache)
                        for s in cache.get("songs", []):
                            if str(s.get("id")) == str(tid):
                                title = s.get("name") or title
                                artist_list = [a.get("name") for a in s.get("ar", []) if a.get("name")]
                                if artist_list:
                                    artist = " / ".join(artist_list)
                                album = s.get("al", {}).get("name") or album
                                duration_ms = s.get("dt") or 0
                                break
                    except Exception:
                        pass

            # 3. Match with pre-indexed offlineTrack
            off = offline_map.get(str(tid))
            local_path = ""
            size_bytes = 0
            is_downloaded = False

            if off and off.get("local_file_path"):
                local_path = off["local_file_path"]
                size_bytes = off["size_bytes"]
                is_downloaded = True
                if not title or title.startswith("曲目 "):
                    title = off.get("track_name") or title
                if not artist or artist == "未知艺术家":
                    artist = off.get("artist_name") or artist

            tracks.append({
                "tid": str(tid),
                "seq": seq,
                "title": title,
                "artist": artist,
                "album": album,
                "duration_sec": round(duration_ms / 1000.0, 1),
                "size_bytes": size_bytes,
                "local_file_path": local_path,
                "is_downloaded": is_downloaded
            })

        conn.close()
        return tracks

    def get_downloaded_albums(self) -> List[Dict[str, Any]]:
        """
        Groups all locally downloaded tracks in offlineTrack by Album.
        Returns clean, structured albums with accurate track counts.
        """
        if not self.is_available():
            return []

        conn = self._get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT albumName, COUNT(*), GROUP_CONCAT(artistName, ' / ')
            FROM offlineTrack
            WHERE albumName IS NOT NULL AND albumName != ''
            GROUP BY albumName
            ORDER BY COUNT(*) DESC;
        """)

        albums = []
        for row in cur.fetchall():
            album_name = row[0]
            track_count = row[1]
            artist_candidates = [a.strip() for a in (row[2] or "").split(" / ") if a.strip()]
            main_artist = artist_candidates[0] if artist_candidates else "未知艺术家"

            albums.append({
                "id": f"alb_{abs(hash(album_name)) % 10000000}",
                "type": "album",
                "name": album_name,
                "main_artist": main_artist,
                "track_count": track_count,
                "target_folder": f"Albums/{unicodedata.normalize('NFC', album_name)}"
            })

        conn.close()
        return albums

    def get_tracks_by_album(self, album_name: str) -> List[Dict[str, Any]]:
        """
        Retrieves all tracks belonging to a given album from offlineTrack,
        including download path, size, and cover picUrl.
        """
        if not self.is_available():
            return []

        conn = self._get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, trackName, artistName, albumName, newRelativePath, size, jsonStr
            FROM offlineTrack
            WHERE albumName = ?
            ORDER BY id ASC;
        """, (album_name,))

        tracks = []
        for idx, r in enumerate(cur.fetchall()):
            tid, track_name, artist_name, alb, rel_path, size, jstr = r
            pic_url = ""
            if jstr:
                try:
                    obj = json.loads(jstr)
                    detail = obj.get("detail")
                    if isinstance(detail, str):
                        detail = json.loads(detail)
                    if isinstance(detail, dict):
                        pic_url = detail.get("album", {}).get("picUrl", "")
                except Exception:
                    pass

            full_path = ""
            if rel_path:
                cleaned_rel = rel_path.lstrip("/")
                candidate = os.path.join(self.download_dir, cleaned_rel)
                if os.path.exists(candidate):
                    full_path = candidate

            tracks.append({
                "tid": str(tid),
                "seq": f"{idx + 1:02d}",
                "title": track_name or "未知曲目",
                "artist": artist_name or "未知艺术家",
                "album": alb,
                "size_bytes": size or 0,
                "local_file_path": full_path,
                "is_downloaded": bool(full_path and os.path.exists(full_path)),
                "pic_url": pic_url
            })

        conn.close()
        return tracks
