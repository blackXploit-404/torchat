#!/bin/bash
# ============================================================
# TorChat AppImage Build Script

# please note this build process requires appimagetool which dont include in this script so please download it by running 
# wget https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
# chmod +x appimagetool-x86_64.AppImage
# ============================================================

set -e

APP_NAME="TorChat"
APPDIR="${APP_NAME}.AppDir"
ARCH="x86_64"
OUTPUT="${APP_NAME}-x86_64.AppImage"
APPIMAGETOOL="./appimagetool-x86_64.AppImage"

echo "TorChat Build Script"
echo "===================="


for f in main.py server.py client.py crypto.py; do
    if [ ! -f "$f" ]; then
        echo "Error: missing $f"
        exit 1
    fi
done


echo "Creating AppDir structure..."

mkdir -p "${APPDIR}/usr/bin"
mkdir -p "${APPDIR}/usr/lib/python3/site-packages"


echo "Syncing source files to AppDir..."

cp main.py   "${APPDIR}/usr/bin/"
cp server.py "${APPDIR}/usr/bin/"
cp client.py "${APPDIR}/usr/bin/"
cp crypto.py "${APPDIR}/usr/bin/"

chmod +x "${APPDIR}/usr/bin/"*.py

echo "Source files synced."


if [ ! -x "${APPDIR}/AppRun" ]; then
    echo "Error: AppRun missing or not executable"
    exit 1
fi


if [ ! -x "${APPIMAGETOOL}" ]; then
    echo "Error: appimagetool-x86_64.AppImage not found"
    exit 1
fi

rm -f "${OUTPUT}"

ARCH="${ARCH}" "${APPIMAGETOOL}" "${APPDIR}" "${OUTPUT}"

sha256sum "${OUTPUT}" > "${OUTPUT}.sha256"

echo ""
echo "Build complete!"
echo "Output: ${OUTPUT}"
echo "Checksum: ${OUTPUT}.sha256"
