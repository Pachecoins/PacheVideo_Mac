#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/Pachecoins/PacheVideo_Mac.git"
APP_NAME="PacheVideo"
WORK_DIR="${PACHEVIDEO_DIR:-$HOME/PacheVideo_Mac}"
INSTALL_DIR="${PACHEVIDEO_INSTALL_DIR:-$HOME/Applications}"

echo ""
echo "========================================"
echo "  PacheVideo macOS Installer"
echo "========================================"
echo ""

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Este instalador es solo para macOS."
  exit 1
fi

if ! xcode-select -p >/dev/null 2>&1; then
  echo "Faltan Xcode Command Line Tools."
  echo "Se abrira el instalador de Apple. Cuando termine, vuelve a ejecutar este comando."
  xcode-select --install || true
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "No se encontro git. Instala Xcode Command Line Tools y reintenta."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "No se encontro python3."
  echo "Instala Python 3.11+ desde https://www.python.org/downloads/macos/ o con Homebrew: brew install python"
  exit 1
fi

if [[ -d "$WORK_DIR/.git" ]]; then
  echo "[1/4] Actualizando repo en $WORK_DIR..."
  git -C "$WORK_DIR" pull --ff-only
else
  echo "[1/4] Bajando repo en $WORK_DIR..."
  rm -rf "$WORK_DIR"
  git clone "$REPO_URL" "$WORK_DIR"
fi

cd "$WORK_DIR"

echo "[2/4] Construyendo app macOS..."
bash build.sh

echo "[3/4] Instalando app en $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
rm -rf "$INSTALL_DIR/${APP_NAME}.app"
ditto "dist/${APP_NAME}.app" "$INSTALL_DIR/${APP_NAME}.app"
xattr -dr com.apple.quarantine "$INSTALL_DIR/${APP_NAME}.app" 2>/dev/null || true

echo "[4/4] Abriendo PacheVideo..."
open "$INSTALL_DIR/${APP_NAME}.app"

echo ""
echo "Listo. PacheVideo quedo instalado en:"
echo "  $INSTALL_DIR/${APP_NAME}.app"
echo ""
