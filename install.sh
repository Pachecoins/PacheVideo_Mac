#!/bin/bash
# ─────────────────────────────────────────────
#  PacheVideo — Instalador automático para Mac
# ─────────────────────────────────────────────
set -e

APP_DIR="$HOME/.pachevideo"
REPO="https://github.com/Pachecoins/PacheVideo_Mac.git"
LAUNCHER="$HOME/Desktop/PacheVideo.command"

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║        PacheVideo  Installer         ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# ── 1. Python 3 ───────────────────────────────
echo "→ Verificando Python 3..."
if ! command -v python3 &>/dev/null; then
    echo ""
    echo "  ✗  Python 3 no encontrado."
    echo "     Instalalo desde: https://www.python.org/downloads/"
    echo "     Luego volvé a ejecutar este script."
    exit 1
fi
echo "  ✓  $(python3 --version)"

# ── 2. Homebrew ───────────────────────────────
echo "→ Verificando Homebrew..."
if ! command -v brew &>/dev/null; then
    echo "  → Instalando Homebrew (puede pedir tu contraseña)..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Apple Silicon path
    [ -f /opt/homebrew/bin/brew ] && eval "$(/opt/homebrew/bin/brew shellenv)"
fi
echo "  ✓  Homebrew listo"

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
echo "  ✓  Código listo en $APP_DIR"

# ── 5. Entorno virtual + dependencias ─────────
echo "→ Instalando dependencias Python..."
python3 -m venv "$APP_DIR/venv" --quiet
"$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/venv/bin/pip" install --quiet customtkinter yt-dlp Pillow
echo "  ✓  Dependencias instaladas"

# ── 6. Lanzador en el Escritorio ──────────────
echo "→ Creando lanzador en el Escritorio..."
cat > "$LAUNCHER" <<'LAUNCH'
#!/bin/bash
APP_DIR="$HOME/.pachevideo"
source "$APP_DIR/venv/bin/activate"
python3 "$APP_DIR/pache_video.py"
LAUNCH
chmod +x "$LAUNCHER"
echo "  ✓  PacheVideo.command creado en el Escritorio"

# ── 7. Listo ──────────────────────────────────
echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║   ✓  Instalación completada          ║"
echo "  ║                                      ║"
echo "  ║   Abrí PacheVideo.command desde      ║"
echo "  ║   tu Escritorio para iniciar la app  ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# Abrir la app ahora mismo
read -r -p "  ¿Abrir PacheVideo ahora? [S/n] " resp
resp="${resp:-S}"
if [[ "$resp" =~ ^[Ss]$ ]]; then
    open "$LAUNCHER"
fi
