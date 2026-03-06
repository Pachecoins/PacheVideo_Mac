#!/bin/bash
# ============================================================
#   PacheVideo — macOS PKG Installer Creator
#   Equivalente a installer.iss (Inno Setup) pero para macOS
#   Genera un wizard de instalación nativo de macOS (.pkg)
#   Ejecutar DESPUÉS de build.sh
# ============================================================

APP_NAME="PacheVideo"
APP_VERSION="1.0.0"
BUNDLE_ID="com.pachevideo.app"
APP_PATH="dist/${APP_NAME}.app"
OUTPUT_DIR="installer_output"
PKG_NAME="${APP_NAME}_v${APP_VERSION}.pkg"
COMPONENT_PKG="component_${APP_NAME}.pkg"

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║     PacheVideo  PKG  Creator         ║"
echo "  ║     Wizard Installer para macOS      ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# ── Verificar prerequisitos ────────────────────────────────
if [ ! -d "$APP_PATH" ]; then
    echo "  [ERROR] No se encontró $APP_PATH"
    echo "  Ejecutá primero:  bash build.sh"
    exit 1
fi

if ! command -v pkgbuild &> /dev/null || ! command -v productbuild &> /dev/null; then
    echo "  [ERROR] pkgbuild / productbuild no encontrados."
    echo "  Instalá Xcode Command Line Tools:  xcode-select --install"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

echo "  [1/3] Creando paquete componente..."

# Construir el paquete componente (instala .app en /Applications)
pkgbuild \
    --root "dist" \
    --identifier "$BUNDLE_ID" \
    --version "$APP_VERSION" \
    --install-location "/Applications" \
    --scripts "pkg_resources/scripts" \
    "$OUTPUT_DIR/$COMPONENT_PKG"

echo "  [2/3] Armando wizard de instalación..."

# Construir el instalador final con wizard usando distribution.xml
productbuild \
    --distribution "pkg_resources/distribution.xml" \
    --resources "pkg_resources" \
    --package-path "$OUTPUT_DIR" \
    "$OUTPUT_DIR/$PKG_NAME"

# Limpiar componente temporal
rm -f "$OUTPUT_DIR/$COMPONENT_PKG"

if [ -f "$OUTPUT_DIR/$PKG_NAME" ]; then
    SIZE=$(du -sh "$OUTPUT_DIR/$PKG_NAME" | cut -f1)

    echo "  [3/3] Firmando el paquete (opcional)..."
    # Descomenta las líneas de abajo si tenés un Developer ID Installer
    # para distribuir fuera del Mac App Store:
    # productsign \
    #     --sign "Developer ID Installer: TU NOMBRE (TEAM_ID)" \
    #     "$OUTPUT_DIR/$PKG_NAME" \
    #     "$OUTPUT_DIR/${APP_NAME}_v${APP_VERSION}_signed.pkg"

    echo ""
    echo "  ╔══════════════════════════════════════════════════════════════╗"
    echo "  ║  ¡Listo!  El instalador .pkg está en:                       ║"
    printf  "  ║  %-60s║\n" "  ${OUTPUT_DIR}/${PKG_NAME}  (${SIZE})"
    echo "  ║                                                              ║"
    echo "  ║  El wizard incluye:                                          ║"
    echo "  ║   ✓ Página de Bienvenida con branding PacheVideo             ║"
    echo "  ║   ✓ Paso de Tipo de instalación                              ║"
    echo "  ║   ✓ Instalación automática en /Applications                  ║"
    echo "  ║   ✓ Página de Conclusión con instrucciones                   ║"
    echo "  ╚══════════════════════════════════════════════════════════════╝"
    echo ""
    echo "  Para distribuir: compartí el archivo .pkg."
    echo "  Los usuarios lo abren y siguen el wizard nativo de macOS."
    echo ""
else
    echo "  [ERROR] No se generó el .pkg."
    exit 1
fi
