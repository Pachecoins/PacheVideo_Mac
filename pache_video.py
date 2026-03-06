import customtkinter as ctk
from tkinter import filedialog
import yt_dlp
import threading
import os
import sys
import datetime
import urllib.request
from io import BytesIO
import subprocess

try:
    from PIL import Image
    PIL_OK = True
except ImportError:
    PIL_OK = False


# --- PyInstaller: detectar ruta de ffmpeg bundleado ---
def get_ffmpeg_path():
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
        # macOS: 'ffmpeg' (sin extensión); Windows: 'ffmpeg.exe'
        for name in ('ffmpeg', 'ffmpeg.exe'):
            ffmpeg = os.path.join(base, name)
            if os.path.exists(ffmpeg):
                os.environ['PATH'] = base + os.pathsep + os.environ.get('PATH', '')
                return ffmpeg
    import shutil
    return shutil.which('ffmpeg') or ""


FFMPEG_PATH = get_ffmpeg_path()


# --- PyInstaller: resolver ruta de recursos bundleados ---
def resource_path(filename):
    """Devuelve la ruta correcta tanto en desarrollo como en app congelada."""
    if getattr(sys, 'frozen', False):
        # En macOS .app, los datos van a _MEIPASS
        base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, filename)

# ══════════════════════════════════════════════════════════════════════════════
#  PALETA  CYBER-LUXURY
# ══════════════════════════════════════════════════════════════════════════════
BG_DEEP       = "#080808"
SURFACE       = "#1A1A1A"
SURFACE_ALT   = "#111111"
PURPLE        = "#A020F0"
PURPLE_DARK   = "#7A18B5"
PURPLE_GLOW   = "#B44DFF"
GOLD          = "#D4AF37"
GOLD_DIM      = "#9E7E28"
TEXT_PRIMARY   = "#EAEAEA"
TEXT_SECONDARY = "#888888"
TEXT_MUTED     = "#555555"
BORDER_SUBTLE  = "#2A2A2A"
SUCCESS        = "#4CAF50"
ERROR_RED      = "#E94560"

SIDEBAR_W      = 72
MIN_WIN_W      = 700
MIN_WIN_H      = 560

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR BUTTON
# ══════════════════════════════════════════════════════════════════════════════
class SidebarButton(ctk.CTkFrame):
    """Botón de sidebar con icono dorado y barra indicadora púrpura."""

    def __init__(self, master, icon_char, tooltip, command, **kw):
        super().__init__(master, fg_color="transparent", cursor="hand2",
                         width=SIDEBAR_W, height=56, **kw)
        self.pack_propagate(False)
        self._command = command
        self._active = False

        self._indicator = ctk.CTkFrame(self, fg_color="transparent",
                                       width=3, corner_radius=2)
        self._indicator.pack(side="left", fill="y", padx=(0, 0), pady=10)

        self._icon = ctk.CTkLabel(
            self, text=icon_char,
            font=ctk.CTkFont(size=22),
            text_color=GOLD_DIM,
        )
        self._icon.pack(expand=True)

        self._tooltip_text = tooltip
        self._tip_win = None

        for w in (self, self._icon):
            w.bind("<Button-1>", lambda e: self._command())
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)

    def set_active(self, active):
        self._active = active
        if active:
            self._indicator.configure(fg_color=PURPLE)
            self._icon.configure(text_color=GOLD)
            self.configure(fg_color="#1A1A1A")
        else:
            self._indicator.configure(fg_color="transparent")
            self._icon.configure(text_color=GOLD_DIM)
            self.configure(fg_color="transparent")

    def _on_enter(self, e):
        if not self._active:
            self._icon.configure(text_color=GOLD)
        # Tooltip
        x = self.winfo_rootx() + SIDEBAR_W + 4
        y = self.winfo_rooty() + 12
        self._tip_win = tw = ctk.CTkToplevel(self)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.configure(fg_color=SURFACE)
        ctk.CTkLabel(tw, text=self._tooltip_text,
                     font=ctk.CTkFont(size=11),
                     text_color=TEXT_PRIMARY,
                     fg_color=SURFACE,
                     corner_radius=4).pack(padx=8, pady=4)

    def _on_leave(self, e):
        if not self._active:
            self._icon.configure(text_color=GOLD_DIM)
        if self._tip_win:
            self._tip_win.destroy()
            self._tip_win = None


# ══════════════════════════════════════════════════════════════════════════════
#  GLOW BUTTON  (hover púrpura)
# ══════════════════════════════════════════════════════════════════════════════
class GlowButton(ctk.CTkButton):
    """CTkButton con efecto glow en hover."""

    def __init__(self, master, glow_color=PURPLE_GLOW, **kw):
        kw.setdefault("corner_radius", 10)
        super().__init__(master, **kw)
        self._base_border = kw.get("border_color", self.cget("border_color"))
        self._glow = glow_color
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)

    def _enter(self, e):
        try:
            self.configure(border_color=self._glow, border_width=2)
        except Exception:
            pass

    def _leave(self, e):
        try:
            self.configure(border_color=self._base_border or BG_DEEP, border_width=0)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  EXPANDABLE HISTORY CARD
# ══════════════════════════════════════════════════════════════════════════════
class HistoryCard(ctk.CTkFrame):
    """Mini-tarjeta de historial que se expande al hacer clic."""

    COLLAPSED_H = 68
    EXPANDED_H = 120

    def __init__(self, master, entry, **kw):
        super().__init__(master, fg_color=SURFACE, corner_radius=12,
                         border_width=1, border_color=BORDER_SUBTLE, **kw)
        self._expanded = False
        self._entry = entry

        # --- fila compacta ---
        self._compact = ctk.CTkFrame(self, fg_color="transparent")
        self._compact.pack(fill="x", padx=10, pady=(8, 4))

        # Thumbnail
        thumb_lbl = ctk.CTkLabel(self._compact, text="", width=80, height=45,
                                 corner_radius=8, fg_color=SURFACE_ALT)
        thumb_lbl.pack(side="left", padx=(0, 10))

        if entry.get("thumbnail") and PIL_OK:
            img = entry["thumbnail"]
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(80, 45))
            thumb_lbl.configure(image=ctk_img)
            thumb_lbl.image = ctk_img
        else:
            thumb_lbl.configure(text="🎬", font=ctk.CTkFont(size=18))

        # Info
        info = ctk.CTkFrame(self._compact, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True)

        title_short = entry["title"][:48] + ("…" if len(entry["title"]) > 48 else "")
        ctk.CTkLabel(info, text=title_short, anchor="w",
                     font=ctk.CTkFont(size=11, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(fill="x")

        meta = f"{entry['fmt']}  ·  {entry['quality']}  ·  {entry['time']}"
        ctk.CTkLabel(info, text=meta, anchor="w",
                     font=ctk.CTkFont(size=10),
                     text_color=TEXT_SECONDARY).pack(fill="x")

        # Badge dorado ✓
        ctk.CTkLabel(self._compact, text="✓", width=24,
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=GOLD).pack(side="right", padx=4)

        # --- fila expandida (oculta) ---
        self._detail = ctk.CTkFrame(self, fg_color="transparent")

        path_text = entry.get("filepath", "—")
        size_text = entry.get("filesize", "—")

        detail_row = ctk.CTkFrame(self._detail, fg_color="transparent")
        detail_row.pack(fill="x", padx=14, pady=(0, 6))

        ctk.CTkLabel(detail_row,
                     text=f"📁 {path_text}   ·   {size_text}",
                     anchor="w",
                     font=ctk.CTkFont(size=10),
                     text_color=TEXT_MUTED).pack(side="left", fill="x", expand=True)

        GlowButton(detail_row, text="Abrir carpeta", width=100, height=28,
                   font=ctk.CTkFont(size=10),
                   fg_color=SURFACE_ALT, hover_color=PURPLE_DARK,
                   text_color=TEXT_PRIMARY,
                   command=lambda: self._open_folder(entry.get("folder", ""))
                   ).pack(side="right")

        # Clic para expandir/colapsar
        for w in (self, self._compact, info):
            w.bind("<Button-1>", lambda e: self._toggle())

    def _toggle(self):
        if self._expanded:
            self._detail.pack_forget()
            self._expanded = False
        else:
            self._detail.pack(fill="x", after=self._compact)
            self._expanded = True

    @staticmethod
    def _open_folder(folder):
        if not folder or not os.path.isdir(folder):
            return
        if sys.platform == "win32":
            os.startfile(folder)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])


# ══════════════════════════════════════════════════════════════════════════════
#  APLICACIÓN PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
class PacheVideo(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PacheVideo")
        self.geometry(f"{MIN_WIN_W}x{MIN_WIN_H}")
        self.minsize(MIN_WIN_W, MIN_WIN_H)
        self.configure(fg_color=BG_DEEP)

        # Ícono en barra de título
        # En macOS el ícono lo maneja el bundle .app directamente (no iconbitmap)
        if sys.platform != "darwin":
            ico = resource_path("icon.ico")
            if os.path.exists(ico):
                try:
                    self.iconbitmap(ico)
                except Exception:
                    pass

        self._output_folder = os.path.join(os.path.expanduser("~"), "Downloads")
        self._download_thread = None
        self._history = []
        self._pulse_job = None

        self._build_sidebar()
        self._build_panels()
        self._show_panel("home")

    # ══════════════════════════  SIDEBAR  ══════════════════════════════════

    def _build_sidebar(self):
        self._sidebar = ctk.CTkFrame(self, fg_color=SURFACE_ALT,
                                     width=SIDEBAR_W, corner_radius=0)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        # Separador dorado fino
        ctk.CTkFrame(self, fg_color=GOLD_DIM, width=1,
                      corner_radius=0).pack(side="left", fill="y")

        # Logo
        ctk.CTkLabel(self._sidebar, text="P",
                     font=ctk.CTkFont(size=26, weight="bold"),
                     text_color=PURPLE).pack(pady=(18, 24))

        self._sb_btns = {}
        items = [
            ("home",     "⌂", "Inicio"),
            ("history",  "☰", "Historial"),
            ("settings", "⚙", "Ajustes"),
        ]
        for key, icon, tip in items:
            btn = SidebarButton(self._sidebar, icon, tip,
                                command=lambda k=key: self._show_panel(k))
            btn.pack(fill="x", pady=2)
            self._sb_btns[key] = btn

        # Versión al fondo
        ctk.CTkLabel(self._sidebar, text="v1.0",
                     font=ctk.CTkFont(size=9),
                     text_color=TEXT_MUTED).pack(side="bottom", pady=10)

    # ══════════════════════════  PANELES  ══════════════════════════════════

    def _build_panels(self):
        self._panel_area = ctk.CTkFrame(self, fg_color=BG_DEEP, corner_radius=0)
        self._panel_area.pack(side="left", fill="both", expand=True)

        self._panels = {}
        self._panels["home"] = self._build_home_panel()
        self._panels["history"] = self._build_history_panel()
        self._panels["settings"] = self._build_settings_panel()
        self._current_panel = None

    def _show_panel(self, name):
        for k, btn in self._sb_btns.items():
            btn.set_active(k == name)
        if self._current_panel:
            self._current_panel.pack_forget()
        panel = self._panels[name]
        panel.pack(in_=self._panel_area, fill="both", expand=True)
        self._current_panel = panel

    # ─────────────────────────  HOME  ─────────────────────────────────────

    def _build_home_panel(self):
        panel = ctk.CTkFrame(self._panel_area, fg_color=BG_DEEP, corner_radius=0)

        # Header
        hdr = ctk.CTkFrame(panel, fg_color="transparent")
        hdr.pack(fill="x", padx=32, pady=(28, 4))

        ctk.CTkLabel(hdr, text="PacheVideo",
                     font=ctk.CTkFont(size=28, weight="bold"),
                     text_color=PURPLE).pack(side="left")
        ctk.CTkLabel(hdr, text="  Premium",
                     font=ctk.CTkFont(size=12),
                     text_color=GOLD).pack(side="left", pady=(10, 0))

        ctk.CTkLabel(panel, text="Descargá videos y música de YouTube con la mejor calidad.",
                     font=ctk.CTkFont(size=12),
                     text_color=TEXT_SECONDARY, anchor="w").pack(fill="x", padx=32, pady=(0, 18))

        # Scrollable content
        content = ctk.CTkScrollableFrame(panel, fg_color="transparent",
                                         scrollbar_button_color=PURPLE_DARK)
        content.pack(fill="both", expand=True, padx=32, pady=(0, 16))

        # URL
        self._section_label(content, "URL de YouTube")
        url_row = ctk.CTkFrame(content, fg_color="transparent")
        url_row.pack(fill="x", pady=(4, 14))

        self.url_entry = ctk.CTkEntry(
            url_row,
            placeholder_text="https://www.youtube.com/watch?v=...",
            height=42, font=ctk.CTkFont(size=12), corner_radius=8,
            fg_color=SURFACE, border_color=BORDER_SUBTLE, border_width=1,
            text_color=TEXT_PRIMARY,
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        GlowButton(url_row, text="Pegar", width=72, height=42,
                   fg_color=SURFACE, hover_color=PURPLE_DARK,
                   text_color=GOLD, font=ctk.CTkFont(size=12),
                   command=self._paste_url).pack(side="right")

        # Modo
        self._section_label(content, "Modo de descarga")
        self.mode_var = ctk.StringVar(value="Video (MP4)")
        ctk.CTkSegmentedButton(
            content,
            values=["Video (MP4)", "Solo Audio (MP3)"],
            variable=self.mode_var, height=40,
            font=ctk.CTkFont(size=12),
            fg_color=SURFACE, selected_color=PURPLE,
            selected_hover_color=PURPLE_DARK,
            unselected_color=SURFACE_ALT,
            unselected_hover_color=BORDER_SUBTLE,
            text_color=TEXT_PRIMARY,
            command=self._on_mode_change,
        ).pack(fill="x", pady=(4, 14))

        # Calidad video
        self._quality_label = self._section_label(content, "Calidad de video")
        self.quality_var = ctk.StringVar(value="Máxima calidad")
        self.quality_menu = ctk.CTkOptionMenu(
            content,
            values=["Máxima calidad", "1080p", "720p", "480p", "360p"],
            variable=self.quality_var, height=40,
            font=ctk.CTkFont(size=12), corner_radius=8,
            fg_color=SURFACE, button_color=PURPLE_DARK,
            button_hover_color=PURPLE, dropdown_fg_color=SURFACE,
            dropdown_hover_color=PURPLE_DARK, text_color=TEXT_PRIMARY,
        )
        self.quality_menu.pack(fill="x", pady=(4, 14))

        # Calidad audio (oculto)
        self._audio_label = self._section_label(content, "Calidad de audio")
        self.audio_quality_var = ctk.StringVar(value="320 kbps")
        self.audio_quality_menu = ctk.CTkOptionMenu(
            content,
            values=["320 kbps", "192 kbps", "128 kbps"],
            variable=self.audio_quality_var, height=40,
            font=ctk.CTkFont(size=12), corner_radius=8,
            fg_color=SURFACE, button_color=PURPLE_DARK,
            button_hover_color=PURPLE, dropdown_fg_color=SURFACE,
            dropdown_hover_color=PURPLE_DARK, text_color=TEXT_PRIMARY,
        )
        self._audio_label.pack_forget()
        self.audio_quality_menu.pack_forget()

        # Carpeta destino
        self._section_label(content, "Carpeta de destino")
        folder_row = ctk.CTkFrame(content, fg_color="transparent")
        folder_row.pack(fill="x", pady=(4, 18))

        self.folder_entry = ctk.CTkEntry(
            folder_row, height=40, font=ctk.CTkFont(size=11),
            state="readonly", corner_radius=8,
            fg_color=SURFACE, border_color=BORDER_SUBTLE, border_width=1,
            text_color=TEXT_SECONDARY,
        )
        self.folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._refresh_folder_entry()

        GlowButton(folder_row, text="Explorar", width=90, height=40,
                   fg_color=SURFACE, hover_color=PURPLE_DARK,
                   text_color=GOLD, font=ctk.CTkFont(size=12),
                   command=self._browse_folder).pack(side="right")

        # Botón descargar
        self.download_btn = GlowButton(
            content, text="⬇   Descargar", height=50,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=PURPLE, hover_color=PURPLE_DARK,
            text_color="#FFFFFF", corner_radius=12,
            border_width=0,
            glow_color=GOLD,
            command=self._start_download,
        )
        self.download_btn.pack(fill="x", pady=(0, 14))

        # Barra de progreso
        self.progress_bar = ctk.CTkProgressBar(
            content, height=6, corner_radius=3,
            fg_color=SURFACE, progress_color=PURPLE,
        )
        self.progress_bar.pack(fill="x", pady=(0, 6))
        self.progress_bar.set(0)

        # Estado
        self.status_label = ctk.CTkLabel(
            content, text="Listo para descargar",
            font=ctk.CTkFont(size=11), text_color=TEXT_MUTED,
        )
        self.status_label.pack()

        return panel

    # ─────────────────────────  HISTORY  ──────────────────────────────────

    def _build_history_panel(self):
        panel = ctk.CTkFrame(self._panel_area, fg_color=BG_DEEP, corner_radius=0)

        hdr = ctk.CTkFrame(panel, fg_color="transparent")
        hdr.pack(fill="x", padx=32, pady=(28, 16))

        ctk.CTkLabel(hdr, text="Historial",
                     font=ctk.CTkFont(size=24, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(side="left")

        self._history_count_lbl = ctk.CTkLabel(
            hdr, text="0 descargas",
            font=ctk.CTkFont(size=11), text_color=TEXT_MUTED)
        self._history_count_lbl.pack(side="left", padx=(12, 0), pady=(6, 0))

        self._history_scroll = ctk.CTkScrollableFrame(
            panel, fg_color="transparent",
            scrollbar_button_color=PURPLE_DARK,
        )
        self._history_scroll.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        # Placeholder vacío
        self._history_empty = ctk.CTkLabel(
            self._history_scroll,
            text="Aún no hay descargas.\nDescargá algo desde Inicio.",
            font=ctk.CTkFont(size=13), text_color=TEXT_MUTED,
            justify="center",
        )
        self._history_empty.pack(expand=True, pady=60)

        return panel

    # ─────────────────────────  SETTINGS  ─────────────────────────────────

    def _build_settings_panel(self):
        panel = ctk.CTkFrame(self._panel_area, fg_color=BG_DEEP, corner_radius=0)

        ctk.CTkLabel(panel, text="Ajustes",
                     font=ctk.CTkFont(size=24, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(padx=32, pady=(28, 20), anchor="w")

        content = ctk.CTkScrollableFrame(panel, fg_color="transparent",
                                         scrollbar_button_color=PURPLE_DARK)
        content.pack(fill="both", expand=True, padx=32, pady=(0, 16))

        # — Carpeta por defecto
        self._settings_card(content, "Carpeta de descargas",
                           f"Actual: {self._output_folder}",
                           "Cambiar", self._browse_folder)

        # — Color de acento
        self._section_label(content, "Color de acento")
        self._accent_var = ctk.StringVar(value="Púrpura")
        ctk.CTkSegmentedButton(
            content, values=["Púrpura", "Cyan", "Verde"],
            variable=self._accent_var, height=36,
            font=ctk.CTkFont(size=11),
            fg_color=SURFACE, selected_color=PURPLE,
            selected_hover_color=PURPLE_DARK,
            unselected_color=SURFACE_ALT,
            unselected_hover_color=BORDER_SUBTLE,
            text_color=TEXT_PRIMARY,
            command=self._change_accent,
        ).pack(fill="x", pady=(4, 14))

        # — FFmpeg info
        ff_status = "✓ Detectado" if FFMPEG_PATH else "✗ No encontrado"
        ff_color = SUCCESS if FFMPEG_PATH else ERROR_RED
        card = ctk.CTkFrame(content, fg_color=SURFACE, corner_radius=10,
                            border_width=1, border_color=BORDER_SUBTLE)
        card.pack(fill="x", pady=(8, 4))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=12)
        ctk.CTkLabel(inner, text="FFmpeg",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=TEXT_PRIMARY).pack(anchor="w")
        ctk.CTkLabel(inner, text=f"{ff_status}   {FFMPEG_PATH or ''}",
                     font=ctk.CTkFont(size=10),
                     text_color=ff_color).pack(anchor="w")

        # — About
        ctk.CTkLabel(content, text="PacheVideo v1.0  ·  Powered by yt-dlp",
                     font=ctk.CTkFont(size=10),
                     text_color=TEXT_MUTED).pack(pady=(20, 0))

        return panel

    def _settings_card(self, parent, title, subtitle, btn_text, btn_cmd):
        card = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=10,
                            border_width=1, border_color=BORDER_SUBTLE)
        card.pack(fill="x", pady=(0, 10))
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=12)

        info = ctk.CTkFrame(inner, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(info, text=title,
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=TEXT_PRIMARY, anchor="w").pack(fill="x")
        self._settings_folder_sub = ctk.CTkLabel(
            info, text=subtitle,
            font=ctk.CTkFont(size=10),
            text_color=TEXT_SECONDARY, anchor="w")
        self._settings_folder_sub.pack(fill="x")

        GlowButton(inner, text=btn_text, width=80, height=30,
                   font=ctk.CTkFont(size=11),
                   fg_color=PURPLE_DARK, hover_color=PURPLE,
                   text_color="#FFFFFF",
                   command=btn_cmd).pack(side="right")

    # ══════════════════════════  HELPERS UI  ══════════════════════════════

    def _section_label(self, parent, text):
        lbl = ctk.CTkLabel(parent, text=text, anchor="w",
                           font=ctk.CTkFont(size=12, weight="bold"),
                           text_color=GOLD_DIM)
        lbl.pack(fill="x")
        return lbl

    # ══════════════════════════  CALLBACKS  ═══════════════════════════════

    def _change_accent(self, value):
        global PURPLE, PURPLE_DARK, PURPLE_GLOW
        accents = {
            "Púrpura": ("#A020F0", "#7A18B5", "#B44DFF"),
            "Cyan":    ("#00BCD4", "#0097A7", "#4DD0E1"),
            "Verde":   ("#00C853", "#009624", "#69F0AE"),
        }
        PURPLE, PURPLE_DARK, PURPLE_GLOW = accents.get(value, accents["Púrpura"])
        try:
            self.download_btn.configure(fg_color=PURPLE, hover_color=PURPLE_DARK)
            self.progress_bar.configure(progress_color=PURPLE)
            for btn in self._sb_btns.values():
                if btn._active:
                    btn._indicator.configure(fg_color=PURPLE)
        except Exception:
            pass

    def _on_mode_change(self, value):
        if value == "Solo Audio (MP3)":
            self._quality_label.pack_forget()
            self.quality_menu.pack_forget()
            self._audio_label.pack(fill="x")
            self.audio_quality_menu.pack(fill="x", pady=(4, 14))
        else:
            self._audio_label.pack_forget()
            self.audio_quality_menu.pack_forget()
            self._quality_label.pack(fill="x")
            self.quality_menu.pack(fill="x", pady=(4, 14))

    def _paste_url(self):
        try:
            text = self.clipboard_get().strip()
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, text)
        except Exception:
            pass

    def _browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self._output_folder)
        if folder:
            self._output_folder = folder
            self._refresh_folder_entry()
            if hasattr(self, '_settings_folder_sub'):
                self._settings_folder_sub.configure(text=f"Actual: {folder}")

    def _refresh_folder_entry(self):
        self.folder_entry.configure(state="normal")
        self.folder_entry.delete(0, "end")
        self.folder_entry.insert(0, self._output_folder)
        self.folder_entry.configure(state="readonly")

    def _set_status(self, text, color=TEXT_MUTED):
        self.status_label.configure(text=text, text_color=color)

    def _set_progress(self, value):
        self.progress_bar.set(value)
        if value >= 1.0:
            self.progress_bar.configure(progress_color=GOLD)
        elif value > 0:
            self.progress_bar.configure(progress_color=PURPLE)

    # ══════════════════════════  PULSE ANIMATION  ════════════════════════

    def _start_pulse(self):
        self._pulse_state = True
        self._pulse()

    def _pulse(self):
        if not self._pulse_state:
            return
        try:
            current = self.download_btn.cget("fg_color")
            nxt = PURPLE_DARK if current == PURPLE else PURPLE
            self.download_btn.configure(fg_color=nxt)
            self._pulse_job = self.after(600, self._pulse)
        except Exception:
            pass

    def _stop_pulse(self):
        self._pulse_state = False
        if self._pulse_job:
            self.after_cancel(self._pulse_job)
            self._pulse_job = None
        try:
            self.download_btn.configure(fg_color=PURPLE)
        except Exception:
            pass

    # ══════════════════════════  DESCARGA  ════════════════════════════════

    def _start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            self._set_status("Por favor ingresá una URL.", ERROR_RED)
            return
        if self._download_thread and self._download_thread.is_alive():
            return

        self.download_btn.configure(state="disabled", text="Descargando...")
        self._set_progress(0)
        self._set_status("Iniciando descarga...", TEXT_SECONDARY)
        self._start_pulse()

        self._download_thread = threading.Thread(
            target=self._download_worker, args=(url,), daemon=True
        )
        self._download_thread.start()

    def _download_worker(self, url):
        audio_only = self.mode_var.get() == "Solo Audio (MP3)"
        quality = self.quality_var.get()
        audio_kbps = self.audio_quality_var.get().replace(" kbps", "")

        if audio_only:
            fmt = "bestaudio/best"
        elif quality == "Máxima calidad":
            fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
        else:
            h = quality.replace("p", "")
            fmt = (
                f"bestvideo[ext=mp4][height<={h}]+bestaudio[ext=m4a]"
                f"/bestvideo[height<={h}]+bestaudio/best[height<={h}]"
            )

        def progress_hook(d):
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                downloaded = d.get("downloaded_bytes", 0)
                speed = d.get("speed", 0) or 0
                eta = d.get("eta", 0) or 0
                if total:
                    pct = downloaded / total
                    speed_str = f"{speed / 1048576:.1f} MB/s" if speed else ""
                    eta_str = f"ETA {eta}s" if eta else ""
                    self.after(0, self._set_progress, pct)
                    self.after(
                        0, self._set_status,
                        f"Descargando… {pct * 100:.1f}%  {speed_str}  {eta_str}",
                        TEXT_SECONDARY,
                    )
            elif d["status"] == "finished":
                self.after(0, self._set_progress, 0.97)
                self.after(0, self._set_status, "Procesando archivo…", GOLD)

        postprocessors = []
        if audio_only:
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": audio_kbps,
            })

        ydl_opts = {
            "format": fmt,
            "outtmpl": os.path.join(self._output_folder, "%(title)s.%(ext)s"),
            "merge_output_format": None if audio_only else "mp4",
            "noplaylist": True,
            "progress_hooks": [progress_hook],
            "postprocessors": postprocessors,
            "ffmpeg_location": FFMPEG_PATH,
        }
        if audio_only:
            ydl_opts.pop("merge_output_format")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "video")
                short = title[:50] + ("…" if len(title) > 50 else "")
                thumbnail_url = info.get("thumbnail", "")
                self.after(0, self._set_status, f"Descargando: {short}", TEXT_SECONDARY)
                ydl.download([url])

            self.after(0, self._set_progress, 1.0)
            self.after(0, self._set_status, f"✓  Completado: {short}", SUCCESS)

            # Preparar thumbnail
            thumb_img = None
            if PIL_OK and thumbnail_url:
                try:
                    with urllib.request.urlopen(thumbnail_url, timeout=6) as resp:
                        data = resp.read()
                    thumb_img = Image.open(BytesIO(data)).convert("RGB")
                    thumb_img = thumb_img.resize((80, 45), Image.LANCZOS)
                except Exception:
                    thumb_img = None

            # Calcular tamaño del archivo
            ext = "mp3" if audio_only else "mp4"
            expected_file = os.path.join(self._output_folder, f"{title}.{ext}")
            filesize_str = "—"
            if os.path.exists(expected_file):
                size_b = os.path.getsize(expected_file)
                if size_b > 1048576:
                    filesize_str = f"{size_b / 1048576:.1f} MB"
                else:
                    filesize_str = f"{size_b / 1024:.0f} KB"

            fmt_label = "MP3" if audio_only else "MP4"
            quality_label = f"{audio_kbps} kbps" if audio_only else quality
            time_str = datetime.datetime.now().strftime("%H:%M")

            entry = {
                "title": title,
                "fmt": fmt_label,
                "quality": quality_label,
                "time": time_str,
                "thumbnail": thumb_img,
                "filepath": expected_file,
                "filesize": filesize_str,
                "folder": self._output_folder,
            }
            self.after(0, self._add_history_entry, entry)

        except Exception as e:
            err = str(e)[:90]
            self.after(0, self._set_status, f"✗  Error: {err}", ERROR_RED)
            self.after(0, self._set_progress, 0)
        finally:
            self.after(0, self._stop_pulse)
            self.after(0, lambda: self.download_btn.configure(
                state="normal", text="⬇   Descargar"
            ))

    # ══════════════════════════  HISTORIAL  ═══════════════════════════════

    def _add_history_entry(self, entry):
        self._history.append(entry)
        n = len(self._history)
        self._history_count_lbl.configure(
            text=f"{n} descarga{'s' if n != 1 else ''}")

        if n == 1:
            self._history_empty.pack_forget()

        card = HistoryCard(self._history_scroll, entry)
        card.pack(fill="x", pady=(0, 8), before=self._history_scroll.winfo_children()[0]
                  if self._history_scroll.winfo_children() else None)


if __name__ == "__main__":
    app = PacheVideo()
    app.mainloop()
