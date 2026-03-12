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
LAUNCHER="$DESKTOP/PacheVideo.command"

# ── 1. Homebrew ───────────────────────────────
echo "→ Verificando Homebrew..."
if ! command -v brew &>/dev/null && [ ! -f /opt/homebrew/bin/brew ]; then
    echo "  → Instalando Homebrew (puede pedir tu contraseña)..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Agregar Homebrew al PATH si no está
if [ -f /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
    # Guardar en .zprofile si no está ya
    if ! grep -q "brew shellenv" "$HOME/.zprofile" 2>/dev/null; then
        echo >> "$HOME/.zprofile"
        echo 'eval "$(/opt/homebrew/bin/brew shellenv zsh)"' >> "$HOME/.zprofile"
    fi
fi
echo "  ✓  Homebrew listo"

# ── 2. Tcl/Tk + Python 3.12 ──────────────────
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

# ── 6. Lanzador en el Escritorio ──────────────
echo "→ Creando lanzador en el Escritorio..."
cat > "$LAUNCHER" << 'LAUNCH'
#!/bin/bash
~/.pachevideo/venv/bin/python3 ~/.pachevideo/pache_video.py
LAUNCH
chmod +x "$LAUNCHER"
echo "  ✓  PacheVideo.command creado en: $DESKTOP"

# ── 7. Listo ──────────────────────────────────
echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║   ✓  Instalación completada          ║"
echo "  ║                                      ║"
echo "  ║   Doble clic en PacheVideo.command   ║"
echo "  ║   (primera vez: click derecho→Abrir) ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

read -r -p "  ¿Abrir PacheVideo ahora? [S/n] " resp
resp="${resp:-S}"
if [[ "$resp" =~ ^[Ss]$ ]]; then
    ~/.pachevideo/venv/bin/python3 ~/.pachevideo/pache_video.py &
fi
