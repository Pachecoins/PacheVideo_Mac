#!/usr/bin/env bash
set -euo pipefail

APP_NAME="PacheVideo"
BUNDLE_ID="com.pachevideo.app"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo ""
echo "========================================"
echo "  PacheVideo macOS Builder"
echo "========================================"
echo ""

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Este build debe ejecutarse en macOS para generar PacheVideo.app."
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "No se encontro python3. Instala Python 3.11+ o Homebrew: brew install python"
  exit 1
fi

if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
then
  echo "Python 3.10+ es requerido. Detectado: $("$PYTHON_BIN" --version)"
  echo "Instala Python moderno con Homebrew:"
  echo "  brew install python"
  echo "o ejecuta install_mac.sh, que intenta resolverlo automaticamente."
  exit 1
fi

echo "[1/6] Python:"
"$PYTHON_BIN" --version

VENV_DIR="${VENV_DIR:-$ROOT/.venv-macos}"

if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  echo "Creando entorno virtual en $VENV_DIR..."
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python"

echo "[2/6] Instalando dependencias..."
"$VENV_PYTHON" -m pip install --upgrade pip
"$VENV_PYTHON" -m pip install -r requirements.txt

echo "[3/6] Preparando ffmpeg..."
FFMPEG_PATH=""
if "$VENV_PYTHON" - <<'PY' >/dev/null 2>&1
import ffmpeg_downloader as ffd
ffd.download()
PY
then
  FFMPEG_PATH="$("$VENV_PYTHON" - <<'PY' 2>/dev/null || true
import ffmpeg_downloader as ffd
print(ffd.ffmpeg_path)
PY
)"
fi

if [[ -z "$FFMPEG_PATH" || ! -f "$FFMPEG_PATH" ]]; then
  FFMPEG_PATH="$(command -v ffmpeg || true)"
fi

if [[ -z "$FFMPEG_PATH" || ! -f "$FFMPEG_PATH" ]]; then
  echo "No se encontro ffmpeg. Instala Homebrew y ejecuta: brew install ffmpeg"
  exit 1
fi

cp -f "$FFMPEG_PATH" ./ffmpeg
chmod +x ./ffmpeg
echo "ffmpeg: $FFMPEG_PATH"

echo "[4/6] Preparando icono macOS..."
ICON_ARG=()
if [[ ! -f icon.icns && -f logo.png ]]; then
  rm -rf icon.iconset
  mkdir -p icon.iconset
  sips -z 16 16 logo.png --out icon.iconset/icon_16x16.png >/dev/null
  sips -z 32 32 logo.png --out icon.iconset/icon_16x16@2x.png >/dev/null
  sips -z 32 32 logo.png --out icon.iconset/icon_32x32.png >/dev/null
  sips -z 64 64 logo.png --out icon.iconset/icon_32x32@2x.png >/dev/null
  sips -z 128 128 logo.png --out icon.iconset/icon_128x128.png >/dev/null
  sips -z 256 256 logo.png --out icon.iconset/icon_128x128@2x.png >/dev/null
  sips -z 256 256 logo.png --out icon.iconset/icon_256x256.png >/dev/null
  sips -z 512 512 logo.png --out icon.iconset/icon_256x256@2x.png >/dev/null
  sips -z 512 512 logo.png --out icon.iconset/icon_512x512.png >/dev/null
  sips -z 1024 1024 logo.png --out icon.iconset/icon_512x512@2x.png >/dev/null
  iconutil -c icns icon.iconset -o icon.icns
  rm -rf icon.iconset
fi

if [[ -f icon.icns ]]; then
  ICON_ARG=(--icon icon.icns)
fi

echo "[5/6] Limpiando builds anteriores..."
rm -rf build dist
rm -f PacheVideo.spec

echo "[6/6] Construyendo PacheVideo.app..."
"$VENV_PYTHON" -m PyInstaller \
  --windowed \
  --name "$APP_NAME" \
  --osx-bundle-identifier "$BUNDLE_ID" \
  "${ICON_ARG[@]}" \
  --add-binary "ffmpeg:." \
  --add-data "logo.png:." \
  --hidden-import customtkinter \
  --hidden-import yt_dlp \
  --hidden-import PIL \
  --hidden-import mutagen \
  --hidden-import yt_dlp_ejs \
  --collect-all customtkinter \
  --collect-all yt_dlp_ejs \
  pache_video.py

rm -f ./ffmpeg
rm -rf build
rm -f PacheVideo.spec

if [[ ! -d "dist/${APP_NAME}.app" ]]; then
  echo "No se genero dist/${APP_NAME}.app."
  exit 1
fi

xattr -dr com.apple.quarantine "dist/${APP_NAME}.app" 2>/dev/null || true

echo ""
echo "Listo. App generada en:"
echo "  dist/${APP_NAME}.app"
echo ""
echo "Para abrir:"
echo "  open dist/${APP_NAME}.app"
echo ""
echo "Para crear instalador:"
echo "  bash create_pkg.sh"
