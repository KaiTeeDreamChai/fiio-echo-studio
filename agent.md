# FiiO Echo Studio — AI Agent Handover & Engineering Runbook

This document is the authoritative technical reference for AI Agents taking over development, debugging, packaging, or maintenance of **FiiO Echo Studio** (`fiio-echo-studio`). Read this file completely before modifying code.

---

## 1. Project Identity & Overview

- **Project Name**: FiiO Echo Studio
- **Remote GitHub**: `https://github.com/KaiTeeDreamChai/fiio-echo-studio` (`main` branch)
- **License**: WTFPL (`LICENSE`)
- **Target Hardware**: SNOWSKY / FiiO Echo Mini & portable lossless DAPs with embedded decoders and FAT32 microSD storage.
- **Design System**: **Swiss International Typographic Style** (asymmetric 3-column grid, `#000000` / `#FFFFFF` / `#F4F4F0` + `#FF3300` accent, tabular monospace telemetry, full Light/Dark mode).
- **Version**: `1.2.0` (API `1.2.0`, manifest schema `1.1.0`)

---

## 2. The Hardware Compliance Rules (Domain Invariants)

### 2.1 FLAC frame BlockSize ≤ 4096 — `engine/core/flac_reframer.py`
Embedded decoders allocate a 4 KB DMA buffer; `max_blocksize > 4096` (NetEase uses 8192) causes pops / skips / freezes.
`FlacReframer.reframe_audio_stream()` runs `ffmpeg -vn -c:a flac -frame_size 4096` and **verifies the output** with mutagen. PCM stays bit-exact.

### 2.2 Embedded cover: 500×500 baseline JPEG, YUV 4:2:0, Type 3 — `engine/core/cover_normalizer.py`
NetEase `.ncm` payloads often carry a picture block whose **FLAC metadata says 0×0** even though the bytes are e.g. 1115×1115 `yuvj444p`. Compliance is therefore decided by `engine/core/inspector.py`, which parses the real JPEG/PNG bytes (SOF markers) — never by the metadata alone.

Pipeline cover strategy:
1. embedded picture non-compliant → normalize bytes with ffmpeg (`scale` + `pad` + `-pix_fmt yuvj420p`), re-embed as the only Type 3 picture;
2. embedded picture already compliant → keep (re-attach after a reframe, because `ffmpeg -vn` drops picture blocks);
3. **no embedded picture → use NetEase's local art store** `<download_dir>/meta/track-<id>.jpg` (`cover_local_path`, full-res, offline, 457/457 tracks on the test library);
4. **local cache missing → download from the NetEase `picUrl` (`cover_url`)**; network failure never fails the track.

MP3 files get the same treatment through ID3 `APIC` frames (`_write_mp3_cover` writes exactly one Type 3 APIC). The `report.cover_source` field records `embedded` / `local_meta` / `downloaded`.

### 2.3 Companion LRC — `engine/core/lrc_sanitizer.py`
Strips NetEase JSON lines (`{"t":1234,"c":[...]}`), normalizes timestamps to `[mm:ss.xx]`, NFC-normalizes text, writes **UTF-8 without BOM** + CRLF by default. Set `FIIO_LRC_BOM=1` for players that require a BOM. Reads UTF-8/UTF-16/GB18030/Big5 input.

### 2.4 NCM decryption — `engine/core/ncm_decryptor.py`
Wraps the bundled `ncmdump`. **The output container decides the extension**: `PipelineOrchestrator._detect_container()` sniffs `.flac` vs `.mp3` (or magic bytes) and writes `dest_stem + ".flac"` / `".mp3"`. An MP3 is never renamed to `.flac` (a regression that broke playback in ≤1.0.0).

### 2.5 FAT32 ordering & ghost files — `engine/core/pipeline.py`
- `fat_sort_directory()`: moves each directory's files to a staging bucket inside the card and moves them back in sorted order to rebuild directory entries. **Best-effort**: the FS driver owns final ordering.
- `dot_clean_directory()`: deletes `._*`, `.DS_Store`, `.Spotlight-V100`, `.Trashes`, `.fseventsd`, then runs `/usr/sbin/dot_clean -m`.

### 2.6 Data-source discovery — `engine/providers/netease_db.py`
Never hardcode the user's database path or download folder.
- `_detect_db_path()` scans Application Support / Containers patterns, validates `offlineTrack` + `requestCache`, and picks the largest valid DB (legacy DBs are much smaller). `NETEASE_DB_PATH` overrides.
- `_detect_download_dir()` scores candidate roots (`~/Music`, `~/Downloads`, subfolders, volumes, common NetEase folder names) against real `newRelativePath` values; the best hit-rate wins. `NETEASE_DOWNLOAD_DIR` overrides.
- `POST /api/reload-sources` re-runs detection (used by “重新探测”); `/api/status` returns the detection report.

### 2.7 Native macOS menu — `app_launcher.py`
The packaged app replaces pywebview's default menu with an AppKit `NSMenu` built in `build_macos_menu()`:
- Installed on the **main thread** via `PyObjCTools.AppHelper.callAfter` (pywebview's `start(func=...)` runs in a worker thread).
- Menu names/roles: 文件 (⌘R rescan, ⌘B build, ⌘O choose root, ⌘W close), 编辑 (undo/redo/cut/copy/paste/select all — required for text inputs), 视图 (⌘T theme, ⌘⇧R reload, ⌃⌘F fullscreen), 窗口, 帮助.
- Custom items dispatch `window.dispatchEvent(new CustomEvent('fiio:menu', {detail: action}))`; `App.tsx` listens and calls the existing handlers (rescan/build/theme/choose-root/reload).
- `--dump-menu` prints the native menu tree without opening a window (useful for CI/verification).

### 2.8 FAT32-safe naming — `engine/core/naming.py`
Every destination path goes through `sanitize_filename()` / `sanitize_relative_dir()` / `build_dest_stem()`:
- `\ / : * ? " < > |` → full-width equivalents, control chars stripped, trailing dots/spaces removed;
- `..` and absolute segments dropped (no path traversal);
- UTF-8-aware truncation (default 180 bytes for the stem);
- DOS device names (`CON`, `PRN`, …) prefixed with `_`;
- collisions get ` (2)`, ` (3)` via `make_unique`/builder bookkeeping.

---

## 3. Codebase Architecture & File Map

```text
fiio-echo-studio/
├── app_launcher.py                 # Native macOS entrypoint (HTTP server thread + pywebview Cocoa window)
├── build_app.sh                    # One-click .app & .dmg packaging (provisions engine/bin first)
├── FiiO_Echo_Studio.spec           # PyInstaller bundle specification
├── assets/screenshots/             # README screenshots
├── docs/FIIO_ECHO_AUDIO_SPECIFICATION.md
├── engine/
│   ├── server.py                   # Threaded HTTP API + background build jobs + Host/Origin guard
│   ├── bridge.py                   # CLI: playlists/albums/tracks/inspect/build-library (JSON on stdout)
│   ├── bin/                        # git-ignored static binaries (ffmpeg, ncmdump)
│   ├── providers/netease_db.py     # Read-only SQLite reader (mode=ro) + local meta cover index
│   ├── core/
│   │   ├── bin_resolver.py         # _MEIPASS → engine/bin → PATH → Homebrew
│   │   ├── inspector.py            # Real container/PCM/cover telemetry (no audio decode)
│   │   ├── naming.py               # FAT32-safe filename/path helpers
│   │   ├── ncm_decryptor.py        # .ncm → .flac/.mp3
│   │   ├── flac_reframer.py        # STREAMINFO check + ≤4096 reframe
│   │   ├── cover_normalizer.py     # 500×500 YUV420p baseline JPEG, picUrl download
│   │   ├── lrc_sanitizer.py        # JSON/3-digit-ms cleanup, UTF-8(+optional BOM) CRLF
│   │   ├── pipeline.py             # Per-track pipeline + FAT32 sort + dot_clean + manifest
│   │   └── builder.py              # Shared library builder (server + CLI)
│   └── tests/test_core.py          # 17 unit tests (skips media fixtures without ffmpeg)
└── src/
    ├── App.tsx                     # Root state: real inspection, job polling, single-track build
    ├── services/api.ts             # Typed fetch wrapper (/inspect, /build-library, /build-progress)
    ├── types/library.ts            # TrackItem (nullable real values), manifest schema v1.1
    ├── hooks/useAdaptiveLayout.ts  # 3-tier layout (desktop / split / mobile)
    └── components/
        ├── SwissHeader.tsx         # Theme, library root input (aria-label), BROWSE
        ├── QueuePanel.tsx          # COL 01: album/playlist browser, real BLOCK/COVER columns
        ├── InspectorPanel.tsx      # COL 02: telemetry, cover reasons, LRC diff
        ├── LocalLibraryPanel.tsx   # COL 03: metrics, tree, FAT32 tools, build + progress/cancel
        └── TelemetryFooter.tsx     # Live log + {ok}/{total} OK
```

---

## 4. Critical Invariants (Do Not Regress!)

1. **Zero invented telemetry.** `blockSize`, `pcm`, `coverRes`, `coverYuv`, `coverType` come from `AudioInspector`. Unknown ⇒ `null` / `—`. Never hardcode 8192 / 1400×1400 / 24bit-96kHz (this was the 1.0.0 bug).
2. **Zero mock data.** No hardcoded sample albums/playlists/tracks (`Blonde`, `Hurry Up Tomorrow` etc. must not appear in source).
3. **Honest counts.** `COMPLIANT` only after a real inspection/build proves it. `NOT_DOWNLOADED` for cloud-only tracks. Never mark a track compliant from a UI-only state change.
4. **Real container extensions.** MP3 stays `.mp3`; FLAC `.flac`. `process_track()` takes an extension-less `dest_stem`.
5. **No-op success is forbidden.** A mutating endpoint must either do the work or report failure; `fat-sort` used to only count files.
6. **Destructive operations stay inside `library_root`.** `sanitize_relative_dir()` strips `..`/absolute paths; `_serve_static()` refuses paths outside `dist/`.
7. **API access is origin-checked.** Only `127.0.0.1` / `localhost` `Host`+`Origin` are accepted; do not widen to `*`.
8. **Split action buttons in COL 03** (`执行` red + `BUILD LOCAL LIBRARY`) are a user request — preserve them. A cancel button and progress bar now sit above them while a job runs.
9. **Native folder picker** uses `osascript` with `System Events to activate`.
10. **Dark mode**: never hardcode Tailwind `bg-white` / `text-black` on structural containers; use `var(--*)` tokens from `src/index.css`.

---

## 5. HTTP API (`engine/server.py`, default `127.0.0.1:57123`)

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/status` | DB path, download dir, ffmpeg/ncmdump availability, version |
| GET | `/api/albums` · `/api/playlists` · `/api/album-tracks` · `/api/playlist-tracks` | NetEase DB reads (tracks include `pic_url` + sanitized LRC) |
| GET | `/api/inspect?file=` | Single-file real telemetry |
| POST | `/api/inspect` | `{files: []}` → `{items: {path: info}}` (thread pool 8, LRU cache by mtime+size) |
| POST | `/api/build-library` | `{library_root, tracks}` → `{job_id}` (starts background job) |
| GET | `/api/build-progress?job_id=` | Live snapshot: `status/done/total/current/results/*_count/manifest_path` |
| POST | `/api/build-cancel` | `{job_id}` → graceful stop after the current track |
| POST | `/api/fat-sort` · `/api/dot-clean` | Real TF-card maintenance, returns counts |
| GET | `/api/pick-folder` | Native macOS folder dialog |

Job lifecycle: `running → done | cancelled | error`. Jobs are kept in memory (last 20). `POST /api/build-library` returns immediately; the frontend polls every 500 ms.

Inspection payload (per file):

```json
{
  "container": "flac|mp3|ncm|unknown", "encrypted": false,
  "sample_rate": 96000, "bits_per_sample": 24, "channels": 2,
  "duration_sec": 215.4, "block_size": 8192, "needs_reframe": true,
  "cover": {"present": true, "count": 1, "type": 3, "format": "jpeg",
            "width": 1115, "height": 1115, "meta_width": 0, "meta_height": 0,
            "subsampling": "4:4:4", "progressive": false,
            "compliant": false, "reasons": ["SIZE", "CHROMA", "METADATA_ZERO_OR_MISMATCH"]},
  "error": null
}
```

---

## 6. Development, Testing & Packaging

### A. Local development
```bash
python3 -m engine.server --port 57123     # threaded API
npm run dev                                # Vite on :5173 (dev mode talks to :57123)
```
Stop both servers when finished. `npm run build` runs `tsc -b && vite build` (strict TS, `noUnusedLocals`).

### B. Tests
```bash
python3 -m unittest discover -s engine/tests -v      # 17 tests
```
Media fixtures are generated with `ffmpeg`; tests skip automatically when ffmpeg is absent.

### C. CLI bridge (same code path as the app)
```bash
python3 -m engine.bridge get-playlists [--creator NAME] [--only-mine]
python3 -m engine.bridge get-albums
python3 -m engine.bridge get-playlist-tracks --pid <ID>
python3 -m engine.bridge get-album-tracks --name "<ALBUM>"
python3 -m engine.bridge inspect --file "/path/to/track.flac"
python3 -m engine.bridge build-library --config build.json [--library-root DIR] [--quiet]
```
`build.json` = `{"library_root": "...", "tracks": [{"src_path","target_folder","seq","title","artist","album","cover_url"}]}`.

### D. Packaging
```bash
./build_app.sh
```
Provisions `engine/bin/{ffmpeg,ncmdump}` from `node_modules/ffmpeg-static` / `PATH` / Homebrew when missing, builds the frontend, packages with PyInstaller, then creates the DMG. Outputs in `dist_app/` (git-ignored).

---

## 7. Data Model

`echo_library.json` (schema `1.1.0`) is written to the library root:

```json
{
  "schema_version": "1.1.0",
  "library_root": "/path/to/library",
  "target_profile": "SNOWSKY_FIIO_ECHO",
  "updated_at": "2026-10-24T20:30:00",
  "total_tracks": 2,
  "collections": [{
    "id": "albums_hurry_up_tomorrow", "type": "album",
    "name": "Hurry Up Tomorrow", "directory": "Albums/Hurry Up Tomorrow",
    "tracks": [{
      "seq": "01", "filename": "01 The Weeknd - São Paulo.flac",
      "lrc_filename": "01 The Weeknd - São Paulo.lrc",
      "container": "flac", "size_bytes": 76881226,
      "block_size": 4096, "sample_rate": 96000, "bits_per_sample": 24,
      "cover": {"compliant": true, "width": 500, "height": 500,
                "subsampling": "4:2:0", "format": "jpeg", "type": 3,
                "source": "local_meta"},
      "compliant": true
    }]
  }]
}
```

---

## 8. Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| `UNSUPPORTED_CONTAINER` | Only FLAC/MP3 are normalized; decrypt/extract others first |
| Cover stays "无封面" | No embedded art, no `meta/track-<id>.jpg`, and no reachable `picUrl`; inspect `report.cover_error` |
| `ffmpeg` not found | `brew install ffmpeg` or place the binary at `engine/bin/ffmpeg` |
| `ncmdump` not found | `brew install ncmdump` or `engine/bin/ncmdump` |
| Browser shows 403 `ORIGIN_NOT_ALLOWED` | Access via `http://localhost:5173` or `http://127.0.0.1:57123`, not an arbitrary host |
| Build stuck at `running` | Check `/api/build-progress`; a huge `.ncm` decode can take a while. Cancel via `/api/build-cancel` |
| FAT32 order still wrong | Driver-dependent; re-copy the folder after `fat-sort` |
