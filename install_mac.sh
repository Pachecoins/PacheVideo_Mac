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

ensure_brew_package() {
  local package="$1"
  local binary="${2:-$1}"
  if command -v "$binary" >/dev/null 2>&1; then
    return 0
  fi
  if command -v brew >/dev/null 2>&1; then
    echo "Instalando $package con Homebrew..."
    brew install "$package"
    return 0
  fi
  return 1
}

find_modern_python() {
  for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
      then
        command -v "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

PYTHON_BIN="$(find_modern_python || true)"

if [[ -z "$PYTHON_BIN" ]]; then
  echo "Python 3.10+ no esta instalado. El Python de Apple suele ser 3.9 y ya no alcanza para yt-dlp actual."
  if command -v brew >/dev/null 2>&1; then
    echo "Instalando Python moderno con Homebrew..."
    brew install python
    PYTHON_BIN="$(find_modern_python || true)"
  else
    echo "No se encontro Homebrew."
    echo "Instala Homebrew y vuelve a ejecutar el comando:"
    echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    echo ""
    echo "Luego ejecuta otra vez el instalador de PacheVideo."
    open "https://brew.sh" >/dev/null 2>&1 || true
    exit 1
  fi
fi

if [[ -z "$PYTHON_BIN" ]]; then
  echo "No pude activar Python 3.10+. Instala Python 3.11+ y vuelve a ejecutar el comando."
  exit 1
fi

echo "Python seleccionado: $("$PYTHON_BIN" --version)"

if ! ensure_brew_package deno deno; then
  echo "Aviso: no se pudo instalar deno porque Homebrew no esta disponible."
  echo "YouTube puede devolver errores de formato si no puede resolver sus challenges."
fi

if [[ -d "$WORK_DIR/.git" ]]; then
  echo "[1/4] Actualizando repo en $WORK_DIR..."
  git -C "$WORK_DIR" fetch origin main
  git -C "$WORK_DIR" reset --hard origin/main
else
  echo "[1/4] Bajando repo en $WORK_DIR..."
  rm -rf "$WORK_DIR"
  git clone "$REPO_URL" "$WORK_DIR"
fi

cd "$WORK_DIR"

echo "[2/4] Construyendo app macOS..."
PYTHON_BIN="$PYTHON_BIN" bash build.sh

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
