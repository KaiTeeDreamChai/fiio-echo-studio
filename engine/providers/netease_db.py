#!/usr/bin/env python3
"""
NetEase Cloud Music Local SQLite Database Provider
Supports reading NetEase Cloud Music SQLite databases (Modern 3.x & Legacy).
Safely opens in read-only mode (mode=ro) to prevent database locking or corruption.
"""

import glob
import hashlib
import os
import json
import re
import sqlite3
import unicodedata
from typing import List, Dict, Any, Optional

NETEASE_APP_DIR = os.path.expanduser("~/Library/Application Support/com.netease.163music")
NETEASE_CONTAINER_DIR = os.path.expanduser("~/Library/Containers/com.netease.163music/Data")
DB_FILENAME = "sqlite_storage.sqlite3"

#: Ordered search patterns; the first valid candidate with the largest size wins.
DB_SEARCH_PATTERNS = [
    f"{NETEASE_APP_DIR}/Documents/storage/{DB_FILENAME}",
    f"{NETEASE_CONTAINER_DIR}/Documents/storage/{DB_FILENAME}",
    f"{NETEASE_CONTAINER_DIR}/Library/Application Support/com.netease.163music/Documents/storage/{DB_FILENAME}",
    f"{NETEASE_APP_DIR}/Documents/**/{DB_FILENAME}",
    f"{NETEASE_CONTAINER_DIR}/Documents/**/{DB_FILENAME}",
]

#: Folder names NetEase uses for downloads across versions / languages.
DOWNLOAD_DIR_NAMES = ("网易云音乐", "网易云", "CloudMusic", "NetEase", "Music")
DEFAULT_DOWNLOAD_DIR = os.path.expanduser("~/Music/网易云音乐")


class NetEaseDBProvider:
    """Safe, read-only reader for NetEase Cloud Music desktop database."""

    def __init__(self, db_path: Optional[str] = None, download_dir: Optional[str] = None):
        self.db_candidates: List[str] = []
        self.download_candidates: List[str] = []
        self.download_matches = 0
        self.download_sample_size = 0
        self.db_source = "none"

        if db_path and os.path.exists(db_path):
            self.db_path = db_path
            self.db_source = "explicit"
        else:
            self.db_path = self._detect_db_path()

        self.download_dir = download_dir or self._detect_download_dir()
        self.detection = {
            "db_path": self.db_path,
            "db_source": self.db_source,
            "db_candidates": self.db_candidates,
            "download_dir": self.download_dir,
            "download_candidates": self.download_candidates,
            "download_matched": self.download_matches,
            "download_sample_size": self.download_sample_size,
        }

    # ------------------------------------------------------------- detection
    @staticmethod
    def _is_valid_db(path: str) -> bool:
        """A usable NetEase DB must expose offlineTrack + requestCache."""
        try:
            conn = sqlite3.connect(f"file:{os.path.abspath(path)}?mode=ro", uri=True)
            names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            conn.close()
            return "offlineTrack" in names and "requestCache" in names
        except Exception:
            return False

    def _detect_db_path(self) -> Optional[str]:
        """Find the NetEase SQLite DB on this machine instead of assuming one path."""
        candidates: List[str] = []

        env_path = os.environ.get("NETEASE_DB_PATH", "").strip()
        if env_path:
            candidates.append(os.path.expanduser(env_path))
            if os.path.exists(candidates[0]):
                self.db_source = "env"
                self.db_candidates = candidates
                return candidates[0]

        for pattern in DB_SEARCH_PATTERNS:
            expanded = os.path.expanduser(pattern)
            for match in glob.glob(expanded, recursive=True):
                if os.path.isfile(match) and match not in candidates:
                    candidates.append(match)

        valid = []
        for path in candidates:
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            if self._is_valid_db(path):
                valid.append((size, path))

        self.db_candidates = candidates
        if not valid:
            self.db_source = "none"
            return None

        # Multiple installs/containers may exist (legacy DB is much smaller).
        valid.sort(reverse=True)
        self.db_source = "scan"
        return valid[0][1]

    def _read_relative_paths(self, limit: int = 60) -> List[str]:
        if not self.db_path or not os.path.exists(self.db_path):
            return []
        try:
            conn = sqlite3.connect(f"file:{os.path.abspath(self.db_path)}?mode=ro", uri=True)
            rows = conn.execute(
                "SELECT newRelativePath FROM offlineTrack "
                "WHERE newRelativePath IS NOT NULL AND newRelativePath != '' LIMIT ?",
                (limit,),
            ).fetchall()
            conn.close()
            return [str(row[0]) for row in rows if row and row[0]]
        except Exception:
            return []

    def _download_root_candidates(self) -> List[str]:
        home = os.path.expanduser("~")
        roots: List[str] = []

        if getattr(self, "download_dir", None) and os.path.isdir(self.download_dir):
            roots.append(self.download_dir)

        env_dir = os.environ.get("NETEASE_DOWNLOAD_DIR", "").strip()
        if env_dir:
            roots.append(os.path.expanduser(env_dir))

        for base in (os.path.join(home, "Music"), os.path.join(home, "Downloads")):
            if os.path.isdir(base):
                roots.append(base)
                try:
                    for name in sorted(os.listdir(base)):
                        child = os.path.join(base, name)
                        if os.path.isdir(child):
                            roots.append(child)
                except OSError:
                    pass

        for name in DOWNLOAD_DIR_NAMES:
            roots.append(os.path.join(home, "Music", name))
            roots.append(os.path.join(home, "Downloads", name))

        for volume in glob.glob("/Volumes/*"):
            roots.append(volume)
            for name in DOWNLOAD_DIR_NAMES:
                roots.append(os.path.join(volume, name))

        roots.append(DEFAULT_DOWNLOAD_DIR)

        unique: List[str] = []
        for root in roots:
            normalized = os.path.abspath(os.path.expanduser(root))
            if normalized not in unique:
                unique.append(normalized)
        return unique

    def _detect_download_dir(self) -> str:
        """
        NetEase does not store the download root in its public settings, so score
        candidate folders against the real ``newRelativePath`` values in the DB.
        """
        candidates = self._download_root_candidates()
        self.download_candidates = candidates
        relative_paths = self._read_relative_paths()
        self.download_sample_size = len(relative_paths)

        best_root = None
        best_score = -1
        best_meta = 0
        for root in candidates:
            if not os.path.isdir(root):
                continue
            hits = 0
            for rel in relative_paths:
                candidate = os.path.join(root, str(rel).lstrip("/"))
                if os.path.exists(candidate):
                    hits += 1
            has_meta = 1 if os.path.isdir(os.path.join(root, "meta")) else 0
            if hits > best_score or (hits == best_score and has_meta > best_meta):
                best_score = hits
                best_meta = has_meta
                best_root = root
            if hits == len(relative_paths) and relative_paths:
                break

        if best_root and best_score > 0:
            self.download_matches = best_score
            return best_root

        env_dir = os.environ.get("NETEASE_DOWNLOAD_DIR", "").strip()
        if env_dir and os.path.isdir(os.path.expanduser(env_dir)):
            self.download_matches = 0
            return os.path.abspath(os.path.expanduser(env_dir))

        self.download_matches = 0
        return DEFAULT_DOWNLOAD_DIR

    def refresh_detection(self) -> Dict[str, Any]:
        """Re-run discovery (called by the “重新探测” action)."""
        if not self.db_path or not os.path.exists(self.db_path):
            self.db_path = self._detect_db_path()
        self.download_dir = self._detect_download_dir()
        self.detection = {
            "db_path": self.db_path,
            "db_source": self.db_source,
            "db_candidates": self.db_candidates,
            "download_dir": self.download_dir,
            "download_candidates": self.download_candidates,
            "download_matched": self.download_matches,
            "download_sample_size": self.download_sample_size,
        }
        return self.detection

    def is_available(self) -> bool:
        return bool(self.db_path and os.path.exists(self.db_path))

    def _get_connection(self) -> sqlite3.Connection:
        if not self.db_path or not os.path.exists(self.db_path):
            raise FileNotFoundError("NetEase database not found.")
        uri = f"file:{os.path.abspath(self.db_path)}?mode=ro"
        return sqlite3.connect(uri, uri=True)

    def _index_local_covers(self) -> Dict[str, str]:
        """
        Index NetEase's local album-art store: ``<download_dir>/meta/track-<id>.jpg``.

        The desktop client writes one full-resolution JPEG per downloaded track
        (sometimes duplicated as ``track-<id> (1).jpg``). This lets the pipeline
        normalize covers fully offline instead of re-downloading them.
        """
        meta_dir = os.path.join(self.download_dir, "meta")
        index: Dict[str, str] = {}
        if not os.path.isdir(meta_dir):
            return index

        pattern = re.compile(r"^track-(\d+)(?: \((\d+)\))?\.(jpg|jpeg|png)$", re.IGNORECASE)
        try:
            entries = os.listdir(meta_dir)
        except OSError:
            return index

        for name in entries:
            match = pattern.match(name)
            if not match:
                continue
            track_id = match.group(1)
            is_duplicate = match.group(2) is not None
            existing = index.get(track_id)
            if existing is None or (is_duplicate is False and " (" in os.path.basename(existing)):
                index[track_id] = os.path.join(meta_dir, name)
        return index

    def resolve_local_cover(self, track_id: str) -> str:
        """Return the local cover path for a NetEase track ID ('' when absent)."""
        clean_id = str(track_id or "").replace("track-", "").strip()
        if not clean_id:
            return ""
        return self._index_local_covers().get(clean_id, "")

    def _user_playlist_context(self, cur) -> tuple:
        """
        Identify the logged-in user and the playlists they created / favorited.

        - `page:userDetail` holds the profile (id / nickname) of the current account.
        - `page:userDetail|userChange|<uid>` holds that user's createPlaylist /
          favPlaylist record sets, which is the only reliable way to separate
          "created by me" from "favorited by me".
        """
        self_id = None
        created_ids = set()
        favorited_ids = set()

        try:
            cur.execute("SELECT jsonStr FROM persistentModel WHERE uniKey = 'page:userDetail' LIMIT 1")
            row = cur.fetchone()
            if row:
                self_id = json.loads(row[0]).get("data", {}).get("id")
        except Exception:
            pass

        if self_id:
            try:
                cur.execute(
                    "SELECT jsonStr FROM persistentModel WHERE uniKey = ? LIMIT 1",
                    (f"page:userDetail|userChange|{self_id}",),
                )
                row = cur.fetchone()
                if row:
                    data = json.loads(row[0]).get("data", {})
                    for key, bucket in (("createPlaylist", created_ids), ("favPlaylist", favorited_ids)):
                        obj = data.get(key) or {}
                        if isinstance(obj, dict):
                            for block in obj.values():
                                if isinstance(block, dict):
                                    for pl in block.get("records", []) or []:
                                        pid = pl.get("id")
                                        if pid is not None:
                                            bucket.add(str(pid))
            except Exception:
                pass

        return self_id, created_ids, favorited_ids

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
                            "creator": (pl.get("creator") or {}).get("nickname") or "网易云用户",
                            "creator_id": (pl.get("creator") or {}).get("userId"),
                            "description": pl.get("description", "") or "",
                            "create_time": int(pl.get("createTime") or 0),
                            "update_time": int(pl.get("updateTime") or 0)
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
                                            "creator": (pl.get("creator") or {}).get("nickname") or "网易云用户",
                                            "creator_id": (pl.get("creator") or {}).get("userId"),
                                            "description": pl.get("description", "") or "",
                                            "create_time": int(pl.get("createTime") or 0),
                                            "update_time": int(pl.get("updateTime") or 0)
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
                                "creator": (evalue.get("creator") or {}).get("nickname") or "网易云用户",
                                "creator_id": (evalue.get("creator") or {}).get("userId"),
                                "description": evalue.get("description", "") or "",
                                "create_time": int(evalue.get("createTime") or 0),
                                "update_time": int(evalue.get("updateTime") or 0)
                            }
        except Exception:
            pass

        self_id, created_ids, favorited_ids = self._user_playlist_context(cur)
        conn.close()
        all_pls = list(playlists_dict.values())

        for playlist in all_pls:
            pid = str(playlist.get("id"))
            if pid in favorited_ids:
                playlist["relation"] = "favorited"
            elif pid in created_ids or (
                self_id is not None and str(playlist.get("creator_id")) == str(self_id)
            ):
                playlist["relation"] = "created"
            else:
                playlist["relation"] = "cached"

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

        local_covers = self._index_local_covers()

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
            pic_url = ""

            # 1. Query db_track_map
            if str(tid) in db_track_map:
                obj = db_track_map[str(tid)]
                title = obj.get("name") or title
                artist_list = [a.get("name") for a in obj.get("artists", []) if a.get("name")]
                if artist_list:
                    artist = " / ".join(artist_list)
                album = obj.get("album", {}).get("name") or album
                pic_url = obj.get("album", {}).get("picUrl") or ""
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
                                pic_url = s.get("al", {}).get("picUrl") or ""
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
                "is_downloaded": is_downloaded,
                "pic_url": pic_url,
                "cover_local_path": local_covers.get(str(tid), "")
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
                "id": f"alb_{hashlib.md5(album_name.encode('utf-8')).hexdigest()[:10]}",
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

        local_covers = self._index_local_covers()

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
                "pic_url": pic_url,
                "cover_local_path": local_covers.get(str(tid).replace("track-", ""), "")
            })

        conn.close()
        return tracks
