#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

export DEVELOPER_DIR="/Library/Developer/CommandLineTools"

echo "========================================="
echo "   Building FiiO Echo Studio macOS App   "
echo "========================================="

# 1. Build Frontend
echo "[1/4] Building Vite frontend..."
npm run build

# 2. Package App with PyInstaller into dist_app/
echo "[2/4] Packaging native macOS App Bundle with PyInstaller..."
rm -rf dist_app
pyinstaller --clean -y --distpath dist_app FiiO_Echo_Studio.spec

APP_PATH="dist_app/FiiO Echo Studio.app"

if [ ! -d "$APP_PATH" ]; then
    echo "Error: $APP_PATH was not created!"
    exit 1
fi

echo "[3/4] Stripping quarantine attributes from $APP_PATH..."
xattr -cr "$APP_PATH" || true

# 3. Create DMG Installer
echo "[4/4] Creating DMG Disk Image..."
DMG_NAME="FiiO_Echo_Studio_v1.0.0_arm64.dmg"
DMG_STAGING="dist_app/dmg_staging"

rm -rf "$DMG_STAGING" "dist_app/$DMG_NAME"
mkdir -p "$DMG_STAGING"

# Copy App to staging
cp -R "$APP_PATH" "$DMG_STAGING/"

# Create symlink to /Applications
ln -s /Applications "$DMG_STAGING/Applications"

# Generate compressed DMG using hdiutil
hdiutil create \
    -volname "FiiO Echo Studio" \
    -srcfolder "$DMG_STAGING" \
    -ov \
    -format UDZO \
    "dist_app/$DMG_NAME"

rm -rf "$DMG_STAGING"

echo ""
echo "========================================="
echo "  ✓ BUILD SUCCESSFUL!                    "
echo "  App:  $APP_PATH                        "
echo "  DMG:  dist_app/$DMG_NAME               "
echo "========================================="
