# FiiO Echo Studio — AI Agent Handover & Engineering Runbook

This document is the authoritative technical reference for AI Agents taking over development, debugging, packaging, or maintenance of **FiiO Echo Studio** (`fiio-echo-studio`). Read this file completely before modifying code.

---

## 1. Project Identity & Overview

- **Project Name**: FiiO Echo Studio
- **Repository Root**: `/Users/qzchai/.gemini/antigravity/scratch/NetEase2Mp3Player/fiio-echo-studio`
- **Remote GitHub**: `https://github.com/KaiTeeDreamChai/fiio-echo-studio` (`main` branch)
- **License**: WTFPL (`LICENSE`)
- **Target Hardware**: SNOWSKY / FiiO Echo Mini & portable lossless DAPs with embedded hardware decoders and FAT32 microSD storage.
- **Design System**: **Swiss International Typographic Style** (Asymmetric 3-column grid, high-contrast monochrome `#000000` / `#FFFFFF` / `#F4F4F0` + `#FF3300` International Orange/Red accent, tabular monospace telemetry, full Light/Dark mode support).

---

## 2. The 5 Hardware Compliance Rules (Domain Invariants)

Portable embedded DAPs suffer from strict hardware decoder and filesystem limitations. All audio processing in `engine/core/` enforces these 5 rules:

1. **FLAC Frame BlockSize ≤ 4096** (`engine/core/flac_reframer.py`)
   - **Why**: Embedded rockchip/ingenic/RTOS decoders allocate a 4KB DMA frame buffer. FLAC files encoded with `BlockSize > 4096` (e.g., 8192 or 16384) cause loud audio pops, track skipping, or hard freezes.
   - **Rule**: Parse the 34-byte `STREAMINFO` header (`max_blocksize`). If `> 4096`, re-encode losslessly via `ffmpeg -c:a flac -compression_level 5` (which caps blocksize at 4096) while preserving 100% bit-exact PCM (16/24-bit, up to 192kHz).

2. **Embedded Cover Art: 500×500 Baseline JPEG, YUV 4:2:0** (`engine/core/cover_normalizer.py`)
   - **Why**: Progressive JPEGs, PNGs, >1000px images, or `YUV 4:4:4` (`yuvj444p`) chroma subsampling fail to render or crash the player's UI thread.
   - **Rule**: Convert cover art to `500×500` Baseline JPEG with `YUV 4:2:0` (`-vf scale=500:500 -pix_fmt yuvj420p`), strip all secondary `METADATA_BLOCK_PICTURE` blocks, and embed a single `Type 3 (Cover Front)` block.

3. **Companion `.lrc` Lyrics Sanitization** (`engine/core/lrc_sanitizer.py`)
   - **Why**: NetEase Cloud Music injects JSON metadata lines (`{"t":0,"c":[...]}`) and 3-digit milliseconds `[mm:ss.xxx]` which break hardware lyric parsers.
   - **Rule**: Output a companion `.lrc` file with the **exact same filename stem** as the audio file, convert JSON headers to clean text, normalize timestamps to 2-digit centiseconds `[mm:ss.xx]`, and encode as `UTF-8` with `CRLF` (`\r\n`) line endings.

4. **NCM Lossless Decryption** (`engine/core/ncm_decryptor.py`)
   - **Why**: NetEase VIP downloads are encrypted `.ncm` containers.
   - **Rule**: Decrypt via bundled `ncmdump` into native `.flac` or `.mp3`, preserving original Vorbis/ID3 metadata before feeding into the FLAC/Cover/LRC normalization pipeline.

5. **FAT32 Physical Directory Slot Sorting & Ghost File Purge** (`engine/core/pipeline.py`)
   - **Why**: Embedded DAPs often iterate files in raw FAT32 directory table entry order rather than sorting alphabetically, and display macOS AppleDouble (`._*`) files as broken tracks.
   - **Rule**:
     - `fat_sort_directory()`: Moves files into a temporary directory and moves them back sequentially in strict `01..N` alphabetical order so FAT32 allocates contiguous directory slots.
     - `dot_clean_directory()`: Executes `/usr/sbin/dot_clean -m` and removes `.DS_Store`, `._*`, `.Spotlight-V100`, `.Trashes`, and `.fseventsd`.

---

## 3. Codebase Architecture & File Map

```text
fiio-echo-studio/
├── app_launcher.py                 # Native macOS app entrypoint (starts HTTP server + pywebview Cocoa window)
├── build_app.sh                    # One-click macOS .app & .dmg packaging script
├── FiiO_Echo_Studio.spec           # PyInstaller bundle specification
├── assets/
│   └── icon.icns                   # macOS app icon (Swiss red/black style)
├── docs/
│   └── FIIO_ECHO_AUDIO_SPECIFICATION.md  # Detailed hardware decoding & FAT32 specification
├── engine/                         # Python Backend & Core Audio Engine
│   ├── server.py                   # HTTP JSON API Server (127.0.0.1:19880)
│   ├── bridge.py                   # CLI interface for headless/agent invocation
│   ├── bin/                        # Static bundled binaries (git-ignored: ffmpeg, ncmdump)
│   ├── providers/
│   │   └── netease_db.py           # Read-only SQLite parser for NetEase macOS client DB
│   ├── core/
│   │   ├── bin_resolver.py         # Locates ffmpeg & ncmdump (PyInstaller _MEIPASS -> engine/bin -> PATH)
│   │   ├── ncm_decryptor.py        # .ncm decryption wrapper
│   │   ├── flac_reframer.py        # STREAMINFO inspector & BlockSize <= 4096 reframer
│   │   ├── cover_normalizer.py     # 500x500 YUV420p Baseline JPEG normalizer
│   │   ├── lrc_sanitizer.py        # NetEase JSON lyric cleaner & UTF-8 CRLF writer
│   │   └── pipeline.py             # End-to-end track processor, FAT32 slot sorter, dot_clean runner
│   └── tests/
│       └── test_core.py            # Unit tests for FLAC, LRC, and pipeline logic
└── src/                            # React 19 + TypeScript + Tailwind CSS Frontend
    ├── App.tsx                     # Root state, NetEase DB loading, track normalization & build handlers
    ├── index.css                   # Swiss design tokens (:root & .dark), badges, custom scrollbars
    ├── services/
    │   └── api.ts                  # Typed fetch wrapper for 127.0.0.1:19880/api/*
    ├── types/
    │   └── library.ts              # TrackItem, FilterType, ClassifyMode interfaces
    ├── hooks/
    │   └── useAdaptiveLayout.ts    # 3-Tier responsive layout hook (Desktop 3-col / Split 2-col / Mobile 1-col)
    └── components/
        ├── SwissHeader.tsx         # Top bar: Theme toggle, Library Root input, native BROWSE button
        ├── QueuePanel.tsx          # COL 01: NetEase DB Album/Playlist browser, creator filter, track table
        ├── InspectorPanel.tsx      # COL 02: Real-time hardware spec telemetry & LRC diff viewer
        ├── LocalLibraryPanel.tsx   # COL 03: Target folder tree, FAT32/dot_clean tools, split Build buttons
        └── TelemetryFooter.tsx     # Bottom bar: Live log output & {okCount}/{totalCount} OK badge
```

---

## 4. Critical UI & Business Logic Invariants (Do Not Regress!)

When modifying the frontend or backend, **strictly preserve** the following behaviors requested by the user:

1. **Zero Demo / Mock Data**:
   - Do not reintroduce hardcoded mock tracks (`src/data/mockTracks.ts` was intentionally deleted). All tracks come live from the NetEase SQLite DB via `/api/albums` and `/api/playlists`.

2. **Generic Creator Filtering (No Hardcoded Username)**:
   - `preferredCreator` defaults to `""` (empty string) and `onlyMine` defaults to `false` across `App.tsx`, `api.ts`, `server.py`, and `bridge.py`.
   - By default, all playlists in the local NetEase database are listed.
   - In `QueuePanel.tsx`, the input placeholder is `"作者昵称 (可选)"`. When `preferredCreator.trim()` is empty, the `"仅看 TA 的歌单"` checkbox is disabled and dimmed (`opacity-40`).

3. **Accurate Downloaded vs. Undownloaded Track Status (`X / Y OK`)**:
   - Playlists/albums in NetEase often contain tracks that are not downloaded locally (`is_downloaded: false`, `local_file_path: ""`).
   - Undownloaded tracks must have `status: 'NOT_DOWNLOADED'` (rendered as `[未下载]`).
   - When executing `buildLibrary`, **only** tracks with `isDownloaded && localFilePath` are sent to the backend pipeline and marked `COMPLIANT` upon success.
   - The footer and summary must report `okCount / tracks.length OK` (e.g., `30 / 1640 OK`), never falsely marking undownloaded tracks as OK.

4. **Split Action Buttons in `LocalLibraryPanel.tsx` (`COL 03`)**:
   - The bottom build action is split into two side-by-side buttons in a 12-column grid:
     - **Left (`col-span-4`)**: Red background (`bg-[#FF3300] text-white`), label `"执行"` (or `"执行中..."` when building).
     - **Right (`col-span-8`)**: Matches panel background (`bg-[var(--background)] text-[var(--foreground)]`), label `"BUILD LOCAL LIBRARY"`.
   - Both buttons trigger `onBuildLibrary`.

5. **Native macOS Folder Picker (`BROWSE` Button)**:
   - Handled by `GET /api/pick-folder` in `engine/server.py`.
   - Uses `osascript` with `tell application "System Events" to activate` before `choose folder` so the native Finder dialog always appears in the foreground.

6. **Strict Dark Mode Compliance**:
   - Never use hardcoded Tailwind `bg-white`, `bg-black`, `text-black`, or `border-black` on structural containers, tabs, selects, or badges.
   - Always use CSS variables defined in `src/index.css`: `bg-[var(--background)]`, `bg-[var(--card)]`, `bg-[var(--sidebar)]`, `text-[var(--foreground)]`, `border-[var(--border)]`, `bg-[var(--active-bg)]`, `text-[var(--active-fg)]`.

---

## 5. Development, Testing & Packaging Workflows

### A. Local Development (Web UI + Python API)
If the user wants to preview or debug in a browser:
```bash
# Terminal 1: Start Python HTTP Engine on 127.0.0.1:19880
python3 -m engine.server --port 19880

# Terminal 2: Start Vite Dev Server on http://localhost:5173
npm run dev
```
*(Remember to stop background dev servers when finished so ports `19880` and `5173` are not left hanging.)*

### B. Running Backend Unit Tests
```bash
python3 -m unittest discover -s engine/tests
```

### C. Building Standalone macOS `.app` and `.dmg` (Scheme A)
The project packages into a 100% standalone macOS application using `pywebview` (Cocoa `WKWebView`) + `PyInstaller` + embedded static `ffmpeg` and `ncmdump`.

**Prerequisites before running `./build_app.sh`**:
- Ensure `engine/bin/ffmpeg` (static binary) and `engine/bin/ncmdump` exist and have `chmod +x` permissions (they are git-ignored to avoid bloating the repo).
- `build_app.sh` automatically sets `export DEVELOPER_DIR="/Library/Developer/CommandLineTools"` to avoid Xcode license agreement errors (Error 69) during `lipo` / `codesign`.

```bash
# Run full build pipeline (Vite build -> PyInstaller .app -> xattr clean -> hdiutil .dmg)
./build_app.sh
```
**Build Outputs** (in `dist_app/`, git-ignored):
- `dist_app/FiiO Echo Studio.app` (~78 MB standalone bundle)
- `dist_app/FiiO_Echo_Studio_v1.0.0_arm64.dmg` (~37 MB compressed installer with `/Applications` symlink)

---

## 6. Headless CLI Bridge (`engine/bridge.py`)

Agents can also invoke the backend engine directly via CLI (outputs pure JSON):

```bash
# 1. List all playlists in NetEase DB
python3 -m engine.bridge get-playlists

# 2. List playlists filtered by creator
python3 -m engine.bridge get-playlists --creator "SomeUser" --only-mine

# 3. List all downloaded albums
python3 -m engine.bridge get-albums

# 4. Get tracks for a specific playlist ID or album name
python3 -m engine.bridge get-playlist-tracks --pid "<PLAYLIST_ID>"
python3 -m engine.bridge get-album-tracks --name "<ALBUM_NAME>"

# 5. Inspect a single audio file's hardware compliance
python3 -m engine.bridge inspect --file "/path/to/track.flac"
```
