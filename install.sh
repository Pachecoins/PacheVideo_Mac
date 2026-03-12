#!/bin/bash
# ─────────────────────────────────────────────
#  PacheVideo — Instalador automático para Mac
# ─────────────────────────────────────────────
set -e

APP_DIR="$HOME/.pachevideo"
REPO="https://github.com/Pachecoins/PacheVideo_Mac.git"
PYTHON="/opt/homebrew/bin/python3.12"

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║        PacheVideo  Installer         ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# ── Detectar Escritorio (español o inglés) ────
if [ -d "$HOME/Desktop" ]; then
    DESKTOP="$HOME/Desktop"
elif [ -d "$HOME/Escritorio" ]; then
    DESKTOP="$HOME/Escritorio"
else
    DESKTOP="$HOME/Desktop"
    mkdir -p "$DESKTOP"
fi
APP="$DESKTOP/PacheVideo.app"

# ── 1. Homebrew ───────────────────────────────
echo "→ Verificando Homebrew..."
if ! command -v brew &>/dev/null && [ ! -f /opt/homebrew/bin/brew ]; then
    echo "  → Instalando Homebrew (puede pedir tu contraseña)..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

if [ -f /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
    if ! grep -q "brew shellenv" "$HOME/.zprofile" 2>/dev/null; then
        echo >> "$HOME/.zprofile"
        echo 'eval "$(/opt/homebrew/bin/brew shellenv zsh)"' >> "$HOME/.zprofile"
    fi
fi
echo "  ✓  Homebrew listo"

# ── 2. Python 3.12 + Tkinter ─────────────────
echo "→ Instalando Python 3.12 con soporte gráfico..."
brew install tcl-tk python@3.12 python-tk@3.12 2>/dev/null || true
echo "  ✓  Python 3.12 listo"

# ── 3. ffmpeg ─────────────────────────────────
echo "→ Verificando ffmpeg..."
if ! command -v ffmpeg &>/dev/null; then
    echo "  → Instalando ffmpeg..."
    brew install ffmpeg
fi
echo "  ✓  ffmpeg listo"

# ── 4. Código fuente ──────────────────────────
echo "→ Descargando PacheVideo..."
if [ -d "$APP_DIR/.git" ]; then
    echo "  → Actualizando versión existente..."
    git -C "$APP_DIR" pull --quiet
else
    rm -rf "$APP_DIR"
    git clone --quiet "$REPO" "$APP_DIR"
fi
echo "  ✓  Código listo"

# ── 5. Entorno virtual + dependencias ─────────
echo "→ Instalando dependencias Python..."
rm -rf "$APP_DIR/venv"
"$PYTHON" -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/venv/bin/pip" install --quiet customtkinter yt-dlp Pillow
echo "  ✓  Dependencias instaladas"

# ── 6. Convertir ícono ico → icns ─────────────
echo "→ Preparando ícono..."
if [ -f "$APP_DIR/icon.ico" ]; then
    rm -rf /tmp/pache.iconset
    mkdir -p /tmp/pache.iconset
    sips -z 16 16   "$APP_DIR/icon.ico" --out /tmp/pache.iconset/icon_16x16.png    &>/dev/null
    sips -z 32 32   "$APP_DIR/icon.ico" --out /tmp/pache.iconset/icon_16x16@2x.png &>/dev/null
    sips -z 32 32   "$APP_DIR/icon.ico" --out /tmp/pache.iconset/icon_32x32.png    &>/dev/null
    sips -z 64 64   "$APP_DIR/icon.ico" --out /tmp/pache.iconset/icon_32x32@2x.png &>/dev/null
    sips -z 128 128 "$APP_DIR/icon.ico" --out /tmp/pache.iconset/icon_128x128.png  &>/dev/null
    sips -z 256 256 "$APP_DIR/icon.ico" --out /tmp/pache.iconset/icon_128x128@2x.png &>/dev/null
    sips -z 256 256 "$APP_DIR/icon.ico" --out /tmp/pache.iconset/icon_256x256.png  &>/dev/null
    sips -z 512 512 "$APP_DIR/icon.ico" --out /tmp/pache.iconset/icon_256x256@2x.png &>/dev/null
    sips -z 512 512 "$APP_DIR/icon.ico" --out /tmp/pache.iconset/icon_512x512.png  &>/dev/null
    iconutil -c icns /tmp/pache.iconset -o /tmp/PacheVideo.icns 2>/dev/null
    echo "  ✓  Ícono listo"
else
    echo "  ⚠  icon.ico no encontrado, se usará ícono por defecto"
fi

# ── 7. Crear .app en el Escritorio ────────────
echo "→ Creando PacheVideo.app en el Escritorio..."
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

[ -f /tmp/PacheVideo.icns ] && cp /tmp/PacheVideo.icns "$APP/Contents/Resources/AppIcon.icns"

cat > "$APP/Contents/MacOS/PacheVideo" << 'EOF'
#!/bin/bash
eval "$(/opt/homebrew/bin/brew shellenv)"
exec ~/.pachevideo/venv/bin/python3 ~/.pachevideo/pache_video.py
EOF
chmod +x "$APP/Contents/MacOS/PacheVideo"

ICON_KEY=""
[ -f "$APP/Contents/Resources/AppIcon.icns" ] && ICON_KEY="
  <key>CFBundleIconFile</key><string>AppIcon</string>"

cat > "$APP/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>PacheVideo</string>
  <key>CFBundleDisplayName</key><string>PacheVideo</string>
  <key>CFBundleIdentifier</key><string>com.pache.video</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleExecutable</key><string>PacheVideo</string>
  <key>CFBundlePackageType</key><string>APPL</string>${ICON_KEY}
  <key>LSUIElement</key><false/>
</dict>
</plist>
EOF

xattr -cr "$APP"
echo "  ✓  PacheVideo.app creado en: $DESKTOP"

# ── 8. Listo ──────────────────────────────────
echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║   ✓  Instalación completada          ║"
echo "  ║                                      ║"
echo "  ║   Doble clic en PacheVideo.app       ║"
echo "  ║   (primera vez: click derecho→Abrir) ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

read -r -p "  ¿Abrir PacheVideo ahora? [S/n] " resp
resp="${resp:-S}"
if [[ "$resp" =~ ^[Ss]$ ]]; then
    open "$APP"
fi
