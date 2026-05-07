#!/usr/bin/env bash
set -euo pipefail

APP_NAME="PacheVideo"
APP_VERSION="${APP_VERSION:-1.0.0}"
BUNDLE_ID="com.pachevideo.app"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

APP_PATH="dist/${APP_NAME}.app"
OUTPUT_DIR="installer_output"
COMPONENT_PKG="component_${APP_NAME}.pkg"
PKG_NAME="${APP_NAME}_macOS_v${APP_VERSION}.pkg"

echo ""
echo "========================================"
echo "  PacheVideo macOS PKG Creator"
echo "========================================"
echo ""

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "El instalador .pkg debe generarse en macOS."
  exit 1
fi

if [[ ! -d "$APP_PATH" ]]; then
  echo "No se encontro $APP_PATH"
  echo "Ejecuta primero: bash build.sh"
  exit 1
fi

if ! command -v pkgbuild >/dev/null 2>&1 || ! command -v productbuild >/dev/null 2>&1; then
  echo "Faltan pkgbuild/productbuild. Instala Xcode Command Line Tools:"
  echo "  xcode-select --install"
  exit 1
fi

mkdir -p "$OUTPUT_DIR"
rm -f "$OUTPUT_DIR/$COMPONENT_PKG" "$OUTPUT_DIR/$PKG_NAME"

echo "[1/3] Creando paquete componente..."
if [[ -d "pkg_resources/scripts" ]]; then
  pkgbuild \
    --root "dist" \
    --identifier "$BUNDLE_ID" \
    --version "$APP_VERSION" \
    --install-location "/Applications" \
    --scripts "pkg_resources/scripts" \
    "$OUTPUT_DIR/$COMPONENT_PKG"
else
  pkgbuild \
    --root "dist" \
    --identifier "$BUNDLE_ID" \
    --version "$APP_VERSION" \
    --install-location "/Applications" \
    "$OUTPUT_DIR/$COMPONENT_PKG"
fi

echo "[2/3] Armando instalador final..."
if [[ -f "pkg_resources/distribution.xml" ]]; then
  productbuild \
    --distribution "pkg_resources/distribution.xml" \
    --resources "pkg_resources" \
    --package-path "$OUTPUT_DIR" \
    "$OUTPUT_DIR/$PKG_NAME"
else
  productbuild \
    --package "$OUTPUT_DIR/$COMPONENT_PKG" \
    "$OUTPUT_DIR/$PKG_NAME"
fi

rm -f "$OUTPUT_DIR/$COMPONENT_PKG"

if [[ ! -f "$OUTPUT_DIR/$PKG_NAME" ]]; then
  echo "No se genero el instalador."
  exit 1
fi

SIZE="$(du -sh "$OUTPUT_DIR/$PKG_NAME" | cut -f1)"

echo "[3/3] Listo."
echo ""
echo "Instalador generado:"
echo "  $OUTPUT_DIR/$PKG_NAME ($SIZE)"
echo ""
echo "Firma opcional para distribuir masivamente:"
echo "  productsign --sign \"Developer ID Installer: TU NOMBRE (TEAM_ID)\" \\"
echo "    \"$OUTPUT_DIR/$PKG_NAME\" \\"
echo "    \"$OUTPUT_DIR/${APP_NAME}_macOS_v${APP_VERSION}_signed.pkg\""
