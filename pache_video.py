import customtkinter as ctk
from tkinter import filedialog
import yt_dlp
import threading
import os
import sys
import datetime
import json
import urllib.request
from io import BytesIO
import subprocess
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from PIL import Image
    PIL_OK = True
except ImportError:
    PIL_OK = False


def get_ffmpeg_path():
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
        for name in ("ffmpeg.exe", "ffmpeg"):
            ffmpeg = os.path.join(base, name)
            if os.path.exists(ffmpeg):
                os.environ["PATH"] = base + os.pathsep + os.environ.get("PATH", "")
                return ffmpeg
    import shutil
    return shutil.which("ffmpeg") or ""


FFMPEG_PATH = get_ffmpeg_path()


def resource_path(filename):
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, filename)


APP_BG = "#fbf8ff"
SIDEBAR_BG = "#fcf9ff"
CARD_BG = "#ffffff"
SOFT_BG = "#f7f2ff"
INPUT_BG = "#ffffff"
TEXT = "#20202a"
TEXT_MUTED = "#6b6876"
TEXT_FAINT = "#9b97a6"
BORDER = "#eadff3"
PURPLE = "#8f43e8"
PURPLE_DARK = "#6e32cc"
PINK = "#f255b8"
SUCCESS = "#6bce77"
ERROR = "#e34d6a"

MIN_WIN_W = 1120
MIN_WIN_H = 720
SIDEBAR_W = 236

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class GradientButton(ctk.CTkButton):
    """Button styled like the reference gradient controls."""

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", PURPLE)
        kwargs.setdefault("hover_color", PURPLE_DARK)
        kwargs.setdefault("corner_radius", 18)
        kwargs.setdefault("text_color", "#ffffff")
        super().__init__(master, **kwargs)


class NavButton(ctk.CTkFrame):
    def __init__(self, master, icon, text, command):
        super().__init__(master, fg_color="transparent", corner_radius=10, height=48)
        self.pack_propagate(False)
        self._active = False
        self._command = command
        self._icon = ctk.CTkLabel(self, text=icon, width=28, font=ctk.CTkFont(size=22), text_color=TEXT_MUTED)
        self._icon.pack(side="left", padx=(18, 10))
        self._label = ctk.CTkLabel(self, text=text, font=ctk.CTkFont(size=15, weight="bold"), text_color=TEXT_MUTED)
        self._label.pack(side="left")
        for widget in (self, self._icon, self._label):
            widget.bind("<Button-1>", lambda _event: self._command())
            widget.bind("<Enter>", self._enter)
            widget.bind("<Leave>", self._leave)

    def set_active(self, active):
        self._active = active
        color = PURPLE if active else TEXT_MUTED
        self.configure(fg_color=SOFT_BG if active else "transparent")
        self._icon.configure(text_color=color)
        self._label.configure(text_color=color)

    def _enter(self, _event):
        if not self._active:
            self.configure(fg_color="#f3ebfb")

    def _leave(self, _event):
        if not self._active:
            self.configure(fg_color="transparent")


class PrefTabButton(ctk.CTkFrame):
    def __init__(self, master, icon, text, command):
        super().__init__(master, fg_color="transparent", corner_radius=8, width=94, height=82)
        self.pack_propagate(False)
        self._active = False
        self._command = command
        self._icon = ctk.CTkLabel(self, text=icon, font=ctk.CTkFont(size=32), text_color=TEXT_MUTED)
        self._icon.pack(pady=(8, 0))
        self._label = ctk.CTkLabel(self, text=text, font=ctk.CTkFont(size=11), text_color=TEXT)
        self._label.pack(pady=(0, 8))
        for widget in (self, self._icon, self._label):
            widget.bind("<Button-1>", lambda _event: self._command())

    def set_active(self, active):
        self._active = active
        self.configure(fg_color="#d9ecff" if active else "transparent", border_width=1 if active else 0, border_color="#90c9ff")


class HistoryCard(ctk.CTkFrame):
    def __init__(self, master, entry):
        super().__init__(master, fg_color=CARD_BG, corner_radius=14, border_width=1, border_color=BORDER)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=12)

        thumb = ctk.CTkLabel(row, text="", width=96, height=54, corner_radius=10, fg_color=SOFT_BG)
        thumb.pack(side="left", padx=(0, 12))
        if entry.get("thumbnail") and PIL_OK:
            img = ctk.CTkImage(light_image=entry["thumbnail"], dark_image=entry["thumbnail"], size=(96, 54))
            thumb.configure(image=img)
            thumb.image = img
        else:
            thumb.configure(text="▶", font=ctk.CTkFont(size=24), text_color=PURPLE)

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(info, text=entry["title"], anchor="w", font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXT).pack(fill="x")
        meta = f"{entry['fmt']}  |  {entry['quality']}  |  {entry['time']}  |  {entry.get('filesize', '-')}"
        ctk.CTkLabel(info, text=meta, anchor="w", font=ctk.CTkFont(size=11), text_color=TEXT_MUTED).pack(fill="x", pady=(4, 0))
        ctk.CTkLabel(info, text=entry.get("filepath", ""), anchor="w", font=ctk.CTkFont(size=10),
                     text_color=TEXT_FAINT).pack(fill="x", pady=(2, 0))

        ctk.CTkButton(row, text="Abrir", width=72, height=32, corner_radius=10, fg_color=SOFT_BG,
                      hover_color="#ead8ff", text_color=PURPLE,
                      command=lambda: self._open_folder(entry.get("folder", ""))).pack(side="right")

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


class PacheVideo(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PacheVideo")
        self.geometry(f"{MIN_WIN_W}x{MIN_WIN_H}")
        self.minsize(980, 640)
        self.configure(fg_color=APP_BG)

        if sys.platform != "darwin":
            ico = resource_path("icon.ico")
            if os.path.exists(ico):
                try:
                    self.iconbitmap(ico)
                except Exception:
                    pass

        home = os.path.expanduser("~")
        self._output_folder = os.path.join(home, "Downloads")
        self._audio_folder = os.path.join(home, "Downloads", "MediaHuman", "Music")
        self._video_folder = os.path.join(home, "Downloads", "MediaHuman", "Video")
        self._temp_folder = ""
        self._cookies_file = ""
        self._state_dir = os.path.join(home, ".pachevideo")
        self._downloads_store = os.path.join(self._state_dir, "downloads.json")
        self._downloads_records = self._load_download_records()
        self._queue_cards = {}
        self._failed_items = []
        self._download_pause_flags = {}
        self._download_cancel_flags = {}
        self._download_thread = None
        self._pulse_job = None
        self._pulse_state = False

        self._init_preferences()
        self._logo_images = {}
        self._build_shell()
        self._show_panel("home")
        self.after(300, self._maybe_auto_clipboard)

    def _init_preferences(self):
        self.pref_language = ctk.StringVar(value="Automatico (espanol)")
        self.pref_auto_clipboard = ctk.BooleanVar(value=False)
        self.pref_auto_start = ctk.BooleanVar(value=False)
        self.pref_remove_completed = ctk.BooleanVar(value=False)
        self.pref_expand_list = ctk.BooleanVar(value=False)
        self.pref_close_to_tray = ctk.BooleanVar(value=False)
        self.pref_startup = ctk.StringVar(value="ventana normal")
        self.pref_new_video_pos = ctk.StringVar(value="al inicio de la lista")
        self.pref_notify_added = ctk.BooleanVar(value=False)
        self.pref_notify_started = ctk.BooleanVar(value=True)
        self.pref_notify_done = ctk.BooleanVar(value=True)
        self.pref_after_all = ctk.StringVar(value="No hacer nada")
        self.pref_display_scale = ctk.StringVar(value="Automatico")
        self.pref_update_check = ctk.StringVar(value="Siempre al inicio")
        self.pref_analytics = ctk.BooleanVar(value=False)
        self.pref_notifications = ctk.BooleanVar(value=True)
        self.pref_smart_folders = ctk.BooleanVar(value=False)
        self.pref_download_profile = ctk.StringVar(value="Personalizado")
        self.pref_playlist_enabled = ctk.BooleanVar(value=True)
        self.pref_playlist_limit = ctk.StringVar(value="0")

        self.pref_simultaneous = ctk.IntVar(value=5)
        self.pref_bandwidth_enabled = ctk.BooleanVar(value=False)
        self.pref_bandwidth = ctk.StringVar(value="500")
        self.pref_speed_limit = ctk.StringVar(value="200")
        self.pref_prevent_sleep = ctk.BooleanVar(value=False)
        self.pref_ignore_30fps = ctk.BooleanVar(value=False)
        self.pref_ignore_360 = ctk.BooleanVar(value=True)
        self.pref_prefer_hdr = ctk.BooleanVar(value=False)
        self.pref_video_quality_mode = ctk.StringVar(value="max")
        self.pref_video_resolution = ctk.StringVar(value="4320p (8K) o inferior")
        self.pref_subfolder_audio = ctk.BooleanVar(value=False)
        self.pref_subfolder_video = ctk.BooleanVar(value=False)
        self.pref_same_video_folder = ctk.BooleanVar(value=False)
        self.pref_temp_mode = ctk.StringVar(value="Usar carpeta temporal del sistema")

        self.pref_connections = ctk.IntVar(value=3)
        self.pref_safe_mode = ctk.BooleanVar(value=False)
        self.pref_youtube_extractors = ctk.StringVar(value="3")
        self.pref_proxy_type = ctk.StringVar(value="Ninguno")
        self.pref_proxy_host = ctk.StringVar(value="")
        self.pref_proxy_port = ctk.StringVar(value="0")
        self.pref_proxy_auth = ctk.BooleanVar(value=False)
        self.pref_proxy_user = ctk.StringVar(value="")
        self.pref_proxy_pass = ctk.StringVar(value="")

        self.pref_audio_name_mode = ctk.StringVar(value="simple")
        self.pref_audio_template = ctk.StringVar(value="Artista - Titulo")
        self.pref_audio_delimiter = ctk.StringVar(value="-")
        self.pref_audio_number = ctk.BooleanVar(value=False)
        self.pref_audio_remove_emoji = ctk.BooleanVar(value=False)
        self.pref_audio_skip_existing = ctk.BooleanVar(value=False)
        self.pref_audio_skip_previous = ctk.BooleanVar(value=False)
        self.pref_audio_output = ctk.StringVar(value="MP3")
        self.pref_audio_bitrate = ctk.StringVar(value="192")
        self.pref_audio_quality = ctk.StringVar(value="5")
        self.pref_audio_sample = ctk.StringVar(value="44100")
        self.pref_add_itunes_audio = ctk.BooleanVar(value=False)

        self.pref_video_name_mode = ctk.StringVar(value="simple")
        self.pref_video_template = ctk.StringVar(value="Titulo del video")
        self.pref_video_delimiter = ctk.StringVar(value="-")
        self.pref_video_number = ctk.BooleanVar(value=False)
        self.pref_video_remove_emoji = ctk.BooleanVar(value=False)
        self.pref_video_skip_existing = ctk.BooleanVar(value=False)
        self.pref_video_skip_previous = ctk.BooleanVar(value=False)
        self.pref_video_output_mode = ctk.StringVar(value="original")
        self.pref_enable_mp4 = ctk.BooleanVar(value=True)
        self.pref_enable_flv = ctk.BooleanVar(value=False)
        self.pref_enable_webm = ctk.BooleanVar(value=False)
        self.pref_video_convert = ctk.StringVar(value="MP4")
        self.pref_macos_codecs = ctk.BooleanVar(value=False)
        self.pref_better_bitrate = ctk.BooleanVar(value=False)

        self.pref_write_tags = ctk.BooleanVar(value=True)
        self.pref_year_tag = ctk.StringVar(value="No escribir")
        self.pref_album_artist = ctk.StringVar(value="")
        self.pref_comment_mode = ctk.StringVar(value="Comentario personalizado")
        self.pref_comment = ctk.StringVar(value="www.pachevideo.com")
        self.pref_cover = ctk.StringVar(value="si")
        self.pref_explicit_tag = ctk.BooleanVar(value=True)
        self.pref_original_tag = ctk.StringVar(value="Artista - Titulo")
        self.pref_tags_from_description = ctk.BooleanVar(value=True)
        self.pref_uploader_as_artist = ctk.BooleanVar(value=False)
        self.pref_remove_quotes = ctk.BooleanVar(value=False)
        self.pref_remove_emoticon = ctk.BooleanVar(value=False)
        self.pref_save_thumbnail = ctk.BooleanVar(value=False)
        self.pref_playlist_track = ctk.BooleanVar(value=False)
        self.pref_playlist_album = ctk.BooleanVar(value=False)

        self.pref_browser = ctk.StringVar(value="Ninguno")

        self.tool_convert_input = ctk.StringVar(value="")
        self.tool_convert_output = ctk.StringVar(value="MP4")
        self.tool_convert_status = ctk.StringVar(value="Selecciona un archivo para convertir.")

    def _logo_label(self, parent, width, height, corner_radius, fallback_size=22):
        logo_path = resource_path("logo.png")
        if PIL_OK and os.path.exists(logo_path):
            try:
                image = Image.open(logo_path).convert("RGBA")
                ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=(width, height))
                self._logo_images[(width, height)] = ctk_image
                return ctk.CTkLabel(parent, text="", image=ctk_image, width=width, height=height)
            except Exception:
                pass
        return ctk.CTkLabel(
            parent, text="P", width=width, height=height, corner_radius=corner_radius,
            fg_color=PURPLE, text_color="#ffffff",
            font=ctk.CTkFont(size=fallback_size, weight="bold"),
        )

    def _build_shell(self):
        self._main = ctk.CTkFrame(self, fg_color=APP_BG, corner_radius=0)
        self._main.pack(fill="both", expand=True, padx=14, pady=14)

        self._sidebar = ctk.CTkFrame(self._main, fg_color=SIDEBAR_BG, width=SIDEBAR_W, corner_radius=16,
                                     border_width=1, border_color=BORDER)
        self._sidebar.pack(side="left", fill="y", padx=(0, 14))
        self._sidebar.pack_propagate(False)

        brand = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=20, pady=(20, 28))
        self._logo_label(brand, 38, 38, 10, fallback_size=22).pack(side="left")
        ctk.CTkLabel(brand, text="PacheVideo", font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=TEXT).pack(side="left", padx=(12, 6))
        ctk.CTkLabel(brand, text="Premium", font=ctk.CTkFont(size=11, weight="bold"), text_color="#d85818",
                     fg_color="#fff1e8", corner_radius=14, padx=8, pady=3).pack(side="left")

        self._nav_buttons = {}
        for key, icon, text in (
            ("home", "⌂", "Inicio"),
            ("downloads", "⇩", "Descargas"),
            ("settings", "⚙", "Ajustes"),
            ("about", "ⓘ", "Acerca de"),
        ):
            btn = NavButton(self._sidebar, icon, text, lambda k=key: self._show_panel(k))
            btn.pack(fill="x", padx=18, pady=5)
            self._nav_buttons[key] = btn

        promo = ctk.CTkFrame(self._sidebar, fg_color=CARD_BG, corner_radius=14, border_width=1, border_color=BORDER)
        promo.pack(side="bottom", fill="x", padx=18, pady=18)
        ctk.CTkLabel(promo, text="◆", font=ctk.CTkFont(size=28), text_color=PINK).pack(anchor="w", padx=18, pady=(18, 4))
        ctk.CTkLabel(promo, text="PacheVideo Premium", font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=PURPLE).pack(anchor="w", padx=18)
        ctk.CTkLabel(promo, text="Mas velocidad, mejor calidad\ny sin limites.",
                     font=ctk.CTkFont(size=11), text_color=TEXT_MUTED, justify="left").pack(anchor="w", padx=18, pady=(6, 12))
        ctk.CTkButton(promo, text="Ver beneficios", height=34, corner_radius=8, fg_color=SOFT_BG, hover_color="#ead8ff",
                      text_color=PURPLE).pack(fill="x", padx=18, pady=(0, 18))

        self._content = ctk.CTkFrame(self._main, fg_color=CARD_BG, corner_radius=22, border_width=1, border_color=BORDER)
        self._content.pack(side="left", fill="both", expand=True)

        self._panels = {
            "home": self._build_home_panel(),
            "downloads": self._build_downloads_panel(),
            "tools": self._build_tools_panel(),
            "settings": self._build_settings_panel(),
            "about": self._build_about_panel(),
        }
        self._current_panel = None

    def _show_panel(self, name):
        for key, btn in self._nav_buttons.items():
            btn.set_active(key == name)
        if self._current_panel:
            self._current_panel.pack_forget()
        panel = self._panels[name]
        panel.pack(in_=self._content, fill="both", expand=True, padx=34, pady=34)
        self._current_panel = panel

    def _build_home_panel(self):
        panel = ctk.CTkFrame(self._content, fg_color="transparent")

        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.pack(fill="x", pady=(8, 28))
        self._logo_label(header, 64, 64, 16, fallback_size=42).pack(side="left")
        title_wrap = ctk.CTkFrame(header, fg_color="transparent")
        title_wrap.pack(side="left", padx=26)
        row = ctk.CTkFrame(title_wrap, fg_color="transparent")
        row.pack(anchor="w")
        ctk.CTkLabel(row, text="PacheVideo", font=ctk.CTkFont(size=30, weight="bold"),
                     text_color=PURPLE).pack(side="left")
        ctk.CTkLabel(row, text="Premium", font=ctk.CTkFont(size=13, weight="bold"), text_color="#d85818",
                     fg_color="#fff1e8", corner_radius=14, padx=10, pady=4).pack(side="left", padx=(12, 0), pady=(8, 0))
        ctk.CTkButton(row, text="Herramientas", width=118, height=30, fg_color=SOFT_BG,
                      hover_color="#ead8ff", text_color=PURPLE,
                      command=lambda: self._show_panel("tools")).pack(side="left", padx=(12, 0), pady=(8, 0))
        ctk.CTkLabel(title_wrap, text="Descarga videos y musica de YouTube, X, TikTok, Instagram, Facebook y mas.",
                     font=ctk.CTkFont(size=14), text_color=TEXT_MUTED).pack(anchor="w", pady=(6, 0))

        footer = ctk.CTkFrame(panel, fg_color="transparent")
        footer.pack(side="bottom", fill="x", pady=(12, 0))

        body = ctk.CTkScrollableFrame(panel, fg_color="transparent", scrollbar_button_color=PURPLE)
        body.pack(side="top", fill="both", expand=True)

        form = ctk.CTkFrame(body, fg_color=CARD_BG, corner_radius=18, border_width=1, border_color=BORDER)
        form.pack(fill="x", pady=(4, 10))
        inner = ctk.CTkFrame(form, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=18)

        self._label(inner, "URL del video")
        url_row = ctk.CTkFrame(inner, fg_color="transparent")
        url_row.pack(fill="x", pady=(8, 20))
        self.url_entry = ctk.CTkTextbox(url_row, height=66, corner_radius=10, fg_color=INPUT_BG, border_color=BORDER,
                                        text_color=TEXT, font=ctk.CTkFont(size=14), wrap="word")
        self.url_entry.pack(side="left", fill="x", expand=True)
        self.url_entry.insert("1.0", "https://www.youtube.com/watch?v=...\nhttps://www.tiktok.com/@usuario/video/...\nhttps://x.com/usuario/status/...\nPega varias URLs una debajo de otra")
        self.url_entry.bind("<FocusIn>", self._clear_url_placeholder)
        ctk.CTkButton(url_row, text="⛓  Pegar", width=118, height=44, corner_radius=10,
                      fg_color=SOFT_BG, hover_color="#ead8ff", text_color=PURPLE,
                      font=ctk.CTkFont(size=14, weight="bold"), command=self._paste_url).pack(side="left", padx=(12, 0))
        ctk.CTkLabel(inner, text="Acepta enlaces de YouTube, X/Twitter, TikTok, Instagram, Facebook y otros sitios soportados por yt-dlp. Puedes pegar varios links en bloque.",
                     text_color=TEXT_MUTED, font=ctk.CTkFont(size=11), wraplength=820,
                     justify="left").pack(anchor="w", pady=(0, 18))

        quick_row = ctk.CTkFrame(inner, fg_color="transparent")
        quick_row.pack(fill="x", pady=(0, 18))
        ctk.CTkCheckBox(
            quick_row, text="Incluir playlists", variable=self.pref_playlist_enabled,
            checkbox_width=18, checkbox_height=18, fg_color=PURPLE, hover_color=PURPLE_DARK,
            text_color=TEXT,
        ).pack(side="left")
        ctk.CTkLabel(quick_row, text="Limite", text_color=TEXT_MUTED).pack(side="left", padx=(20, 8))
        ctk.CTkEntry(
            quick_row, textvariable=self.pref_playlist_limit, width=58, height=30,
            fg_color=INPUT_BG, border_color=BORDER, text_color=TEXT,
        ).pack(side="left")
        ctk.CTkLabel(quick_row, text="0 = todo", text_color=TEXT_FAINT).pack(side="left", padx=(8, 22))
        ctk.CTkLabel(quick_row, text="Perfil", text_color=TEXT_MUTED).pack(side="left", padx=(0, 8))
        ctk.CTkOptionMenu(
            quick_row, variable=self.pref_download_profile,
            values=["Personalizado", "MP4 1080p", "MP4 maxima", "Audio MP3 320", "Audio MP3 192"],
            width=150, height=30, fg_color=INPUT_BG, button_color=INPUT_BG,
            button_hover_color=SOFT_BG, text_color=TEXT,
            command=self._apply_download_profile,
        ).pack(side="left")

        self._label(inner, "Modo de descarga")
        mode_box = ctk.CTkFrame(inner, fg_color=INPUT_BG, corner_radius=12, border_width=1, border_color=BORDER)
        mode_box.pack(fill="x", pady=(8, 14))
        self.mode_var = ctk.StringVar(value="Video (MP4)")
        self.video_mode_btn = ctk.CTkButton(mode_box, text="▰  Video (MP4)", height=44, corner_radius=10,
                                            fg_color=PURPLE, hover_color=PURPLE_DARK, text_color="#ffffff",
                                            font=ctk.CTkFont(size=14, weight="bold"),
                                            command=lambda: self._set_mode("Video (MP4)"))
        self.video_mode_btn.pack(side="left", fill="x", expand=True, padx=2, pady=2)
        self.audio_mode_btn = ctk.CTkButton(mode_box, text="♪  Solo Audio (MP3)", height=44, corner_radius=10,
                                            fg_color=INPUT_BG, hover_color=SOFT_BG, text_color=TEXT,
                                            font=ctk.CTkFont(size=14),
                                            command=lambda: self._set_mode("Solo Audio (MP3)"))
        self.audio_mode_btn.pack(side="left", fill="x", expand=True, padx=2, pady=2)

        self._quality_title = self._label(inner, "Calidad de video")
        self.quality_var = ctk.StringVar(value="Maxima calidad")
        self.quality_menu = self._option(inner, self.quality_var, ["Maxima calidad", "4320p", "2160p", "1440p", "1080p", "720p", "480p", "360p"])
        self.quality_menu.pack(fill="x", pady=(8, 14))

        self.audio_quality_var = ctk.StringVar(value=self.pref_audio_bitrate.get() + " kbps")
        self.audio_quality_menu = self._option(inner, self.audio_quality_var, ["320 kbps", "256 kbps", "192 kbps", "128 kbps"])

        self._label(inner, "Carpeta de destino")
        folder_row = ctk.CTkFrame(inner, fg_color="transparent")
        folder_row.pack(fill="x", pady=(8, 2))
        self.folder_entry = ctk.CTkEntry(folder_row, height=44, corner_radius=10, fg_color=INPUT_BG,
                                         border_color=BORDER, text_color=TEXT_MUTED, state="readonly",
                                         font=ctk.CTkFont(size=13))
        self.folder_entry.pack(side="left", fill="x", expand=True)
        self._refresh_folder_entry()
        ctk.CTkButton(folder_row, text="▣  Explorar", width=132, height=44, corner_radius=10,
                      fg_color=SOFT_BG, hover_color="#ead8ff", text_color=PURPLE,
                      font=ctk.CTkFont(size=14, weight="bold"), command=self._browse_folder).pack(side="left", padx=(12, 0))

        self.download_btn = GradientButton(panel, text="⇩   Descargar", height=58,
                                           font=ctk.CTkFont(size=20, weight="bold"),
                                           command=self._start_download)
        self.download_btn.pack(fill="x", pady=(0, 14))

        status = ctk.CTkFrame(panel, fg_color="#ffffff", corner_radius=16, border_width=1, border_color=BORDER)
        status.pack(fill="x", pady=(0, 4))
        status_row = ctk.CTkFrame(status, fg_color="transparent")
        status_row.pack(fill="x", padx=18, pady=(14, 8))
        self.status_label = ctk.CTkLabel(status_row, text="✓  Listo para descargar", text_color=TEXT_MUTED,
                                         font=ctk.CTkFont(size=13), anchor="w")
        self.status_label.pack(side="left", fill="x", expand=True)
        self.percent_label = ctk.CTkLabel(status_row, text="0%", text_color=PURPLE,
                                          font=ctk.CTkFont(size=16, weight="bold"), width=58)
        self.percent_label.pack(side="right")
        progress_track = ctk.CTkFrame(status, fg_color=SOFT_BG, corner_radius=10, height=22)
        progress_track.pack(fill="x", padx=18, pady=(0, 16))
        progress_track.pack_propagate(False)
        self.progress_bar = ctk.CTkProgressBar(progress_track, height=14, corner_radius=7,
                                               fg_color=SOFT_BG, progress_color=PURPLE)
        self.progress_bar.pack(fill="x", padx=4, pady=4)
        self.progress_bar.set(0)

        # Keep the primary action and progress visible when the window is not maximized.
        self.download_btn.pack_forget()
        status.pack_forget()

        self.download_btn = GradientButton(
            footer, text="Descargar", height=52,
            font=ctk.CTkFont(size=20, weight="bold"),
            command=self._start_download,
        )
        self.download_btn.pack(fill="x", pady=(0, 10))

        status = ctk.CTkFrame(footer, fg_color="#ffffff", corner_radius=16,
                              border_width=1, border_color=BORDER)
        status.pack(fill="x", pady=(0, 4))
        status_row = ctk.CTkFrame(status, fg_color="transparent")
        status_row.pack(fill="x", padx=18, pady=(12, 8))
        self.status_label = ctk.CTkLabel(
            status_row, text="Listo para descargar", text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=13), anchor="w",
        )
        self.status_label.pack(side="left", fill="x", expand=True)
        self.percent_label = ctk.CTkLabel(
            status_row, text="0%", text_color=PURPLE,
            font=ctk.CTkFont(size=16, weight="bold"), width=58,
        )
        self.percent_label.pack(side="right")
        progress_track = ctk.CTkFrame(status, fg_color=SOFT_BG, corner_radius=10, height=24)
        progress_track.pack(fill="x", padx=18, pady=(0, 14))
        progress_track.pack_propagate(False)
        self.progress_bar = ctk.CTkProgressBar(
            progress_track, height=16, corner_radius=8,
            fg_color=SOFT_BG, progress_color=PURPLE,
        )
        self.progress_bar.pack(fill="x", padx=4, pady=4)
        self.progress_bar.set(0)

        return panel

    def _build_downloads_panel(self):
        panel = ctk.CTkFrame(self._content, fg_color="transparent")
        header = self._panel_title(panel, "Descargas", "Cola, progreso y videos completados.")
        ctk.CTkButton(
            header, text="Limpiar lista", width=124, height=34, corner_radius=10,
            fg_color=SOFT_BG, hover_color="#ead8ff", text_color=PURPLE,
            font=ctk.CTkFont(size=13, weight="bold"), command=self._clear_downloads_list,
        ).pack(side="right")
        ctk.CTkButton(
            header, text="Reintentar fallidas", width=150, height=34, corner_radius=10,
            fg_color=SOFT_BG, hover_color="#ead8ff", text_color=PURPLE,
            font=ctk.CTkFont(size=13, weight="bold"), command=self._retry_failed_downloads,
        ).pack(side="right", padx=(0, 10))
        self._downloads_box = ctk.CTkScrollableFrame(panel, fg_color="transparent", scrollbar_button_color=PURPLE)
        self._downloads_box.pack(fill="both", expand=True)
        self._downloads_empty = ctk.CTkLabel(self._downloads_box, text="No hay descargas activas.",
                                             font=ctk.CTkFont(size=14), text_color=TEXT_MUTED)
        self._downloads_empty.pack(pady=80)
        self._render_saved_downloads()
        return panel

    def _build_tools_panel(self):
        panel = ctk.CTkFrame(self._content, fg_color="transparent")
        self._panel_title(panel, "Herramientas", "Convierte archivos descargados y prueba reproduccion.")

        converter = ctk.CTkFrame(panel, fg_color=CARD_BG, corner_radius=16, border_width=1, border_color=BORDER)
        converter.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(converter, text="Conversor", font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=TEXT).pack(anchor="w", padx=18, pady=(18, 8))
        row = ctk.CTkFrame(converter, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(0, 10))
        entry = ctk.CTkEntry(row, textvariable=self.tool_convert_input, height=38, fg_color=INPUT_BG,
                             border_color=BORDER, text_color=TEXT)
        entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="Elegir", width=86, height=38, fg_color=SOFT_BG, hover_color="#ead8ff",
                      text_color=PURPLE, command=self._browse_convert_input).pack(side="left", padx=(10, 0))
        row2 = ctk.CTkFrame(converter, fg_color="transparent")
        row2.pack(fill="x", padx=18, pady=(0, 12))
        ctk.CTkLabel(row2, text="Formato", text_color=TEXT_MUTED).pack(side="left")
        ctk.CTkOptionMenu(row2, variable=self.tool_convert_output, values=["MP4", "MP3", "WAV", "MKV", "WEBM"],
                          width=110, height=34, fg_color=INPUT_BG, button_color=INPUT_BG,
                          button_hover_color=SOFT_BG, text_color=TEXT).pack(side="left", padx=10)
        ctk.CTkButton(row2, text="Convertir", width=112, height=34, fg_color=PURPLE,
                      hover_color=PURPLE_DARK, text_color="#ffffff",
                      command=self._start_convert_tool).pack(side="left", padx=(4, 0))
        ctk.CTkButton(row2, text="Reproducir", width=112, height=34, fg_color=SOFT_BG,
                      hover_color="#ead8ff", text_color=PURPLE,
                      command=self._play_convert_input).pack(side="left", padx=(8, 0))
        ctk.CTkLabel(converter, textvariable=self.tool_convert_status, text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=12), anchor="w").pack(fill="x", padx=18, pady=(0, 18))

        updater = ctk.CTkFrame(panel, fg_color=CARD_BG, corner_radius=16, border_width=1, border_color=BORDER)
        updater.pack(fill="x")
        ctk.CTkLabel(updater, text="Actualizador", font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=TEXT).pack(anchor="w", padx=18, pady=(18, 8))
        ctk.CTkLabel(updater, text="Actualiza yt-dlp, dependencias y vuelve a generar el ejecutable cuando trabajas desde el proyecto.",
                     text_color=TEXT_MUTED, font=ctk.CTkFont(size=12), wraplength=860,
                     justify="left").pack(anchor="w", padx=18)
        ctk.CTkButton(updater, text="Actualizar y reconstruir EXE", height=38, fg_color=PURPLE,
                      hover_color=PURPLE_DARK, text_color="#ffffff",
                      command=self._run_project_update).pack(anchor="w", padx=18, pady=18)
        return panel

    def _build_settings_panel(self):
        panel = ctk.CTkFrame(self._content, fg_color="transparent")
        self._panel_title(panel, "Ajustes", "Preferencias de descarga, red, salida y etiquetas.")

        tabbar = ctk.CTkFrame(panel, fg_color="transparent")
        tabbar.pack(fill="x", pady=(0, 16))
        self._pref_tabs = {}
        for key, icon, text in (
            ("general", "▯", "General"),
            ("download", "⬇", "Descarga"),
            ("network", "◎", "Red"),
            ("audio", "♪", "Salida audio"),
            ("video", "▣", "Salida video"),
            ("tags", "◇", "Etiquetas"),
            ("auth", "⚿", "Autorizacion"),
        ):
            btn = PrefTabButton(tabbar, icon, text, lambda k=key: self._show_pref(k))
            btn.pack(side="left", padx=(0, 6))
            self._pref_tabs[key] = btn

        self._pref_area = ctk.CTkScrollableFrame(panel, fg_color="#f7f7f8", corner_radius=12,
                                                 scrollbar_button_color=PURPLE)
        self._pref_area.pack(fill="both", expand=True)
        self._current_pref = "general"
        self._show_pref("general")
        return panel

    def _build_about_panel(self):
        panel = ctk.CTkFrame(self._content, fg_color="transparent")
        self._panel_title(panel, "Acerca de", "PacheVideo para Windows.")
        card = ctk.CTkFrame(panel, fg_color=CARD_BG, corner_radius=16, border_width=1, border_color=BORDER)
        card.pack(fill="x")
        ctk.CTkLabel(card, text="PacheVideo Premium", font=ctk.CTkFont(size=24, weight="bold"),
                     text_color=PURPLE).pack(anchor="w", padx=22, pady=(22, 6))
        ctk.CTkLabel(card, text="Descargador de videos y musica basado en yt-dlp.",
                     font=ctk.CTkFont(size=14), text_color=TEXT_MUTED).pack(anchor="w", padx=22)
        ff = f"FFmpeg: {'detectado' if FFMPEG_PATH else 'no encontrado'}"
        ctk.CTkLabel(card, text=ff, font=ctk.CTkFont(size=12), text_color=SUCCESS if FFMPEG_PATH else ERROR).pack(anchor="w", padx=22, pady=22)
        return panel

    def _show_pref(self, name):
        for key, btn in self._pref_tabs.items():
            btn.set_active(key == name)
        for child in self._pref_area.winfo_children():
            child.destroy()
        builders = {
            "general": self._pref_general,
            "download": self._pref_download,
            "network": self._pref_network,
            "audio": self._pref_audio,
            "video": self._pref_video,
            "tags": self._pref_tags,
            "auth": self._pref_auth,
        }
        builders[name](self._pref_area)
        self._current_pref = name

    def _pref_general(self, parent):
        self._form_option(parent, "Idioma:", self.pref_language, ["Automatico (espanol)", "Espanol", "English"])
        self._form_check(parent, "Automatizacion:", "Anadir URL automaticamente desde portapapeles", self.pref_auto_clipboard)
        self._form_check(parent, "", "Iniciar descarga automaticamente", self.pref_auto_start)
        self._form_check(parent, "", "Remover descargas completadas automaticamente", self.pref_remove_completed)
        self._form_check(parent, "", "Expandir lista automaticamente", self.pref_expand_list)
        self._form_check(parent, "Apariencia:", "cerrar hacia la bandeja", self.pref_close_to_tray)
        self._form_option(parent, "Empezar:", self.pref_startup, ["ventana normal", "minimizado"])
        self._form_option(parent, "Anadir nuevo video:", self.pref_new_video_pos, ["al inicio de la lista", "al final de la lista"])
        row = self._form_row(parent, "Notificaciones:")
        for text, var in (("anadido", self.pref_notify_added), ("iniciado", self.pref_notify_started), ("completado", self.pref_notify_done)):
            ctk.CTkCheckBox(row, text=text, variable=var, checkbox_width=18, checkbox_height=18,
                            fg_color="#0b70c9", hover_color="#0b70c9", text_color=TEXT).pack(side="left", padx=(0, 18))
        self._form_option(parent, "Cuando todo se termine:", self.pref_after_all, ["No hacer nada", "Abrir carpeta", "Apagar equipo"])
        self._form_option(parent, "Factor de escala de visualizacion:", self.pref_display_scale, ["Automatico", "100%", "125%", "150%"])
        self._form_check(parent, "", "Mostrar notificaciones de Windows al terminar", self.pref_notifications)
        self._form_check(parent, "", "Carpetas inteligentes por sitio", self.pref_smart_folders)
        self._form_radio(parent, "Buscar actualizacion:", self.pref_update_check, [("Siempre al inicio", "Siempre al inicio"), ("Chequeo manual solamente", "Manual")])
        row = self._form_row(parent, "Actualizacion:")
        ctk.CTkLabel(row, text="Actualizacion disponible", text_color=TEXT).pack(side="left")
        ctk.CTkButton(row, text="Descargar", width=120, height=34, fg_color=INPUT_BG, border_width=1,
                      border_color="#cfcfd3", text_color=TEXT, hover_color="#f2f2f2",
                      command=self._do_update).pack(side="left", padx=16)
        self._form_check(parent, "", "Envio de estadisticas de uso anonimo para mejorar aplicacion", self.pref_analytics)

    def _pref_download(self, parent):
        self._form_stepper(parent, "Descargas simultaneas:", self.pref_simultaneous, 1, 10)
        self._form_entry(parent, "Limite de ancho de banda global:", self.pref_bandwidth, "Kb/s", check_var=self.pref_bandwidth_enabled)
        self._form_entry(parent, "Modo de velocidad limitada:", self.pref_speed_limit, "Kb/s")
        self._form_check(parent, "Equipo en suspension:", "Evitar que el equipo entre en suspension mientras descarga", self.pref_prevent_sleep)
        self._form_check(parent, "", "Ignorar videos a 30+ fps", self.pref_ignore_30fps)
        self._form_check(parent, "", "Ignorar videos AEC 360", self.pref_ignore_360)
        self._form_check(parent, "", "Prefiero video HDR", self.pref_prefer_hdr)
        self._form_radio(parent, "Seleccion de calidad de video:", self.pref_video_quality_mode,
                         [("resolucion mas alta disponible", "max"), ("seleccionar resolucion:", "select"), ("resolucion mas baja disponible", "min")])
        self._form_option(parent, "", self.pref_video_resolution, ["4320p (8K) o inferior", "2160p (4K) o inferior", "1080p o inferior", "720p o inferior"])
        self._folder_row(parent, "Carpeta de descargas para audio:", self._audio_folder, self._set_audio_folder)
        self._form_check(parent, "", "guardar en una subcarpeta nombrada como el titulo de la lista de reproduccion", self.pref_subfolder_audio)
        self._folder_row(parent, "carpeta de descargas para video:", self._video_folder, self._set_video_folder)
        self._form_check(parent, "", "guardar en una subcarpeta nombrada como el titulo de la lista de reproduccion", self.pref_subfolder_video)
        self._form_check(parent, "", "misma carpeta que para audio", self.pref_same_video_folder)
        self._form_option(parent, "Folder temporal:", self.pref_temp_mode, ["Usar carpeta temporal del sistema", "Elegir carpeta temporal"])

    def _pref_network(self, parent):
        self._form_stepper(parent, "Conexiones maximas por video:", self.pref_connections, 1, 10)
        self._form_check(parent, "", "modo de descarga segura", self.pref_safe_mode)
        self._form_option(parent, "Limitar analizadores de YouTube:", self.pref_youtube_extractors, ["1", "2", "3", "4", "5"])
        sep = ctk.CTkFrame(parent, fg_color="#c8c8c8", height=1)
        sep.pack(fill="x", padx=18, pady=16)
        row = self._form_row(parent, "Servidor Proxy:")
        self._mini_option(row, self.pref_proxy_type, ["Ninguno", "HTTP", "SOCKS5"]).pack(side="left")
        ctk.CTkLabel(row, text="Direccion:", text_color=TEXT_MUTED).pack(side="left", padx=(14, 6))
        ctk.CTkEntry(row, textvariable=self.pref_proxy_host, height=34, width=420, fg_color=INPUT_BG,
                     border_color="#dddddd").pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(row, text="Puerto", text_color=TEXT_MUTED).pack(side="left", padx=(14, 6))
        ctk.CTkEntry(row, textvariable=self.pref_proxy_port, height=34, width=58, fg_color=INPUT_BG,
                     border_color="#dddddd").pack(side="left")
        self._form_check(parent, "", "Autenticacion", self.pref_proxy_auth)
        row2 = self._form_row(parent, "")
        ctk.CTkLabel(row2, text="Nombre de usuario:", text_color=TEXT_MUTED).pack(side="left", padx=(20, 8))
        ctk.CTkEntry(row2, textvariable=self.pref_proxy_user, height=34, fg_color=INPUT_BG, border_color="#dddddd").pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(row2, text="Contrasena:", text_color=TEXT_MUTED).pack(side="left", padx=(24, 8))
        ctk.CTkEntry(row2, textvariable=self.pref_proxy_pass, show="*", height=34, fg_color=INPUT_BG, border_color="#dddddd").pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(parent, text="●  yt-dlp listo para sitios compatibles", text_color=SUCCESS, font=ctk.CTkFont(size=13)).pack(anchor="w", padx=18, pady=(120, 10))

    def _pref_audio(self, parent):
        self._name_template(parent, "audio")
        self._form_radio(parent, "Formato de salida:", self.pref_audio_output,
                         [("M4A Original", "M4A Original"), ("Convertir a", "MP3")])
        row = self._form_row(parent, "")
        ctk.CTkLabel(row, text="Tasa de bits", text_color=TEXT).pack(side="left", padx=(42, 8))
        self._mini_option(row, self.pref_audio_bitrate, ["320", "256", "192", "128"]).pack(side="left")
        ctk.CTkLabel(row, text="Kbps", text_color=TEXT).pack(side="left", padx=8)
        row = self._form_row(parent, "")
        ctk.CTkLabel(row, text="Calidad", text_color=TEXT).pack(side="left", padx=(42, 8))
        self._mini_option(row, self.pref_audio_quality, ["0", "2", "5", "7"]).pack(side="left")
        ctk.CTkLabel(row, text="~130 Kbps", text_color=TEXT_MUTED).pack(side="left", padx=8)
        self._form_option(parent, "simplificar", self.pref_audio_sample, ["44100", "48000"], suffix="Hz")
        self._form_check(parent, "iTunes:", "Anadir a iTunes", self.pref_add_itunes_audio)

    def _pref_video(self, parent):
        self._name_template(parent, "video")
        self._form_radio(parent, "Formato de salida:", self.pref_video_output_mode,
                         [("Calidad original", "original"), ("Convertir", "convert")])
        self._form_check(parent, "", "Habilitar formato MP4", self.pref_enable_mp4)
        self._form_check(parent, "", "Habilitar formato FLV", self.pref_enable_flv)
        self._form_check(parent, "", "Habilitar formato WebM", self.pref_enable_webm)
        self._form_option(parent, "", self.pref_video_convert, ["Apple TV - High", "MP4", "WebM", "MKV"])
        self._form_check(parent, "", "usar solamente codecs compatibles con macOS para el formato mp4", self.pref_macos_codecs)
        self._form_check(parent, "", "descargar bitrate mejorado si es posible", self.pref_better_bitrate)

    def _pref_tags(self, parent):
        self._form_check(parent, "", "Escribir etiquetas", self.pref_write_tags)
        self._form_option(parent, "Etiqueta de ano:", self.pref_year_tag, ["No escribir", "Ano de publicacion"])
        self._form_entry(parent, "Artista del album:", self.pref_album_artist)
        self._form_option(parent, "Comentario:", self.pref_comment_mode, ["Comentario personalizado", "No escribir"])
        self._form_entry(parent, "", self.pref_comment)
        self._form_option(parent, "Portada:", self.pref_cover, ["si", "no"])
        self._form_check(parent, "", "Escribir etiqueta explicita (solo para m4a)", self.pref_explicit_tag)
        self._form_option(parent, "Obtener etiqueta original", self.pref_original_tag, ["Artista - Titulo", "Titulo", "Canal - Titulo"])
        self._form_check(parent, "", "Buscar etiquetas en la descripcion", self.pref_tags_from_description)
        self._form_check(parent, "", "Usar el usuario que subio el video si el artista esta vacio", self.pref_uploader_as_artist)
        self._form_check(parent, "", "Quitar comillas", self.pref_remove_quotes)
        self._form_check(parent, "", "Quitar emoticono.", self.pref_remove_emoticon)
        self._form_check(parent, "", "Guardar miniatura en archivo", self.pref_save_thumbnail)
        self._form_check(parent, "Para video en lista de reproduccion (album):", "Escribir posicion en la etiqueta de pista", self.pref_playlist_track)
        self._form_check(parent, "", "Escribir el titulo de la lista de reproduccion en la etiqueta de album", self.pref_playlist_album)

    def _pref_auth(self, parent):
        self._form_option(parent, "Navegador para cookies:", self.pref_browser, ["Ninguno", "chrome", "edge", "firefox", "brave", "opera", "safari"])
        row = self._form_row(parent, "Archivo cookies.txt:")
        self._cookies_entry = ctk.CTkEntry(row, height=34, fg_color=INPUT_BG, border_color="#dddddd", state="readonly")
        self._cookies_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="Seleccionar", width=110, height=34, fg_color=INPUT_BG, border_width=1,
                      border_color="#cfcfd3", text_color=TEXT, hover_color="#f2f2f2",
                      command=self._browse_cookies).pack(side="left", padx=8)
        ctk.CTkButton(row, text="Limpiar", width=82, height=34, fg_color=INPUT_BG, border_width=1,
                      border_color="#cfcfd3", text_color=TEXT, hover_color="#f2f2f2",
                      command=self._clear_cookies).pack(side="left")
        quick = self._form_row(parent, "Cookies faciles:")
        for browser in ("chrome", "edge", "firefox", "brave"):
            ctk.CTkButton(
                quick, text=browser.title(), width=82, height=32, fg_color=SOFT_BG,
                hover_color="#ead8ff", text_color=PURPLE,
                command=lambda b=browser: self._use_browser_cookies(b),
            ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(parent, text="Usa cookies si el sitio solicita login, edad o permisos. Cerrar el navegador mejora la lectura directa.",
                     text_color=TEXT_MUTED, font=ctk.CTkFont(size=12), wraplength=760,
                     justify="left").pack(anchor="w", padx=18, pady=18)

    def _name_template(self, parent, target):
        mode = self.pref_audio_name_mode if target == "audio" else self.pref_video_name_mode
        template = self.pref_audio_template if target == "audio" else self.pref_video_template
        delimiter = self.pref_audio_delimiter if target == "audio" else self.pref_video_delimiter
        number = self.pref_audio_number if target == "audio" else self.pref_video_number
        remove_emoji = self.pref_audio_remove_emoji if target == "audio" else self.pref_video_remove_emoji
        skip_existing = self.pref_audio_skip_existing if target == "audio" else self.pref_video_skip_existing
        skip_previous = self.pref_audio_skip_previous if target == "audio" else self.pref_video_skip_previous
        example = "Super Band - The new song" if target == "audio" else "Video title"

        row = self._form_row(parent, "Plantilla del nombre del archivo:")
        for label, value in (("simple", "simple"), ("avanzado", "avanzado")):
            ctk.CTkRadioButton(row, text=label, variable=mode, value=value, fg_color="#0b70c9",
                               text_color=TEXT).pack(side="left", padx=(0, 18))
        self._form_option(parent, "", template, ["Artista - Titulo", "Titulo del video", "Canal - Titulo"])
        self._form_entry(parent, "delimitador:", delimiter)
        self._form_check(parent, "", "Agregar un numero al nombre del archivo (si el video es parte de una lista de reproduccion)", number)
        ctk.CTkLabel(parent, text=example, text_color="#000000", font=ctk.CTkFont(size=18, slant="italic")).pack(anchor="w", padx=250, pady=18)
        self._form_check(parent, "", "quitar emoji del nombre del archivo", remove_emoji)
        self._form_check(parent, "", "Saltar descarga si el archivo existe", skip_existing)
        self._form_check(parent, "", "omitir si se descargo anteriormente (incluso si el archivo no existe)", skip_previous)

    def _panel_title(self, parent, title, subtitle):
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", pady=(0, 24))
        ctk.CTkLabel(header, text=title, font=ctk.CTkFont(size=28, weight="bold"), text_color=TEXT).pack(side="left")
        ctk.CTkLabel(header, text=subtitle, font=ctk.CTkFont(size=13), text_color=TEXT_MUTED).pack(side="left", padx=(16, 0), pady=(10, 0))
        return header

    def _label(self, parent, text):
        label = ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=14, weight="bold"), text_color=TEXT)
        label.pack(anchor="w")
        return label

    def _option(self, parent, variable, values):
        return ctk.CTkOptionMenu(parent, values=values, variable=variable, height=42, corner_radius=10,
                                 fg_color=INPUT_BG, button_color=INPUT_BG, button_hover_color=SOFT_BG,
                                 dropdown_fg_color=INPUT_BG, dropdown_hover_color=SOFT_BG, text_color=TEXT)

    def _mini_option(self, parent, variable, values):
        return ctk.CTkOptionMenu(parent, values=values, variable=variable, height=34, width=120, corner_radius=0,
                                 fg_color=INPUT_BG, button_color=INPUT_BG, button_hover_color="#eeeeee",
                                 dropdown_fg_color=INPUT_BG, dropdown_hover_color="#eeeeee", text_color=TEXT)

    def _form_row(self, parent, label):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=6)
        ctk.CTkLabel(row, text=label, width=220, anchor="w", font=ctk.CTkFont(size=12), text_color=TEXT).pack(side="left")
        return row

    def _form_check(self, parent, label, text, variable):
        row = self._form_row(parent, label)
        ctk.CTkCheckBox(row, text=text, variable=variable, checkbox_width=18, checkbox_height=18,
                        fg_color="#0b70c9", hover_color="#0b70c9", text_color=TEXT,
                        font=ctk.CTkFont(size=12)).pack(side="left")

    def _form_option(self, parent, label, variable, values, suffix=None):
        row = self._form_row(parent, label)
        self._mini_option(row, variable, values).pack(side="left")
        if suffix:
            ctk.CTkLabel(row, text=suffix, text_color=TEXT).pack(side="left", padx=8)

    def _form_entry(self, parent, label, variable, suffix=None, check_var=None):
        row = self._form_row(parent, label)
        if check_var is not None:
            ctk.CTkCheckBox(row, text="", variable=check_var, width=24, checkbox_width=18, checkbox_height=18,
                            fg_color="#0b70c9", hover_color="#0b70c9").pack(side="left")
        ctk.CTkEntry(row, textvariable=variable, height=34, fg_color=INPUT_BG, border_color="#dddddd",
                     text_color=TEXT).pack(side="left", fill="x", expand=True)
        if suffix:
            ctk.CTkLabel(row, text=suffix, text_color=TEXT).pack(side="left", padx=8)

    def _form_stepper(self, parent, label, variable, min_value, max_value):
        row = self._form_row(parent, label)
        ctk.CTkButton(row, text="-", width=28, height=28, fg_color=INPUT_BG, border_width=1,
                      border_color="#cfcfd3", text_color=TEXT, hover_color="#eeeeee",
                      command=lambda: variable.set(max(min_value, variable.get() - 1))).pack(side="left")
        ctk.CTkLabel(row, textvariable=variable, width=38, text_color=TEXT).pack(side="left")
        ctk.CTkButton(row, text="+", width=28, height=28, fg_color=INPUT_BG, border_width=1,
                      border_color="#cfcfd3", text_color=TEXT, hover_color="#eeeeee",
                      command=lambda: variable.set(min(max_value, variable.get() + 1))).pack(side="left")

    def _form_radio(self, parent, label, variable, options):
        first = True
        for text, value in options:
            row = self._form_row(parent, label if first else "")
            first = False
            ctk.CTkRadioButton(row, text=text, variable=variable, value=value, fg_color="#0b70c9",
                               text_color=TEXT, font=ctk.CTkFont(size=12)).pack(side="left")

    def _folder_row(self, parent, label, value, setter):
        row = self._form_row(parent, label)
        entry = ctk.CTkEntry(row, height=34, fg_color=INPUT_BG, border_color="#dddddd", text_color=TEXT)
        entry.insert(0, value)
        entry.configure(state="readonly")
        entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="Seleccionar...", width=120, height=34, fg_color=INPUT_BG, border_width=1,
                      border_color="#cfcfd3", text_color=TEXT, hover_color="#f2f2f2",
                      command=lambda: setter(entry)).pack(side="left", padx=8)

    def _set_audio_folder(self, entry):
        folder = filedialog.askdirectory(initialdir=self._audio_folder)
        if folder:
            self._audio_folder = folder
            entry.configure(state="normal")
            entry.delete(0, "end")
            entry.insert(0, folder)
            entry.configure(state="readonly")

    def _set_video_folder(self, entry):
        folder = filedialog.askdirectory(initialdir=self._video_folder)
        if folder:
            self._video_folder = folder
            entry.configure(state="normal")
            entry.delete(0, "end")
            entry.insert(0, folder)
            entry.configure(state="readonly")

    def _set_mode(self, value):
        self.mode_var.set(value)
        if value == "Video (MP4)":
            self.video_mode_btn.configure(fg_color=PURPLE, text_color="#ffffff", font=ctk.CTkFont(size=14, weight="bold"))
            self.audio_mode_btn.configure(fg_color=INPUT_BG, text_color=TEXT, font=ctk.CTkFont(size=14))
            self._quality_title.configure(text="Calidad de video")
            if not self.quality_menu.winfo_ismapped():
                self.audio_quality_menu.pack_forget()
                self.quality_menu.pack(fill="x", pady=(8, 20), after=self._quality_title)
        else:
            self.audio_mode_btn.configure(fg_color=PURPLE, text_color="#ffffff", font=ctk.CTkFont(size=14, weight="bold"))
            self.video_mode_btn.configure(fg_color=INPUT_BG, text_color=TEXT, font=ctk.CTkFont(size=14))
            self._quality_title.configure(text="Calidad de audio")
            if self.quality_menu.winfo_ismapped():
                self.quality_menu.pack_forget()
                self.audio_quality_menu.pack(fill="x", pady=(8, 20), after=self._quality_title)

    def _paste_url(self):
        try:
            text = self.clipboard_get().strip()
            if text:
                self.url_entry.delete("1.0", "end")
                self.url_entry.insert("1.0", text)
                if self.pref_auto_start.get():
                    self._start_download()
        except Exception:
            pass

    def _maybe_auto_clipboard(self):
        if self.pref_auto_clipboard.get() and not self._url_text().strip():
            self._paste_url()

    def _clear_url_placeholder(self, _event=None):
        text = self._url_text()
        if "Pega varias URLs" in text and "youtube.com/watch" in text:
            self.url_entry.delete("1.0", "end")

    def _url_text(self):
        return self.url_entry.get("1.0", "end").strip()

    def _extract_urls(self, text):
        urls = re.findall(r"https?://[^\s,;]+", text)
        cleaned = []
        seen = set()
        for url in urls:
            url = url.rstrip(").],;\"'")
            if url not in seen:
                seen.add(url)
                cleaned.append(url)
        return cleaned

    def _browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self._output_folder)
        if folder:
            self._output_folder = folder
            self._refresh_folder_entry()

    def _refresh_folder_entry(self):
        self.folder_entry.configure(state="normal")
        self.folder_entry.delete(0, "end")
        self.folder_entry.insert(0, self._output_folder)
        self.folder_entry.configure(state="readonly")

    def _browse_cookies(self):
        path = filedialog.askopenfilename(title="Seleccionar cookies.txt",
                                          filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            self._cookies_file = path
            if hasattr(self, "_cookies_entry"):
                self._cookies_entry.configure(state="normal")
                self._cookies_entry.delete(0, "end")
                self._cookies_entry.insert(0, path)
                self._cookies_entry.configure(state="readonly")

    def _clear_cookies(self):
        self._cookies_file = ""
        if hasattr(self, "_cookies_entry"):
            self._cookies_entry.configure(state="normal")
            self._cookies_entry.delete(0, "end")
            self._cookies_entry.configure(state="readonly")

    def _use_browser_cookies(self, browser):
        self.pref_browser.set(browser)
        self._cookies_file = ""
        if hasattr(self, "_cookies_entry"):
            self._cookies_entry.configure(state="normal")
            self._cookies_entry.delete(0, "end")
            self._cookies_entry.insert(0, f"Usando cookies de {browser}")
            self._cookies_entry.configure(state="readonly")
        self._set_status(f"Cookies de {browser} activadas. Cierra el navegador si falla la lectura.", TEXT_MUTED)

    def _do_update(self):
        try:
            subprocess.Popen(["cmd", "/c", "start", "https://github.com/Pachecoins/PacheVideo_Mac"])
        except Exception:
            pass

    def _set_status(self, text, color=TEXT_MUTED):
        self.status_label.configure(text=text, text_color=color)

    def _set_progress(self, value):
        value = max(0, min(1, float(value)))
        self.progress_bar.set(value)
        self.progress_bar.configure(progress_color=SUCCESS if value >= 1 else PURPLE)
        if hasattr(self, "percent_label"):
            self.percent_label.configure(text=f"{round(value * 100)}%")

    def _apply_download_profile(self, profile):
        if profile == "MP4 1080p":
            self._set_mode("Video (MP4)")
            self.quality_var.set("1080p")
            self.pref_video_quality_mode.set("select")
            self.pref_video_resolution.set("1080p o inferior")
        elif profile == "MP4 maxima":
            self._set_mode("Video (MP4)")
            self.quality_var.set("Maxima calidad")
            self.pref_video_quality_mode.set("max")
        elif profile == "Audio MP3 320":
            self._set_mode("Solo Audio (MP3)")
            self.audio_quality_var.set("320 kbps")
            self.pref_audio_bitrate.set("320")
        elif profile == "Audio MP3 192":
            self._set_mode("Solo Audio (MP3)")
            self.audio_quality_var.set("192 kbps")
            self.pref_audio_bitrate.set("192")
        self._set_status(f"Perfil aplicado: {profile}", TEXT_MUTED)

    def _expand_playlist_urls(self, urls):
        if not self.pref_playlist_enabled.get():
            return urls
        expanded = []
        try:
            limit = int(self.pref_playlist_limit.get() or "0")
        except ValueError:
            limit = 0
        opts = {
            "extract_flat": "in_playlist",
            "quiet": True,
            "ignoreerrors": True,
            "noplaylist": False,
        }
        for url in urls:
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                entries = info.get("entries") if isinstance(info, dict) else None
                if entries:
                    count = 0
                    for item in entries:
                        if not item:
                            continue
                        entry_url = item.get("url") or item.get("webpage_url")
                        if entry_url and not entry_url.startswith("http"):
                            entry_url = "https://www.youtube.com/watch?v=" + entry_url
                        if entry_url:
                            expanded.append(entry_url)
                            count += 1
                            if limit and count >= limit:
                                break
                else:
                    expanded.append(url)
            except Exception:
                expanded.append(url)
        cleaned = []
        seen = set()
        for url in expanded:
            if url not in seen:
                seen.add(url)
                cleaned.append(url)
        return cleaned

    def _notify(self, title, message):
        if not self.pref_notifications.get():
            return
        try:
            safe_title = title[:40].replace("'", "''")
            safe_message = message[:120].replace("'", "''")
            if sys.platform == "darwin":
                mac_title = safe_title.replace('"', '\\"')
                mac_message = safe_message.replace('"', '\\"')
                subprocess.Popen(
                    ["osascript", "-e", f"display notification \"{mac_message}\" with title \"{mac_title}\""],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            if sys.platform != "win32":
                return
            script = (
                "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;"
                "$template=[Windows.UI.Notifications.ToastTemplateType]::ToastText02;"
                "$xml=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template);"
                "$texts=$xml.GetElementsByTagName('text');"
                f"$texts.Item(0).AppendChild($xml.CreateTextNode('{safe_title}')) > $null;"
                f"$texts.Item(1).AppendChild($xml.CreateTextNode('{safe_message}')) > $null;"
                "$toast=[Windows.UI.Notifications.ToastNotification]::new($xml);"
                "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('PacheVideo').Show($toast);"
            )
            subprocess.Popen(["powershell", "-NoProfile", "-Command", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def _start_pulse(self):
        self._pulse_state = True
        self._pulse()

    def _pulse(self):
        if not self._pulse_state:
            return
        current = self.download_btn.cget("fg_color")
        self.download_btn.configure(fg_color=PINK if current == PURPLE else PURPLE)
        self._pulse_job = self.after(650, self._pulse)

    def _stop_pulse(self):
        self._pulse_state = False
        if self._pulse_job:
            self.after_cancel(self._pulse_job)
            self._pulse_job = None
        self.download_btn.configure(fg_color=PURPLE)

    def _start_download(self):
        urls = self._extract_urls(self._url_text())
        if not urls:
            self._set_status("Ingresa una o varias URLs de video.", ERROR)
            return
        if self._download_thread and self._download_thread.is_alive():
            return

        self._set_status("Analizando enlaces y playlists...", TEXT_MUTED)
        urls = self._expand_playlist_urls(urls)
        label = "Descargando..." if len(urls) == 1 else f"Descargando {len(urls)} videos..."
        self.download_btn.configure(state="disabled", text=label)
        self._set_progress(0)
        self._set_status(f"Preparando cola: {len(urls)} enlace{'s' if len(urls) != 1 else ''}", TEXT_MUTED)
        queue_keys = self._prepare_queue(urls)
        self._start_pulse()
        self._download_thread = threading.Thread(target=self._batch_download_worker, args=(list(zip(urls, queue_keys)),), daemon=True)
        self._download_thread.start()

    def _prepare_queue(self, urls):
        try:
            if self._downloads_empty.winfo_ismapped():
                self._downloads_empty.pack_forget()
        except Exception:
            pass
        keys = []
        for index, url in enumerate(urls, start=1):
            key = self._queue_key(url)
            keys.append(key)
            self._create_download_card(key, index, "Pendiente", url, "Pendiente", "", "", self._output_folder, 0)
        return keys

    def _queue_key(self, url):
        return f"{datetime.datetime.now().timestamp()}:{url}"

    def _find_queue_key(self, url):
        for key in reversed(list(self._queue_cards.keys())):
            if key.endswith(":" + url):
                return key
        return url

    def _create_download_card(self, key, index, title, url, status, thumbnail_url="", path="", folder="", progress=0, color=TEXT):
        try:
            if self._downloads_empty.winfo_ismapped():
                self._downloads_empty.pack_forget()
        except Exception:
            pass

        card = ctk.CTkFrame(self._downloads_box, fg_color=CARD_BG, corner_radius=12,
                            border_width=1, border_color=BORDER)
        card.pack(fill="x", pady=(0, 10))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=12)

        thumb = ctk.CTkLabel(row, text="", width=96, height=54, corner_radius=10, fg_color=SOFT_BG)
        thumb.pack(side="left", padx=(0, 12))

        info_col = ctk.CTkFrame(row, fg_color="transparent")
        info_col.pack(side="left", fill="both", expand=True)

        title_lbl = ctk.CTkLabel(
            info_col, text=f"{index}. {title}", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=color, anchor="w", wraplength=780,
        )
        title_lbl.pack(fill="x")
        status_lbl = ctk.CTkLabel(
            info_col, text=status, font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED, anchor="w",
        )
        status_lbl.pack(fill="x", pady=(3, 0))
        url_lbl = ctk.CTkLabel(
            info_col, text=url, font=ctk.CTkFont(size=10),
            text_color=TEXT_FAINT, anchor="w", wraplength=780,
        )
        url_lbl.pack(fill="x", pady=(2, 6))

        bar = ctk.CTkProgressBar(info_col, height=5, fg_color=SOFT_BG, progress_color=PURPLE)
        bar.pack(fill="x")
        bar.set(progress)

        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.pack(side="right", padx=(12, 0))
        pause_btn = ctk.CTkButton(actions, text="Pausar", width=76, height=28, fg_color=SOFT_BG,
                                  hover_color="#ead8ff", text_color=PURPLE,
                                  command=lambda k=key: self._toggle_pause_download(k))
        pause_btn.pack(pady=(0, 6))
        cancel_btn = ctk.CTkButton(actions, text="Cancelar", width=76, height=28, fg_color=SOFT_BG,
                                   hover_color="#ffe1e8", text_color=ERROR,
                                   command=lambda k=key: self._cancel_download(k))
        cancel_btn.pack(pady=(0, 6))
        retry_btn = ctk.CTkButton(actions, text="Reintentar", width=76, height=28, fg_color=SOFT_BG,
                                  hover_color="#ead8ff", text_color=PURPLE,
                                  command=lambda k=key: self._retry_download(k))
        retry_btn.pack()

        self._queue_cards[key] = {
            "card": card,
            "bar": bar,
            "index": index,
            "title": title_lbl,
            "status": status_lbl,
            "url": url_lbl,
            "source_url": url,
            "thumb": thumb,
            "pause_btn": pause_btn,
            "cancel_btn": cancel_btn,
            "retry_btn": retry_btn,
            "path": path or "",
            "folder": folder or self._output_folder,
            "thumbnail_url": "",
            "display_title": title,
        }
        for widget in (card, row, thumb, info_col, title_lbl, status_lbl, url_lbl, bar):
            try:
                widget.configure(cursor="hand2")
                widget.bind("<Button-1>", lambda _event, k=key: self._open_queue_item(k))
            except Exception:
                pass
        self._set_download_thumbnail(key, thumbnail_url)
        return card

    def _set_download_thumbnail(self, key, thumbnail_url):
        info = self._queue_cards.get(key)
        if not info:
            return
        thumb = info.get("thumb")
        if not thumb:
            return
        if thumbnail_url and thumbnail_url == info.get("thumbnail_url"):
            return
        info["thumbnail_url"] = thumbnail_url or ""
        img = self._load_thumbnail(thumbnail_url)
        if img and PIL_OK:
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(96, 54))
            thumb.configure(image=ctk_img, text="")
            thumb.image = ctk_img
        else:
            thumb.configure(image=None, text=">", font=ctk.CTkFont(size=26, weight="bold"), text_color=PURPLE)
            thumb.image = None

    def _update_queue_item(self, url_or_key, status, progress=None, color=TEXT, path=None, folder=None, title=None, thumbnail_url=None):
        key = url_or_key if url_or_key in self._queue_cards else self._find_queue_key(url_or_key)
        info = self._queue_cards.get(key)
        if not info:
            return
        if path:
            info["path"] = path
        if folder:
            info["folder"] = folder
        if title:
            info["display_title"] = title
            info["title"].configure(text=f"{info['index']}. {title}", text_color=color)
        elif color == ERROR:
            info["display_title"] = status
            info["title"].configure(text=f"{info['index']}. {status}", text_color=color)
        elif info.get("display_title") in ("Pendiente", "Iniciando"):
            info["display_title"] = status
            info["title"].configure(text=f"{info['index']}. {status}", text_color=color)
        else:
            info["title"].configure(text=f"{info['index']}. {info.get('display_title', status)}", text_color=TEXT)
        if "status" in info:
            info["status"].configure(text=status, text_color=color if color == ERROR else TEXT_MUTED)
        if thumbnail_url:
            self._set_download_thumbnail(key, thumbnail_url)
        if progress is not None:
            info["bar"].set(progress)
            info["bar"].configure(progress_color=SUCCESS if progress >= 1 else PURPLE)

    def _complete_queue_item(self, key, entry):
        title = entry.get("title", "Video descargado")
        self._update_queue_item(
            key, "Completado", 1.0, SUCCESS,
            entry.get("filepath", ""), entry.get("folder", ""),
            title, entry.get("thumbnail_url", ""),
        )
        self._remember_download(entry)

    def _download_record(self, entry):
        return {
            "title": entry.get("title", "Video descargado"),
            "url": entry.get("url", ""),
            "fmt": entry.get("fmt", ""),
            "quality": entry.get("quality", ""),
            "time": entry.get("time", datetime.datetime.now().strftime("%H:%M")),
            "thumbnail_url": entry.get("thumbnail_url", ""),
            "filepath": entry.get("filepath", ""),
            "filesize": entry.get("filesize", ""),
            "folder": entry.get("folder", ""),
        }

    def _load_download_records(self):
        try:
            if not os.path.isfile(self._downloads_store):
                return []
            with open(self._downloads_store, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
        except Exception:
            pass
        return []

    def _save_download_records(self):
        try:
            os.makedirs(self._state_dir, exist_ok=True)
            with open(self._downloads_store, "w", encoding="utf-8") as fh:
                json.dump(self._downloads_records, fh, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _remember_download(self, entry):
        record = self._download_record(entry)
        filepath = record.get("filepath", "")
        if filepath:
            self._downloads_records = [item for item in self._downloads_records if item.get("filepath") != filepath]
        self._downloads_records.append(record)
        self._save_download_records()

    def _render_saved_downloads(self):
        for index, record in enumerate(self._downloads_records, start=1):
            key = f"saved:{index}:{record.get('filepath') or record.get('url')}"
            meta = "Completado"
            details = []
            for field in ("fmt", "quality", "filesize", "time"):
                value = record.get(field)
                if value:
                    details.append(value)
            if details:
                meta = "Completado  |  " + "  |  ".join(details)
            self._create_download_card(
                key, index, record.get("title", "Video descargado"),
                record.get("url", ""), meta, record.get("thumbnail_url", ""),
                record.get("filepath", ""), record.get("folder", ""), 1.0, SUCCESS,
            )
            self._queue_cards[key]["bar"].configure(progress_color=SUCCESS)

    def _clear_downloads_list(self):
        for info in list(self._queue_cards.values()):
            card = info.get("card")
            if card and card.winfo_exists():
                card.destroy()
        self._queue_cards.clear()
        self._downloads_records = []
        self._save_download_records()
        self._downloads_empty.pack(pady=80)

    def _toggle_pause_download(self, key):
        current = self._download_pause_flags.get(key, False)
        self._download_pause_flags[key] = not current
        info = self._queue_cards.get(key)
        if info and info.get("pause_btn"):
            info["pause_btn"].configure(text="Reanudar" if not current else "Pausar")
        self._update_queue_item(key, "Pausado" if not current else "Reanudando", None, PURPLE)

    def _cancel_download(self, key):
        self._download_cancel_flags[key] = True
        self._download_pause_flags[key] = False
        self._update_queue_item(key, "Cancelando...", None, ERROR)

    def _retry_download(self, key):
        info = self._queue_cards.get(key)
        if not info:
            return
        url = info.get("source_url", "")
        if url:
            self._start_specific_downloads([url])

    def _retry_failed_downloads(self):
        urls = [item.get("url") for item in self._failed_items if item.get("url")]
        if not urls:
            self._set_status("No hay descargas fallidas para reintentar.", TEXT_MUTED)
            return
        self._failed_items = []
        self._start_specific_downloads(urls)

    def _start_specific_downloads(self, urls):
        if self._download_thread and self._download_thread.is_alive():
            self._set_status("Espera a que termine la cola actual para reintentar.", ERROR)
            return
        queue_keys = self._prepare_queue(urls)
        self.download_btn.configure(state="disabled", text=f"Descargando {len(urls)}...")
        self._set_progress(0)
        self._start_pulse()
        self._download_thread = threading.Thread(target=self._batch_download_worker, args=(list(zip(urls, queue_keys)),), daemon=True)
        self._download_thread.start()

    def _open_queue_item(self, key):
        info = self._queue_cards.get(key, {})
        path = info.get("path", "")
        folder = info.get("folder", "") or self._output_folder
        if path and os.path.exists(path):
            if sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", path])
            else:
                subprocess.Popen(["xdg-open", os.path.dirname(path)])
        elif folder and os.path.isdir(folder):
            HistoryCard._open_folder(folder)

    def _batch_download_worker(self, queue_items):
        total = len(queue_items)
        completed = 0
        max_workers = max(1, min(int(self.pref_simultaneous.get()), total))

        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {
                    executor.submit(self._download_one, url, idx, total, key): key
                    for idx, (url, key) in enumerate(queue_items, start=1)
                }
                for future in as_completed(future_map):
                    key = future_map[future]
                    completed += 1
                    try:
                        entry = future.result()
                        if entry:
                            self.after(0, self._complete_queue_item, key, entry)
                    except Exception as e:
                        info = self._queue_cards.get(key, {})
                        self._failed_items.append({"url": info.get("source_url", ""), "error": str(e)})
                        self.after(0, self._update_queue_item, key, f"Error: {str(e)[:70]}", 0, ERROR)
                    self.after(0, self._set_progress, completed / total)
                    self.after(0, self._set_status, f"Cola: {completed}/{total} completado{'s' if completed != 1 else ''}", TEXT_MUTED)

            self.after(0, self._set_status, f"✓  Cola terminada: {completed}/{total}", SUCCESS)
            self.after(0, self._notify, "PacheVideo", f"Cola terminada: {completed}/{total}")
            if self.pref_after_all.get() == "Abrir carpeta":
                self.after(0, lambda: HistoryCard._open_folder(self._output_folder))
        finally:
            self.after(0, self._stop_pulse)
            self.after(0, lambda: self.download_btn.configure(state="normal", text="Descargar"))

    def _download_one(self, url, index=1, total=1, queue_key=None):
        item_key = queue_key or url
        self.after(0, self._update_queue_item, item_key, "Iniciando", 0.02, TEXT)
        audio_only = self.mode_var.get() == "Solo Audio (MP3)"
        output_folder = self._audio_folder if audio_only else self._video_folder
        if self.pref_same_video_folder.get() and not audio_only:
            output_folder = self._audio_folder
        if self.pref_smart_folders.get():
            output_folder = os.path.join(output_folder, self._site_folder_name(url))
        if not os.path.isdir(output_folder):
            os.makedirs(output_folder, exist_ok=True)
        self.after(0, self._update_queue_item, item_key, "Iniciando", 0.02, TEXT, None, output_folder)

        quality = self.quality_var.get()
        audio_kbps = self.audio_quality_var.get().replace(" kbps", "")
        fmt = self._format_selector(audio_only, quality, url)
        downloaded_path = {"value": ""}

        def progress_hook(d):
            if self._download_cancel_flags.get(item_key):
                raise RuntimeError("Descarga cancelada por el usuario.")
            while self._download_pause_flags.get(item_key):
                time.sleep(0.25)
                if self._download_cancel_flags.get(item_key):
                    raise RuntimeError("Descarga cancelada por el usuario.")
            if d["status"] == "downloading":
                total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                downloaded = d.get("downloaded_bytes", 0)
                speed = d.get("speed", 0) or 0
                eta = d.get("eta", 0) or 0
                if total_bytes:
                    pct = downloaded / total_bytes
                    speed_str = f"{speed / 1048576:.1f} MB/s" if speed else ""
                    eta_str = f"ETA {eta}s" if eta else ""
                    self.after(0, self._update_queue_item, item_key, f"Descargando {pct * 100:.1f}%  {speed_str} {eta_str}", pct, TEXT)
                    if total == 1:
                        self.after(0, self._set_progress, pct)
                    self.after(0, self._set_status, f"Descargando {index}/{total}: {pct * 100:.1f}%  {speed_str}  {eta_str}", TEXT_MUTED)
            elif d["status"] == "finished":
                downloaded_path["value"] = d.get("filename") or downloaded_path["value"]
                self.after(0, self._update_queue_item, item_key, "Procesando archivo", 0.97, PURPLE)
                if total == 1:
                    self.after(0, self._set_progress, 0.97)
                self.after(0, self._set_status, "Procesando archivo...", PURPLE)

        postprocessors = []
        if audio_only and self.pref_audio_output.get() != "M4A Original":
            postprocessors.append({"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": audio_kbps})
        if self.pref_write_tags.get():
            postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True})
        if audio_only and self.pref_cover.get() == "si":
            postprocessors.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})

        template = self._filename_template(audio_only)
        ydl_opts = {
            "outtmpl": os.path.join(output_folder, template),
            "noplaylist": True,
            "progress_hooks": [progress_hook],
            "postprocessors": postprocessors,
            "ffmpeg_location": FFMPEG_PATH,
            "continuedl": True,
            "ignoreerrors": False,
            "concurrent_fragment_downloads": max(1, min(int(self.pref_connections.get()), 2)),
            "retries": 50,
            "fragment_retries": 50,
            "file_access_retries": 10,
            "extractor_retries": 5,
            "socket_timeout": 60,
            "http_chunk_size": 10 * 1024 * 1024,
            "nopart": False,
            "windowsfilenames": True,
            "format_sort": ["vcodec:avc1:h264", "vcodec:vp9", "res", "br"],
        }
        if "youtube.com" in url or "youtu.be" in url:
            ydl_opts["extractor_args"] = {"youtube": {"player_client": ["web"]}}

        if fmt:
            ydl_opts["format"] = fmt
        if not audio_only and self.pref_enable_mp4.get():
            ydl_opts["merge_output_format"] = "mp4"
        if self.pref_bandwidth_enabled.get():
            try:
                ydl_opts["ratelimit"] = int(self.pref_bandwidth.get()) * 1024
            except ValueError:
                pass
        if self.pref_safe_mode.get():
            ydl_opts["retries"] = 100
            ydl_opts["fragment_retries"] = 100
            ydl_opts["sleep_interval_requests"] = 1
            ydl_opts["concurrent_fragment_downloads"] = 1
        if self.pref_audio_skip_existing.get() or self.pref_video_skip_existing.get():
            ydl_opts["overwrites"] = False
        if self.pref_save_thumbnail.get() or (audio_only and self.pref_cover.get() == "si"):
            ydl_opts["writethumbnail"] = True
        proxy = self._proxy_url()
        if proxy:
            ydl_opts["proxy"] = proxy
        if self._cookies_file and os.path.isfile(self._cookies_file):
            ydl_opts["cookiefile"] = self._cookies_file
        elif self.pref_browser.get() != "Ninguno":
            ydl_opts["cookiesfrombrowser"] = (self.pref_browser.get(), None, None, None)

        last_error = None
        fallback_formats = self._format_fallbacks(audio_only, quality, url)
        for attempt, attempt_format in enumerate(fallback_formats, start=1):
            attempt_opts = dict(ydl_opts)
            if attempt_format:
                attempt_opts["format"] = attempt_format
            else:
                attempt_opts.pop("format", None)
            if (attempt_format in ("best", None, "")) and "merge_output_format" in attempt_opts:
                attempt_opts.pop("merge_output_format", None)
            try:
                if attempt > 1:
                    self.after(0, self._update_queue_item, item_key, f"Reintentando formato {attempt}/{len(fallback_formats)}", None, PURPLE)
                with yt_dlp.YoutubeDL(attempt_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    title = info.get("title", "video")
                    short = title[:54] + ("..." if len(title) > 54 else "")
                    thumbnail_url = info.get("thumbnail", "")
                    self.after(0, self._update_queue_item, item_key, f"Descargando: {short}", 0.05, TEXT, None, None, title, thumbnail_url)
                    self.after(0, self._set_status, f"Descargando {index}/{total}: {short}", TEXT_MUTED)
                    ydl.download([url])
                break
            except Exception as e:
                last_error = e
                message = str(e).lower()
                if self._is_youtube_solver_error(message):
                    raise self._friendly_download_error(e)
                if "requested format is not available" not in message and "invalid format" not in message:
                    raise self._friendly_download_error(e)
        else:
            raise self._friendly_download_error(last_error)

        thumb_img = self._load_thumbnail(thumbnail_url)
        ext = "mp3" if audio_only and self.pref_audio_output.get() != "M4A Original" else ("m4a" if audio_only else "mp4")
        expected_file = self._resolve_downloaded_file(output_folder, title, ext, downloaded_path["value"])
        if not expected_file or expected_file.lower().endswith(".part") or not os.path.exists(expected_file):
            raise RuntimeError("La descarga quedo incompleta (.part). Reintenta para continuar desde el parcial.")
        filesize = self._filesize(expected_file)
        return {
            "title": title,
            "url": url,
            "fmt": ext.upper(),
            "quality": f"{audio_kbps} kbps" if audio_only else quality,
            "time": datetime.datetime.now().strftime("%H:%M"),
            "thumbnail": thumb_img,
            "thumbnail_url": thumbnail_url,
            "filepath": expected_file,
            "filesize": filesize,
            "folder": output_folder,
        }

    def _format_selector(self, audio_only, quality, url=""):
        if audio_only:
            return "ba/b"
        if self.pref_video_quality_mode.get() == "min":
            return "wv*[vcodec!*=av01][vcodec!*=av1]+wa/w[vcodec!*=av01][vcodec!*=av1]/w"
        if self.pref_video_quality_mode.get() == "select":
            quality = self.pref_video_resolution.get().split("p")[0] + "p"
        if quality == "Maxima calidad":
            return (
                "bv*[vcodec^=avc1]+ba[ext=m4a]/b[vcodec^=avc1]"
                "/bv*[ext=mp4][vcodec!*=av01][vcodec!*=av1]+ba[ext=m4a]"
                "/b[ext=mp4][vcodec!*=av01][vcodec!*=av1]"
                "/bv*[vcodec^=vp09]+ba/b[vcodec^=vp09]"
                "/b[vcodec!*=av01][vcodec!*=av1]"
            )
        h = quality.replace("p", "")
        return (
            f"bv*[vcodec^=avc1][height<={h}]+ba"
            f"/b[vcodec^=avc1][height<={h}]"
            f"/bv*[ext=mp4][vcodec!*=av01][vcodec!*=av1][height<={h}]+ba[ext=m4a]"
            f"/b[ext=mp4][vcodec!*=av01][vcodec!*=av1][height<={h}]"
            f"/bv*[vcodec^=vp09][height<={h}]+ba"
            f"/b[vcodec^=vp09][height<={h}]"
            f"/b[vcodec!*=av01][vcodec!*=av1][height<={h}]"
        )

    def _format_fallbacks(self, audio_only, quality, url=""):
        primary = self._format_selector(audio_only, quality, url)
        if audio_only:
            candidates = [
                primary,
                "ba/b",
                "b",
                None,
            ]
        else:
            candidates = [
                primary,
                "bv*[vcodec^=avc1]+ba[ext=m4a]/b[vcodec^=avc1]",
                "bv*[ext=mp4][vcodec!*=av01][vcodec!*=av1]+ba[ext=m4a]",
                "b[ext=mp4][vcodec!*=av01][vcodec!*=av1]/b[vcodec!*=av01][vcodec!*=av1]",
                "bv*[vcodec^=vp09]+ba/b[vcodec^=vp09]",
                "worst[ext=mp4][vcodec!*=av01][vcodec!*=av1]/worst[vcodec!*=av01][vcodec!*=av1]",
            ]
        unique = []
        for fmt in candidates:
            if fmt not in unique:
                unique.append(fmt)
        return unique

    def _friendly_download_error(self, error):
        message = str(error) if error else "Error desconocido"
        lower = message.lower()
        if "sign in to confirm" in lower or "not a bot" in lower or "login" in lower:
            return RuntimeError("YouTube pide login/cookies. En Ajustes > Autorizacion selecciona navegador o cookies.txt.")
        if self._is_youtube_solver_error(lower):
            return RuntimeError("Falta el solver de YouTube. Ejecuta: python -m pip install -r requirements.txt")
        if "requested format is not available" in lower or "invalid format" in lower:
            return RuntimeError("No hay formato compatible sin AV1 para este video. Prueba Maxima calidad, usa cookies si pide login, o actualiza yt-dlp desde Herramientas.")
        if "timed out" in lower or "timeout" in lower:
            return RuntimeError("La conexion se corto por timeout. Reintenta; la descarga parcial deberia continuar.")
        if ".part" in lower or "incompleta" in lower:
            return RuntimeError("La descarga quedo incompleta (.part). Reintenta y continuara desde el parcial.")
        return error

    def _browse_convert_input(self):
        path = filedialog.askopenfilename(
            title="Seleccionar archivo",
            filetypes=[("Media", "*.mp4 *.mkv *.webm *.mov *.avi *.mp3 *.m4a *.wav"), ("All files", "*.*")],
        )
        if path:
            self.tool_convert_input.set(path)
            self.tool_convert_status.set("Listo para convertir.")

    def _play_convert_input(self):
        path = self.tool_convert_input.get().strip()
        if path and os.path.exists(path):
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])

    def _start_convert_tool(self):
        path = self.tool_convert_input.get().strip()
        if not path or not os.path.exists(path):
            self.tool_convert_status.set("Elige un archivo valido.")
            return
        threading.Thread(target=self._convert_tool_worker, args=(path, self.tool_convert_output.get()), daemon=True).start()

    def _convert_tool_worker(self, path, output_format):
        if not FFMPEG_PATH:
            self.after(0, self.tool_convert_status.set, "FFmpeg no esta disponible.")
            return
        root, _ext = os.path.splitext(path)
        out_ext = output_format.lower()
        output = f"{root}_convertido.{out_ext}"
        cmd = [FFMPEG_PATH, "-y", "-i", path]
        if out_ext == "mp3":
            cmd += ["-vn", "-codec:a", "libmp3lame", "-b:a", "192k"]
        elif out_ext == "wav":
            cmd += ["-vn", "-codec:a", "pcm_s16le"]
        elif out_ext == "mp4":
            cmd += ["-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart"]
        else:
            cmd += ["-c", "copy"]
        cmd.append(output)
        self.after(0, self.tool_convert_status.set, "Convirtiendo...")
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.after(0, self.tool_convert_input.set, output)
            self.after(0, self.tool_convert_status.set, f"Convertido: {output}")
            self.after(0, self._notify, "PacheVideo", "Conversion finalizada")
        except Exception as e:
            self.after(0, self.tool_convert_status.set, f"Error al convertir: {str(e)[:90]}")

    def _run_project_update(self):
        script_name = "build.sh" if sys.platform == "darwin" else "build_windows.ps1"
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)
        if not os.path.exists(script):
            self._set_status(f"No encontre {script_name}.", ERROR)
            return
        try:
            if sys.platform == "darwin":
                command = f"cd '{os.path.dirname(script)}'; python3 -m pip install -U -r requirements.txt; bash ./build.sh"
                subprocess.Popen(["open", "-a", "Terminal", os.path.dirname(script)])
                subprocess.Popen(["osascript", "-e", f'tell application "Terminal" to do script "{command}"'])
                self._set_status("Actualizador iniciado en Terminal.", TEXT_MUTED)
            else:
                subprocess.Popen([
                    "powershell", "-NoExit", "-ExecutionPolicy", "Bypass",
                    "-Command",
                    f"cd '{os.path.dirname(script)}'; C:\\Python311\\python.exe -m pip install -U -r requirements.txt; .\\build_windows.ps1 -PythonPath C:\\Python311\\python.exe",
                ])
                self._set_status("Actualizador iniciado en PowerShell.", TEXT_MUTED)
        except Exception as e:
            self._set_status(f"No pude iniciar el actualizador: {e}", ERROR)

    def _is_youtube_solver_error(self, message):
        return (
            "n challenge" in message
            or "only images are available" in message
            or "gvs po token" in message
            or "po token" in message
            or "supported javascript runtime" in message
        )

    def _filename_template(self, audio_only):
        if audio_only:
            template = self.pref_audio_template.get()
            delimiter = self.pref_audio_delimiter.get() or "-"
            numbered = self.pref_audio_number.get()
        else:
            template = self.pref_video_template.get()
            delimiter = self.pref_video_delimiter.get() or "-"
            numbered = self.pref_video_number.get()
        prefix = "%(playlist_index)03d " if numbered else ""
        if "{" in template and "}" in template:
            advanced = (
                template.replace("{title}", "%(title)s")
                .replace("{uploader}", "%(uploader)s")
                .replace("{channel}", "%(channel)s")
                .replace("{date}", "%(upload_date)s")
                .replace("{id}", "%(id)s")
                .replace("{playlist_index}", "%(playlist_index)03d")
            )
            return prefix + advanced + ".%(ext)s"
        if template == "Artista - Titulo":
            return prefix + f"%(uploader)s {delimiter} %(title)s.%(ext)s"
        if template == "Canal - Titulo":
            return prefix + f"%(channel)s {delimiter} %(title)s.%(ext)s"
        return prefix + "%(title)s.%(ext)s"

    def _proxy_url(self):
        proxy_type = self.pref_proxy_type.get()
        host = self.pref_proxy_host.get().strip()
        port = self.pref_proxy_port.get().strip()
        if proxy_type == "Ninguno" or not host or not port or port == "0":
            return ""
        scheme = "socks5" if proxy_type == "SOCKS5" else "http"
        auth = ""
        if self.pref_proxy_auth.get() and self.pref_proxy_user.get():
            auth = f"{self.pref_proxy_user.get()}:{self.pref_proxy_pass.get()}@"
        return f"{scheme}://{auth}{host}:{port}"

    def _site_folder_name(self, url):
        lower = url.lower()
        if "youtu" in lower:
            return "YouTube"
        if "tiktok" in lower:
            return "TikTok"
        if "instagram" in lower:
            return "Instagram"
        if "facebook" in lower or "fb.watch" in lower:
            return "Facebook"
        if "twitter" in lower or "x.com" in lower:
            return "X"
        return "Otros"

    def _load_thumbnail(self, url):
        if not PIL_OK or not url:
            return None
        try:
            with urllib.request.urlopen(url, timeout=6) as resp:
                data = resp.read()
            img = Image.open(BytesIO(data)).convert("RGB")
            return img.resize((96, 54), Image.LANCZOS)
        except Exception:
            return None

    def _filesize(self, path):
        if not os.path.exists(path):
            return "-"
        size = os.path.getsize(path)
        if size > 1048576:
            return f"{size / 1048576:.1f} MB"
        return f"{size / 1024:.0f} KB"

    def _resolve_downloaded_file(self, output_folder, title, ext, hook_path=""):
        candidates = []
        if hook_path:
            if not hook_path.lower().endswith(".part"):
                candidates.append(hook_path)
            root, _old_ext = os.path.splitext(hook_path)
            candidates.extend([root + "." + ext, root + ".mp4", root + ".m4a", root + ".mp3", root + ".webm", root + ".mkv"])
        candidates.append(os.path.join(output_folder, f"{title}.{ext}"))

        for path in candidates:
            if path and not path.lower().endswith(".part") and os.path.exists(path):
                return path

        try:
            files = [
                os.path.join(output_folder, name)
                for name in os.listdir(output_folder)
                if os.path.isfile(os.path.join(output_folder, name)) and not name.lower().endswith(".part")
            ]
            if files:
                return max(files, key=os.path.getmtime)
        except Exception:
            pass
        return candidates[0] if candidates else os.path.join(output_folder, f"{title}.{ext}")

if __name__ == "__main__":
    app = PacheVideo()
    app.mainloop()
