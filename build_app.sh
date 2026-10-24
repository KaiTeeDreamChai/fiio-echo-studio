#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

export DEVELOPER_DIR="/Library/Developer/CommandLineTools"
# Keep PyInstaller's binary cache out of ~/Library (works in sandboxed / CI shells too)
export PYINSTALLER_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR:-${TMPDIR:-/tmp}/fiio-echo-pyinstaller-cache}"

echo "========================================="
echo "   Building FiiO Echo Studio macOS App   "
echo "========================================="

# 0. Ensure the bundled binaries exist (they are git-ignored on purpose)
echo "[0/5] Checking engine/bin binaries..."
mkdir -p engine/bin

FF_STATIC="node_modules/ffmpeg-static/ffmpeg"
if [ ! -x engine/bin/ffmpeg ]; then
  if [ -x "$FF_STATIC" ]; then
    cp "$FF_STATIC" engine/bin/ffmpeg
    chmod +x engine/bin/ffmpeg
    echo "      ffmpeg <- node_modules/ffmpeg-static (static build)"
  elif command -v ffmpeg >/dev/null 2>&1; then
    cp "$(command -v ffmpeg)" engine/bin/ffmpeg
    chmod +x engine/bin/ffmpeg
    echo "      WARNING: copied the system ffmpeg (may not be fully self-contained)."
    echo "      For a truly standalone app run: npm approve-scripts ffmpeg-static && npm rebuild ffmpeg-static"
  else
    echo "ERROR: ffmpeg is missing. Install it with 'brew install ffmpeg' or provide engine/bin/ffmpeg."
    exit 1
  fi
fi

if [ ! -x engine/bin/ncmdump ]; then
  if command -v ncmdump >/dev/null 2>&1; then
    cp "$(command -v ncmdump)" engine/bin/ncmdump
    chmod +x engine/bin/ncmdump
    echo "      ncmdump <- $(command -v ncmdump)"
  else
    echo "ERROR: ncmdump is missing. Install it with 'brew install ncmdump' or provide engine/bin/ncmdump."
    exit 1
  fi
fi

# 1. Build Frontend
echo "[1/5] Building Vite frontend..."
npm run build

# 2. Package App with PyInstaller into dist_app/
echo "[2/5] Packaging native macOS App Bundle with PyInstaller..."
rm -rf dist_app
pyinstaller --clean -y --distpath dist_app FiiO_Echo_Studio.spec

APP_PATH="dist_app/FiiO Echo Studio.app"

if [ ! -d "$APP_PATH" ]; then
    echo "Error: $APP_PATH was not created!"
    exit 1
fi

echo "[3/5] Stripping quarantine attributes from $APP_PATH..."
xattr -cr "$APP_PATH" || true

# The raw one-dir COLLECT output is an internal artefact; the .app is the deliverable.
rm -rf "dist_app/FiiO Echo Studio"

# 3. Create DMG Installer
echo "[4/5] Creating DMG Disk Image..."
DMG_NAME="FiiO_Echo_Studio_v1.1.0_arm64.dmg"
DMG_STAGING="dist_app/dmg_staging"

rm -rf "$DMG_STAGING" "dist_app/$DMG_NAME"
mkdir -p "$DMG_STAGING"

# Copy App to staging
cp -R "$APP_PATH" "$DMG_STAGING/"

# Create symlink to /Applications
ln -s /Applications "$DMG_STAGING/Applications"

# Generate compressed DMG using hdiutil; fall back to a mount-free route when
# the environment forbids mounting volumes (sandboxed shells / some CI runners).
if ! hdiutil create \
    -volname "FiiO Echo Studio" \
    -srcfolder "$DMG_STAGING" \
    -ov \
    -format UDZO \
    "dist_app/$DMG_NAME"; then
    echo "      hdiutil create could not mount a volume; using makehybrid fallback..."
    INTERIM_DMG="${TMPDIR:-/tmp}/fiio_echo_interim.dmg"
    rm -f "$INTERIM_DMG" "dist_app/$DMG_NAME"
    hdiutil makehybrid -quiet -hfs \
        -default-volume-name "FiiO Echo Studio" \
        -o "$INTERIM_DMG" "$DMG_STAGING"
    hdiutil convert "$INTERIM_DMG" \
        -format UDZO -imagekey zlib-level=9 \
        -o "dist_app/$DMG_NAME"
    rm -f "$INTERIM_DMG"
fi

rm -rf "$DMG_STAGING"

echo ""
echo "[5/5] Done."
echo "========================================="
echo "  ✓ BUILD SUCCESSFUL!                    "
echo "  App:  $APP_PATH                        "
echo "  DMG:  dist_app/$DMG_NAME               "
echo "========================================="
