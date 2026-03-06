#!/bin/bash
# ============================================================
#   PacheVideo — macOS Builder
#   Equivalente a build.bat pero para macOS
#   Ejecutar ANTES de create_pkg.sh
# ============================================================

set -e

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║        PacheVideo  Builder           ║"
echo "  ║           macOS Edition              ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# ── 1. Verificar Python 3 ──────────────────────────────────
if ! command -v python3 &> /dev/null; then
    echo "  [ERROR] Python 3 no está instalado."
    echo "  Instalalo desde: https://www.python.org/downloads/macos/"
    echo "  O con Homebrew:  brew install python"
    exit 1
fi
echo "  [1/5] Python: $(python3 --version)"

# ── 2. Instalar dependencias ───────────────────────────────
echo "  [2/5] Instalando dependencias..."
pip3 install -r requirements.txt --quiet
echo "  OK"

# ── 3. Descargar ffmpeg para macOS ─────────────────────────
echo "  [3/5] Descargando ffmpeg para macOS..."
python3 -c "import ffmpeg_downloader as ffd; ffd.download()" 2>/dev/null || true

FFMPEG_PATH=$(python3 -c "import ffmpeg_downloader as ffd; print(ffd.ffmpeg_path)" 2>/dev/null || echo "")

if [ -z "$FFMPEG_PATH" ] || [ ! -f "$FFMPEG_PATH" ]; then
    # Fallback: ffmpeg del sistema (Homebrew)
    FFMPEG_PATH=$(which ffmpeg 2>/dev/null || echo "")
fi

if [ -z "$FFMPEG_PATH" ] || [ ! -f "$FFMPEG_PATH" ]; then
    echo "  [ERROR] No se encontró ffmpeg."
    echo "  Instalalo con Homebrew: brew install ffmpeg"
    exit 1
fi

echo "  ffmpeg: $FFMPEG_PATH"
cp -f "$FFMPEG_PATH" ./ffmpeg
chmod +x ./ffmpeg

# ── 4. Icono macOS (.icns preferido, .ico como fallback) ───
echo "  [4/5] Configurando icono..."
ICON_FLAG=""
if [ -f "icon.icns" ]; then
    ICON_FLAG="--icon icon.icns"
    echo "  Usando icon.icns"
elif [ -f "icon.ico" ]; then
    ICON_FLAG="--icon icon.ico"
    echo "  Usando icon.ico (recomendado: convertir a .icns)"
else
    echo "  Sin icono (agregar icon.icns para mejor apariencia)"
fi

# ── 5. Construir PacheVideo.app con PyInstaller ────────────
echo "  [5/5] Construyendo PacheVideo.app..."

pyinstaller \
    --onefile \
    --windowed \
    --name "PacheVideo" \
    $ICON_FLAG \
    --add-binary "ffmpeg:." \
    --hidden-import customtkinter \
    --hidden-import yt_dlp \
    --hidden-import PIL \
    --collect-all customtkinter \
    --osx-bundle-identifier "com.pachevideo.app" \
    pache_video.py

# ── Limpiar temporales ─────────────────────────────────────
rm -f ./ffmpeg
rm -rf build
rm -f PacheVideo.spec

if [ -d "dist/PacheVideo.app" ]; then
    echo ""
    echo "  ╔══════════════════════════════════════════════════════════════╗"
    echo "  ║  ¡Listo!  La app está en:  dist/PacheVideo.app              ║"
    echo "  ║                                                              ║"
    echo "  ║  Siguiente paso: bash create_pkg.sh                         ║"
    echo "  ║  para generar el instalador .pkg con wizard de macOS.       ║"
    echo "  ╚══════════════════════════════════════════════════════════════╝"
else
    echo ""
    echo "  [ERROR] No se generó dist/PacheVideo.app. Revisá los errores arriba."
    exit 1
fi
echo ""
