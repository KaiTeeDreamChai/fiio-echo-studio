# SNOWSKY / FiiO Echo Studio

> A lightweight, cross-platform audio normalization & FAT32 sync studio tailored for the **SNOWSKY / FiiO Echo** portable lossless player, crafted with the **Swiss International Typographic Style**.

## Core Capabilities

1. **NCM Batch Decryption**: Native AES/RC4 stream decryption from NetEase Cloud Music `.ncm` to lossless `.flac` / `.mp3` with full metadata recovery.
2. **FLAC Hardware Frame Reframing**: Automatically inspects `STREAMINFO` and reframes tracks where `BlockSize > 4096` down to `4096` (preserving 100% bit-exact 16/24-bit PCM up to 192kHz).
3. **Album Art Normalization**: Enforces `500 × 500` Baseline JPEG with `YUV 4:2:0` (`yuvj420p`) chroma subsampling and single `Type 3 (Cover Front)` picture block to prevent display freezing.
4. **Companion LRC Sanitizer**: Converts NetEase JSON word-level timestamps into strict `[mm:ss.xx]` 2-digit format with `UTF-8` encoding and `CRLF` line endings, 100% filename-matched.
5. **FAT32 Physical Directory Sorter & Ghost Cleaner**: Reconstructs FAT32 directory table entries sequentially (`01..N`) and purges macOS AppleDouble (`._*`, `.DS_Store`) files.

## Project Structure

- `docs/FIIO_ECHO_AUDIO_SPECIFICATION.md`: Hardware decoding & filesystem specification.
- `src/`: Swiss International UI Frontend (TypeScript + Tailwind CSS).
- `src-tauri/`: Cross-platform Rust Core Engine (Tauri v2 targeting macOS, Windows, Linux, Android).
